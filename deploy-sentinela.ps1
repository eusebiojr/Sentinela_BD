# Deploy final com Dockerfile corrigido
# Execute: .\deploy_final.ps1

$PROJECT_ID = "sz-wsp-00009"
$SERVICE_NAME = "sentinela"
$REGION = "us-central1"

Write-Host "Deploy FINAL do Sentinela (Dockerfile corrigido!)" -ForegroundColor Green
Write-Host "Projeto: $PROJECT_ID"
Write-Host "Regiao: $REGION"
Write-Host "Servico: $SERVICE_NAME"
Write-Host ""

# Configura projeto
Write-Host "Configurando projeto..." -ForegroundColor Yellow
gcloud config set project $PROJECT_ID

Write-Host "Iniciando deploy com Dockerfile corrigido..." -ForegroundColor Yellow
Write-Host ""

# Deploy com Dockerfile corrigido
gcloud run deploy $SERVICE_NAME `
    --source . `
    --region $REGION `
    --platform managed `
    --allow-unauthenticated `
    --memory 1Gi `
    --cpu 1 `
    --min-instances 0 `
    --max-instances 10 `
    --port 8080 `
    --timeout 300 `
    --set-env-vars ENVIRONMENT=production

if ($LASTEXITCODE -eq 0) {
    Write-Host ""
    Write-Host "🎉 SUCESSO! SENTINELA ESTA ONLINE!" -ForegroundColor Green
    Write-Host ""
    
    # Obtem URL
    try {
        $SERVICE_URL = gcloud run services describe $SERVICE_NAME --region=$REGION --format="value(status.url)"
        Write-Host "🌐 URL DA APLICACAO: $SERVICE_URL" -ForegroundColor Cyan
        Write-Host ""
        Write-Host "🚀 ACESSE A URL ACIMA PARA VER O SENTINELA FUNCIONANDO!" -ForegroundColor Green
    } catch {
        Write-Host "Verifique a URL no Google Cloud Console"
        Write-Host "https://console.cloud.google.com/run" -ForegroundColor Cyan
    }
    
    Write-Host ""
    Write-Host "📊 Monitoramento: https://console.cloud.google.com/run/detail/$REGION/$SERVICE_NAME" -ForegroundColor Yellow
    Write-Host "📋 Logs: gcloud run services logs tail $SERVICE_NAME --region=$REGION" -ForegroundColor Yellow
    
} else {
    Write-Host ""
    Write-Host "❌ FALHOU - vamos investigar..." -ForegroundColor Red
    Write-Host "Verifique os logs no Cloud Build Console"
}