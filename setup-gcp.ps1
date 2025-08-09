# Setup GCP Infrastructure para Sistema de Detecção de Desvios - Sentinela BD
# Script de configuração completa do ambiente GCP
# Execute: PowerShell -ExecutionPolicy Bypass -File .\setup-gcp.ps1

param(
    [string]$ProjectId = "sz-wsp-00009",
    [string]$Region = "us-central1",
    [string]$ServiceName = "sentinela-detection",
    [string]$DatasetId = "sentinela_bd"
)

Write-Host "🚛 SETUP GCP - SISTEMA SENTINELA BD" -ForegroundColor Green
Write-Host "=" * 50
Write-Host "Projeto: $ProjectId"
Write-Host "Região: $Region" 
Write-Host "Serviço: $ServiceName"
Write-Host "Dataset: $DatasetId"
Write-Host ""

# Função para verificar se comando existe
function Test-Command($command) {
    try {
        Get-Command $command -ErrorAction Stop
        return $true
    }
    catch {
        return $false
    }
}

# Verificar dependências
Write-Host "🔍 Verificando dependências..." -ForegroundColor Yellow

if (-not (Test-Command "gcloud")) {
    Write-Error "❌ Google Cloud CLI não encontrado! Instale: https://cloud.google.com/sdk/docs/install"
    exit 1
}

if (-not (Test-Command "terraform")) {
    Write-Warning "⚠️ Terraform não encontrado. Algumas funcionalidades não estarão disponíveis."
}

# Configurar projeto
Write-Host "⚙️ Configurando projeto GCP..." -ForegroundColor Yellow
gcloud config set project $ProjectId
gcloud config set compute/region $Region

if ($LASTEXITCODE -ne 0) {
    Write-Error "❌ Erro ao configurar projeto. Verifique se você tem acesso ao projeto $ProjectId"
    exit 1
}

# Habilitar APIs necessárias
Write-Host "🔌 Habilitando APIs necessárias..." -ForegroundColor Yellow

$APIs = @(
    "run.googleapis.com",
    "cloudscheduler.googleapis.com",
    "bigquery.googleapis.com", 
    "monitoring.googleapis.com",
    "logging.googleapis.com",
    "secretmanager.googleapis.com",
    "cloudbuild.googleapis.com",
    "artifactregistry.googleapis.com"
)

foreach ($api in $APIs) {
    Write-Host "  Habilitando $api..." -ForegroundColor Gray
    gcloud services enable $api --quiet
    
    if ($LASTEXITCODE -ne 0) {
        Write-Warning "⚠️ Falha ao habilitar $api - continuando..."
    }
}

# Criar Service Account
Write-Host "👤 Criando Service Account..." -ForegroundColor Yellow

$ServiceAccountName = "sentinela-detection-sa"
$ServiceAccountEmail = "$ServiceAccountName@$ProjectId.iam.gserviceaccount.com"

# Verificar se já existe
$existing = gcloud iam service-accounts list --filter="email:$ServiceAccountEmail" --format="value(email)" --quiet

if (-not $existing) {
    gcloud iam service-accounts create $ServiceAccountName `
        --display-name="Sentinela Detection Service Account" `
        --description="Service Account para sistema de detecção de desvios" `
        --quiet
        
    if ($LASTEXITCODE -eq 0) {
        Write-Host "✅ Service Account criada: $ServiceAccountEmail" -ForegroundColor Green
    } else {
        Write-Error "❌ Erro ao criar Service Account"
        exit 1
    }
} else {
    Write-Host "ℹ️ Service Account já existe: $ServiceAccountEmail" -ForegroundColor Blue
}

# Atribuir roles necessários
Write-Host "🔐 Configurando permissões IAM..." -ForegroundColor Yellow

$Roles = @(
    "roles/bigquery.dataEditor",
    "roles/bigquery.jobUser",
    "roles/monitoring.metricWriter", 
    "roles/logging.logWriter",
    "roles/secretmanager.secretAccessor"
)

foreach ($role in $Roles) {
    Write-Host "  Atribuindo $role..." -ForegroundColor Gray
    gcloud projects add-iam-policy-binding $ProjectId `
        --member="serviceAccount:$ServiceAccountEmail" `
        --role=$role `
        --quiet
        
    if ($LASTEXITCODE -ne 0) {
        Write-Warning "⚠️ Falha ao atribuir role $role - continuando..."
    }
}

