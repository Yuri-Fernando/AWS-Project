# Inventário dos recursos que existiram na AWS real

Gerado por `tools/real_inventory.py` em 2026-11-12 a partir dos states locais do Terraform (snapshot de antes do `destroy`). ID da conta, IDs IAM, e-mails e IPs públicos mascarados; atributos sensíveis nunca são copiados. Todos estes recursos foram **destruídos** em 11/11/2026, exceto a R0 (roles, policy e budgets, sem custo).

| Sessão | Recursos | Snapshot |
|---|---|---|
| R0 — identidade, guardrails de custo e Pod Identity (`platform/terraform/06-identity`) | 19 | `06-identity-aws.tfstate.backup` |
| R1 — rede (`platform/terraform/01-networking`) | 23 | `01-networking-aws.tfstate.backup` |
| R2 — EKS e ECR (`platform/terraform/02-eks`) | 27 | `02-eks-aws.tfstate.backup` |
| R4 — Credit Score serverless (repo `meu-projeto-aws/infra/terraform`) | 30 | `r4-creditscore-aws.tfstate.backup` |
| **Total** | **99** | |

## R0 — identidade, guardrails de custo e Pod Identity (`platform/terraform/06-identity`)

Fonte: `platform/.state/06-identity-aws.tfstate.backup` · 19 recursos

| Recurso (endereço Terraform) | Tipo | Configuração relevante |
|---|---|---|
| `aws_budgets_budget.monthly` | `aws_budgets_budget` | `name`=argus-platform-lab-monthly · `limit_amount`=5.0 · `limit_unit`=USD · `time_unit`=MONTHLY · `budget_type`=COST |
| `aws_budgets_budget.zero_spend` | `aws_budgets_budget` | `name`=argus-platform-lab-zero-spend · `limit_amount`=0.01 · `limit_unit`=USD · `time_unit`=MONTHLY · `budget_type`=COST |
| `aws_eks_pod_identity_association.workload["argus-api"]` | `aws_eks_pod_identity_association` | `cluster_name`=argus-platform-lab-eks · `namespace`=ecosystem · `service_account`=argus-api |
| `aws_eks_pod_identity_association.workload["creditscore-app"]` | `aws_eks_pod_identity_association` | `cluster_name`=argus-platform-lab-eks · `namespace`=ecosystem · `service_account`=creditscore-app |
| `aws_eks_pod_identity_association.workload["riskcredit-train"]` | `aws_eks_pod_identity_association` | `cluster_name`=argus-platform-lab-eks · `namespace`=ecosystem · `service_account`=riskcredit-train |
| `aws_iam_policy.free_plan_guard` | `aws_iam_policy` | `name`=argus-platform-lab-free-plan-guard · `description`=Nega ações que convertem o Free Plan em pago (Organizations, Control Tower, Managed Grafana/Identity Center) ou compr… |
| `aws_iam_role.deployer` | `aws_iam_role` | `name`=argus-platform-lab-deployer · `max_session_duration`=14400 |
| `aws_iam_role.mcp_readonly` | `aws_iam_role` | `name`=argus-platform-lab-mcp-readonly · `max_session_duration`=3600 |
| `aws_iam_role.workload["argus-api"]` | `aws_iam_role` | `name`=argus-platform-lab-wl-argus-api · `max_session_duration`=3600 |
| `aws_iam_role.workload["creditscore-app"]` | `aws_iam_role` | `name`=argus-platform-lab-wl-creditscore-app · `max_session_duration`=3600 |
| `aws_iam_role.workload["riskcredit-train"]` | `aws_iam_role` | `name`=argus-platform-lab-wl-riskcredit-train · `max_session_duration`=3600 |
| `aws_iam_role_policy.deployer_iam_scoped` | `aws_iam_role_policy` | `name`=iam-scoped-to-project · `role`=argus-platform-lab-deployer |
| `aws_iam_role_policy.workload["argus-api"]` | `aws_iam_role_policy` | `name`=s3-minimo · `role`=argus-platform-lab-wl-argus-api |
| `aws_iam_role_policy.workload["creditscore-app"]` | `aws_iam_role_policy` | `name`=s3-minimo · `role`=argus-platform-lab-wl-creditscore-app |
| `aws_iam_role_policy.workload["riskcredit-train"]` | `aws_iam_role_policy` | `name`=s3-minimo · `role`=argus-platform-lab-wl-riskcredit-train |
| `aws_iam_role_policy_attachment.deployer["guard"]` | `aws_iam_role_policy_attachment` | `role`=argus-platform-lab-deployer · `policy_arn`=arn:aws:iam::<conta>:policy/argus-platform-lab-free-plan-guard |
| `aws_iam_role_policy_attachment.deployer["power"]` | `aws_iam_role_policy_attachment` | `role`=argus-platform-lab-deployer · `policy_arn`=arn:aws:iam::aws:policy/PowerUserAccess |
| `aws_iam_role_policy_attachment.mcp_readonly["guard"]` | `aws_iam_role_policy_attachment` | `role`=argus-platform-lab-mcp-readonly · `policy_arn`=arn:aws:iam::<conta>:policy/argus-platform-lab-free-plan-guard |
| `aws_iam_role_policy_attachment.mcp_readonly["read"]` | `aws_iam_role_policy_attachment` | `role`=argus-platform-lab-mcp-readonly · `policy_arn`=arn:aws:iam::aws:policy/ReadOnlyAccess |

