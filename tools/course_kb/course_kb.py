#!/usr/bin/env python
"""course_kb — extrai conhecimento de videoaulas (transcrição + OCR de tela) e organiza em Markdown/JSON.

Estágios (idempotentes; a existência do arquivo de saída marca o estágio como concluído):
  discover   inventário do curso + escolha do melhor arquivo por aula (ffprobe, descarta clipes inválidos)
  transcribe faster-whisper (GPU) -> transcript.json / .srt / .txt          (retoma de .partial.jsonl)
  ocr        quadros via ffmpeg -> detecção de mudança de tela -> RapidOCR -> ocr.jsonl + keyframes/
  knowledge  extração determinística: serviços AWS, ferramentas, comandos, recursos Terraform, custos, alertas
  render     <aula>/lesson.md + KNOWLEDGE.md do curso
  summarize  (opcional) resumo por bloco via Ollama local — custo zero
  compare    cobertura: conhecimento do curso x repositórios x plano  -> COVERAGE.md / coverage.json

Uso típico (Python 3.10 canônico):
  python course_kb.py discover  --course "Q:\\Cursos Pagos\\DevOps na Nuvem ( )"
  python course_kb.py run       --course ... --stages transcribe          # processo 1 (GPU)
  python course_kb.py run       --course ... --stages ocr                 # processo 2 (CPU), em paralelo
  python course_kb.py run       --course ... --stages knowledge,render
  python course_kb.py compare   --course ... --plan Plano.md --repo NOME=CAMINHO --repo ...

Saída padrão: <course>\\_kb  (material derivado de curso pago: manter privado, não versionar em repo público).
"""
from __future__ import annotations

import argparse
import difflib
import json
import os
import re
import shutil
import subprocess
import sys
import time
import unicodedata
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

SKIP_DIR_PARTS = {"_invalid_clips", "_teste_validado", "_kb"}
DEFAULT_PROMPT = (
    "Aula de DevOps na AWS em português do Brasil. Termos: AWS, Terraform, Kubernetes, EKS, VPC, subnet, "
    "NAT Gateway, Internet Gateway, kubectl, Helm, Kustomize, ArgoCD, Karpenter, Prometheus, Grafana, "
    "Node Exporter, GitHub Actions, OIDC, IAM, IAM Identity Center, ECR, ALB, WAF, S3, DynamoDB, Claude Code, MCP."
)


# ----------------------------------------------------------------------------- util
def log(msg: str) -> None:
    print(f"[{datetime.now():%H:%M:%S}] {msg}", flush=True)


def slugify(s: str) -> str:
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()
    s = re.sub(r"[^a-zA-Z0-9]+", "-", s).strip("-").lower()
    return s[:80] or "aula"


def hms(t: float) -> str:
    t = max(0, int(t))
    return f"{t // 3600:02d}:{t % 3600 // 60:02d}:{t % 60:02d}"


def srt_ts(t: float) -> str:
    ms = int(round(t * 1000))
    return f"{ms // 3600000:02d}:{ms % 3600000 // 60000:02d}:{ms % 60000 // 1000:02d},{ms % 1000:03d}"


def parse_hms(s: str) -> float:
    parts = [int(p) for p in s.strip().split(":")]
    v = 0
    for p in parts:
        v = v * 60 + p
    return float(v)


def write_json(path: Path, data) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, path)


def write_text(path: Path, text: str) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, path)


def tool(name: str) -> str:
    p = shutil.which(name)
    if not p:
        sys.exit(f"ERRO: '{name}' não encontrado no PATH.")
    return p