# Criar BigQuery Dataset
Write-Host "📊 Configurando BigQuery Dataset..." -ForegroundColor Yellow

# Verificar se dataset existe
$existingDataset = gcloud alpha bq datasets list --filter="datasetId:$DatasetId" --format="value(datasetId)" --quiet 2>$null

if (-not $existingDataset) {
    gcloud alpha bq datasets create $DatasetId `
        --location=US `
        --description="Dataset para sistema de detecção de desvios Sentinela BD" `
        --default-table-expiration=31536000 `
        --quiet
        
    if ($LASTEXITCODE -eq 0) {
        Write-Host "✅ Dataset criado: $DatasetId" -ForegroundColor Green
    } else {
        Write-Warning "⚠️ Erro ao criar dataset - pode já existir"
    }
} else {
    Write-Host "ℹ️ Dataset já existe: $DatasetId" -ForegroundColor Blue
}

# Criar tabelas BigQuery
Write-Host "🗃️ Criando tabelas BigQuery..." -ForegroundColor Yellow

# Executar script SQL das tabelas
if (Test-Path "bigquery_schemas.sql") {
    Write-Host "  Executando schemas SQL..." -ForegroundColor Gray
    
    # Dividir o arquivo SQL em comandos individuais e executar cada um
    $sqlContent = Get-Content "bigquery_schemas.sql" -Raw
    $commands = $sqlContent -split ";\s*(?=CREATE|PARTITION)"
    
    foreach ($command in $commands) {
        if ($command.Trim() -and $command.Trim() -match "^CREATE") {
            $tempFile = [System.IO.Path]::GetTempFileName()
            $command | Out-File -FilePath $tempFile -Encoding UTF8
            
            gcloud alpha bq query --use_legacy_sql=false --format=none --quiet < $tempFile
            Remove-Item $tempFile -Force
        }
    }
    
    Write-Host "✅ Tabelas BigQuery configuradas" -ForegroundColor Green
} else {
    Write-Warning "⚠️ Arquivo bigquery_schemas.sql não encontrado - pule a criação manual das tabelas"
}

# Criar Secret Manager para credenciais da API
Write-Host "🔒 Configurando Secret Manager..." -ForegroundColor Yellow

$SecretName = "frotalog-api-credentials"

# Verificar se secret existe
$existingSecret = gcloud secrets list --filter="name:projects/$ProjectId/secrets/$SecretName" --format="value(name)" --quiet 2>$null

if (-not $existingSecret) {
    # Criar secret
    gcloud secrets create $SecretName --replication-policy="automatic" --quiet
    
    if ($LASTEXITCODE -eq 0) {
        # Criar versão com credenciais (placeholder)
        $credentials = @{
            client_id = "56963"
            client_secret = "1MSiBaH879w="
        } | ConvertTo-Json
        
        $credentials | gcloud secrets versions add $SecretName --data-file=- --quiet
        
        Write-Host "✅ Secret criado: $SecretName" -ForegroundColor Green
        Write-Host "ℹ️ Atualize as credenciais reais posteriormente" -ForegroundColor Blue
    } else {
        Write-Warning "⚠️ Erro ao criar secret"
    }
} else {
    Write-Host "ℹ️ Secret já existe: $SecretName" -ForegroundColor Blue
}

# Configurar Artifact Registry (para imagens Docker)
Write-Host "📦 Configurando Artifact Registry..." -ForegroundColor Yellow

$RepoName = "sentinela-images"

# Verificar se repositório existe
$existingRepo = gcloud artifacts repositories list --location=$Region --filter="name:projects/$ProjectId/locations/$Region/repositories/$RepoName" --format="value(name)" --quiet 2>$null

if (-not $existingRepo) {
    gcloud artifacts repositories create $RepoName `
        --location=$Region `
        --repository-format=docker `
        --description="Repositório de imagens Docker para Sentinela BD" `
        --quiet
        
    if ($LASTEXITCODE -eq 0) {
        Write-Host "✅ Artifact Registry criado: $RepoName" -ForegroundColor Green
        
        # Configurar autenticação Docker
        gcloud auth configure-docker "$Region-docker.pkg.dev" --quiet
    } else {
        Write-Warning "⚠️ Erro ao criar Artifact Registry"
    }
} else {
    Write-Host "ℹ️ Artifact Registry já existe: $RepoName" -ForegroundColor Blue
}

