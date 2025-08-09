# Arquitetura GCP - Sistema de Detecção de Desvios Sentinela BD

## Visão Geral da Arquitetura

```
┌─────────────────┐    ┌────────────────┐    ┌─────────────────┐
│   Cloud         │    │   Cloud Run    │    │   BigQuery      │
│   Scheduler     │───▶│   Service      │───▶│   Dataset       │
│   (Horário)     │    │   (Detector)   │    │   (Armazenamento│
└─────────────────┘    └────────────────┘    └─────────────────┘
                              │
                              ▼
                       ┌────────────────┐
                       │   API Externa  │
                       │   (Frotalog)   │
                       └────────────────┘
                              │
                              ▼
                       ┌────────────────┐    ┌─────────────────┐
                       │   Cloud        │    │   Cloud         │
                       │   Monitoring   │    │   Logging       │
                       │   (Alertas)    │    │   (Auditoria)   │
                       └────────────────┘    └─────────────────┘
```

## Componentes da Arquitetura

### 1. Cloud Scheduler (Trigger Horário)
- **Função**: Executa o sistema de detecção a cada hora
- **Configuração**: 
  - Schedule: `0 * * * *` (início de cada hora)
  - Timezone: `America/Sao_Paulo`
  - Target: Cloud Run Service HTTP endpoint
  - Retry: 3 tentativas em caso de falha
  - Timeout: 300 segundos

### 2. Cloud Run Service (Processamento)
- **Função**: Processa detecção de desvios e persiste dados
- **Configuração**:
  - CPU: 1 vCPU
  - Memory: 1GB RAM  
  - Min instances: 0 (cold start aceitável)
  - Max instances: 10
  - Concurrency: 1 (processamento sequencial)
  - Timeout: 300 segundos
  - Port: 8080

### 3. BigQuery Dataset (Armazenamento)
- **Função**: Armazena dados de veículos, eventos de desvio e métricas
- **Configuração**:
  - Dataset: `sentinela_bd`
  - Location: `US` (multi-region)
  - Retention: 1 ano para eventos, 3 meses para métricas

### 4. Cloud Monitoring & Logging (Observabilidade)
- **Função**: Monitoramento de saúde e performance do sistema
- **Métricas customizadas**:
  - Desvios detectados por filial/grupo
  - Tempo de resposta da API externa
  - Taxa de erro do processamento
  - Volume de veículos por POI

## Fluxo de Dados

### 1. Trigger Horário
```
Cloud Scheduler → POST /execute → Cloud Run
```

### 2. Processamento Principal
```
1. Cloud Run recebe trigger
2. Autentica com API externa (Frotalog)
3. Busca veículos ativos nos POIs
4. Aplica regras de SLA por grupo/filial
5. Detecta desvios (N1-N4)
6. Persiste dados no BigQuery
7. Envia métricas ao Cloud Monitoring
8. Retorna status de execução
```

### 3. Persistência de Dados
```
Veículos Ativos → tabela: `veiculos_ativos`
Eventos Desvio → tabela: `eventos_desvio` 
Métricas SLA → tabela: `metricas_sla`
Escalações N1-N4 → tabela: `escalacoes_niveis`
```

## Estratégia de Escalonamento N1-N4

### Níveis de Escalonamento
- **N1 (0-1h)**: Alerta inicial - registro no sistema
- **N2 (1-2h)**: Notificação supervisor - email/Slack
- **N3 (2-4h)**: Escalonamento gerencial - dashboard/SMS
- **N4 (4h+)**: Escalonamento executivo - chamada/WhatsApp

### Persistência de Estado
```sql
-- Tabela de controle de escalonamentos
escalacoes_niveis (
  evento_id, 
  nivel_atual,
  timestamp_nivel,
  acao_realizada,
  proximo_nivel_em
)
```

## Segurança e IAM

### Service Account Permissions
```
- BigQuery Data Editor
- BigQuery Job User  
- Cloud Run Invoker
- Monitoring Metric Writer
- Logging Writer
```

### Network Security
- Cloud Run: Ingress interno apenas (VPC)
- BigQuery: Acesso restrito por service account
- API Externa: OAuth2 com refresh token

## Custos Estimados (Mensal)

### Cloud Run
- Execuções: 744/mês (24h × 31 dias)
- CPU time: ~2min/execução = ~25 horas/mês
- Custo: ~$2-3/mês

### BigQuery
- Storage: ~100MB/mês (dados históricos)
- Queries: ~1GB processado/mês  
- Custo: <$1/mês

### Cloud Scheduler
- Jobs: 744 execuções/mês
- Custo: <$1/mês

### Total Estimado: $4-5/mês

## Disaster Recovery

### Backup Strategy
- BigQuery: Backup automático (7 dias)
- Código: Git repository + Container Registry
- Configuração: Infrastructure as Code (Terraform)

### Failover
- Multi-region BigQuery dataset
- Cloud Run com auto-scaling
- Dead letter queue para falhas de processamento

## Monitoramento SLIs/SLOs

### Service Level Indicators (SLIs)
- **Disponibilidade**: 99.5% uptime
- **Latência**: <30s processamento médio
- **Precisão**: >95% detecção de desvios
- **Completude**: >99% dados coletados

### Service Level Objectives (SLOs)  
- **RTO**: 5 minutos (Recovery Time Objective)
- **RPO**: 1 hora (Recovery Point Objective)
- **Error Budget**: 0.5% falhas/mês

## Compliance & Auditoria

### Logging Strategy
- Todos os eventos registrados no Cloud Logging
- Retenção: 30 dias (logs), 1 ano (eventos)
- Formato estruturado (JSON)

### Data Governance
- Classificação de dados: Interno/Confidencial
- Criptografia em repouso (BigQuery)
- Criptografia em trânsito (HTTPS/TLS)
- Controle de acesso baseado em roles (RBAC)