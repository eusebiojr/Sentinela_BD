# POI Deviation Detection System - Sentinela BD

## 📋 Project Overview

A comprehensive 24/7 POI (Points of Interest) deviation detection system that monitors vehicle activity at RRP and TLS facilities, implementing automated alert escalation with N1-N4 levels. Built on Google Cloud Platform with modern serverless architecture.

### 🎯 Key Features

- **24/7 Monitoring**: Continuous POI monitoring with hourly data collection
- **Smart Deviation Detection**: Group-based analysis with escalation logic (N1→N2→N3→N4)
- **Multi-Channel Alerts**: Email, SMS, and webhook delivery with specific formatting
- **Historical Analytics**: Time-series data storage and analysis in BigQuery
- **Real-time State Management**: Live alert states and configuration in Firestore
- **Security by Design**: Comprehensive IAM, VPC, and audit controls

### 🏗️ System Architecture

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   Creare Cloud  │───▶│  Data Collector  │───▶│    BigQuery     │
│       API       │    │ Cloud Function   │    │ (poi_monitoring)│
└─────────────────┘    └──────────────────┘    └─────────────────┘
                                │
                                ▼
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│ Alert Delivery  │◀───│ Deviation        │───▶│   Firestore     │
│ Cloud Function  │    │ Detector         │    │ (alert_states)  │
└─────────────────┘    │ Cloud Function   │    └─────────────────┘
        │               └──────────────────┘
        ▼
┌─────────────────┐
│ Multi-Channel   │
│ Alert Delivery  │
│ (Email/SMS)     │
└─────────────────┘
```

## 🗂️ Project Structure

```
Sentinela_BD/
├── scripts/pontos_notaveis/               # Original implementation
│   └── gerar_relatorio_pontos_notaveis.py
├── cloud-functions/                       # Cloud Functions (NEW)
│   ├── data-collector/
│   ├── deviation-detector/
│   └── alert-manager/
├── deployment/                            # Deployment scripts (NEW)
│   └── deploy.sh
├── security/                             # Security framework (NEW)
│   ├── security-framework.md
│   └── setup-security.sh
├── database-schema.sql                   # BigQuery schema (NEW)
├── firestore-schema.md                   # Firestore schema (NEW)
├── gcp-architecture.md                   # Architecture docs (NEW)
├── backend-architecture.md               # Backend design (NEW)
├── Grupos.csv                           # POI mappings (PRESERVED)
└── README.md                            # This documentation
```

## 🚀 Quick Start

### Prerequisites

- Google Cloud Platform account with billing enabled
- `gcloud` CLI installed and configured
- Project with necessary APIs enabled
- Domain with email/SMS capabilities for alerts

### 1. Clone and Setup

```bash
git clone <repository-url>
cd Sentinela_BD

# Update project configuration
export PROJECT_ID="your-project-id"
sed -i 's/poi-monitoring-prod/'$PROJECT_ID'/g' deployment/deploy.sh
sed -i 's/poi-monitoring-prod/'$PROJECT_ID'/g' security/setup-security.sh
```

### 2. Deploy Security Framework

```bash
# Setup security (IAM, VPC, secrets)
./security/setup-security.sh

# Add your actual API credentials
echo "your-client-id" | gcloud secrets versions add creare-client-id --data-file=-
echo "your-client-secret" | gcloud secrets versions add creare-client-secret --data-file=-
```

### 3. Deploy System Components

```bash
# Deploy all Cloud Functions and infrastructure
./deployment/deploy.sh

# Verify deployment
gcloud functions list --filter="name:poi-"
```

### 4. Configure Alert Recipients

```bash
# Import Firestore configuration (update with your recipients)
# Edit /tmp/firestore-init.json and import to Firestore console
```

### 5. Test the System

```bash
# Trigger manual execution
gcloud scheduler jobs run data-collection-schedule --location=us-central1

# Monitor logs
gcloud functions logs read poi-data-collector --limit=50
```

## 📊 Business Logic

### POI Monitoring Rules

The system monitors **29 POIs** across two facilities:
- **RRP**: 11 POIs (Carregamento Fábrica, Buffer Frotas, etc.)
- **TLS**: 18 POIs (Carregamento Fábrica, AREA EXTERNA SUZANO, etc.)

### Alert Escalation Logic

```yaml
N1 (First Alert): 2+ hours in POI
  - Channels: Email only
  - Re-alert: Every 4 hours
  
N2 (Escalation): 4+ hours in POI  
  - Channels: Email + SMS
  - Re-alert: Every 2 hours
  
N3 (Critical): 8+ hours in POI
  - Channels: Email + SMS
  - Re-alert: Every 1 hour
  
N4 (Emergency): 12+ hours in POI
  - Channels: Email + SMS + Webhook
  - Re-alert: Every 1 hour
