# 🚛 Deploy Sistema Sentinela BD - Detecção de Desvios

## 📋 Resumo do Sistema

O Sistema Sentinela BD é uma solução completa para monitoramento automático de desvios de SLA em pontos notáveis (POIs), executando de hora em hora no Google Cloud Platform.

### ✅ Funcionalidades Implementadas

- **Monitoramento Automático**: Execução horária via Cloud Scheduler
- **Detecção de Desvios**: Análise de SLA por grupo e filial
- **Critério Otimizado**: Utiliza `status = 1` para 66.7% de acurácia
- **Janelas Adaptativas**: 2h → 6h → 24h → 72h → 7 dias conforme necessário
- **Escalonamento N1-N4**: Níveis de alerta baseados na gravidade do desvio
- **BigQuery Integration**: Armazenamento estruturado de dados
- **Logs Detalhados**: Monitoramento via Cloud Logging

### 📊 SLAs Configurados

| Filial | Grupo | Limite |
|--------|-------|--------|
| RRP | Fábrica | 6 veículos |
| RRP | Terminal | 12 veículos |
| RRP | Manutenção | 12 veículos |
| RRP | Ponto Apoio | 6 veículos |
| TLS | Fábrica | 5 veículos |
| TLS | Terminal | 5 veículos |
| TLS | Manutenção | 10 veículos |
| TLS | Ponto Apoio | 5 veículos |

## 🚀 Como Fazer o Deploy

### Pré-requisitos

1. **Google Cloud SDK** instalado e configurado
2. **PowerShell** com permissões para executar scripts
3. **Permissões GCP**: 
   - Cloud Run Admin
   - Cloud Scheduler Admin
   - BigQuery Admin
   - Service Account User

### Passo a Passo

1. **Abrir PowerShell** no diretório do projeto:
   ```powershell
   cd /caminho/para/Sentinela_BD
   ```

2. **Executar o deploy**:
   ```powershell
   PowerShell -ExecutionPolicy Bypass -File .\deploy.ps1
   ```

3. **Aguardar conclusão** (~5-10 minutos):
   - Habilitação de APIs
   - Build da imagem Docker
   - Deploy do Cloud Run
   - Configuração do BigQuery
   - Criação do Cloud Scheduler

## 📁 Estrutura de Arquivos

```
Sentinela_BD/
├── deploy.ps1                          # Script de deploy principal
├── Dockerfile                          # Configuração do container
├── requirements.txt                    # Dependências Python
├── .dockerignore                       # Arquivos a ignorar no build
├── Grupos.csv                          # Mapeamento POI → Grupo
├── scripts/pontos_notaveis/
│   ├── main.py                        # Entry point Flask para Cloud Run
│   ├── sistema_deteccao_desvios.py    # Sistema principal (modificado)
│   └── bigquery_integration.py        # Integração com BigQuery
└── DEPLOY.md                          # Esta documentação
```

## 🏗️ Arquitetura GCP

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│  Cloud Scheduler │───▶│    Cloud Run     │───▶│    BigQuery     │
│  (Execução       │    │  (Processing)    │    │  (Storage)      │
│   Horária)       │    │                  │    │                 │
└─────────────────┘    └──────────────────┘    └─────────────────┘
                                │
                                ▼
                       ┌──────────────────┐
                       │  Cloud Logging   │
                       │  (Monitoring)    │
                       └──────────────────┘
