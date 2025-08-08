# POI Monitoring System - Complete Deployment Guide

## 🎯 Overview

This guide provides step-by-step instructions for deploying the comprehensive POI Deviation Detection System on Google Cloud Platform. The system transforms your existing on-demand POI monitoring into a 24/7 automated alerting platform.

## 📋 Pre-Deployment Checklist

### Prerequisites Verification

- [ ] Google Cloud Platform account with billing enabled
- [ ] Project with Owner or Editor permissions
- [ ] `gcloud` CLI installed and authenticated
- [ ] Domain for email alerts (with SMTP access)
- [ ] SMS service account (Twilio, etc.) - optional
- [ ] Existing Creare Cloud API credentials
- [ ] 30-60 minutes for full deployment

### GCP Project Setup

```bash
# Create new project (optional)
gcloud projects create poi-monitoring-prod --name="POI Monitoring Production"

# Set active project
gcloud config set project poi-monitoring-prod

# Enable billing (required)
gcloud billing projects link poi-monitoring-prod --billing-account=YOUR_BILLING_ACCOUNT_ID

# Verify project setup
gcloud config list
gcloud auth list
```

## 🚀 Phase 1: Security Foundation

### Step 1: Deploy Security Framework

```bash
# Navigate to project directory
cd /path/to/Sentinela_BD

# Update project ID in scripts
export PROJECT_ID="poi-monitoring-prod"  # Replace with your project ID
sed -i 's/poi-monitoring-prod/'$PROJECT_ID'/g' security/setup-security.sh
sed -i 's/poi-monitoring-prod/'$PROJECT_ID'/g' deployment/deploy.sh

# Execute security setup
chmod +x security/setup-security.sh
./security/setup-security.sh
```

**Expected Duration**: 10-15 minutes

**What This Creates**:
- 4 service accounts with least privilege access
- 3 custom IAM roles
- VPC network with private subnets
- Cloud Armor WAF protection
- Secret Manager setup
- Firewall rules and security policies

### Step 2: Configure Secrets

```bash
# Add API credentials (replace with your actual values)
echo "56963" | gcloud secrets versions add creare-client-id --data-file=-
echo "1MSiBaH879w=" | gcloud secrets versions add creare-client-secret --data-file=-

# Create SMTP configuration file
cat > smtp-config.json << EOF
{
    "smtp_server": "smtp.gmail.com",
    "smtp_port": 587,
    "username": "alerts@yourcompany.com",
    "password": "your_app_password",
    "from_address": "alerts@yourcompany.com"
}
EOF

# Add SMTP configuration
gcloud secrets versions add smtp-config --data-file=smtp-config.json

# Clean up temporary file
rm smtp-config.json

# Verify secrets
gcloud secrets list
```

## 🏗️ Phase 2: Infrastructure Deployment

### Step 3: Deploy Core Infrastructure

```bash
# Execute main deployment
chmod +x deployment/deploy.sh
./deployment/deploy.sh
```

**Expected Duration**: 15-20 minutes

**What This Creates**:
- BigQuery dataset and tables
- Cloud Storage bucket for configuration
- 3 Cloud Functions
- Pub/Sub topics
- Cloud Scheduler jobs
- Firestore database

### Step 4: Verify Infrastructure Deployment

```bash
# Check Cloud Functions
gcloud functions list --filter="name:poi-"

# Check BigQuery dataset
bq ls poi_monitoring

# Check Pub/Sub topics
gcloud pubsub topics list | grep poi

# Check Cloud Scheduler jobs
gcloud scheduler jobs list --location=us-central1

# Check secrets
gcloud secrets list --filter="name:creare OR name:smtp"
```

Expected output:
```
NAME                    STATUS   TRIGGER        REGION
poi-alert-manager       ACTIVE   eventTrigger   us-central1
poi-data-collector      ACTIVE   eventTrigger   us-central1
poi-deviation-detector  ACTIVE   eventTrigger   us-central1

poi_events_raw
poi_events_processed
poi_deviations
alert_history
```

## ⚙️ Phase 3: Configuration Setup

### Step 5: Upload POI Configuration