## R1 — rede (`platform/terraform/01-networking`)

Fonte: `platform/.state/01-networking-aws.tfstate.backup` · 23 recursos

| Recurso (endereço Terraform) | Tipo | Configuração relevante |
|---|---|---|
| `aws_cloudwatch_log_group.flow_logs[0]` | `aws_cloudwatch_log_group` | `name`=/vpc/argus-platform-lab/flow-logs · `retention_in_days`=7 |
| `aws_flow_log.this[0]` | `aws_flow_log` | `traffic_type`=ALL · `log_destination_type`=cloud-watch-logs |
| `aws_iam_role.flow_logs[0]` | `aws_iam_role` | `name`=argus-platform-lab-vpc-flow-logs · `max_session_duration`=3600 |
| `aws_iam_role_policy.flow_logs[0]` | `aws_iam_role_policy` | `name`=write-flow-logs · `role`=argus-platform-lab-vpc-flow-logs |
| `module.networking.aws_internet_gateway.this` | `aws_internet_gateway` | `tags`={"Name":"argus-platform-lab-igw"} |
| `module.networking.aws_route.public_internet` | `aws_route` |  |
| `module.networking.aws_route_table.private[0]` | `aws_route_table` | `tags`={"Name":"argus-platform-lab-private-rt-us-east-1a"} |
| `module.networking.aws_route_table.private[1]` | `aws_route_table` | `tags`={"Name":"argus-platform-lab-private-rt-us-east-1b"} |
| `module.networking.aws_route_table.private[2]` | `aws_route_table` | `tags`={"Name":"argus-platform-lab-private-rt-us-east-1c"} |
| `module.networking.aws_route_table.public` | `aws_route_table` | `tags`={"Name":"argus-platform-lab-public-rt"} |
| `module.networking.aws_route_table_association.private[0]` | `aws_route_table_association` |  |
| `module.networking.aws_route_table_association.private[1]` | `aws_route_table_association` |  |
| `module.networking.aws_route_table_association.private[2]` | `aws_route_table_association` |  |
| `module.networking.aws_route_table_association.public[0]` | `aws_route_table_association` |  |
| `module.networking.aws_route_table_association.public[1]` | `aws_route_table_association` |  |
| `module.networking.aws_route_table_association.public[2]` | `aws_route_table_association` |  |
| `module.networking.aws_subnet.private[0]` | `aws_subnet` | `cidr_block`=10.20.128.0/20 · `availability_zone`=us-east-1a · `map_public_ip_on_launch`=False · `tags`={"Name":"argus-platform-lab-private-us-east-1a","Tier":"private"} |
| `module.networking.aws_subnet.private[1]` | `aws_subnet` | `cidr_block`=10.20.144.0/20 · `availability_zone`=us-east-1b · `map_public_ip_on_launch`=False · `tags`={"Name":"argus-platform-lab-private-us-east-1b","Tier":"private"} |
| `module.networking.aws_subnet.private[2]` | `aws_subnet` | `cidr_block`=10.20.160.0/20 · `availability_zone`=us-east-1c · `map_public_ip_on_launch`=False · `tags`={"Name":"argus-platform-lab-private-us-east-1c","Tier":"private"} |
| `module.networking.aws_subnet.public[0]` | `aws_subnet` | `cidr_block`=10.20.0.0/20 · `availability_zone`=us-east-1a · `map_public_ip_on_launch`=True · `tags`={"Name":"argus-platform-lab-public-us-east-1a","Tier":"public"} |
| `module.networking.aws_subnet.public[1]` | `aws_subnet` | `cidr_block`=10.20.16.0/20 · `availability_zone`=us-east-1b · `map_public_ip_on_launch`=True · `tags`={"Name":"argus-platform-lab-public-us-east-1b","Tier":"public"} |
| `module.networking.aws_subnet.public[2]` | `aws_subnet` | `cidr_block`=10.20.32.0/20 · `availability_zone`=us-east-1c · `map_public_ip_on_launch`=True · `tags`={"Name":"argus-platform-lab-public-us-east-1c","Tier":"public"} |
| `module.networking.aws_vpc.this` | `aws_vpc` | `cidr_block`=10.20.0.0/16 · `tags`={"Name":"argus-platform-lab-vpc"} |

