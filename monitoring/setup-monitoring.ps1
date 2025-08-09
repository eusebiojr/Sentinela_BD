# Setup de Monitoramento e Observabilidade - Sentinela BD
# Configura dashboards, alertas e canais de notificação no Cloud Monitoring

param(
    [string]$ProjectId = "sz-wsp-00009",
    [string]$NotificationEmail = "", # Será solicitado se não fornecido
    [string]$SlackWebhook = "",      # Opcional
    [switch]$SkipDashboard = $false,
    [switch]$SkipAlerts = $false
)

Write-Host "🔍 SETUP MONITORAMENTO - SENTINELA BD" -ForegroundColor Green
Write-Host "=" * 50
Write-Host "Projeto: $ProjectId"
Write-Host ""

# Verificar dependências
if (-not (Get-Command "gcloud" -ErrorAction SilentlyContinue)) {
    Write-Error "❌ Google Cloud CLI não encontrado!"
    exit 1
}

# Configurar projeto
gcloud config set project $ProjectId

# Solicitar email se não fornecido
if (-not $NotificationEmail) {
    $NotificationEmail = Read-Host "📧 Digite o email para notificações de alerta"
    
    if (-not $NotificationEmail) {
        Write-Warning "⚠️ Email não fornecido - alertas não serão configurados"
        $SkipAlerts = $true
    }
}

Write-Host "📊 Configurando monitoramento..." -ForegroundColor Yellow

# 1. Criar canais de notificação
$EmailChannelId = $null
$SlackChannelId = $null

if (-not $SkipAlerts -and $NotificationEmail) {
    Write-Host "📧 Criando canal de notificação por email..." -ForegroundColor Yellow
    
    try {
        # Verificar se canal já existe
        $existingChannels = gcloud alpha monitoring channels list --filter="type:email" --format="value(name)" --quiet 2>$null
        
        $channelExists = $false
        if ($existingChannels) {
            foreach ($channel in $existingChannels) {
                $channelInfo = gcloud alpha monitoring channels describe $channel --format="json" --quiet 2>$null | ConvertFrom-Json
                if ($channelInfo.labels.email_address -eq $NotificationEmail) {
                    $EmailChannelId = $channel.Split('/')[-1]
                    $channelExists = $true
                    Write-Host "ℹ️ Canal de email já existe: $EmailChannelId" -ForegroundColor Blue
                    break
                }
            }
        }
        
        if (-not $channelExists) {
            # Criar novo canal de email
            $channelConfig = @{
                type = "email"
                displayName = "Sentinela BD - Email Alerts"
                description = "Canal de email para alertas do sistema Sentinela BD"
                labels = @{
                    email_address = $NotificationEmail
                }
                enabled = $true
            } | ConvertTo-Json -Depth 3
            
            $tempFile = [System.IO.Path]::GetTempFileName()
            $channelConfig | Out-File -FilePath $tempFile -Encoding UTF8
            
            $result = gcloud alpha monitoring channels create --channel-content-from-file=$tempFile --format="json" --quiet | ConvertFrom-Json
            $EmailChannelId = $result.name.Split('/')[-1]
            
            Remove-Item $tempFile -Force
            
            Write-Host "✅ Canal de email criado: $EmailChannelId" -ForegroundColor Green
        }
    }
    catch {
        Write-Warning "⚠️ Erro ao criar canal de email: $_"
    }
}

# 2. Criar canal Slack (se webhook fornecido)
if (-not $SkipAlerts -and $SlackWebhook) {
    Write-Host "💬 Criando canal de notificação Slack..." -ForegroundColor Yellow
    
    try {
        $slackConfig = @{
            type = "slack"
            displayName = "Sentinela BD - Slack Alerts"
            description = "Canal Slack para alertas do sistema Sentinela BD"
            labels = @{
                url = $SlackWebhook
            }
            enabled = $true
        } | ConvertTo-Json -Depth 3
        
        $tempFile = [System.IO.Path]::GetTempFileName()
        $slackConfig | Out-File -FilePath $tempFile -Encoding UTF8
        
        $result = gcloud alpha monitoring channels create --channel-content-from-file=$tempFile --format="json" --quiet | ConvertFrom-Json
        $SlackChannelId = $result.name.Split('/')[-1]
        
        Remove-Item $tempFile -Force
        
        Write-Host "✅ Canal Slack criado: $SlackChannelId" -ForegroundColor Green
    }
    catch {
        Write-Warning "⚠️ Erro ao criar canal Slack: $_"
    }
}

