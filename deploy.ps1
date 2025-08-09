# Deploy Sistema Sentinela BD - Detecção de Desvios
# Execute: PowerShell -ExecutionPolicy Bypass -File .\deploy.ps1

$PROJECT_ID = "sz-wsp-00009"
$SERVICE_NAME = "sentinela-desvios"
$REGION = "us-central1"
$SCHEDULER_NAME = "sentinela-scheduler"

Write-Host "🚛 DEPLOY SISTEMA SENTINELA BD - DETECÇÃO DE DESVIOS" -ForegroundColor Green
Write-Host "=" * 60
Write-Host "Projeto: $PROJECT_ID"
Write-Host "Região: $REGION"
Write-Host "Serviço: $SERVICE_NAME"
Write-Host ""

# Configurar projeto
Write-Host "📋 Configurando projeto GCP..." -ForegroundColor Yellow
gcloud config set project $PROJECT_ID

# Habilitar APIs necessárias
Write-Host "🔧 Habilitando APIs necessárias..." -ForegroundColor Yellow
$apis = @(
    "run.googleapis.com",
    "cloudbuild.googleapis.com", 
    "cloudscheduler.googleapis.com",
    "bigquery.googleapis.com",
    "logging.googleapis.com"
)

foreach ($api in $apis) {
    Write-Host "   Habilitando $api..."
    gcloud services enable $api --quiet
}

# Fazer deploy do Cloud Run
Write-Host "🚀 Fazendo deploy do Cloud Run..." -ForegroundColor Yellow
Write-Host ""

gcloud run deploy $SERVICE_NAME `
    --source . `
    --region $REGION `
    --platform managed `
    --allow-unauthenticated `
    --memory 2Gi `
    --cpu 2 `
    --min-instances 0 `
    --max-instances 5 `
    --port 8080 `
    --timeout 900 `
    --set-env-vars ENVIRONMENT=production,GOOGLE_CLOUD_PROJECT=$PROJECT_ID `
    --service-account "sentinela-sa@$PROJECT_ID.iam.gserviceaccount.com"