# Criar bucket para Terraform state (se usando Terraform)
if (Test-Command "terraform") {
    Write-Host "🏗️ Configurando Terraform backend..." -ForegroundColor Yellow
    
    $TerraformBucket = "$ProjectId-terraform-state"
    
    # Verificar se bucket existe
    $existingBucket = gsutil ls -b "gs://$TerraformBucket" 2>$null
    
    if ($LASTEXITCODE -ne 0) {
        gsutil mb -l $Region "gs://$TerraformBucket"
        
        if ($LASTEXITCODE -eq 0) {
            # Habilitar versionamento
            gsutil versioning set on "gs://$TerraformBucket"
            Write-Host "✅ Bucket Terraform criado: $TerraformBucket" -ForegroundColor Green
        } else {
            Write-Warning "⚠️ Erro ao criar bucket Terraform"
        }
    } else {
        Write-Host "ℹ️ Bucket Terraform já existe: $TerraformBucket" -ForegroundColor Blue
    }
}

# Criar arquivo de configuração local
Write-Host "📄 Criando arquivo de configuração local..." -ForegroundColor Yellow

$configContent = @"
# Configuração GCP para Sentinela BD
# Gerado automaticamente em $(Get-Date -Format "yyyy-MM-dd HH:mm:ss")

GCP_PROJECT_ID=$ProjectId
GCP_REGION=$Region
GCP_SERVICE_NAME=$ServiceName
BIGQUERY_DATASET=$DatasetId
SERVICE_ACCOUNT_EMAIL=$ServiceAccountEmail
ARTIFACT_REGISTRY_URL=$Region-docker.pkg.dev/$ProjectId/sentinela-images

# URLs úteis
CLOUD_CONSOLE=https://console.cloud.google.com/home/dashboard?project=$ProjectId
BIGQUERY_CONSOLE=https://console.cloud.google.com/bigquery?project=$ProjectId
CLOUD_RUN_CONSOLE=https://console.cloud.google.com/run?project=$ProjectId
MONITORING_CONSOLE=https://console.cloud.google.com/monitoring?project=$ProjectId
"@

$configContent | Out-File -FilePath ".env.gcp" -Encoding UTF8

Write-Host ""
Write-Host "🎉 SETUP CONCLUÍDO COM SUCESSO!" -ForegroundColor Green
Write-Host "=" * 50

Write-Host ""
Write-Host "📋 RECURSOS CRIADOS:" -ForegroundColor Yellow
Write-Host "  ✅ APIs habilitadas"
Write-Host "  ✅ Service Account: $ServiceAccountEmail"
Write-Host "  ✅ BigQuery Dataset: $DatasetId"  
Write-Host "  ✅ Secret Manager: $SecretName"
Write-Host "  ✅ Artifact Registry: $RepoName"
Write-Host "  ✅ Configuração salva: .env.gcp"

Write-Host ""
Write-Host "🚀 PRÓXIMOS PASSOS:" -ForegroundColor Cyan
Write-Host "  1. Execute o deploy: .\deploy-sentinela.ps1"
Write-Host "  2. Configure o Cloud Scheduler após deploy"
Write-Host "  3. Configure monitoramento e alertas"
Write-Host "  4. Teste o sistema: POST /execute"

Write-Host ""
Write-Host "🔗 LINKS ÚTEIS:" -ForegroundColor Blue
Write-Host "  Cloud Console: https://console.cloud.google.com/home/dashboard?project=$ProjectId"
Write-Host "  BigQuery: https://console.cloud.google.com/bigquery?project=$ProjectId"
Write-Host "  Cloud Run: https://console.cloud.google.com/run?project=$ProjectId"

Write-Host ""
Write-Host "⚠️ LEMBRE-SE:" -ForegroundColor Yellow
Write-Host "  - Atualize as credenciais da API no Secret Manager"
Write-Host "  - Configure alertas de monitoramento"
Write-Host "  - Teste a conectividade com a API externa"
Write-Host "  - Revise as permissões IAM se necessário"

if ($LASTEXITCODE -eq 0) {
    Write-Host ""
    Write-Host "✨ Setup finalizado! Execute agora: .\deploy-sentinela.ps1" -ForegroundColor Green
}