```bash
# Upload your POI groups file
gsutil cp Grupos.csv gs://poi-config-bucket-$PROJECT_ID/poi_groups.csv

# Verify upload
gsutil ls gs://poi-config-bucket-$PROJECT_ID/
```

### Step 6: Configure Firestore

```bash
# The deployment script creates /tmp/firestore-init.json
# Review and customize the configuration
cat /tmp/firestore-init.json

# Import via Firestore console or use Firebase CLI
# https://console.cloud.google.com/firestore

# Or import via gcloud (if available)
# gcloud firestore import gs://firestore-backup-bucket/firestore-init.json
```

**Key Configurations to Update**:
1. **Alert Recipients** (`system_settings/alert_recipients`):
   - Replace example emails with actual recipient addresses
   - Add SMS numbers for each facility (RRP/TLS)
   - Configure escalation matrix by alert level

2. **POI Thresholds** (`poi_configurations`):
   - Customize deviation thresholds per POI if needed
   - Set operating hours and maintenance windows

### Step 7: Initialize Firestore Manually

If automatic import isn't available, manually create these documents in Firestore:

**Collection: `system_settings`**

**Document: `global_config`**
```json
{
  "api_config": {
    "creare_cloud": {
      "base_url": "https://api.crearecloud.com.br",
      "timeout_seconds": 30,
      "retry_count": 3,
      "rate_limit_per_minute": 60
    }
  },
  "alert_config": {
    "channels": {
      "email": {
        "enabled": true
      },
      "sms": {
        "enabled": false
      }
    },
    "delivery_config": {
      "max_retries": 3,
      "retry_delay_minutes": 5
    }
  }
}
```

**Document: `alert_recipients`**
```json
{
  "by_filial": {
    "RRP": {
      "email": [
        "manager.rrp@yourcompany.com",
        "operations.rrp@yourcompany.com"
      ],
      "sms": [
        "+5567999999999"
      ]
    },
    "TLS": {
      "email": [
        "manager.tls@yourcompany.com",
        "operations.tls@yourcompany.com"
      ],
      "sms": [
        "+5567888888888"
      ]
    }
  },
  "by_level": {
    "N1": ["operations"],
    "N2": ["operations", "supervisors"],
    "N3": ["operations", "supervisors", "managers"], 
    "N4": ["operations", "supervisors", "managers", "directors"]
  },
  "escalation_matrix": {
    "N1": {
      "channels": ["email"],
      "delay_minutes": 0
    },
    "N2": {
      "channels": ["email"],
      "delay_minutes": 5
    },
    "N3": {
      "channels": ["email", "sms"],
      "delay_minutes": 0
    },
    "N4": {
      "channels": ["email", "sms"],
      "delay_minutes": 0
    }
  }
}
```

## 🧪 Phase 4: Testing & Validation

### Step 8: System Testing

```bash
# Test 1: Manual data collection
echo "Testing data collection..."
gcloud scheduler jobs run data-collection-schedule --location=us-central1

# Wait 2-3 minutes and check logs
gcloud functions logs read poi-data-collector --limit=20

# Test 2: Manual deviation detection
echo "Testing deviation detection..."
gcloud scheduler jobs run deviation-detection-schedule --location=us-central1

# Check logs
gcloud functions logs read poi-deviation-detector --limit=20

# Test 3: Query collected data
echo "Checking data collection..."
bq query "SELECT COUNT(*) as event_count FROM poi_monitoring.poi_events_raw WHERE DATE(event_date) = CURRENT_DATE()"
```

### Step 9: End-to-End Testing

```bash
# Monitor system execution
echo "Monitoring system execution..."

# Watch data collection logs
gcloud functions logs tail poi-data-collector &

# In another terminal, watch deviation detection
gcloud functions logs tail poi-deviation-detector &

# In a third terminal, watch alert delivery
gcloud functions logs tail poi-alert-manager &

# Trigger full cycle
gcloud scheduler jobs run data-collection-schedule --location=us-central1

# Wait 5 minutes for full processing cycle
sleep 300

# Check results
bq query "SELECT filial, poi_name, COUNT(*) as events FROM poi_monitoring.poi_events_processed WHERE DATE(event_date) = CURRENT_DATE() GROUP BY filial, poi_name ORDER BY events DESC"
```

