Fiz o script, rodei nas 9 aulas e montei o plano: PLANO_v0.2_Curso_DevOps_x_Repos_AWS_Free.md. O v0.1 continua intacto.

O script e a base de conhecimento
O script é o tools/course_kb/course_kb.py, com README. Ele transcreve o áudio com Whisper na GPU e lê a tela com OCR só quando ela muda, então captura o código digitado e a saída do terminal. Depois extrai serviços AWS, comandos, recursos Terraform e menções a custo, e compara tudo com os seus repos. Serve para outros cursos também.
Rodou nas 9 aulas (11h57 de vídeo) em cerca de 1h30 de transcrição e 2h20 de OCR, em paralelo e de graça. Saíram ~84 mil palavras e 1.054 telas lidas.
A base fica em Q:\Cursos Pagos\DevOps na Nuvem ( )\_kb\. Comece pelo KNOWLEDGE.md (índice do curso), COVERAGE.md (comparação com os repos) e o lesson.md de cada aula. Fica privada, porque é material de curso pago.
Os IDs de conta AWS que aparecem na tela foram mascarados.
O que o curso ensina × o que você já tem
80 de 108 termos do curso já aparecem em algum repo seu. 18 só existem no material do curso, entre eles Kustomize, add-ons e access entries do EKS, ECR, scraper do AMP, flow logs e Karpenter.
"Aparece" muitas vezes é só documentação. No Enterprise, EKS e ArgoCD estão apenas em ADR, sem código.
O ArgusAI já tem um módulo EKS mínimo e um módulo de rede que duplica o do Enterprise. Recomendo levar esse módulo para o Enterprise, completá-lo com o que o curso ensina e fazer o Argus usá-lo, em vez de manter duas cópias.
O meu-projeto-aws (Lambda, API Gateway, SageMaker) complementa o curso sem sobreposição.
O curso não cobre dados e ML. Essas partes do v0.1 continuam locais.
AWS de graça: o que encontrei
Os dados precisam ficar fora da AWS. Quando o Free Plan acaba (05/05/2027 ou quando os créditos zerarem), a conta fecha e tudo é apagado depois de 90 dias. O plano deixa na AWS só máquinas temporárias e guarda o resto no GitHub, GHCR, Cloudflare R2 e Supabase/Neon/Atlas, que você já usa.
O custo é viável. O próprio instrutor diz que os alunos gastam US$ 10–15/mês subindo e derrubando o ambiente todo dia. Minha estimativa é de US$ 1–1,20 por sessão de 4h com EKS. Os seus US$ 100 cobrem o curso, e dá para ganhar mais US$ 100 com 5 atividades simples.
Três coisas do curso quebrariam o seu R$ 0:
Não faça as aulas 05/06 como gravadas. O Grafana gerenciado com login pelo Identity Center ativa o AWS Organizations, e isso converte o Free Plan em pago sem volta. O instrutor fez dentro da organização dele. No plano, troquei por um Grafana instalado por você, lendo as métricas do AMP.
Use 1 NAT Gateway ou nenhum, não 3. A arquitetura que o agente gerou no Dia 1 dava cerca de US$ 65/mês só de rede.
Pule Route 53, ACM e external-dns se você não tiver um domínio próprio, porque zona e domínio são pagos.
Ordem do plano: primeiro os limites de gasto e as atividades de crédito. Depois tudo do Dia 2 em Kubernetes local (custo zero). Então Terraform base, uma primeira sessão real só com a rede, uma sessão com EKS e GitOps, e por fim observabilidade.
Preciso de você em três pontos
Abra os consoles do EKS e do Prometheus na sua conta e me diga se aparecem bloqueados no Free Plan. Não achei lista oficial, e isso define as fases com EKS.
Para o estado do Terraform, recomendo o padrão do curso (bucket S3 na própria AWS). Como tudo é destruído no fim de cada sessão, perder esse bucket não custa nada. A alternativa é o HCP Terraform gratuito. Qual prefere?
Quando quiser, autorize a primeira sessão real (só a rede, menos de US$ 0,50 de crédito).
Se quiser, transformo o plano numa página para compartilhar.

Fontes:

AWS — Choosing a plan (Free × Paid)
AWS Builder Center — The $0 AWS account in 2026
Amazon Managed Grafana — IAM Identity Center
Amazon Managed Grafana — AWS Organizations
HashiCorp — HCP Terraform enhanced free tier
Cloudflare R2