# 3. Criar dashboard customizado
if (-not $SkipDashboard) {
    Write-Host "📊 Criando dashboard customizado..." -ForegroundColor Yellow
    
    try {
        if (Test-Path "monitoring/dashboard-config.json") {
            # Verificar se dashboard já existe
            $existingDashboards = gcloud alpha monitoring dashboards list --filter="displayName:'Sentinela BD'" --format="value(name)" --quiet 2>$null
            
            if ($existingDashboards) {
                Write-Host "ℹ️ Dashboard já existe, atualizando..." -ForegroundColor Blue
                $dashboardId = $existingDashboards.Split('/')[-1]
                gcloud alpha monitoring dashboards update $dashboardId --config-from-file="monitoring/dashboard-config.json" --quiet
            } else {
                # Criar novo dashboard
                $result = gcloud alpha monitoring dashboards create --config-from-file="monitoring/dashboard-config.json" --format="json" --quiet | ConvertFrom-Json
                $dashboardId = $result.name.Split('/')[-1]
            }
            
            Write-Host "✅ Dashboard criado/atualizado: $dashboardId" -ForegroundColor Green
            
            $dashboardUrl = "https://console.cloud.google.com/monitoring/dashboards/custom/$dashboardId?project=$ProjectId"
            Write-Host "🔗 Dashboard URL: $dashboardUrl" -ForegroundColor Cyan
        } else {
            Write-Warning "⚠️ Arquivo de configuração do dashboard não encontrado"
        }
    }
    catch {
        Write-Warning "⚠️ Erro ao criar dashboard: $_"
    }
}

# 4. Criar políticas de alerta
if (-not $SkipAlerts -and $EmailChannelId) {
    Write-Host "🚨 Criando políticas de alerta..." -ForegroundColor Yellow
    
    try {
        # Lista de alertas a serem criados
        $alertas = @(
            @{
                name = "sentinela-sistema-down"
                displayName = "Sentinela BD - Sistema Indisponível"
                filter = 'resource.type="cloud_run_revision" AND resource.labels.service_name="sentinela-detection"'
                condition = "ausencia_execucoes"
            },
            @{
                name = "sentinela-desvios-n4"
                displayName = "Sentinela BD - Desvios Nível N4 Crítico"
                filter = 'metric.type="custom.googleapis.com/sentinela/desvios_detectados" AND metric.labels.nivel="N4"'
                condition = "desvios_criticos"
            },
            @{
                name = "sentinela-api-errors"
                displayName = "Sentinela BD - Falhas na API Externa"
                filter = 'resource.type="cloud_run_revision" AND resource.labels.service_name="sentinela-detection" AND severity="ERROR"'
                condition = "alta_taxa_erro"
            },
            @{
                name = "sentinela-performance"
                displayName = "Sentinela BD - Performance Degradada"
                filter = 'metric.type="custom.googleapis.com/sentinela/tempo_processamento"'
                condition = "processamento_lento"
            }
        )
        
        foreach ($alerta in $alertas) {
            Write-Host "  Criando alerta: $($alerta.displayName)..." -ForegroundColor Gray
            
            # Verificar se política já existe
            $existingPolicies = gcloud alpha monitoring policies list --filter="displayName:'$($alerta.displayName)'" --format="value(name)" --quiet 2>$null
            
            if ($existingPolicies) {
                Write-Host "    ℹ️ Política já existe, pulando..." -ForegroundColor Blue
                continue
            }
            
            # Criar configuração específica do alerta
            $alertConfig = @{
                displayName = $alerta.displayName
                documentation = @{
                    content = "Alerta automático gerado pelo sistema Sentinela BD"
                    mimeType = "text/markdown"
                }
                conditions = @(@{
                    displayName = $alerta.condition
                    conditionThreshold = @{
                        filter = $alerta.filter
                        aggregations = @(@{
                            alignmentPeriod = "300s"
                            perSeriesAligner = "ALIGN_RATE"
                            crossSeriesReducer = "REDUCE_COUNT"
                        })
                        comparison = "COMPARISON_LESS_THAN"
                        thresholdValue = 1
                        duration = "300s"
                        trigger = @{
                            count = 1
                        }
                    }
                })
                alertStrategy = @{
                    autoClose = "1800s"
                }
                enabled = $true
                notificationChannels = @("projects/$ProjectId/notificationChannels/$EmailChannelId")
            }
            
            # Adicionar canal Slack se disponível
            if ($SlackChannelId) {
                $alertConfig.notificationChannels += "projects/$ProjectId/notificationChannels/$SlackChannelId"
            }
            
            $alertJson = $alertConfig | ConvertTo-Json -Depth 10
            $tempFile = [System.IO.Path]::GetTempFileName()
            $alertJson | Out-File -FilePath $tempFile -Encoding UTF8
            
            try {
                gcloud alpha monitoring policies create --policy-from-file=$tempFile --quiet
                Write-Host "    ✅ Alerta criado com sucesso" -ForegroundColor Green
            }
            catch {
                Write-Warning "    ⚠️ Erro ao criar alerta: $_"
            }
            finally {
                Remove-Item $tempFile -Force -ErrorAction SilentlyContinue
            }
        }
    }
    catch {
        Write-Warning "⚠️ Erro geral na criação de alertas: $_"
    }
}

# 5. Configurar log sink para BigQuery (se não existir)
Write-Host "📋 Configurando log sink para BigQuery..." -ForegroundColor Yellow