### Step 10: Alert Testing

For controlled alert testing, you may need to adjust thresholds temporarily:

```bash
# Query current active sessions to see potential test subjects
bq query "
SELECT 
  vehicle_plate,
  poi_name, 
  filial,
  entry_timestamp,
  DATETIME_DIFF(CURRENT_DATETIME(), entry_timestamp, HOUR) as hours_in_poi
FROM poi_monitoring.poi_events_processed 
WHERE exit_timestamp IS NULL 
AND DATE(event_date) >= DATE_SUB(CURRENT_DATE(), INTERVAL 1 DAY)
ORDER BY hours_in_poi DESC
LIMIT 10"
```

## 🎛️ Phase 5: Operations Setup

### Step 11: Monitoring Dashboard

1. **Access Cloud Console**:
   - Functions: https://console.cloud.google.com/functions
   - BigQuery: https://console.cloud.google.com/bigquery
   - Firestore: https://console.cloud.google.com/firestore
   - Scheduler: https://console.cloud.google.com/cloudscheduler

2. **Set Up Monitoring Alerts**:
```bash
# Create notification channel (email)
gcloud alpha monitoring channels create \
  --display-name="POI System Alerts" \
  --type=email \
  --channel-labels=email_address=admin@yourcompany.com

# Get notification channel ID
CHANNEL_ID=$(gcloud alpha monitoring channels list --filter="displayName:'POI System Alerts'" --format="value(name)")

# Create alerting policy for function failures
gcloud alpha monitoring policies create \
  --policy-from-file=- << EOF
displayName: "POI Functions - Error Rate"
conditions:
- displayName: "Function error rate"
  conditionThreshold:
    filter: 'resource.type="cloud_function" AND resource.label.function_name=~"poi-.*"'
    comparison: COMPARISON_GREATER_THAN
    thresholdValue: 0.1
    duration: 300s
notificationChannels: ["$CHANNEL_ID"]
EOF
```

### Step 12: Performance Monitoring

```bash
# Create dashboard for system metrics
echo "Creating monitoring dashboard..."

# Set up log-based metrics
gcloud logging metrics create poi_processing_errors \
  --description="POI processing errors" \
  --log-filter='resource.type="cloud_function" AND resource.labels.function_name=~"poi-.*" AND severity>=ERROR'

gcloud logging metrics create poi_api_calls \
  --description="POI API calls" \
  --log-filter='resource.type="cloud_function" AND resource.labels.function_name="poi-data-collector" AND textPayload=~"API.*"'

# Set up cost monitoring
gcloud alpha billing budgets create \
  --billing-account=YOUR_BILLING_ACCOUNT \
  --display-name="POI Monitoring Budget" \
  --budget-amount=100.00 \
  --threshold-rules-percent-threshold=0.5,0.9 \
  --threshold-rules-spend-basis=current-spend
```

## ✅ Phase 6: Validation & Go-Live

### Step 13: Production Readiness Checklist

- [ ] All Cloud Functions deployed and responding
- [ ] BigQuery tables created and receiving data
- [ ] Firestore configuration properly set
- [ ] Alert recipients configured correctly
- [ ] Secrets properly configured
- [ ] Test alerts received successfully
- [ ] Monitoring and alerting configured
- [ ] Documentation reviewed by operations team
- [ ] Backup and recovery procedures tested

### Step 14: Go-Live

```bash
# Final system health check
echo "🔍 Final system health check..."

# Check all functions are healthy
gcloud functions list --filter="name:poi-" --format="table(name,status,trigger.eventTrigger.eventType)"

# Check recent data collection
bq query "SELECT MAX(processed_at) as last_collection FROM poi_monitoring.poi_events_raw"

# Check scheduler jobs
gcloud scheduler jobs list --location=us-central1 --filter="name:*-schedule"

# Test manual trigger one final time
echo "🧪 Final end-to-end test..."
gcloud scheduler jobs run data-collection-schedule --location=us-central1

echo "✅ System is live and operational!"
echo "📊 Monitor at: https://console.cloud.google.com/functions"
```

