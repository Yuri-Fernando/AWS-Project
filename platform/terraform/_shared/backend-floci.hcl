# Configuração parcial do backend S3 para o alvo floci (terraform init -backend-config=...).
# A chave (key) é passada pelo Makefile: -backend-config="key=<stack>.tfstate".
bucket                      = "argus-platform-lab-tfstate"
region                      = "us-east-1"
access_key                  = "test"
secret_key                  = "test"
skip_credentials_validation = true
skip_requesting_account_id  = true
skip_region_validation      = true
use_path_style              = true
use_lockfile                = true
endpoints = {
  s3  = "http://localhost.floci.io:4566"
  sts = "http://localhost.floci.io:4566"
}