## R2 — EKS e ECR (`platform/terraform/02-eks`)

Fonte: `platform/.state/02-eks-aws.tfstate.backup` · 27 recursos

| Recurso (endereço Terraform) | Tipo | Configuração relevante |
|---|---|---|
| `aws_ecr_lifecycle_policy.this["argus-api"]` | `aws_ecr_lifecycle_policy` |  |
| `aws_ecr_lifecycle_policy.this["churn-api"]` | `aws_ecr_lifecycle_policy` |  |
| `aws_ecr_lifecycle_policy.this["creditscore-app"]` | `aws_ecr_lifecycle_policy` |  |
| `aws_ecr_lifecycle_policy.this["omnimind-api"]` | `aws_ecr_lifecycle_policy` |  |
| `aws_ecr_lifecycle_policy.this["retentiq-api"]` | `aws_ecr_lifecycle_policy` |  |
| `aws_ecr_lifecycle_policy.this["riskcredit-train"]` | `aws_ecr_lifecycle_policy` |  |
| `aws_ecr_lifecycle_policy.this["themis-api"]` | `aws_ecr_lifecycle_policy` |  |
| `aws_ecr_repository.this["argus-api"]` | `aws_ecr_repository` | `name`=argus-platform/argus-api · `image_tag_mutability`=MUTABLE · `image_scanning_configuration`=[{"scan_on_push":true}] |
| `aws_ecr_repository.this["churn-api"]` | `aws_ecr_repository` | `name`=argus-platform/churn-api · `image_tag_mutability`=MUTABLE · `image_scanning_configuration`=[{"scan_on_push":true}] |
| `aws_ecr_repository.this["creditscore-app"]` | `aws_ecr_repository` | `name`=argus-platform/creditscore-app · `image_tag_mutability`=MUTABLE · `image_scanning_configuration`=[{"scan_on_push":true}] |
| `aws_ecr_repository.this["omnimind-api"]` | `aws_ecr_repository` | `name`=argus-platform/omnimind-api · `image_tag_mutability`=MUTABLE · `image_scanning_configuration`=[{"scan_on_push":true}] |
| `aws_ecr_repository.this["retentiq-api"]` | `aws_ecr_repository` | `name`=argus-platform/retentiq-api · `image_tag_mutability`=MUTABLE · `image_scanning_configuration`=[{"scan_on_push":true}] |
| `aws_ecr_repository.this["riskcredit-train"]` | `aws_ecr_repository` | `name`=argus-platform/riskcredit-train · `image_tag_mutability`=MUTABLE · `image_scanning_configuration`=[{"scan_on_push":true}] |
| `aws_ecr_repository.this["themis-api"]` | `aws_ecr_repository` | `name`=argus-platform/themis-api · `image_tag_mutability`=MUTABLE · `image_scanning_configuration`=[{"scan_on_push":true}] |
| `module.eks.aws_eks_addon.this["coredns"]` | `aws_eks_addon` | `cluster_name`=argus-platform-lab-eks · `addon_name`=coredns · `addon_version`=v1.12.4-eksbuild.82 |
| `module.eks.aws_eks_addon.this["eks-pod-identity-agent"]` | `aws_eks_addon` | `cluster_name`=argus-platform-lab-eks · `addon_name`=eks-pod-identity-agent · `addon_version`=v1.4.1-eksbuild.3 |
| `module.eks.aws_eks_addon.this["kube-proxy"]` | `aws_eks_addon` | `cluster_name`=argus-platform-lab-eks · `addon_name`=kube-proxy · `addon_version`=v1.33.10-eksbuild.69 |
| `module.eks.aws_eks_addon.this["vpc-cni"]` | `aws_eks_addon` | `cluster_name`=argus-platform-lab-eks · `addon_name`=vpc-cni · `addon_version`=v1.22.4-eksbuild.14 |
| `module.eks.aws_eks_cluster.this` | `aws_eks_cluster` | `name`=argus-platform-lab-eks · `version`=1.33 · `platform_version`=eks.51 · `status`=ACTIVE · `vpc_config`=[{"cluster_security_group_id":"sg-0159df397d3a81d7b","control_plane_egress_mode":"AWS_MANAGED","endpoint_private_acce… |
| `module.eks.aws_eks_node_group.default` | `aws_eks_node_group` | `cluster_name`=argus-platform-lab-eks · `node_group_name`=argus-platform-lab-eks-default · `version`=1.33 · `instance_types`=["c7i-flex.large"] · `capacity_type`=SPOT · `ami_type`=AL2023_x86_64_STANDARD · `disk_size`=20 · `scaling_config`=[{"desired_size":2,"max_size":3,"min_size":1}] · `status`=ACTIVE |
| `module.eks.aws_iam_openid_connect_provider.irsa[0]` | `aws_iam_openid_connect_provider` |  |
| `module.eks.aws_iam_role.cluster` | `aws_iam_role` | `name`=argus-platform-lab-eks-eks-cluster · `max_session_duration`=3600 |
| `module.eks.aws_iam_role.node` | `aws_iam_role` | `name`=argus-platform-lab-eks-eks-node · `max_session_duration`=3600 |
| `module.eks.aws_iam_role_policy_attachment.cluster["AmazonEKSClusterPolicy"]` | `aws_iam_role_policy_attachment` | `role`=argus-platform-lab-eks-eks-cluster · `policy_arn`=arn:aws:iam::aws:policy/AmazonEKSClusterPolicy |
| `module.eks.aws_iam_role_policy_attachment.node["AmazonEC2ContainerRegistryReadOnly"]` | `aws_iam_role_policy_attachment` | `role`=argus-platform-lab-eks-eks-node · `policy_arn`=arn:aws:iam::aws:policy/AmazonEC2ContainerRegistryReadOnly |
| `module.eks.aws_iam_role_policy_attachment.node["AmazonEKSWorkerNodePolicy"]` | `aws_iam_role_policy_attachment` | `role`=argus-platform-lab-eks-eks-node · `policy_arn`=arn:aws:iam::aws:policy/AmazonEKSWorkerNodePolicy |
| `module.eks.aws_iam_role_policy_attachment.node["AmazonEKS_CNI_Policy"]` | `aws_iam_role_policy_attachment` | `role`=argus-platform-lab-eks-eks-node · `policy_arn`=arn:aws:iam::aws:policy/AmazonEKS_CNI_Policy |

## R4 — Credit Score serverless (repo `meu-projeto-aws/infra/terraform`)

Fonte: `platform/.state/r4-creditscore-aws.tfstate.backup` · 30 recursos

| Recurso (endereço Terraform) | Tipo | Configuração relevante |
|---|---|---|
| `aws_apigatewayv2_api.http` | `aws_apigatewayv2_api` | `name`=credit-score-lab-api · `protocol_type`=HTTP |
| `aws_apigatewayv2_authorizer.jwt` | `aws_apigatewayv2_authorizer` | `name`=cognito |
| `aws_apigatewayv2_integration.lambda` | `aws_apigatewayv2_integration` |  |
| `aws_apigatewayv2_route.predict` | `aws_apigatewayv2_route` | `route_key`=POST /predict |
| `aws_apigatewayv2_stage.default` | `aws_apigatewayv2_stage` | `name`=$default |
| `aws_budgets_budget.monthly` | `aws_budgets_budget` | `name`=credit-score-lab-monthly-budget · `limit_amount`=10.0 · `limit_unit`=USD · `time_unit`=MONTHLY · `budget_type`=COST |
| `aws_cloudwatch_dashboard.main` | `aws_cloudwatch_dashboard` | `dashboard_name`=credit-score-lab-operacional |
| `aws_cloudwatch_log_group.api` | `aws_cloudwatch_log_group` | `name`=/aws/apigateway/credit-score-lab · `retention_in_days`=1 |
| `aws_cloudwatch_log_group.lambda` | `aws_cloudwatch_log_group` | `name`=/aws/lambda/credit-score-lab-predict · `retention_in_days`=1 |
| `aws_cloudwatch_metric_alarm.api_5xx` | `aws_cloudwatch_metric_alarm` | `namespace`=AWS/ApiGateway · `comparison_operator`=GreaterThanOrEqualToThreshold · `threshold`=1 · `metric_name`=5xx |
| `aws_cloudwatch_metric_alarm.lambda_errors` | `aws_cloudwatch_metric_alarm` | `namespace`=AWS/Lambda · `comparison_operator`=GreaterThanThreshold · `threshold`=5 · `metric_name`=Errors |
| `aws_cloudwatch_metric_alarm.lambda_p95` | `aws_cloudwatch_metric_alarm` | `namespace`=AWS/Lambda · `comparison_operator`=GreaterThanThreshold · `threshold`=300 · `metric_name`=Duration |
| `aws_cloudwatch_metric_alarm.lambda_throttles` | `aws_cloudwatch_metric_alarm` | `namespace`=AWS/Lambda · `comparison_operator`=GreaterThanThreshold · `threshold`=0 · `metric_name`=Throttles |
| `aws_cognito_user_pool.main` | `aws_cognito_user_pool` | `name`=credit-score-lab-users · `mfa_configuration`=OPTIONAL |
| `aws_cognito_user_pool_client.api` | `aws_cognito_user_pool_client` | `name`=credit-score-lab-api |
| `aws_dynamodb_table.inference` | `aws_dynamodb_table` | `name`=credit-score-lab-inference-log · `billing_mode`=PAY_PER_REQUEST · `hash_key`=request_id · `point_in_time_recovery`=[{"enabled":true,"recovery_period_in_days":35}] |
| `aws_iam_role.lambda` | `aws_iam_role` | `name`=credit-score-lab-lambda · `max_session_duration`=3600 |
| `aws_iam_role.sagemaker` | `aws_iam_role` | `name`=credit-score-lab-sagemaker · `max_session_duration`=3600 |
| `aws_iam_role_policy.lambda` | `aws_iam_role_policy` | `name`=terraform-20261111194801296100000001 · `role`=credit-score-lab-lambda |
| `aws_iam_role_policy.sagemaker` | `aws_iam_role_policy` | `name`=terraform-20261111194556916900000001 · `role`=credit-score-lab-sagemaker |
| `aws_kms_alias.main` | `aws_kms_alias` | `name`=alias/credit-score-lab |
| `aws_kms_key.main` | `aws_kms_key` | `enable_key_rotation`=True · `deletion_window_in_days`=7 · `description`=credit-score-lab — dados de inferência, artefatos e logs |
| `aws_lambda_function.predict` | `aws_lambda_function` | `function_name`=credit-score-lab-predict · `role`=arn:aws:iam::<conta>:role/credit-score-lab-lambda · `version`=$LATEST · `runtime`=python3.11 · `handler`=Nuvem.lambda_function_v3.lambda_handler · `memory_size`=1024 · `timeout`=10 · `reserved_concurrent_executions`=-1 |
| `aws_lambda_permission.api` | `aws_lambda_permission` | `function_name`=credit-score-lab-predict |
| `aws_s3_bucket.artifacts` | `aws_s3_bucket` | `bucket`=credit-score-lab-artifacts-<conta> |
| `aws_s3_bucket_public_access_block.artifacts` | `aws_s3_bucket_public_access_block` | `bucket`=credit-score-lab-artifacts-<conta> |
| `aws_s3_bucket_server_side_encryption_configuration.artifacts` | `aws_s3_bucket_server_side_encryption_configuration` | `bucket`=credit-score-lab-artifacts-<conta> |
| `aws_s3_bucket_versioning.artifacts` | `aws_s3_bucket_versioning` | `bucket`=credit-score-lab-artifacts-<conta> |
| `aws_sagemaker_model_package_group.pd` | `aws_sagemaker_model_package_group` |  |
| `aws_sns_topic.alarms` | `aws_sns_topic` | `name`=credit-score-lab-alarms |