```

### Componentes

1. **Cloud Scheduler**: 
   - Executa a cada hora (0 * * * *)
   - Chama endpoint `/execute` via HTTP POST

2. **Cloud Run**:
   - Container Python com Flask
   - Auto-scaling (0-5 instâncias)
   - Timeout: 15 minutos
   - Memory: 2Gi, CPU: 2

3. **BigQuery**:
   - Dataset: `sentinela_bd`
   - Tabelas: `veiculos_ativos`, `eventos_desvio`, `historico_sla`

## 📊 Tabelas BigQuery

### `veiculos_ativos`
Todos os veículos monitorados em cada execução:
- timestamp_verificacao, filial, grupo, poi, placa_veiculo
- data_entrada, tempo_permanencia_horas, sla_limite
- qtd_grupo, status_sla, em_desvio, evento_id

### `eventos_desvio` 
Eventos de desvio com escalonamento:
- evento_id, timestamp_verificacao, filial, grupo
- placa_veiculo, poi, data_entrada, tempo_permanencia_horas
- nivel_alerta (N1-N4), qtd_veiculos_grupo, sla_limite
- nivel_escalonamento, processado

### `historico_sla`
Histórico de ocupação por grupo (particionado por data):
- timestamp_verificacao, filial, grupo, qtd_veiculos
- sla_limite, percentual_ocupacao, em_desvio, data_particao

## 🎯 Níveis de Escalonamento

| Nível | Critério | Descrição |
|-------|----------|-----------|
| **N1** | 1-25% acima do limite | Desvio leve |
| **N2** | 26-50% acima do limite | Desvio moderado |
| **N3** | 51-100% acima do limite | Desvio grave |
| **N4** | >100% acima do limite | Desvio crítico |

## 🔍 Endpoints da API

| Endpoint | Método | Descrição |
|----------|--------|-----------|
| `/` | GET | Health check |
| `/status` | GET | Status detalhado do sistema |
| `/execute` | POST | Execução do monitoramento |
| `/setup` | POST | Configuração inicial do BigQuery |

## 📈 Monitoramento

### Cloud Console URLs
- **Cloud Run**: `https://console.cloud.google.com/run/detail/us-central1/sentinela-desvios`
- **Cloud Scheduler**: `https://console.cloud.google.com/cloudscheduler`
- **BigQuery**: `https://console.cloud.google.com/bigquery?project=sz-wsp-00009`
- **Logs**: `https://console.cloud.google.com/logs`

### Comandos úteis
```bash
# Ver logs em tempo real
gcloud run services logs tail sentinela-desvios --region=us-central1

# Status do serviço
gcloud run services describe sentinela-desvios --region=us-central1

# Executar manualmente o scheduler
gcloud scheduler jobs run sentinela-scheduler --location=us-central1

# Consultar dados no BigQuery
bq query --use_legacy_sql=false 'SELECT * FROM sz-wsp-00009.sentinela_bd.eventos_desvio ORDER BY timestamp_verificacao DESC LIMIT 10'
```

## ⚠️ Troubleshooting

### Problemas Comuns

1. **Erro de Permissões**:
   - Verificar IAM roles no projeto sz-wsp-00009
   - Confirmar Service Account configurada

2. **Build Falha**:
   - Verificar Dockerfile e requirements.txt
   - Checar logs no Cloud Build

3. **Scheduler não executa**:
   - Verificar configuração do job
   - Confirmar URL do Cloud Run

4. **BigQuery sem dados**:
   - Executar `/setup` endpoint
   - Verificar logs de inserção

### Logs Importantes

```bash
# Logs do sistema
🚛 Iniciando execução do Sistema Sentinela BD
📅 Execução iniciada pelo Cloud Scheduler  
✅ Detecção de desvios executada com sucesso
📊 Dados enviados para BigQuery com sucesso
```

## 🔄 Atualizações

Para atualizar o sistema:

1. Modificar código conforme necessário
2. Executar novamente: `PowerShell -ExecutionPolicy Bypass -File .\deploy.ps1`
3. O Cloud Run fará deploy da nova versão automaticamente

## 📞 Suporte

Em caso de problemas:

1. Verificar logs no Cloud Console
2. Validar configurações no script de deploy
3. Testar endpoints manualmente
4. Consultar dados no BigQuery para validação

---

**Versão**: 1.0.0  
**Última atualização**: 09/08/2025  
**Projeto GCP**: sz-wsp-00009