# PLANO MASTER — ARGUS ENTERPRISE AI & DATA CLOUD PLATFORM
**Versão:** 0.1 — 04/11/2026  
**Foco:** portfólio demonstrável para vagas de Engenharia de Dados, Cientista de Dados, ML/MLOps, AI Engineer, Platform/DevOps e DBRE — AWS-first, local-first e custos controlados.  
**Estado:** blueprint proposto, sem alteração de repositórios, deploys ou contas AWS.

## 0. Decisão executiva
Construir **um ecossistema integrado por contratos**, e não um monorrepositório gigantesco. **Argus** é o produto e control plane de dados/IA; **Enterprise-Automation** é a plataforma reutilizável de IaC, CI/CD, observabilidade e segurança. Os demais repositórios preservam seus domínios e integração por APIs, eventos, SDKs versionados e artefatos.

**Objetivo demonstrável:** Um evento de cliente chega via produto (RetentIQ) → pipeline de ingestão/CDC e Lakehouse (Argus) → contratos de dados, qualidade e governança (Argus/ThemisAI) → features, modelo e registry (Argus/MLflow) → predição por API e consulta RAG/agente (OmniMind/Argus) → dashboard, telemetria, incidentes e auditoria (Enterprise-Automation). Uma segunda trilha demonstra *credit risk* com RiskCredit e Credit-Score-AWS, isolada do domínio de churn. Ambas utilizam os mesmos padrões de plataforma, não o mesmo dataset nem modelo.

**Princípio:** 1 caminho vertical executável, depois extensões. O que não roda não deve constar como experiência operacional consolidada.

