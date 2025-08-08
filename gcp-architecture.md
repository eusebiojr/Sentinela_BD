# GCP Infrastructure Architecture - POI Deviation Detection System

## System Overview
24/7 automated POI deviation detection system with escalating alerts for RRP and TLS facilities.

## Architecture Components

### 1. Data Collection Layer
```
Cloud Scheduler (Hourly Trigger)
    ↓
Cloud Function: data-collector
    ↓
Creare Cloud API
    ↓
BigQuery: poi_events_raw
```

**Cloud Function: `poi-data-collector`**
- **Runtime**: Python 3.11
- **Memory**: 512MB
- **Timeout**: 5 minutes
- **Trigger**: Cloud Scheduler (every hour at :00)
- **Responsibilities**:
  - Fetch POI events from Creare Cloud API
  - Apply POI filtering (RRP/TLS specific)
  - Store raw data in BigQuery
  - Handle API rate limits and retries
  - Log collection metrics

### 2. Processing & Detection Layer
```
Cloud Function: deviation-detector
    ↓
BigQuery: Query historical data
    ↓
Deviation Logic (N1-N4 escalation)
    ↓
Cloud Firestore: alert_state
```

**Cloud Function: `poi-deviation-detector`**
- **Runtime**: Python 3.11
- **Memory**: 1GB
- **Timeout**: 10 minutes
- **Trigger**: Cloud Scheduler (every hour at :05)
- **Responsibilities**:
  - Analyze collected data for deviations
  - Implement group-based detection logic
  - Manage escalation states (N1→N2→N3→N4)
  - Generate alert payloads
  - Update alert states in Firestore

### 3. Alert Management Layer
```
Cloud Function: alert-manager
    ↓
Email/SMS/Webhook Delivery
    ↓
Cloud Logging: alert_history
```

**Cloud Function: `poi-alert-manager`**
- **Runtime**: Python 3.11
- **Memory**: 256MB
- **Timeout**: 3 minutes
- **Trigger**: Pub/Sub from deviation-detector
- **Responsibilities**:
  - Format alerts per specification: `{FILIAL}_{POI_SEM_ESPACOS}_{NIVEL}_{DDMMYYYY}_{HHMMSS}`
  - Send alerts via multiple channels
  - Prevent duplicate alerts
  - Log all alert activities

### 4. Data Storage Layer

**BigQuery Dataset: `poi_monitoring`**

Tables:
- `poi_events_raw` - Raw API data
- `poi_events_processed` - Cleaned and consolidated data
- `poi_deviations` - Detected deviations
- `alert_history` - Alert delivery log

**Cloud Firestore: `poi_system_state`**

Collections:
- `alert_states` - Current alert levels per POI/vehicle
- `configurations` - System parameters and thresholds
- `poi_mappings` - POI group classifications

### 5. Configuration Management
```
Cloud Storage: config-bucket
    ├── poi_groups.csv (uploaded from your Grupos.csv)
    ├── alert_thresholds.json
    └── system_config.json
```

### 6. Monitoring & Operations

**Cloud Monitoring**
- Custom metrics for API health
- Alert on function failures
- Performance dashboards

**Cloud Logging**
- Structured logs for all components
- Error aggregation and alerting

## Resource Specifications

### Compute Resources
```yaml
data-collector:
  memory: 512MB
  timeout: 300s
  max_instances: 1
  
deviation-detector:
  memory: 1GB
  timeout: 600s
  max_instances: 2
  
alert-manager:
  memory: 256MB
  timeout: 180s
  max_instances: 5
```

### Storage Resources
```yaml
BigQuery:
  dataset: poi_monitoring
  location: us-central1
  partition: by day
  retention: 2 years

Firestore:
  database: poi-system
  location: us-central1
  mode: native

Cloud Storage:
  bucket: poi-config-bucket
  location: us-central1
  storage_class: standard
```

## Deployment Architecture

### Environment Structure
```
Production:
  - Project: poi-monitoring-prod
  - Region: us-central1
  - Network: poi-vpc-prod

Development:
  - Project: poi-monitoring-dev
  - Region: us-central1
  - Network: poi-vpc-dev
```

### CI/CD Pipeline
```yaml
Source: GitHub/Cloud Source Repositories
Build: Cloud Build
Deploy: Cloud Functions, BigQuery, Firestore
Test: Automated integration tests
```

## Security Architecture

### Identity & Access Management
- Service accounts for each function
- Least privilege access principles
- API key rotation strategy

### Network Security
- Private networking where possible
- Firewall rules for external API access
- VPC security controls

### Data Security
- Encryption at rest (automatic)
- Encryption in transit (HTTPS/TLS)
- Audit logging enabled

## Monitoring & Alerting

### Key Metrics
- API response times
- Data processing latency
- Alert delivery success rate
- Function error rates
- Cost monitoring

### Alert Channels
- Email for critical failures
- PagerDuty for system outages
- Slack for operational notifications

## Cost Optimization

### Estimated Monthly Costs (USD)
```
Cloud Functions: $20-50
BigQuery: $30-100
Firestore: $10-30
Cloud Storage: $5-15
Monitoring/Logging: $10-25
Total: $75-220/month
```

### Cost Control Measures
- Function timeout optimization
- BigQuery query optimization
- Firestore read/write optimization
- Automatic resource scaling

## Disaster Recovery

### Backup Strategy
- BigQuery automatic backups
- Firestore automated exports
- Configuration file versioning

### Recovery Procedures
- Function redeployment automation
- Data restoration procedures
- System state recovery

## Performance Specifications

### SLA Targets
- Data Collection: 99.9% uptime
- Alert Delivery: < 5 minutes from detection
- API Response: < 30 seconds
- System Recovery: < 15 minutes

### Scaling Parameters
- Auto-scaling based on workload
- Maximum concurrent executions
- Resource utilization thresholds

## Integration Points

### External Systems
- Creare Cloud API (OAuth2)
- Email/SMS providers
- Monitoring dashboards
- Business intelligence tools

### Data Formats
- Input: JSON from API
- Processing: Structured data
- Output: Formatted alerts
- Storage: Optimized schemas

This architecture provides a robust, scalable, and cost-effective foundation for your 24/7 POI deviation detection system.