if ($LASTEXITCODE -eq 0) {
    Write-Host ""
    Write-Host "✅ Cloud Run deployado com sucesso!" -ForegroundColor Green
    
    # Obter URL do serviço
    try {
        $SERVICE_URL = gcloud run services describe $SERVICE_NAME --region=$REGION --format="value(status.url)"
        Write-Host "🌐 URL do serviço: $SERVICE_URL" -ForegroundColor Cyan
        
        # Configurar BigQuery (execução única)
        Write-Host "📊 Configurando tabelas BigQuery..." -ForegroundColor Yellow
        $setupResponse = Invoke-RestMethod -Uri "$SERVICE_URL/setup" -Method POST
        if ($setupResponse.status -eq "success") {
            Write-Host "✅ Tabelas BigQuery configuradas!" -ForegroundColor Green
        } else {
            Write-Host "⚠️ Verifique configuração BigQuery manualmente" -ForegroundColor Yellow
        }
        
        # Criar Cloud Scheduler
        Write-Host "⏰ Configurando Cloud Scheduler..." -ForegroundColor Yellow
        
        # Verificar se job já existe
        $jobExists = gcloud scheduler jobs describe $SCHEDULER_NAME --location=$REGION --format="value(name)" 2>$null
        
        if ($jobExists) {
            Write-Host "   Job scheduler já existe, atualizando..."
            gcloud scheduler jobs update http $SCHEDULER_NAME `
                --location=$REGION `
                --schedule="0 * * * *" `
                --uri="$SERVICE_URL/execute" `
                --http-method=POST `
                --headers="Content-Type=application/json,X-CloudScheduler=true" `
                --body="{}"
        } else {
            Write-Host "   Criando novo job scheduler..."
            gcloud scheduler jobs create http $SCHEDULER_NAME `
                --location=$REGION `
                --schedule="0 * * * *" `
                --uri="$SERVICE_URL/execute" `
                --http-method=POST `
                --headers="Content-Type=application/json,X-CloudScheduler=true" `
                --body="{}" `
                --description="Execução horária do Sistema Sentinela BD"
        }
        
        if ($LASTEXITCODE -eq 0) {
            Write-Host "✅ Cloud Scheduler configurado!" -ForegroundColor Green
            Write-Host "   Execução: A cada hora (0 * * * *)" -ForegroundColor Cyan
        } else {
            Write-Host "❌ Erro ao configurar Cloud Scheduler" -ForegroundColor Red
        }
        
        # Resumo final
        Write-Host ""
        Write-Host "🎉 DEPLOY CONCLUÍDO COM SUCESSO!" -ForegroundColor Green
        Write-Host "=" * 60
        Write-Host "📋 INFORMAÇÕES DO SISTEMA:"
        Write-Host "   • Serviço: $SERVICE_NAME" -ForegroundColor Cyan
        Write-Host "   • URL: $SERVICE_URL" -ForegroundColor Cyan
        Write-Host "   • Região: $REGION" -ForegroundColor Cyan
        Write-Host "   • Execução: Automática a cada hora" -ForegroundColor Cyan
        Write-Host ""
        Write-Host "🔗 ENDPOINTS DISPONÍVEIS:"
        Write-Host "   • Health Check: $SERVICE_URL/" -ForegroundColor Yellow
        Write-Host "   • Status: $SERVICE_URL/status" -ForegroundColor Yellow
        Write-Host "   • Execução Manual: $SERVICE_URL/execute (POST)" -ForegroundColor Yellow
        Write-Host "   • Setup BigQuery: $SERVICE_URL/setup (POST)" -ForegroundColor Yellow
        Write-Host ""
        Write-Host "📊 BIGQUERY:"
        Write-Host "   • Projeto: $PROJECT_ID" -ForegroundColor Yellow
        Write-Host "   • Dataset: sentinela_bd" -ForegroundColor Yellow
        Write-Host "   • Tabelas: veiculos_ativos, eventos_desvio, historico_sla" -ForegroundColor Yellow
        Write-Host ""
        Write-Host "📈 MONITORAMENTO:"
        Write-Host "   • Cloud Run: https://console.cloud.google.com/run/detail/$REGION/$SERVICE_NAME" -ForegroundColor Yellow
        Write-Host "   • Cloud Scheduler: https://console.cloud.google.com/cloudscheduler" -ForegroundColor Yellow
        Write-Host "   • BigQuery: https://console.cloud.google.com/bigquery?project=$PROJECT_ID" -ForegroundColor Yellow
        Write-Host "   • Logs: gcloud run services logs tail $SERVICE_NAME --region=$REGION" -ForegroundColor Yellow
        Write-Host ""
        Write-Host "🎯 PRÓXIMOS PASSOS:"
        Write-Host "   1. Verificar primeira execução automática na próxima hora"
        Write-Host "   2. Monitorar logs do Cloud Run"
        Write-Host "   3. Validar dados no BigQuery"
        Write-Host "   4. Configurar alertas adicionais se necessário"
        
    } catch {
        Write-Host "⚠️ Serviço deployado, mas houve erro na configuração adicional" -ForegroundColor Yellow
        Write-Host "Verifique manualmente no Google Cloud Console"
    }
    
} else {
    Write-Host ""
    Write-Host "❌ FALHA NO DEPLOY" -ForegroundColor Red
    Write-Host "Verifique os logs do Cloud Build:"
    Write-Host "https://console.cloud.google.com/cloud-build/builds?project=$PROJECT_ID" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "Comandos para debug:"
    Write-Host "gcloud run services list --region=$REGION" -ForegroundColor Yellow
    Write-Host "gcloud builds list --limit=5" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "Script concluído!" -ForegroundColor Green