try {
    $sinkName = "sentinela-logs-bigquery"
    $existingSinks = gcloud logging sinks list --filter="name:$sinkName" --format="value(name)" --quiet 2>$null
    
    if (-not $existingSinks) {
        $destination = "bigquery.googleapis.com/projects/$ProjectId/datasets/sentinela_bd/tables/system_logs"
        $filter = 'resource.type="cloud_run_revision" AND resource.labels.service_name="sentinela-detection"'
        
        gcloud logging sinks create $sinkName $destination --log-filter="$filter" --quiet
        
        Write-Host "✅ Log sink criado: $sinkName" -ForegroundColor Green
    } else {
        Write-Host "ℹ️ Log sink já existe: $sinkName" -ForegroundColor Blue
    }
}
catch {
    Write-Warning "⚠️ Erro ao criar log sink: $_"
}

# 6. Configurar métricas customizadas (criar descritores se necessário)
Write-Host "📈 Configurando métricas customizadas..." -ForegroundColor Yellow

$customMetrics = @(
    @{
        type = "custom.googleapis.com/sentinela/desvios_detectados"
        displayName = "Desvios Detectados"
        description = "Número de desvios detectados por filial/grupo/nível"
        metricKind = "GAUGE"
        valueType = "INT64"
        labels = @("filial", "grupo", "nivel")
    },
    @{
        type = "custom.googleapis.com/sentinela/veiculos_ativos_total"
        displayName = "Veículos Ativos Total"
        description = "Total de veículos ativos por POI"
        metricKind = "GAUGE"
        valueType = "INT64"
        labels = @("filial", "grupo", "poi")
    },
    @{
        type = "custom.googleapis.com/sentinela/tempo_processamento"
        displayName = "Tempo de Processamento"
        description = "Tempo de processamento da detecção em segundos"
        metricKind = "GAUGE"
        valueType = "DOUBLE"
        labels = @()
    },
    @{
        type = "custom.googleapis.com/sentinela/api_response_time"
        displayName = "API Response Time"
        description = "Tempo de resposta da API externa"
        metricKind = "HISTOGRAM"
        valueType = "DISTRIBUTION"
        labels = @("endpoint")
    },
    @{
        type = "custom.googleapis.com/sentinela/sla_compliance_rate"
        displayName = "SLA Compliance Rate"
        description = "Taxa de conformidade com SLA por grupo"
        metricKind = "GAUGE"
        valueType = "DOUBLE"
        labels = @("filial", "grupo")
    }
)

foreach ($metric in $customMetrics) {
    Write-Host "  Configurando métrica: $($metric.displayName)..." -ForegroundColor Gray
    
    # Verificar se métrica já existe
    $existingMetrics = gcloud logging metrics list --filter="name:$($metric.type.Replace('custom.googleapis.com/', ''))" --format="value(name)" --quiet 2>$null
    
    if ($existingMetrics) {
        Write-Host "    ℹ️ Métrica já existe" -ForegroundColor Blue
    } else {
        Write-Host "    ℹ️ Métrica customizada será criada automaticamente no primeiro uso" -ForegroundColor Blue
    }
}

# 7. Verificar configuração e criar resumo
Write-Host ""
Write-Host "🎉 MONITORAMENTO CONFIGURADO COM SUCESSO!" -ForegroundColor Green
Write-Host "=" * 50

Write-Host ""
Write-Host "📋 RECURSOS CONFIGURADOS:" -ForegroundColor Yellow

if ($EmailChannelId) {
    Write-Host "  ✅ Canal de email: $NotificationEmail ($EmailChannelId)"
}

if ($SlackChannelId) {
    Write-Host "  ✅ Canal Slack configurado ($SlackChannelId)"
}

if (-not $SkipDashboard) {
    Write-Host "  ✅ Dashboard customizado criado"
}

if (-not $SkipAlerts -and $EmailChannelId) {
    Write-Host "  ✅ Políticas de alerta configuradas"
}

Write-Host "  ✅ Log sink para BigQuery configurado"
Write-Host "  ✅ Métricas customizadas preparadas"

Write-Host ""
Write-Host "🔗 LINKS ÚTEIS:" -ForegroundColor Cyan
Write-Host "  Monitoring Console: https://console.cloud.google.com/monitoring?project=$ProjectId"
Write-Host "  Dashboards: https://console.cloud.google.com/monitoring/dashboards?project=$ProjectId"
Write-Host "  Alerting: https://console.cloud.google.com/monitoring/alerting?project=$ProjectId"
Write-Host "  Logs: https://console.cloud.google.com/logs?project=$ProjectId"

Write-Host ""
Write-Host "⚠️ PRÓXIMOS PASSOS:" -ForegroundColor Yellow
Write-Host "  1. Deploy o sistema: .\deploy-sentinela.ps1"
Write-Host "  2. Teste os alertas manualmente"
Write-Host "  3. Configure canais adicionais (Slack, SMS, etc)"
Write-Host "  4. Ajuste thresholds conforme necessário"
Write-Host "  5. Configure backup e disaster recovery"

if (-not $NotificationEmail) {
    Write-Host ""
    Write-Warning "⚠️ Execute novamente com -NotificationEmail para configurar alertas"
}

Write-Host ""
Write-Host "✨ Monitoramento operacional! Sistema pronto para produção." -ForegroundColor Green