def ffprobe(path: Path) -> dict:
    out = subprocess.run(
        [tool("ffprobe"), "-v", "error", "-print_format", "json", "-show_format", "-show_streams", str(path)],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    if out.returncode != 0:
        return {"ok": False, "error": out.stderr.strip()[:300]}
    d = json.loads(out.stdout or "{}")
    v = next((s for s in d.get("streams", []) if s.get("codec_type") == "video"), {})
    a = next((s for s in d.get("streams", []) if s.get("codec_type") == "audio"), None)
    return {
        "ok": True,
        "duration": float(d.get("format", {}).get("duration", 0) or 0),
        "width": int(v.get("width", 0) or 0),
        "height": int(v.get("height", 0) or 0),
        "has_audio": a is not None,
    }


# ----------------------------------------------------------------------------- discover
def parse_transcrever(course: Path) -> list[dict]:
    """Lê TRANSCREVER.md (gerado pelo downloader memberkit) -> [{module,title,url,expected,stem}]."""
    f = course / "TRANSCREVER.md"
    if not f.exists():
        return []
    items, module, cur = [], "", None
    for line in f.read_text(encoding="utf-8").splitlines():
        if line.startswith("## "):
            module = line[3:].strip()
            continue
        m = re.match(r"\s*- \[.\] \[(.+?)\]\((.+?)\)\s*[—-]\s*([\d:]+)", line)
        if m:
            cur = {"module": module, "title": m.group(1), "url": m.group(2), "expected": parse_hms(m.group(3))}
            items.append(cur)
            continue
        m = re.match(r"\s*`(.+?\.mp4)`", line)
        if m and cur is not None:
            cur["stem"] = Path(m.group(1).replace("\\", "/")).stem
            cur = None
    return items


def norm_stem(p: Path) -> str:
    return re.sub(r"\.(retry\d+|preview)(-rejected)?$", "", p.stem, flags=re.I).strip().lower()


def cmd_discover(args) -> dict:
    course = Path(args.course)
    out = Path(args.out or course / "_kb")
    out.mkdir(parents=True, exist_ok=True)
    cache_f = out / "course.json"
    old = json.loads(cache_f.read_text(encoding="utf-8")) if cache_f.exists() else {}
    probe_cache = old.get("probe_cache", {})

    videos = [p for p in course.rglob("*.mp4") if not (SKIP_DIR_PARTS & set(p.parts))]
    log(f"{len(videos)} mp4 candidatos (ignorando {sorted(SKIP_DIR_PARTS)})")
    probes = {}
    for p in videos:
        st = p.stat()
        key = f"{p}|{st.st_size}|{int(st.st_mtime)}"
        if key not in probe_cache:
            log(f"ffprobe {p.name}")
            probe_cache[key] = ffprobe(p)
        probes[str(p)] = {**probe_cache[key], "size_mb": round(st.st_size / 2**20, 1)}

    catalog = parse_transcrever(course)
    by_stem = defaultdict(list)
    for p in videos:
        by_stem[norm_stem(p)].append(p)
    if not catalog:  # sem catálogo: uma aula por stem
        catalog = [{"module": p[0].parent.parent.name, "title": s, "url": "", "expected": 0, "stem": s} for s, p in by_stem.items()]

    lessons = []
    for i, it in enumerate(catalog, 1):
        cands = by_stem.get((it.get("stem") or it["title"]).lower(), [])
        scored = sorted(
            [(probes[str(c)], c) for c in cands if probes[str(c)].get("ok") and probes[str(c)].get("has_audio")],
            key=lambda x: (x[0]["duration"], x[0]["height"]), reverse=True,
        )
        best = scored[0] if scored else None
        dur = best[0]["duration"] if best else 0
        exp = it.get("expected") or 0
        status = "missing" if not best else ("ok" if not exp or dur >= 0.95 * exp else "incompleto")
        mod_short = re.sub(r"^Workshop DevOps na Nuvem\s*//\s*", "", it["module"]) or it["module"]
        lessons.append({
            "order": i,
            "slug": f"{i:02d}-{slugify(mod_short)[:24]}-{slugify(it['title'])}",
            "module": it["module"], "title": it["title"], "url": it.get("url", ""),
            "expected_s": exp, "duration_s": round(dur, 1), "status": status,
            "video": str(best[1]) if best else None,
            "video_meta": best[0] if best else None,
            "alternatives": [str(c) for c in cands if not best or c != best[1]],
        })
    data = {"course": str(course), "generated": datetime.now().isoformat(timespec="seconds"),
            "lessons": lessons, "probe_cache": probe_cache}
    write_json(cache_f, data)
    tot = sum(l["duration_s"] for l in lessons)
    for l in lessons:
        log(f"  [{l['status']:>10}] {l['slug']}  {hms(l['duration_s'])} / esperado {hms(l['expected_s'])}")
    log(f"Total válido: {hms(tot)} em {sum(1 for l in lessons if l['status']=='ok')}/{len(lessons)} aulas -> {cache_f}")
    return data


def load_course(args) -> tuple[Path, dict]:
    course = Path(args.course)
    out = Path(args.out or course / "_kb")
    f = out / "course.json"
    data = json.loads(f.read_text(encoding="utf-8")) if f.exists() else cmd_discover(args)
    return out, data


def select_lessons(data: dict, only: str | None) -> list[dict]:
    ls = [l for l in data["lessons"] if l.get("video") and l["status"] != "missing"]
    if only:
        keys = [k.strip().lower() for k in only.split(",")]
        ls = [l for l in ls if any(k in l["slug"] for k in keys)]
    return ls


# ----------------------------------------------------------------------------- transcribe
_WHISPER = {}


def get_whisper(model: str, device: str, compute: str):
    if model not in _WHISPER:
        from faster_whisper import WhisperModel
        log(f"carregando faster-whisper '{model}' ({device}/{compute}) — 1ª vez baixa o modelo para o cache HF")
        _WHISPER[model] = WhisperModel(model, device=device, compute_type=compute)
    return _WHISPER[model]


def stage_transcribe(lesson: dict, d: Path, args) -> None:
    final = d / "transcript.json"
    if final.exists() and not args.force:
        return
    partial = d / "transcript.partial.jsonl"
    segs = []
    if partial.exists() and not args.force:
        segs = [json.loads(x) for x in partial.read_text(encoding="utf-8").splitlines() if x.strip()]
    start_at = segs[-1]["end"] if segs else 0.0
    model = get_whisper(args.model, args.device, args.compute)
    log(f"transcrevendo {lesson['slug']} ({hms(lesson['duration_s'])}) a partir de {hms(start_at)}")
    t0 = time.time()
    kw = dict(language=args.language, beam_size=5, initial_prompt=args.prompt or DEFAULT_PROMPT,
              condition_on_previous_text=False, vad_filter=True,
              vad_parameters=dict(min_silence_duration_ms=700))
    if start_at > 0:  # retomada: VAD é ignorado quando clip_timestamps é usado
        kw.pop("vad_filter"); kw.pop("vad_parameters")
        kw["clip_timestamps"] = f"{start_at:.2f}"
    it, info = model.transcribe(lesson["video"], **kw)
    with partial.open("a", encoding="utf-8") as fp:
        last_log = time.time()
        for s in it:
            rec = {"start": round(s.start, 2), "end": round(s.end, 2), "text": s.text.strip(),
                   "avg_logprob": round(s.avg_logprob, 3), "no_speech_prob": round(s.no_speech_prob, 3)}
            fp.write(json.dumps(rec, ensure_ascii=False) + "\n"); fp.flush()
            segs.append(rec)
            if time.time() - last_log > 60:
                pct = 100 * s.end / max(1, lesson["duration_s"])
                log(f"  {lesson['slug'][:40]} {hms(s.end)} ({pct:.0f}%) {(time.time()-t0)/60:.1f} min")
                last_log = time.time()
    segs = clean_segments(segs)
    write_json(final, {"lesson": lesson["slug"], "model": args.model, "language": args.language,
                       "duration_s": lesson["duration_s"], "elapsed_s": round(time.time() - t0, 1),
                       "segments": segs})
    write_text(d / "transcript.srt", "\n".join(
        f"{i}\n{srt_ts(s['start'])} --> {srt_ts(s['end'])}\n{s['text']}\n" for i, s in enumerate(segs, 1)))
    write_text(d / "transcript.txt", "\n".join(f"[{hms(s['start'])}] {s['text']}" for s in segs))
    partial.unlink(missing_ok=True)
    log(f"  ok {len(segs)} segmentos em {(time.time()-t0)/60:.1f} min")


def clean_segments(segs: list[dict]) -> list[dict]:
    """Remove alucinações típicas: silêncio com baixa confiança e repetições em loop."""
    out, rep = [], 0
    for s in sorted(segs, key=lambda x: x["start"]):
        if not s["text"] or (s["no_speech_prob"] > 0.6 and s["avg_logprob"] < -1.0):
            continue
        if out and s["text"] == out[-1]["text"]:
            rep += 1
            if rep >= 2:
                continue
        else:
            rep = 0
        if out and s["start"] < out[-1]["end"] - 0.5 and s["text"] in out[-1]["text"]:
            continue
        out.append(s)
    return out


# ----------------------------------------------------------------------------- ocr
_OCR = {}


def get_ocr():
    if "e" not in _OCR:
        from rapidocr import RapidOCR
        _OCR["e"] = RapidOCR()
    return _OCR["e"]


def ocr_image(img) -> str:
    import cv2
    up = cv2.resize(img, None, fx=1.6, fy=1.6, interpolation=cv2.INTER_CUBIC)
    res = get_ocr()(up)
    txts = list(getattr(res, "txts", None) or [])
    boxes = getattr(res, "boxes", None)
    if not txts:
        return ""
    if boxes is not None and len(boxes) == len(txts):  # agrupa por linha (y) e ordena por x
        items = sorted(((float(b[0][1]), float(b[0][0]), t) for b, t in zip(boxes, txts)))
        lines, cur, cy = [], [], None
        for y, x, t in items:
            if cy is None or abs(y - cy) <= 12:
                cur.append((x, t)); cy = y if cy is None else cy
            else:
                lines.append(" ".join(t for _, t in sorted(cur))); cur, cy = [(x, t)], y
        if cur:
            lines.append(" ".join(t for _, t in sorted(cur)))
        return "\n".join(lines)
    return "\n".join(txts)


ACCOUNT_RX = re.compile(r"(?<!\d)\d{12}(?!\d)")


def stage_ocr(lesson: dict, d: Path, args) -> None:
    import cv2
    import numpy as np
    final = d / "ocr.jsonl"
    if final.exists() and not args.force:
        return
    meta = lesson["video_meta"]
    w, h = meta["width"], meta["height"]
    kf = d / "keyframes"
    kf.mkdir(exist_ok=True)
    interval = args.frame_interval
    log(f"OCR {lesson['slug']} (1 quadro/{interval}s, {w}x{h})")
    t0 = time.time()
    proc = subprocess.Popen(
        [tool("ffmpeg"), "-v", "error", "-i", lesson["video"], "-vf", f"fps=1/{interval}",
         "-f", "rawvideo", "-pix_fmt", "bgr24", "-"],
        stdout=subprocess.PIPE, bufsize=10**8)
    fsz = w * h * 3
    events, prev_small, last_ocr_small, last_ocr_t, idx, n_ocr = [], None, None, -1e9, 0, 0

    def small_of(img):
        g = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        return cv2.resize(g, (128, 72), interpolation=cv2.INTER_AREA).astype(np.float32) / 255.0

    while True:
        buf = proc.stdout.read(fsz)
        if len(buf) < fsz:
            break
        t = idx * interval
        idx += 1
        img = np.frombuffer(buf, np.uint8).reshape(h, w, 3)
        sm = small_of(img)
        stable = prev_small is not None and float(np.mean(np.abs(sm - prev_small))) < args.stable_thr
        changed = last_ocr_small is None or float(np.mean(np.abs(sm - last_ocr_small))) > args.change_thr
        stale = (t - last_ocr_t) > args.stale_s
        prev_small = sm
        if not changed or not (stable or stale):
            if events and not changed:
                events[-1]["t_end"] = t
            continue
        text = ocr_image(img)
        n_ocr += 1
        last_ocr_small, last_ocr_t = sm, t
        text = re.sub(r"[ \t]+", " ", text).strip()
        text = ACCOUNT_RX.sub("<AWS_ACCOUNT_ID>", text)  # não persistir IDs de conta vistos na tela
        if len(text) < args.min_chars:
            continue
        if events:
            r = difflib.SequenceMatcher(None, events[-1]["text"], text).quick_ratio()
            if r > 0.88:
                events[-1]["t_end"] = t
                if len(text) > len(events[-1]["text"]):
                    events[-1]["text"] = text
                continue
        fn = f"{hms(t).replace(':', '')}.jpg"
        cv2.imwrite(str(kf / fn), img, [cv2.IMWRITE_JPEG_QUALITY, 72])
        events.append({"t_start": t, "t_end": t, "text": text, "frame": f"keyframes/{fn}"})
        if len(events) % 25 == 0:
            log(f"  {lesson['slug'][:40]} {hms(t)} eventos={len(events)} ocr={n_ocr} {(time.time()-t0)/60:.1f} min")
    proc.wait()
    write_text(final, "\n".join(json.dumps(e, ensure_ascii=False) for e in events))
    log(f"  ok {len(events)} telas distintas ({n_ocr} OCRs, {idx} quadros) em {(time.time()-t0)/60:.1f} min")


# ----------------------------------------------------------------------------- knowledge
def _rx(*alts):
    return re.compile(r"(?<![\w-])(?:" + "|".join(alts) + r")(?![\w-])", re.I)


AWS_SERVICES = {
    "EC2": _rx(r"EC2", r"inst[aâ]ncias?\s+ec2"), "EKS": _rx(r"EKS", r"elastic kubernetes"),
    "ECS": _rx(r"ECS"), "Fargate": _rx(r"fargate"), "ECR": _rx(r"ECR", r"elastic container registry"),
    "Lambda": _rx(r"lambda"), "API Gateway": _rx(r"api\s?gateway"), "S3": _rx(r"S3", r"bucket"),
    "DynamoDB": _rx(r"dynamo\s?db", r"dynamo"), "RDS": _rx(r"RDS"), "Aurora": _rx(r"aurora"),
    "VPC": _rx(r"VPC"), "Subnets": _rx(r"subnets?", r"sub-?redes?"), "NAT Gateway": _rx(r"nat\s?gateway", r"NAT"),
    "Internet Gateway": _rx(r"internet\s?gateway", r"IGW"), "Elastic IP / IPv4 público": _rx(r"elastic\s?ip", r"EIP", r"ipv4 p[uú]blico"),
    "Route 53": _rx(r"route\s?53"), "CloudFront": _rx(r"cloud\s?front"),
    "ALB/ELB": _rx(r"ALB", r"ELB", r"application load balancer", r"load\s?balancer"), "NLB": _rx(r"NLB"),
    "WAF": _rx(r"WAF"), "IAM": _rx(r"IAM"), "IAM Identity Center/SSO": _rx(r"identity center", r"aws sso", r"SSO"),
    "STS/AssumeRole": _rx(r"STS", r"assume\s?role"), "OIDC": _rx(r"OIDC", r"openid"),
    "IRSA/Pod Identity": _rx(r"IRSA", r"pod identity"), "KMS": _rx(r"KMS"),
    "Secrets Manager": _rx(r"secrets?\s?manager"), "SSM Parameter Store": _rx(r"parameter store", r"SSM"),
    "CloudWatch": _rx(r"cloud\s?watch"), "CloudTrail": _rx(r"cloud\s?trail"),
    "Amazon Managed Prometheus (AMP)": _rx(r"managed (?:service for )?prometheus", r"AMP", r"prometheus workspace"),
    "Amazon Managed Grafana (AMG)": _rx(r"managed grafana", r"AMG", r"grafana workspace"),
    "SNS": _rx(r"SNS"), "SQS": _rx(r"SQS"), "EventBridge": _rx(r"event\s?bridge"),
    "Step Functions": _rx(r"step functions?"), "Kinesis": _rx(r"kinesis"), "MSK": _rx(r"MSK"),
    "Glue": _rx(r"glue"), "Athena": _rx(r"athena"), "Redshift": _rx(r"redshift"), "EMR": _rx(r"EMR"),
    "SageMaker": _rx(r"sage\s?maker"), "Bedrock": _rx(r"bedrock"), "EBS": _rx(r"EBS"), "EFS": _rx(r"EFS"),
    "Auto Scaling": _rx(r"auto\s?scaling", r"ASG"), "CloudFormation": _rx(r"cloud\s?formation"),
    "CDK": _rx(r"CDK"), "ACM": _rx(r"ACM", r"certificate manager"), "Transit Gateway": _rx(r"transit gateway"),
    "VPC Endpoint/PrivateLink": _rx(r"vpc endpoints?", r"private\s?link"), "Security Groups": _rx(r"security groups?", r"SG"),
    "Budgets": _rx(r"budgets?", r"or[cç]amento"), "Cost Explorer": _rx(r"cost explorer"),
    "Organizations/Control Tower": _rx(r"organizations?", r"control tower"), "Free Tier": _rx(r"free\s?tier", r"free plan", r"n[ií]vel gratuito"),
    "Systems Manager/Session Manager": _rx(r"session manager", r"systems manager"),
}
TOOLS = {
    "Terraform": _rx(r"terraform", r"\.tf"), "OpenTofu": _rx(r"open\s?tofu"), "Terragrunt": _rx(r"terragrunt"),
    "Kubernetes": _rx(r"kubernetes", r"k8s"), "kubectl": _rx(r"kubectl", r"kube\s?control"), "Helm": _rx(r"helm"),
    "Kustomize": _rx(r"kustomiz\w*"), "ArgoCD": _rx(r"argo\s?cd", r"argo"), "Karpenter": _rx(r"karpenter"),
    "Prometheus": _rx(r"prometheus"), "Grafana": _rx(r"grafana"), "Node Exporter": _rx(r"node\s?exporter"),
    "Loki": _rx(r"loki"), "OpenTelemetry": _rx(r"open\s?telemetry", r"otel"), "Docker": _rx(r"docker", r"dockerfile"),
    "GitHub Actions": _rx(r"github actions", r"workflows?\.ya?ml", r"actions"), "GitHub": _rx(r"github"),
    "Claude Code": _rx(r"claude code", r"claude"), "MCP": _rx(r"MCP"), "Agentes de IA": _rx(r"agentes?", r"subagents?", r"skills?"),
    "Ansible": _rx(r"ansible"), "eksctl": _rx(r"eksctl"), "AWS CLI": _rx(r"aws cli", r"aws configure"),
    "Next.js": _rx(r"next\.?js"), ".NET": _rx(r"\.net", r"dotnet", r"c#"), "external-dns": _rx(r"external-?dns"),
    "AWS Load Balancer Controller": _rx(r"load balancer controller", r"lb controller"), "cert-manager": _rx(r"cert-?manager"),
    "ingress-nginx": _rx(r"ingress-?nginx", r"ingress"), "Infracost": _rx(r"infracost"), "LocalStack": _rx(r"localstack"),
    "kind/k3d/minikube": _rx(r"kind", r"k3d", r"k3s", r"minikube"), "tflint/checkov/trivy": _rx(r"tflint", r"checkov", r"trivy", r"tfsec"),
    "Remote state (S3+lock)": _rx(r"remote\s?(?:state|backend)", r"state\s?lock\w*", r"backend s3"),
    "HPA/autoscaling pods": _rx(r"HPA", r"horizontal pod autoscaler"), "PDB/probes": _rx(r"pod disruption", r"PDB", r"readiness", r"liveness"),
}
CMD_RX = re.compile(
    r"(?:^|[\s$>#])((?:terraform|tofu|kubectl|helm|aws|eksctl|docker|git|argocd|kustomize|curl|claude|npm|npx|dotnet|make|gh|k9s)"
    r"\s+[\w\-./:=@\"'{}\[\]$, ]{2,160})", re.M)
TF_RES_RX = re.compile(r"\b(aws_[a-z0-9]+(?:_[a-z0-9]+){1,6})\b")
TF_MOD_RX = re.compile(r"module\s+\"([\w\-]+)\"")
URL_RX = re.compile(r"(?:https?://|www\.)[\w\-./?=&%#:]+|github\.com/[\w\-./]+")
COST_RX = re.compile(
    r"\b(custos?|custar\w*|custa|cobra\w*|d[oó]lar\w*|US\$|\$\s?\d+|free\s?tier|free plan|n[ií]vel gratuito|gratuit\w*|de gra[cç]a|"
    r"gr[aá]tis|billing|aws budgets?|fatura\w*|caro|barat\w*|centavos?|por hora|terraform destroy|destr[oó]i\w*|"
    r"apagar|deletar|esquec\w+ ligad\w*|cr[eé]ditos?)\b", re.I)
WARN_RX = re.compile(
    r"\b(cuidado|aten[cç][aã]o|importante|n[aã]o esque[cç]a\w*|nunca|evite\w*|boa pr[aá]tica\w*|best practices?|"
    r"seguran[cç]a|produ[cç][aã]o|least privilege|menor privil[eé]gio|admin\w* access|problema|erro)\b", re.I)


def count_terms(text: str, table: dict) -> Counter:
    c = Counter()
    for k, rx in table.items():
        n = len(rx.findall(text))
        if n:
            c[k] = n
    return c


def stage_knowledge(lesson: dict, d: Path, args) -> None:
    tj, oj = d / "transcript.json", d / "ocr.jsonl"
    segs = json.loads(tj.read_text(encoding="utf-8"))["segments"] if tj.exists() else []
    evs = [json.loads(x) for x in oj.read_text(encoding="utf-8").splitlines() if x.strip()] if oj.exists() else []
    speech = " ".join(s["text"] for s in segs)
    screen = "\n".join(e["text"] for e in evs)

    def ctx(i):
        return " ".join(s["text"] for s in segs[max(0, i - 1): i + 2])

    cost = [{"t": s["start"], "ts": hms(s["start"]), "match": sorted({m.lower() for m in COST_RX.findall(s["text"])}), "text": ctx(i)}
            for i, s in enumerate(segs) if COST_RX.search(s["text"])]
    warn = [{"t": s["start"], "ts": hms(s["start"]), "text": ctx(i)} for i, s in enumerate(segs) if WARN_RX.search(s["text"])]
    cmds = Counter()
    first_seen = {}
    for e in evs:
        for m in CMD_RX.findall(e["text"]):
            c = re.sub(r"\s+", " ", m).strip()[:140]
            cmds[c] += 1
            first_seen.setdefault(c, hms(e["t_start"]))
    tf = Counter(TF_RES_RX.findall(screen))
    mods = Counter(TF_MOD_RX.findall(screen))
    urls = sorted({u.rstrip(".,)") for u in URL_RX.findall(screen + " " + speech)})
    k = {
        "lesson": lesson["slug"], "title": lesson["title"], "module": lesson["module"], "duration_s": lesson["duration_s"],
        "aws_services": dict(count_terms(speech + "\n" + screen, AWS_SERVICES).most_common()),
        "tools": dict(count_terms(speech + "\n" + screen, TOOLS).most_common()),
        "terraform_resources": dict(tf.most_common()), "terraform_modules": dict(mods.most_common()),
        "commands": [{"cmd": c, "n": n, "first": first_seen[c]} for c, n in cmds.most_common(120)],
        "urls": urls[:80], "cost_mentions": cost, "warnings": warn[:200],
        "words_spoken": len(speech.split()), "screens": len(evs),
    }
    write_json(d / "knowledge.json", k)


# ----------------------------------------------------------------------------- summarize (opcional, Ollama)
def ollama(prompt: str, model: str, host: str) -> str:
    import urllib.request
    req = urllib.request.Request(f"{host}/api/generate", method="POST", headers={"Content-Type": "application/json"},
                                 data=json.dumps({"model": model, "prompt": prompt, "stream": False,
                                                  "options": {"num_ctx": 8192, "temperature": 0.2}}).encode())
    with urllib.request.urlopen(req, timeout=600) as r:
        return json.loads(r.read())["response"].strip()


def blocks_of(segs: list[dict], size: int) -> list[tuple[int, list[dict]]]:
    b = defaultdict(list)
    for s in segs:
        b[int(s["start"] // size)].append(s)
    return sorted(b.items())


def stage_summarize(lesson: dict, d: Path, args) -> None:
    f = d / "summaries.json"
    tj = d / "transcript.json"
    if not tj.exists():
        return
    done = json.loads(f.read_text(encoding="utf-8")) if f.exists() and not args.force else {}
    segs = json.loads(tj.read_text(encoding="utf-8"))["segments"]
    for bi, ss in blocks_of(segs, args.block):
        key = str(bi)
        if key in done:
            continue
        txt = " ".join(s["text"] for s in ss)
        p = ("Você organiza conhecimento técnico de uma aula de DevOps/AWS (pt-BR). Do trecho abaixo, extraia em bullets "
             "curtos: (1) conceitos explicados, (2) passos/comandos executados, (3) serviços AWS e ferramentas, "
             "(4) alertas de custo/segurança, (5) decisões e boas práticas. Não invente nada fora do trecho.\n\n"
             f"TRECHO [{hms(bi*args.block)}–{hms((bi+1)*args.block)}]:\n{txt}")
        try:
            done[key] = ollama(p, args.ollama_model, args.ollama_host)
        except Exception as e:
            log(f"  ollama falhou ({e}); interrompendo summarize")
            break
        write_json(f, done)


# ----------------------------------------------------------------------------- render
CODEY = re.compile(r"[{}=$/]|resource\s+\"|module\s+\"|kubectl|terraform|apiVersion|kind:|aws_", re.I)


def stage_render(lesson: dict, d: Path, args) -> None:
    tj, oj, kj, sj = d / "transcript.json", d / "ocr.jsonl", d / "knowledge.json", d / "summaries.json"
    segs = json.loads(tj.read_text(encoding="utf-8"))["segments"] if tj.exists() else []
    evs = [json.loads(x) for x in oj.read_text(encoding="utf-8").splitlines() if x.strip()] if oj.exists() else []
    k = json.loads(kj.read_text(encoding="utf-8")) if kj.exists() else {}
    sums = json.loads(sj.read_text(encoding="utf-8")) if sj.exists() else {}
    L = [f"# {lesson['title']}", "",
         f"- **Módulo:** {lesson['module']}", f"- **Duração:** {hms(lesson['duration_s'])}",
         f"- **Fonte:** `{lesson['video']}`", f"- **Aula online:** {lesson.get('url','')}",
         f"- **Gerado:** {datetime.now():%Y-%m-%d %H:%M} por course_kb (transcrição faster-whisper + OCR RapidOCR; revisar trechos técnicos)",
         "", "> Material derivado de curso pago — uso pessoal, não publicar.", ""]
    if k:
        L += ["## Mapa de conhecimento", "",
              "**Serviços AWS:** " + (", ".join(f"{a} ({n})" for a, n in list(k["aws_services"].items())[:25]) or "—"), "",
              "**Ferramentas:** " + (", ".join(f"{a} ({n})" for a, n in list(k["tools"].items())[:25]) or "—"), ""]
        if k["terraform_resources"]:
            L += ["**Recursos Terraform vistos na tela:** " + ", ".join(f"`{r}`" for r in list(k["terraform_resources"])[:40]), ""]
        if k["commands"]:
            L += ["### Comandos vistos na tela", "", "```bash"] + [f"{c['cmd']}    # {c['first']}" for c in k["commands"][:40]] + ["```", ""]
        if k["cost_mentions"]:
            L += ["### Menções a custo / free tier / teardown", ""] + [f"- **[{c['ts']}]** {c['text']}" for c in k["cost_mentions"][:40]] + [""]
        if k["urls"]:
            L += ["### Links citados", ""] + [f"- {u}" for u in k["urls"][:30]] + [""]
    L += ["## Linha do tempo", ""]
    ev_by_block = defaultdict(list)
    for e in evs:
        ev_by_block[int(e["t_start"] // args.block)].append(e)
    seg_blocks = dict(blocks_of(segs, args.block))
    for bi in sorted(set(seg_blocks) | set(ev_by_block)):
        L += [f"### [{hms(bi*args.block)} – {hms((bi+1)*args.block)}]", ""]
        if str(bi) in sums:
            L += ["**Resumo (LLM local):**", "", sums[str(bi)], ""]
        if bi in seg_blocks:
            L += [" ".join(s["text"] for s in seg_blocks[bi]), ""]
        shown = 0
        for e in ev_by_block.get(bi, []):
            if shown >= args.max_screens or not CODEY.search(e["text"]):
                continue
            lines = e["text"].splitlines()[:30]
            L += [f"<details><summary>Tela {hms(e['t_start'])} — <a href=\"{e['frame']}\">quadro</a></summary>", "",
                  "```text", *lines, "```", "</details>", ""]
            shown += 1
    write_text(d / "lesson.md", "\n".join(L))


def merge_ocr_variants(c: Counter, cutoff: float = 0.9) -> Counter:
    """Funde variantes com erro de OCR (aws_ekcs_cluster -> aws_eks_cluster) no termo mais frequente."""
    kept = Counter()
    for term, n in c.most_common():
        near = difflib.get_close_matches(term, list(kept), n=1, cutoff=cutoff)
        kept[near[0] if near else term] += n
    return kept


def render_course(out: Path, data: dict, lessons: list[dict]) -> None:
    ks = []
    for l in lessons:
        f = out / l["slug"] / "knowledge.json"
        if f.exists():
            ks.append((l, json.loads(f.read_text(encoding="utf-8"))))
    svc, tools_, tf, cmds = Counter(), Counter(), Counter(), Counter()
    for _, k in ks:
        svc.update(k["aws_services"]); tools_.update(k["tools"]); tf.update(k["terraform_resources"])
        for c in k["commands"]:
            cmds[c["cmd"]] += c["n"]
    tf = merge_ocr_variants(tf)
    L = ["# Base de conhecimento — " + Path(data["course"]).name, "",
         f"Gerado {datetime.now():%Y-%m-%d %H:%M} · {len(ks)} aulas · {hms(sum(l['duration_s'] for l,_ in ks))} de vídeo", "",
         "> Derivado de curso pago — privado.", "", "## Aulas", "",
         "| # | Aula | Duração | Palavras | Telas | Top serviços |", "|---|---|---|---|---|---|"]
    for l, k in ks:
        L.append(f"| {l['order']} | [{l['title']}]({l['slug']}/lesson.md) | {hms(l['duration_s'])} | {k['words_spoken']} | "
                 f"{k['screens']} | {', '.join(list(k['aws_services'])[:5])} |")
    L += ["", "## Serviços AWS (menções no curso)", ""] + [f"- {a}: {n}" for a, n in svc.most_common(60)]
    L += ["", "## Ferramentas", ""] + [f"- {a}: {n}" for a, n in tools_.most_common(60)]
    if tf:
        L += ["", "## Recursos Terraform vistos", ""] + [f"- `{a}` ({n})" for a, n in tf.most_common(80)]
    if cmds:
        L += ["", "## Comandos (OCR, deduplicados)", "", "```bash"] + [c for c, _ in cmds.most_common(80)] + ["```"]
    L += ["", "## Todas as menções a custo (para o plano FinOps / AWS grátis)", ""]
    for l, k in ks:
        for c in k["cost_mentions"]:
            L.append(f"- [{l['slug']} {c['ts']}]({l['slug']}/lesson.md) {c['text'][:300]}")
    write_text(out / "KNOWLEDGE.md", "\n".join(L))
    write_json(out / "knowledge_index.json", {"aws_services": dict(svc), "tools": dict(tools_),
                                              "terraform_resources": dict(tf), "commands": dict(cmds.most_common(300))})
    log(f"KNOWLEDGE.md -> {out / 'KNOWLEDGE.md'}")


# ----------------------------------------------------------------------------- compare
SCAN_EXT = {".tf", ".tfvars", ".hcl", ".py", ".yaml", ".yml", ".json", ".md", ".sh", ".ps1", ".toml", ".ts", ".js", ".cs", ".sql", ".ini", ".env.example"}
SKIP_DIRS = {"node_modules", ".git", ".venv", "venv", "dist", "build", "__pycache__", ".terraform", ".next", "site-packages", "_kb", ".mypy_cache", ".pytest_cache"}


def iter_repo_files(path: Path):
    """Arquivos versionados via `git ls-files` (rápido em pasta sincronizada); fallback os.walk."""
    if (path / ".git").exists() and shutil.which("git"):
        r = subprocess.run(["git", "-C", str(path), "ls-files", "-z"], capture_output=True)
        if r.returncode == 0:
            for rel in r.stdout.decode("utf-8", "ignore").split("\0"):
                if rel:
                    yield path / rel
            return
    for root, dirs, files in os.walk(path):
        dirs[:] = [x for x in dirs if x not in SKIP_DIRS and not x.startswith(".cache")]
        for fn in files:
            yield Path(root) / fn


def scan_repo(path: Path, terms: dict, max_files: int = 20000) -> tuple[Counter, dict, int]:
    hits, where, n = Counter(), defaultdict(list), 0
    for p in iter_repo_files(path):
        if p.suffix.lower() not in SCAN_EXT or SKIP_DIRS & set(p.parts):
            continue
        try:
            if p.stat().st_size > 1_000_000:
                continue
            txt = p.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        n += 1
        for t, rx in terms.items():
            c = len(rx.findall(txt))
            if c:
                hits[t] += c
                if len(where[t]) < 4:
                    where[t].append(str(p.relative_to(path)))
        if n >= max_files:
            break
    return hits, where, n


def cmd_compare(args) -> None:
    out, data = load_course(args)
    idx_f = out / "knowledge_index.json"
    if not idx_f.exists():
        sys.exit("rode antes: run --stages knowledge,render")
    idx = json.loads(idx_f.read_text(encoding="utf-8"))
    terms = {}
    for k, n in idx["aws_services"].items():
        if n >= args.min_mentions:
            terms[f"aws:{k}"] = AWS_SERVICES[k]
    for k, n in idx["tools"].items():
        if n >= args.min_mentions:
            terms[f"tool:{k}"] = TOOLS[k]
    for r, n in idx["terraform_resources"].items():
        if n >= args.min_mentions:
            terms[f"tf:{r}"] = re.compile(r"\b" + re.escape(r) + r"\b")
    plan_txt = "\n".join(Path(p).read_text(encoding="utf-8", errors="ignore") for p in (args.plan or []))
    repos = {}
    for spec in args.repo or []:
        name, _, p = spec.partition("=")
        repos[name] = Path(p)
    res = {}
    for name, p in repos.items():
        if not p.exists():
            log(f"repo ausente: {name} -> {p}"); continue
        log(f"varrendo {name} ...")
        h, w, n = scan_repo(p, terms)
        res[name] = {"files": n, "hits": dict(h), "where": w}
    course_n = {**{f"aws:{k}": v for k, v in idx["aws_services"].items()}, **{f"tool:{k}": v for k, v in idx["tools"].items()},
                **{f"tf:{k}": v for k, v in idx["terraform_resources"].items()}}
    rows = []
    for t, rx in terms.items():
        in_plan = bool(rx.search(plan_txt)) if plan_txt else None
        cov = {name: r["hits"].get(t, 0) for name, r in res.items()}
        own = {n: v for n, v in cov.items() if not n.startswith("curso")}
        status = "COBERTO" if any(own.values()) else ("SÓ NO MATERIAL DO CURSO" if any(cov.values()) else "LACUNA")
        rows.append({"term": t, "course_mentions": course_n.get(t, 0), "in_plan": in_plan, "coverage": cov, "status": status})
    rows.sort(key=lambda r: (r["status"] != "LACUNA", -r["course_mentions"]))
    write_json(out / "coverage.json", {"generated": datetime.now().isoformat(timespec="seconds"), "repos": res, "rows": rows})
    names = list(res)
    L = ["# Cobertura: curso x repositórios x plano", "", f"Gerado {datetime.now():%Y-%m-%d %H:%M}. "
         "Contagem = ocorrências textuais do termo nos arquivos (indicador de presença, não prova de implementação funcional).", "",
         "| Termo | Menções no curso | No plano | " + " | ".join(names) + " | Status |",
         "|---|---|---|" + "---|" * len(names) + "---|"]
    for r in rows:
        L.append(f"| {r['term']} | {r['course_mentions']} | {'sim' if r['in_plan'] else ('não' if r['in_plan'] is False else '—')} | "
                 + " | ".join(str(r["coverage"][n] or "") for n in names) + f" | {r['status']} |")
    L += ["", "## Onde aparece (amostra)", ""]
    for n in names:
        L += [f"### {n} ({res[n]['files']} arquivos varridos)", ""]
        for t, files in sorted(res[n]["where"].items()):
            L.append(f"- **{t}**: " + ", ".join(f"`{f}`" for f in files))
        L.append("")
    write_text(out / "COVERAGE.md", "\n".join(L))
    log(f"COVERAGE.md -> {out / 'COVERAGE.md'}  ({sum(r['status']=='LACUNA' for r in rows)} lacunas)")


# ----------------------------------------------------------------------------- main
STAGES = {"transcribe": stage_transcribe, "ocr": stage_ocr, "knowledge": stage_knowledge,
          "summarize": stage_summarize, "render": stage_render}


def cmd_run(args) -> None:
    out, data = load_course(args)
    lessons = select_lessons(data, args.only)
    stages = [s.strip() for s in args.stages.split(",") if s.strip()]
    for s in stages:
        if s not in STAGES:
            sys.exit(f"estágio desconhecido: {s} (válidos: {', '.join(STAGES)})")
    # aulas curtas primeiro: valida o pipeline rápido antes das longas
    for l in sorted(lessons, key=lambda x: x["duration_s"]):
        d = out / l["slug"]
        d.mkdir(parents=True, exist_ok=True)
        for s in stages:
            try:
                STAGES[s](l, d, args)
            except KeyboardInterrupt:
                raise
            except Exception as e:  # uma aula com falha não derruba o lote
                log(f"ERRO {s} {l['slug']}: {type(e).__name__}: {e}")
    if "render" in stages or "knowledge" in stages:
        render_course(out, data, sorted(lessons, key=lambda x: x["order"]))


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    def common(p):
        p.add_argument("--course", required=True, help="pasta raiz do curso")
        p.add_argument("--out", help="pasta de saída (padrão: <course>/_kb)")

    p = sub.add_parser("discover"); common(p)
    p = sub.add_parser("run"); common(p)
    p.add_argument("--stages", default="transcribe,ocr,knowledge,render")
    p.add_argument("--only", help="filtra aulas por trecho do slug (vírgula)")
    p.add_argument("--force", action="store_true")
    p.add_argument("--model", default="large-v3-turbo")
    p.add_argument("--device", default="cuda")
    p.add_argument("--compute", default="float16")
    p.add_argument("--language", default="pt")
    p.add_argument("--prompt", default=None)
    p.add_argument("--frame-interval", type=float, default=4.0)
    p.add_argument("--stable-thr", type=float, default=0.015)
    p.add_argument("--change-thr", type=float, default=0.012)
    p.add_argument("--stale-s", type=float, default=45.0, help="força OCR se a tela ficou N s sem leitura")
    p.add_argument("--min-chars", type=int, default=20)
    p.add_argument("--block", type=int, default=300, help="segundos por bloco da linha do tempo")
    p.add_argument("--max-screens", type=int, default=3)
    p.add_argument("--ollama-model", default="qwen2.5:7b-instruct")
    p.add_argument("--ollama-host", default="http://localhost:11434")
    p = sub.add_parser("compare"); common(p)
    p.add_argument("--repo", action="append", help="NOME=CAMINHO (repita). Prefixo 'curso' = material do curso")
    p.add_argument("--plan", action="append", help="arquivo(s) do plano/ideia")
    p.add_argument("--min-mentions", type=int, default=2)
    args = ap.parse_args()
    {"discover": cmd_discover, "run": cmd_run, "compare": cmd_compare}[args.cmd](args)


if __name__ == "__main__":
    main()