## 1. Inventário verificado e papel de cada repositório
| Repositório | Estado e evidências declarados no README inspecionado em 04/11/2026 | Responsabilidade no master | Trabalho novo prioritário |
|---|---|---|---|
| [Argus](https://github.com/Yuri-Fernando/Argus) | v2.12 local; README indica 306 testes passando/9 pulados. Migração v2.11 com **Spark/Delta reais em contêiner** e 59 testes; sem Teradata/Databricks workspace real. Governança local 121 testes. | Produto principal: Lakehouse/MDM/CDC/RAG/governança e catálogo de integrações. | Conectar fluxo end-to-end, operação e cloud AWS sob custo controlado; testar contratos compartilhados. |
| [Enterprise-Automation](https://github.com/Yuri-Fernando/Enterprise-Automation) | v1.1.0-dev; Terraform, Ansible, Python, CI/CD, Prometheus/Grafana/Loki, RDS MySQL em código. Sem `terraform apply` real. | AWS Platform Engineering: infraestrutura, deploy, CI/CD, FinOps, observabilidade, políticas e runbooks. | Adaptadores para PostgreSQL, stacks cloud pequenas, hardening e smoke tests reais. |
| [RiskCredit](https://github.com/Yuri-Fernando/RiskCredit) | v3.1; README reporta 40 testes; modelagem, calibração, SHAP e governança de risco. | Domínio financeiro: treinamento, validação e aprovação de modelos de risco. | Contratos de release/modelo e handoff automatizado para deploy. |
| [Credit Score Predictor AWS](https://github.com/Yuri-Fernando/Credit-Score-Predictor---AWS-Streamlit) | v1 serverless declarada como implantada em 2025; v2-v3.2 MLOps/Step Functions/Terraform testados **localmente, sem novos applies**. | Serving e MLOps em AWS: SageMaker, Lambda, API Gateway, DynamoDB, S3. | E2E em staging efêmero; alarmes, autenticação, rollout/rollback e métricas reais quando orçamento autorizar. |
| [RetentIQ](https://github.com/Yuri-Fernando/RetentIQ) | v2.1; SaaS/eventos, Kafka/RabbitMQ reais em Docker, CQRS, dashboard, ML e testes locais; sem deploy cloud. | Produto demonstrador/event producer, API, Kafka e caso de negócio de churn/retenção. | Publicar eventos contratados, reconciliar consumo no Argus, demos e métricas de negócio. |
| [ThemisAI](https://github.com/Yuri-Fernando/ThemisAI) | 523 testes informados, governança LGPD e IA local; deploy público pendente. | Política de PII, DPIA/RIPD, auditoria e guardrails antes de agentes e serving. | Expor policy gate e processo de revisão com falso-positivo/negativo documentado. |
| [OmniMind AI OS](https://github.com/Yuri-Fernando/OmniMind_AI_OS) | Orquestração de agentes; observabilidade local; avaliação externa parcialmente bloqueada por credenciais; várias capacidades com testes sem infra real. | Agente consultor que consome serviços governados (dados, modelos, runbooks). | Ferramentas permissionadas, golden set, avaliação real, tracing e custo por solicitação. |
| [IA_Agentica](https://github.com/Yuri-Fernando/IA_Agentica) | Laboratório amplo de skills, MCP, runtimes e automação. | Bancada de desenvolvimento/automação, **não dependência runtime obrigatória** do produto. | Gerar automações com revisão humana e interfaces estáveis; evitar acoplamento de dezenas de agentes. |
| [Churn Intelligence](https://github.com/Yuri-Fernando/Churn_intelligence) | Projeto de modelos, API, PySpark e streaming. | Biblioteca de referência/algoritmos e comparativos do domínio de churn. | Reaproveitar componentes específicos com atribuição e testes, sem duplicar pipeline do Argus. |
| [DVN Workshop Maio](https://github.com/kenerry-serain/dvn-workshop-maio) | Terraform VPC/EKS/OIDC, app Next.js/.NET, ECR, CI/CD, ArgoCD. | **Referência educacional externa** de entrega de aplicações em K8s. | Extrair padrões e reaplicar implementação própria sob revisão. |
| [EKS Express IaC](https://github.com/kenerry-serain/eks-express-iac) | Terraform para backend S3/DynamoDB, networking, EKS, Karpenter, WAF, Prometheus e Grafana AWS. | **Referência educacional externa** para operações EKS e segurança. | Usar só na fase avançada; auditar versões, permissões, preços e bugs antes de qualquer aplicação. |

**Licenças:** o fato de um repositório de terceiro ser público **não autoriza** copiar código sem licença. Conferir licença e permissões dos materiais adquiridos; aprender padrões e produzir implementação própria, ou obter autorização explícita.

## 2. Escopo funcional: duas jornadas separadas, mesma plataforma
**Jornada A — Customer Intelligence (demo principal)**
1. RetentIQ emite eventos de cadastro, compra, sessão e retenção (dados públicos/sintéticos sem PII real).
2. Argus coleta eventos (Redpanda/Kafka local), snapshot e CDC, persiste Bronze/Silver/Gold em Delta/Parquet, com regras de qualidade, idempotência, schema evolution e lineage.
3. MDM gera golden record. Feature Store ponto-no-tempo alimenta modelos de churn; MLflow registra parâmetros, artefatos, métricas e aprovação.
4. Serviço FastAPI fornece predição e explicabilidade. OmniMind usa ferramentas MCP/RAG para responder questões de negócio com fontes e RBAC.
5. ThemisAI aplica máscara PII, avaliação de risco e policy gates; dashboards mostram churn, conversão, latência, custos, qualidade e incidentes.

**Jornada B — Financial ML (demo auxiliar, isolada)**
1. RiskCredit treina e valida *champion/challenger* com dataset público e mantém governança/limites do modelo.
2. Um contrato de artefato e versão transfere o modelo aprovado para Credit Score AWS.
3. A inferência passa por API Gateway/Lambda/SageMaker; resultados são monitorados com métricas de drift, latência e custo.
4. Staging efêmero valida deployment, rollback e alarmes sem alegar uma infra cloud permanente que não existe.

**Não misturar dados** de clientes de churn e crédito nem unificar as decisões de aprovação e marketing no mesmo modelo.

## 3. Arquitetura de referência — três perfis

### Perfil LOCAL (sempre disponível; primeiro a ficar verde)
- Docker Compose com PostgreSQL, Redis, Redpanda/Kafka ou RabbitMQ conforme fluxo, MinIO compatível S3 para testes, Spark/Delta, MLflow, OpenTelemetry, Prometheus/Grafana/Loki.
- FastAPI para serving, Streamlit/Next.js para UI; Langfuse **opcional** após tracing básico funcional.
- `make demo-up`, `make seed`, `make test-e2e`, `make demo-down` (nomes propostos) e dataset determinístico.
- Evitar iniciar todos os serviços simultaneamente; perfis `data`, `ml`, `agent`, `platform`, `dbre` para reduzir RAM.

### Perfil AWS-LITE (mínimo real, orçamento aprovado; não obrigatório para MVP)
- S3 (object storage), IAM least privilege + GitHub Actions OIDC, ECR, CloudWatch, EventBridge, Lambda/API Gateway ou ECS/Fargate para 1–2 serviços; Athena para consultas pontuais a dados no S3.
- Glue Data Catalog/Jobs apenas quando a comparação de execução com Spark local fizer sentido; evitar Glue e Databricks simultâneos no primeiro deploy.
- RDS PostgreSQL em laboratório efêmero independente; Secrets Manager/SSM conforme necessidade; snapshots e limpeza verificada.
- SageMaker Endpoint apenas durante sessões de teste autorizadas. Sem endpoints 24×7 para portfólio.
- Terraform `plan` + policy/cost check → aprovação humana → `apply` manual → smoke/e2e → `destroy` com revisão. Não fazer destruição automática de dados sem snapshot/critério.

### Perfil AWS-ADVANCED (workshop e demonstração de Platform Engineer)
- EKS/Kubernetes, managed node group ou Karpenter (comparação), EBS CSI, ALB Controller, external-dns, ArgoCD, OIDC/IRSA ou Pod Identity onde aplicável, WAF e Amazon Managed Prometheus/Grafana.
- Isolado em ambiente temporário, com TTL e teardown. Não obrigatório para a trilha de ML/DE.
- Comparar ECS/Fargate vs EKS com benchmark de operacionalidade e custo; não promover Kubernetes sem benefício verificável.

**Alternativas Azure/GCP/Databricks:** preservar interfaces; Databricks em workspace cloud real e Unity Catalog são exercícios opcionais após terminar AWS-LITE. Teradata real e Power BI real também são evidências futuras, não estado atual.

## 4. Requisitos transversais (prontos antes de produção)
- **Interfaces:** JSON Schema/Avro ou Pydantic para evento; OpenAPI e versionamento de API; pacote de contratos para `customer_event`, `gold_customer`, `feature_set`, `model_manifest`, `scoring_result`, `governance_decision`.
- **Segurança:** least privilege, OIDC, secrets fora do Git, PII sintético/mascarado, retenção, logs sem payload sensível, rate limit, teste de autorização e threat model. Nenhuma cópia de senha/token do workshop.
- **Qualidade:** pytest, integration tests com contêineres reais, testes de contratos, schema evolution, idempotência/CDC, CI; métricas rastreáveis e relatórios comparativos antes/depois.
- **Operação:** SLI/SLO definidos por serviço, alertas, tracing com correlation ID, dashboards de fila, banco, ML e API, runbooks, backup e restore testados.
- **FinOps:** tags `project`, `environment`, `owner`, `ttl`, `cost_center`; budgets/alertas, relatórios de custo estimado/real, limites de execução e teardown; budgets não substituem limites operacionais.
- **Evidência:** matriz de status por feature `LOCAL_REAL`, `AWS_REAL`, `VALIDATED_ONLY`, `MOCKED`, `PLANNED`; logs de comandos, data, commit SHA, capturas sem segredos e vídeo curto por jornada.

## 5. Plano de implementação sequencial

### P0 — Sprint 0: auditoria e congelamento da baseline
**Onde:** Argus / Enterprise-Automation / demais repos conforme README.  
**Entregas:** inventário código x README; mapear módulos existentes, dependências, scripts, testes, versões, APIs e custos; estabelecer ADRs e contratos de integração; backlog priorizado; corrigir incoerências de documentação.  
**Aceite:** tabela de evidências/commits, todos os demos e testes existentes documentados, nenhuma cópia prematura de código de terceiro.

### P0 — Sprint 1: vertical slice Customer360 local
**Onde:** RetentIQ + Argus.  
**Entregas:** evento `customer_activity.v1` → broker real → ingestão Argus → Bronze/Silver/Gold → consulta SQL → endpoint `/customer/{id}/insights` → UI minimal.  
**Aceite:** um comando sobe a demo, dataset de teste determinístico; teste automático prova replay idempotente, schema inválido bloqueado, evento duplicado não cria duplicata e relatório de reconciliação fecha.

### P0 — Sprint 2: Data Engineering e Databricks-ready
**Onde:** Argus (v2.11 Spark/Delta como base, sem refazer).  
**Entregas:** evolução incremental/CDC por watermark e posição de commit; Delta MERGE, evolução de schema, partição e manutenção; benchmark Spark vs baseline; modelo dimensional; lineage/OpenLineage; governança e controle de acesso nos dados; orquestração Airflow/Job escolhido.  
**Aceite:** pipeline reexecutável com full load + incremental + delete lógico, dados reconciliados e testes em Spark real; documentação deixa claro que não é Databricks workspace real. Depois, validar um job real Databricks se acesso/orçamento permitir.

### P0 — Sprint 3: DBRE/PostgreSQL para John Deere
**Onde:** Enterprise-Automation / módulo novo ou adaptador `database/postgresql`, sem quebrar MySQL original.  
**Entregas:** PostgreSQL Docker + Flyway + Terraform RDS parametrizado; índice e `EXPLAIN (ANALYZE, BUFFERS)` com comparação numérica antes/depois; `pg_dump`/`pg_restore`, backup/PITR no RDS se ativado, replicação lógica em laboratório, atraso e failover simulado; exporter e dashboards; runbook. Preparar Terraform/AWS DMS para migração piloto efêmera, somente após aprovação de custo.  
**Aceite:** restore de banco independente e comparação de checksums/contagens; migração de schema com rollback planejado; indicadores medidos RPO/RTO; incident drill e evidências SQL; testes reais com PG. Distinção entre simular réplica local e executar failover RDS.

### P1 — Sprint 4: ML/MLOps E2E
**Onde:** RiskCredit + Credit Score AWS + Argus ML.  
**Entregas:** artefato versionado com assinatura/metadata, model registry e aprovação; validação treino/serving, shadow/canary local, testes de contrato, drift e qualidade, logs e alertas; benchmark de inferência; pipeline de release para staging opcional.  
**Aceite:** modelo aprovado trafega pela API local com mesmos resultados (golden samples), rollback testado, métricas ROC-AUC/Gini/KS/calibração e p95 geradas de execuções reais; versionamento prova reprodutibilidade.

### P1 — Sprint 5: Agentic AI e governança
**Onde:** Argus + OmniMind + ThemisAI.  
**Entregas:** ferramentas MCP de leitura com allowlist/RBAC; RAG híbrido com fontes, filtros por tenant e teste de *prompt injection*; policy gate de PII, human-in-the-loop para qualquer ação; golden-set e avaliação com latência/tokens/custo/grounding/erro de ferramenta; tracing real.  
**Aceite:** agente responde usando dado governado, recusa ferramenta não autorizada, cita registros, não expõe PII de teste; avaliações executadas sem afirmar métricas externas que dependam de credenciais indisponíveis.

### P1 — Sprint 6: AWS-LITE demonstrável
**Onde:** Enterprise-Automation (infra) + workload do Argus/Credit Score.  
**Entregas:** pipeline GitHub OIDC→Terraform plan→manual approval→deploy AWS de apenas 1 vertical slice→smoke→e2e→teardown; AWS CloudWatch e custo real; nenhum segredo fixo.  
**Aceite:** logs cloud com timestamps, evidências de recursos criados/removidos e custos, rota autenticada, falhas observáveis, zero recursos esquecidos segundo checklist.

### P2 — Sprint 7: EKS/Platform/SRE do curso
**Onde:** Enterprise-Automation + apenas serviços selecionados do Argus/RetentIQ.  
**Entregas:** implementar padrões aprendidos de DVN Workshop e EKS Express em código próprio: VPC, EKS, ECR, GitHub Actions, ArgoCD; depois Karpenter, ALB, WAF, EBS CSI, métricas managed.  
**Aceite:** deploy via GitOps, readiness/liveness, políticas RBAC, rollout/rollback, teste de falha de nó, HPA/Karpenter com evidências reais, custo versus ECS; destroy revisado e testado.

### P2 — Sprint 8: trilhas opcionais por vaga
- **Databricks/Asaas/Nava:** job real PySpark/Delta e Unity Catalog em workspace, lineage, RBAC, otimização, custos, acesso/qualidade — sempre como exercício autenticado e não simulação mascarada.
- **Data Fabric/GCP:** conectores, catálogo, política e camada semântica; comparar AWS Glue/Athena com BigQuery/GCP, somente uma integração cloud por vez.
- **Backend Cobli:** integração Kafka real e consumer Kotlin/Spring isolado para eventos e tracing; não substituir backend do projeto por moda.
- **IA Engineer:** RAG/MCP, políticas e runtime de agentes, avaliação segura, API de produção, Bedrock opcional.
- **.NET MAUI:** manter como estudo separado apenas se uma vaga específica justificar; não integrar mobile à plataforma por obrigação.

### P0 — Sprint 9: pacote de entrevistas e evidências
**Entregas:** README PT/EN com diagrama C4, ADRs, gráfico de trade-offs, comparação custo ECS/EKS, métricas de throughput/p95, incidências, testes e vídeo de demo de 3–5 minutos; `portfolio_matrix.md` associando requisitos das vagas a caminhos/commits/comandos.  
**Aceite:** recrutador técnico consegue clonar e executar uma demo local sem cloud nem segredo; consegue verificar o que de fato foi executado na AWS e o que segue pendente.

## 6. Matriz de aderência às vagas
| Família de vagas | Provas concretas após o plano | Principal lacuna que atacamos |
|---|---|---|
| Data Engineer Databricks (Nava, migração, Alcateia, Asaas) | Spark+Delta real, CDC, reconciliação, data quality, lineage, RBAC, job orquestrado, benchmark; opcional workspace | Databricks cloud/Unity Catalog e performance reais |
| Cientista de Dados / ML Engineer AWS (automotivo, Claro) | RiskCredit→SageMaker/API, MLflow, drift, monitoramento, XGBoost, CloudWatch e custo | rollout/retrain cloud auditável e cenários DL específicos da vaga |
| AI Software Engineer / GenAI | RAG, tool calling, MCP, autorização, agentes, FastAPI, avaliação, tracing, prompt security | e2e operacional com credenciais e avaliação verificável |
| DBRE John Deere | Terraform PostgreSQL RDS, Flyway, restore, replicação, tuning, PITR, observabilidade, DMS opcional | administração real PG/RDS e migrar bases |
| Platform / DevOps AWS | Terraform, CI/CD OIDC, ECS/EKS, ArgoCD, IAM, Karpenter, WAF, Prometheus/Grafana, incidentes | deploy/rollback/falha/custo executados, não só arquivos IaC |
| Backend/event streaming (Cobli) | Kafka/RabbitMQ reais, contratos, CQRS, tracing, API, processamento de eventos | Kotlin/Spring é trilha opcional específica |
| GCP Data Platform / Data Fabric | padrões transferíveis de catálogo, ELT, governança, contratos, IaC | execução real em GCP/BigQuery quando prioritária |

## 7. Gates de qualidade e limites de escopo
- **Gate A (MVP):** Consumer→Delta→API→UI executável local, CI verde, reconciliação e status de evidência documentados. Não começar EKS antes disso.
- **Gate B (Data/DBRE):** Spark/Delta + PostgreSQL/Flyway com backup/restore e `EXPLAIN ANALYZE` mensurável; política de schema/contract e rollback.
- **Gate C (AI):** inferência ML e agente governado, logging sem PII, golden set, autorização/rollback testados.
- **Gate D (Cloud):** custo estimado aprovado, `plan` analisado, deploy efêmero, métricas e teardown comprovados. Sem risco de cobrança contínua desconhecida.
- **Gate E (Portfólio):** no mínimo duas demos independentes: `Data+ML+Agent` e `DBRE/Platform`; histórias de arquitetura e indicadores não fabricados.

**Não entram no P0:** Kubernetes inteiro, multicloud simultâneo, mobile .NET MAUI, processamento de vídeo embarcado, treinamento de LLM grande, migration Teradata real, serviços AWS de custo contínuo, cópia literal do código do curso, mais um repo genérico de Data/Cloud/ML.

## 8. Controles financeiros e segurança antes de AWS
1. Usar conta/ambiente de laboratório separado dos dados/projetos importantes, MFA e acesso federado/OIDC; nunca `AdministratorAccess` genérico nem chaves permanentes nos workflows.
2. Estimar o custo total do experimento na AWS Pricing Calculator, incluindo NAT Gateway, EKS control plane/nodes, EBS, LB, RDS, CloudWatch, data transfer, WAF, AMP/AMG, Glue e SageMaker. Sem valores estáticos de preços fora de fonte atual.
3. Etiquetar tudo e criar AWS Budgets + alertas +, quando útil, Budget Actions. **Um alerta não é um teto de cobrança.** Um bloqueio IAM não necessariamente para recursos já ativos.
4. Definir `ttl`, script de limpeza, inventory de recursos e checklist pós-teardown; proteger dados/snapshots importantes e não destruir sem revisão humana.
5. Em 2026, observar **CloudWatch Database Insights** para RDS (Performance Insights chegou ao fim de vida em julho/2026, conforme documentação AWS consultada em novembro/2026).
6. Para o material externo EKS Express: auditar `controller.resources.limits.cpu = "1Gi"` em `karpenter.release.tf` (aparenta troca de CPU por memória), `AdministratorAccess`, versões de providers, regras WAF e hardcoded ARN/roles antes de usar.

## 9. Estrutura sugerida, sem criar monorepo novo
**Argus:** manter dados, ML, agentes e governança; adicionar `integration/contracts`, `integration/demos`, `integration/adapters`, `docs/master-platform` (nomes a decidir conforme árvore existente).  
**Enterprise-Automation:** manter IaC, CI/CD e SRE; adicionar `terraform/modules/database-postgresql`, `stacks/aws-lite`, `stacks/aws-eks-lab`, `platform/observability`, `platform/finops`, `docs/runbooks` quando ausentes; alterações incrementais.  
**RiskCredit e Credit Score:** modelo/serving permanecem separados e conectados por manifesto versionado.  
**RetentIQ:** eventos/publicador e SaaS, sem duplicar Argus Lakehouse.  
**ThemisAI:** política/auditoria exposta por API ou biblioteca versionada, não importando o projeto inteiro no Argus.  
**OmniMind:** runtime agêntico intercambiável via APIs/MCP, sem acoplamento interno das classes.

## 10. Backlog operacional — primeira rodada recomendada
| ID | Prioridade | Ticket | Critério de pronto |
|---|---|---|---|
| MASTER-001 | P0 | Auditoria de README vs execução nos 7 repos principais | Matriz `REAL_LOCAL/AWS_REAL/VALIDADO/MOCK/PLANEJADO` com commit SHA |
| MASTER-002 | P0 | Contrato `customer_activity.v1` e exemplo determinístico | Contract tests em produtor e consumidor |
| MASTER-003 | P0 | Redpanda/Kafka→Spark/Delta pipeline integrado | Reprocessamento idempotente, CDC e reconciliação |
| MASTER-004 | P0 | Endpoint `/customer/insights` e demo de UI | Smoke e teste E2E no Compose |
| MASTER-005 | P0 | PostgreSQL local+Flyway+migrações | Ciclo up/migrate/rollback/rebuild testado |
| MASTER-006 | P0 | Performance SQL e backup/restore | Benchmark EXPLAIN e checksums pós-restore |
| MASTER-007 | P0 | Stack Terraform RDS PostgreSQL (sem apply) | fmt/validate e plano revisado |
| MASTER-008 | P1 | Manifesto RiskCredit→AWS serving | Paridade golden samples + assinatura e versionamento |
| MASTER-009 | P1 | Drift/registry/model release | Gate de promoção, bloqueio e rollback em teste |
| MASTER-010 | P1 | Agente MCP/RAG governado | AuthZ, grounding, injection tests e tracing real |
| MASTER-011 | P1 | ThemisAI policy gate | PII teste bloqueada/mascarada e auditoria verificável |
| MASTER-012 | P1 | Observabilidade OTel/Prom/Grafana | Dashboards SLI/API/Spark/Postgres, incidente demo |
| MASTER-013 | P1 | AWS OIDC + budget + etiquetas + cleanup | `terraform plan` e checklist de custos/teardown |
| MASTER-014 | P1 | Deploy AWS-LITE de 1 fluxo | Evidência do apply, e2e, métricas, destroy e custo |
| MASTER-015 | P2 | Pipeline ArgoCD/EKS em ambiente efêmero | GitOps e rollout testados |
| MASTER-016 | P2 | EKS autoscaling, ALB, WAF, monitoring | Teste de escala/falha e custo medido |
| MASTER-017 | P2 | Prova Databricks workspace real | Job Spark/Delta, Unity Catalog/ACL, governança |
| MASTER-018 | P0 | Pacote de portfólio e demos PT/EN | Scripts, ADRs e evidências com links GitHub |

**Fase de curso adquirido (quando arquivos chegarem):** inventariar módulos, laboratórios, código e licença; mapear cada aula → ticket MASTER; detectar duplicidade; apontar riscos de custo/versão; substituir padrões externos por implementação própria e teste; atualizar este blueprint para v0.2. Não esperar o curso para executar MASTER-001 a MASTER-007.

## 11. Fontes fundamentais
- [AWS EKS Pricing](https://aws.amazon.com/eks/pricing/)
- [Amazon RDS backup e restore](https://docs.aws.amazon.com/AmazonRDS/latest/gettingstartedguide/managing-backup-restore.html)
- [CloudWatch Database Insights](https://docs.aws.amazon.com/AmazonCloudWatch/latest/monitoring/Database-Insights.html)
- [AWS DMS PostgreSQL migration](https://docs.aws.amazon.com/dms/latest/userguide/dm-migrating-data-postgresql.html)
- [AWS Budgets actions](https://docs.aws.amazon.com/cost-management/latest/userguide/budgets-controls.html)
- Repositórios GitHub específicos listados na seção 1, inspecionados em 04/11/2026; status dos READMEs é evidência declarada pelo autor e não equivale a executar todos os testes nesta sessão.