## 🔄 Post-Deployment Operations

### Daily Operations

```bash
# Check system health
gcloud functions list --filter="name:poi-" --format="value(status)"

# Review error logs
gcloud functions logs read poi-data-collector --severity=ERROR --limit=10
gcloud functions logs read poi-deviation-detector --severity=ERROR --limit=10
gcloud functions logs read poi-alert-manager --severity=ERROR --limit=10

# Check data freshness
bq query "SELECT MAX(processed_at) as last_update FROM poi_monitoring.poi_events_processed"
```

### Weekly Operations

```bash
# Performance review
echo "📈 Weekly performance report"

# Data volume trends
bq query "
SELECT 
  DATE(processed_at) as date,
  COUNT(*) as events,
  COUNT(DISTINCT vehicle_plate) as vehicles,
  COUNT(DISTINCT poi_name) as pois_active
FROM poi_monitoring.poi_events_processed
WHERE processed_at >= DATETIME_SUB(CURRENT_DATETIME(), INTERVAL 7 DAY)
GROUP BY DATE(processed_at)
ORDER BY date DESC"

# Alert performance
bq query "
SELECT 
  alert_level,
  COUNT(*) as alerts_sent,
  AVG(delivery_attempts) as avg_attempts
FROM poi_monitoring.alert_history
WHERE alert_date >= DATE_SUB(CURRENT_DATE(), INTERVAL 7 DAY)
GROUP BY alert_level
ORDER BY alert_level"

# Cost analysis
gcloud billing accounts list
```

## 🚨 Troubleshooting

### Common Issues and Solutions

**Issue: No data being collected**
```bash
# Check API credentials
gcloud secrets versions access latest --secret=creare-client-id
gcloud secrets versions access latest --secret=creare-client-secret

# Check function permissions
gcloud projects get-iam-policy $PROJECT_ID --flatten="bindings[].members" --filter="bindings.members:poi-data-collector"

# Manual function test
gcloud functions call poi-data-collector --data='{}'
```

**Issue: Alerts not being sent**
```bash
# Check SMTP configuration
gcloud secrets versions access latest --secret=smtp-config

# Check alert manager logs
gcloud functions logs read poi-alert-manager --limit=50

# Check Firestore configuration
# Use Firestore console to verify alert_recipients document
```

**Issue: High costs**
```bash
# Check BigQuery usage
bq query "SELECT job_type, user_email, total_bytes_processed/1024/1024/1024 as gb_processed FROM \`region-us\`.INFORMATION_SCHEMA.JOBS_BY_PROJECT WHERE creation_time >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 24 HOUR) ORDER BY total_bytes_processed DESC"

# Check function execution frequency
gcloud functions metrics read poi-data-collector --start-time=2025-08-07T00:00:00Z --end-time=2025-08-08T00:00:00Z
```

## 📞 Support Contacts

- **Technical Issues**: Create issue in project repository
- **GCP Billing**: Check Google Cloud Console billing section  
- **API Issues**: Contact Creare Cloud support
- **Emergency**: Check emergency procedures in main README

---

## ✅ Deployment Complete!

Your POI Deviation Detection System is now operational with:

- ✅ 24/7 automated monitoring
- ✅ N1-N4 escalation alerts  
- ✅ Multi-channel delivery (Email/SMS)
- ✅ Comprehensive security framework
- ✅ Scalable cloud infrastructure
- ✅ Real-time dashboards and monitoring

**Next Steps**:
1. Monitor system performance for first 48 hours
2. Fine-tune alert thresholds based on initial data
3. Train operations team on monitoring procedures
4. Schedule regular maintenance and updates

**System URLs**:
- Cloud Functions: `https://console.cloud.google.com/functions?project=$PROJECT_ID`
- BigQuery: `https://console.cloud.google.com/bigquery?project=$PROJECT_ID`
- Firestore: `https://console.cloud.google.com/firestore?project=$PROJECT_ID`
- Monitoring: `https://console.cloud.google.com/monitoring?project=$PROJECT_ID`

**Congratulations! Your POI monitoring system is now production ready! 🎉**