```

### Alert Title Format

**Format**: `{FILIAL}_{POI_SEM_ESPACOS}_{NIVEL}_{DDMMYYYY}_{HHMMSS}`  
**Example**: `RRP_CarregamentoFabricaRRP_N2_08082025_160000`

- Timestamp always at closed hour (16:10h becomes 16:00:00)
- POI without spaces or special characters
- Brazilian date format (DDMMYYYY)

## 🔧 Configuration Management

### POI Group Mappings

POIs are classified into operational groups via `Grupos.csv`:

```csv
POI;GRUPO
Carregamento Fabrica RRP;Fábrica
Buffer Frotas;Buffer
Abastecimento Frotas RRP;Abastecimento
Manutencao JSL RRP;Manutenção
```

### Alert Recipients Configuration

Managed in Firestore `system_settings/alert_recipients`:

```json
{
  "by_filial": {
    "RRP": {
      "email": ["manager.rrp@company.com"],
      "sms": ["+5567999999999"]
    },
    "TLS": {
      "email": ["manager.tls@company.com"], 
      "sms": ["+5567888888888"]
    }
  },
  "by_level": {
    "N1": ["operations"],
    "N2": ["operations", "supervisors"],
    "N3": ["operations", "supervisors", "managers"],
    "N4": ["operations", "supervisors", "managers", "directors"]
  }
}
```

### Deviation Thresholds

Customizable per POI in Firestore `poi_configurations`:

```json
{
  "poi_name": "Carregamento Fabrica RRP",
  "deviation_thresholds": {
    "escalation_hours": {
      "N1": 2, "N2": 4, "N3": 8, "N4": 12
    },
    "max_duration_hours": 3.0
  }
}
```

## 📈 Data Model

### BigQuery Tables

#### `poi_events_raw`
Raw API data with full event details
- Partitioned by `event_date` 
- Clustered by `filial`, `fence_description`, `vehicle_plate`
- 2-year retention

#### `poi_events_processed` 
Cleaned and consolidated events
- Business logic applied (consolidation, timezone conversion)
- Optimized for deviation detection queries

#### `poi_deviations`
Detected deviations and alert history
- Escalation tracking and state management
- 3-year retention for compliance

#### `alert_history`
Complete alert delivery log
- Multi-channel delivery tracking
- Retry and error information

### Firestore Collections

#### `alert_states`
Real-time alert status tracking
- Current escalation levels
- Delivery status and history
- Auto-cleanup after 7 days

#### `system_settings`
Configuration and recipients
- Global system parameters
- Alert channel settings
- POI group mappings cache

## 🔒 Security Features

### Multi-Layered Security

- **IAM**: Custom roles with least privilege access
- **Service Accounts**: Dedicated accounts per function
- **VPC**: Private networking with controlled egress
- **Secrets**: Encrypted credential storage with rotation
- **Audit**: Comprehensive logging and compliance

### Access Controls

```yaml
poi-data-collector:
  - bigquery.dataEditor (poi_monitoring only)
  - secretmanager.secretAccessor (API creds only)
  - storage.objectViewer (config bucket only)

poi-deviation-detector:
  - bigquery.dataViewer (poi_monitoring)
  - firestore.user (alert_states)
  - pubsub.publisher (deviation alerts only)

poi-alert-manager:
  - firestore.user (alert_states, system_settings)
  - secretmanager.secretAccessor (SMTP creds only)
  - bigquery.dataEditor (alert_history only)
```

### Network Security

- Private VPC with Cloud NAT for outbound access
- Firewall rules allowing only necessary traffic
- Cloud Armor WAF with rate limiting
- VPC Service Controls (optional)

## 📊 Monitoring & Operations

### System Metrics

- **Data Collection**: API response times, error rates, event volumes
- **Processing**: Deviation detection accuracy, processing latency
- **Alerts**: Delivery success rates, channel performance
- **Infrastructure**: Function execution times, costs, resource usage

### Operational Dashboards

1. **Real-time Status**: Active alerts, system health
2. **Historical Analytics**: Trend analysis, POI performance
3. **Security Monitoring**: Access logs, failed attempts
4. **Cost Monitoring**: Resource usage, budget alerts

### Troubleshooting

#### Common Issues

**No events being collected**:
```bash
# Check data collector logs
gcloud functions logs read poi-data-collector --limit=20

# Verify API credentials
gcloud secrets versions access latest --secret=creare-client-id
```

**Alerts not being sent**:
```bash
# Check alert manager logs
gcloud functions logs read poi-alert-manager --limit=20

# Verify SMTP configuration  
gcloud secrets versions access latest --secret=smtp-config
```

**Deviation detection not working**:
```bash
# Check deviation detector logs
gcloud functions logs read poi-deviation-detector --limit=20

