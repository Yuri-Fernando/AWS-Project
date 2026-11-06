# course_kb — extração de conhecimento de videoaulas

Pipeline local e gratuito: **transcrição** (faster-whisper na GPU) + **OCR de tela** (RapidOCR, só quando a tela muda)
→ extração determinística (serviços AWS, ferramentas, comandos, recursos Terraform, custos, alertas)
→ Markdown navegável por aula + índice do curso + **cobertura curso × repositórios × plano**.

## Requisitos (já presentes no Python 3.10 canônico)
`faster-whisper`, `rapidocr` (onnxruntime), `opencv-python`, `numpy`; `ffmpeg`/`ffprobe` no PATH. GPU opcional
(`--device cpu --compute int8`). Modelo padrão `large-v3-turbo` (~1,6 GB, baixado uma vez para o cache HF).

## Uso
```powershell
$py = "C:\Users\Yuri_\AppData\Local\Programs\Python\Python310\python.exe"
$c  = "Q:\Cursos Pagos\DevOps na Nuvem ( )"
& $py course_kb.py discover --course $c                       # inventário + melhor arquivo por aula
& $py course_kb.py run --course $c --stages transcribe         # GPU  (rodar em paralelo com o próximo)
& $py course_kb.py run --course $c --stages ocr                # CPU
& $py course_kb.py run --course $c --stages knowledge,render   # segundos
& $py course_kb.py compare --course $c --plan ..\..\Plano_Master_Argus_AWS_Data_AI_2026.md `
      --repo "EnterpriseAutomation=G:\...\Enterprise Cloud Automation Platform" --repo "curso-eks=...\eks-express-iac"
```
Opcional: `--stages summarize` gera resumo por bloco de 5 min via **Ollama local** (`--ollama-model`), custo zero.

## Saída (`<curso>\_kb\`, privada — derivada de curso pago, não versionar em repo público)
| Arquivo | Conteúdo |
|---|---|
| `course.json` | aulas, arquivo escolhido, duração real × esperada, status |
| `<aula>/transcript.{json,srt,txt}` | segmentos com timestamps |
| `<aula>/ocr.jsonl` + `keyframes/` | telas distintas (código, terminal, console) com intervalo de tempo |
| `<aula>/knowledge.json` | serviços, ferramentas, comandos, recursos TF, URLs, menções a custo e alertas |
| `<aula>/lesson.md` | mapa de conhecimento + linha do tempo (fala + telas de código) |
| `KNOWLEDGE.md`, `knowledge_index.json` | índice consolidado do curso |
| `COVERAGE.md`, `coverage.json` | termo × menções no curso × presença no plano × ocorrências por repositório |

## Decisões
- Idempotente: a saída de cada estágio marca conclusão; `transcribe` retoma de `transcript.partial.jsonl`.
- OCR só em quadro **estável** que **mudou** desde a última leitura (ou após `--stale-s`); textos ≥ 88% iguais são
  fundidos mantendo a versão mais longa (código sendo digitado).
- IDs de conta AWS (12 dígitos) vistos na tela são mascarados como `<AWS_ACCOUNT_ID>`.
- `compare` usa `git ls-files` (rápido em pasta do Google Drive) e conta ocorrências textuais — indicador de presença,
  **não** prova de implementação funcional.

## Resultado da primeira execução (05/11/2026, RTX 3060 Ti)
9 aulas / 11h57 de vídeo: transcrição ~1h30 (≈13× tempo real nos workshops longos), OCR ~2h20 em paralelo
(1.054 telas distintas). Limitações: termos técnicos falados podem sair errados (ex.: "Cloud Code" = Claude Code,
"Carpenter" = Karpenter); vídeos em 480p limitam o OCR de fonte pequena.
