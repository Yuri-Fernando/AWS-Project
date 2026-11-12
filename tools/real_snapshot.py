#!/usr/bin/env python
"""Retrato operacional da AWS real ENQUANTO a sessão está no ar (antes do destroy) — para consulta futura sem nuvem.

  python tools/real_snapshot.py [--out docs/aws-real/sessao-AAAA-MM-DD]

Grava, em arquivos de texto, o estado vivo de: cluster EKS e node group, nós e pods, Ingress/Services, releases do
Helm, Applications do ArgoCD, ALB (listeners, regras, target groups, saúde dos alvos), certificado ACM (metadados),
Lambda/DynamoDB/API Gateway, Pod Identity e o plano/créditos da conta. Só leitura. Mascara ID da conta, IDs IAM,
e-mails e IPs públicos; não lê Secrets nem valores sensíveis.
"""
from __future__ import annotations

import argparse
import os
import re
import subprocess
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def mask(t: str) -> str:
    t = re.sub(r"\b\d{12}\b", "<conta>", t)
    t = re.sub(r"\bA(IDA|ROA|SIA|KIA)[A-Z0-9]{12,}\b", "<id-iam>", t)
    t = re.sub(r"[\w.+-]+@[\w-]+\.[\w.]+", "<email>", t)
    return re.sub(r"\b(?!10\.)\d{1,3}(\.\d{1,3}){3}\b", "<ip-publico>", t)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(ROOT / "docs" / "aws-real" / f"sessao-{datetime.now():%Y-%m-%d}"))
    a = ap.parse_args()
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    aenv = {k: v for k, v in os.environ.items() if k.upper() not in ("AWS_ENDPOINT_URL", "AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY")}
    aenv.setdefault("AWS_PROFILE", os.environ.get("LAB_REAL_PROFILE", "argus-lab"))
    aenv.update(AWS_DEFAULT_REGION="us-east-1", AWS_PAGER="", KUBECONFIG=str(ROOT / "platform" / ".kube" / "aws.yaml"))

    def run(cmd: list[str]) -> str:
        r = subprocess.run(cmd, env=aenv, capture_output=True, text=True, encoding="utf-8", errors="replace")
        return (r.stdout or r.stderr).strip()

    alb_arns = run(["aws", "elbv2", "describe-load-balancers", "--query",
                    "LoadBalancers[?starts_with(LoadBalancerName,'k8s-argus')].LoadBalancerArn", "--output", "text"]).split()
    sections: dict[str, list[tuple[str, list[str]]]] = {
        "01-eks.txt": [
            ("cluster", ["aws", "eks", "describe-cluster", "--name", "argus-platform-lab-eks", "--query",
                         "cluster.{nome:name,versao:version,plataforma:platformVersion,status:status,acesso:accessConfig.authenticationMode,endpointPublico:resourcesVpcConfig.endpointPublicAccess}", "--output", "table"]),
            ("node group", ["aws", "eks", "describe-nodegroup", "--cluster-name", "argus-platform-lab-eks", "--nodegroup-name",
                            "argus-platform-lab-eks-default", "--query",
                            "nodegroup.{tipos:instanceTypes,capacidade:capacityType,ami:amiType,disco:diskSize,escala:scalingConfig,status:status}", "--output", "json"]),
            ("add-ons", ["aws", "eks", "list-addons", "--cluster-name", "argus-platform-lab-eks", "--output", "table"]),
            ("Pod Identity", ["aws", "eks", "list-pod-identity-associations", "--cluster-name", "argus-platform-lab-eks",
                              "--query", "associations[].{ns:namespace,sa:serviceAccount}", "--output", "table"]),
        ],
        "02-kubernetes.txt": [
            ("nós", ["kubectl", "get", "nodes", "-o", "wide"]),
            ("pods (todos os namespaces)", ["kubectl", "get", "pods", "-A", "-o", "wide"]),
            ("deployments/jobs do ecossistema", ["kubectl", "get", "deploy,job,svc,pdb,sa", "-n", "ecosystem"]),
            ("ingress", ["kubectl", "get", "ingress", "-A", "-o", "wide"]),
            ("ingress churn-api (detalhe)", ["kubectl", "describe", "ingress", "churn-api", "-n", "ecosystem"]),
            ("uso de recursos", ["kubectl", "top", "nodes"]),
        ],
        "03-gitops-helm.txt": [
            ("Applications do ArgoCD", ["kubectl", "get", "applications", "-n", "argocd", "-o",
                                        "custom-columns=APP:.metadata.name,SYNC:.status.sync.status,HEALTH:.status.health.status,REVISAO:.status.sync.revision,CAMINHO:.spec.source.path"]),
            ("ApplicationSet", ["kubectl", "get", "applicationset", "-n", "argocd", "-o", "wide"]),
            ("releases Helm", ["helm", "list", "-A"]),
        ],
        "04-alb-acm.txt": [("load balancer", ["aws", "elbv2", "describe-load-balancers", "--load-balancer-arns", *alb_arns,
                                              "--query", "LoadBalancers[].{nome:LoadBalancerName,dns:DNSName,esquema:Scheme,tipo:Type,estado:State.Code,azs:AvailabilityZones[].ZoneName}",
                                              "--output", "json"])] if alb_arns else [],
        "05-serverless.txt": [
            ("Lambda", ["aws", "lambda", "get-function-configuration", "--function-name", "credit-score-lab-predict", "--query",
                        "{nome:FunctionName,runtime:Runtime,memoria:MemorySize,timeout:Timeout,tracing:TracingConfig.Mode,tamanhoZip:CodeSize,estado:State}", "--output", "table"]),
            ("DynamoDB", ["aws", "dynamodb", "describe-table", "--table-name", "credit-score-lab-inference-log", "--query",
                          "Table.{tabela:TableName,status:TableStatus,cobranca:BillingModeSummary.BillingMode,chave:KeySchema}", "--output", "json"]),
            ("API Gateway", ["aws", "apigatewayv2", "get-apis", "--query", "Items[].{nome:Name,protocolo:ProtocolType,endpoint:ApiEndpoint}", "--output", "table"]),
        ],
        "06-conta.txt": [
            ("plano", ["aws", "freetier", "get-account-plan-state", "--query",
                       "{plano:accountPlanType,status:accountPlanStatus,creditos:accountPlanRemainingCredits.amount,expira:accountPlanExpirationDate}", "--output", "table"]),
            ("budgets", ["aws", "budgets", "describe-budgets", "--account-id",
                         run(["aws", "sts", "get-caller-identity", "--query", "Account", "--output", "text"]),
                         "--query", "Budgets[].{nome:BudgetName,limite:BudgetLimit.Amount,gastoAtual:CalculatedSpend.ActualSpend.Amount}", "--output", "table"]),
        ],
    }
    for arn in alb_arns:
        sections["04-alb-acm.txt"] += [
            ("listeners", ["aws", "elbv2", "describe-listeners", "--load-balancer-arn", arn, "--query",
                           "Listeners[].{porta:Port,protocolo:Protocol,politicaTLS:SslPolicy,certificados:length(Certificates || `[]`),acaoPadrao:DefaultActions[0].Type}", "--output", "table"]),
            ("target groups e saúde", ["aws", "elbv2", "describe-target-groups", "--load-balancer-arn", arn, "--query",
                                       "TargetGroups[].{nome:TargetGroupName,porta:Port,tipoAlvo:TargetType,healthcheck:HealthCheckPath}", "--output", "table"]),
        ]
        for tg in run(["aws", "elbv2", "describe-target-groups", "--load-balancer-arn", arn, "--query",
                       "TargetGroups[].TargetGroupArn", "--output", "text"]).split():
            sections["04-alb-acm.txt"].append((f"alvos de {tg.split('/')[-2]}", ["aws", "elbv2", "describe-target-health",
                                               "--target-group-arn", tg, "--query", "TargetHealthDescriptions[].{alvo:Target.Id,porta:Target.Port,estado:TargetHealth.State}", "--output", "table"]))
    sections["04-alb-acm.txt"].append(("certificado ACM (metadados, sem chave)", ["aws", "acm", "list-certificates", "--includes",
                                       "keyTypes=RSA_2048", "--query", "CertificateSummaryList[].{dominio:DomainName,tipo:Type,status:Status,emUso:InUse}", "--output", "table"]))
    for fname, items in sections.items():
        body = [f"# {fname} — capturado em {datetime.now():%Y-%m-%d %H:%M} (sessão real, antes do destroy)\n"]
        for title, cmd in items:
            body.append(f"\n## {title}\n$ {mask(' '.join(cmd))}\n{mask(run(cmd))}\n")
        (out / fname).write_text("".join(body), encoding="utf-8")
        print(f"  ✓ {out.name}/{fname}")


if __name__ == "__main__":
    main()