# Query active sessions
bq query "SELECT COUNT(*) FROM poi_monitoring.poi_events_processed WHERE exit_timestamp IS NULL"
```

### Performance Optimization

#### BigQuery Optimization
- Use partitioning for time-based queries
- Cluster tables by common filter columns
- Optimize SQL queries with proper predicates
- Use materialized views for complex aggregations

#### Function Optimization
- Right-size memory allocation (512MB-1GB)
- Implement proper error handling and retries
- Use connection pooling for external services
- Cache configuration data in memory

#### Cost Optimization
- Monitor BigQuery slot usage and queries
- Use appropriate storage classes for Cloud Storage
- Implement lifecycle policies for old data
- Set up budget alerts and spending controls

## 🔄 Maintenance & Updates

### Regular Maintenance Tasks

**Weekly**:
- Review system performance metrics
- Check error rates and failed alerts
- Verify data quality and completeness

**Monthly**:
- Update POI configurations as needed
- Review and rotate API credentials
- Analyze cost reports and optimize

**Quarterly**:
- Update alert recipient lists
- Review security policies and access
- Performance tuning and capacity planning

### Update Procedures

#### Code Updates
```bash
# Update function code
gcloud functions deploy poi-data-collector \
    --source=cloud-functions/data-collector \
    --trigger-topic=hourly-data-collection

# Test in staging first
gcloud functions call poi-data-collector --data='{}'
```

#### Configuration Updates
```bash
# Update POI groups
gsutil cp Grupos.csv gs://poi-config-bucket/poi_groups.csv

# Update Firestore configurations via console or API
```

#### Schema Updates
```sql
-- Add new columns to existing tables
ALTER TABLE `poi_monitoring.poi_events_processed`
ADD COLUMN new_field STRING;

-- Create new tables as needed
CREATE TABLE `poi_monitoring.new_feature_table` (...);
```

## 📞 Support & Troubleshooting

### Support Contacts

- **System Administration**: admin@company.com
- **Business Operations**: operations@company.com  
- **Technical Support**: tech-support@company.com

### Documentation Links

- [GCP Architecture Details](/gcp-architecture.md)
- [Database Schema Reference](/database-schema.sql)
- [Security Framework](/security/security-framework.md) 
- [Backend Architecture](/backend-architecture.md)

### Emergency Procedures

**System Outage**:
1. Check Cloud Function status and logs
2. Verify BigQuery and Firestore connectivity
3. Review recent deployments and rollback if needed
4. Escalate to GCP support if infrastructure issue

**Data Loss or Corruption**:
1. Stop data processing functions immediately
2. Identify scope and timeline of issue
3. Restore from BigQuery backups if available
4. Implement data recovery procedures

**Security Incident**:
1. Document the incident timeline
2. Review audit logs and access patterns  
3. Rotate compromised credentials immediately
4. Report to security team and stakeholders

## 🎯 Roadmap & Future Enhancements

### Near-term (3 months)
- [ ] Mobile app for alert management
- [ ] Advanced analytics dashboard
- [ ] Machine learning for predictive alerts
- [ ] WhatsApp integration for alerts

### Medium-term (6 months)  
- [ ] Multi-region deployment for DR
- [ ] Integration with fleet management systems
- [ ] Automated incident response workflows
- [ ] Advanced reporting and BI tools

### Long-term (12 months)
- [ ] IoT sensor integration
- [ ] Computer vision for vehicle recognition  
- [ ] Blockchain for audit trail immutability
- [ ] AI-powered root cause analysis

## 📚 Legacy System (Preserved)

### Original Script: `scripts/pontos_notaveis/gerar_relatorio_pontos_notaveis.py`

The original implementation is preserved for reference and migration purposes:

**Functionality:**
- Fetches events from last 5 hours via CREARE API
- Filters by specific POIs (RRP and TLS)
- Consolidates consecutive events from same vehicle/POI
- Classifies POIs using `Grupos.csv` mapping
- Generates detailed CSV reports

**Usage:**
```bash
cd /mnt/c/Users/eusebioagj/OneDrive/Sentinela_BD
python3 scripts/pontos_notaveis/gerar_relatorio_pontos_notaveis.py
```

**Output Format:**
- File: `pontos_notaveis_FILTRO_POIS_[timestamp].csv`
- Fields: Filial, Placa_Veiculo, Descricao_POI, Grupo_POI, Data_Entrada, Data_Saida, Status, Duracao

---

## 📄 License

This project is proprietary software owned by [Your Company]. All rights reserved.

## 👥 Contributors

- **Project Coordinator**: Jarvis (AI Assistant)
- **Original System**: Based on existing Sentinela BD implementation
- **Cloud Architecture**: GCP Infrastructure Specialist
- **Database Design**: BigQuery Data Specialist  
- **Backend Development**: API Integration & Backend System Specialists
- **Security Framework**: GCP Security Specialist
- **Documentation**: Pipeline Documentation Specialist

---

**Last Updated**: August 8, 2025  
**Version**: 1.0.0  
**Status**: Production Ready