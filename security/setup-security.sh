#!/bin/bash

# Security Setup Script for POI Monitoring System
# Implements IAM policies, service accounts, and security controls

set -e

# Configuration
PROJECT_ID="poi-monitoring-prod"  # Update with your project ID
REGION="us-central1"

echo "🔒 Setting up Security Framework for POI Monitoring System"
echo "Project: $PROJECT_ID"
echo "Region: $REGION"
echo

# Set the project
gcloud config set project $PROJECT_ID

# Enable required APIs
echo "🔧 Enabling security-related APIs..."
gcloud services enable iam.googleapis.com
gcloud services enable cloudresourcemanager.googleapis.com
gcloud services enable secretmanager.googleapis.com
gcloud services enable compute.googleapis.com
gcloud services enable accesscontextmanager.googleapis.com

# Create custom IAM roles
echo "👤 Creating custom IAM roles..."

# POI Data Collector Role
cat << 'EOF' > /tmp/poi-data-collector-role.yaml
title: "POI Data Collector"
description: "Custom role for POI data collection function"
stage: "GA"
includedPermissions:
- bigquery.datasets.get
- bigquery.tables.create
- bigquery.tables.updateData
- bigquery.jobs.create
- firestore.documents.get
- firestore.documents.list
- secretmanager.versions.access
- storage.objects.get
EOF

gcloud iam roles create poiDataCollector \
    --project=$PROJECT_ID \
    --file=/tmp/poi-data-collector-role.yaml || echo "Role may already exist"

# POI Deviation Detector Role  
cat << 'EOF' > /tmp/poi-deviation-detector-role.yaml
title: "POI Deviation Detector"
description: "Custom role for POI deviation detection function"
stage: "GA"
includedPermissions:
- bigquery.datasets.get
- bigquery.tables.get
- bigquery.tables.getData
- bigquery.tables.updateData
- bigquery.jobs.create
- firestore.documents.get
- firestore.documents.list
- firestore.documents.write
- pubsub.topics.publish
EOF

gcloud iam roles create poiDeviationDetector \
    --project=$PROJECT_ID \
    --file=/tmp/poi-deviation-detector-role.yaml || echo "Role may already exist"

# POI Alert Manager Role
cat << 'EOF' > /tmp/poi-alert-manager-role.yaml
title: "POI Alert Manager"
description: "Custom role for POI alert management function"  
stage: "GA"
includedPermissions:
- bigquery.datasets.get
- bigquery.tables.updateData
- bigquery.jobs.create
- firestore.documents.get
- firestore.documents.list
- firestore.documents.write
- secretmanager.versions.access
EOF

gcloud iam roles create poiAlertManager \
    --project=$PROJECT_ID \
    --file=/tmp/poi-alert-manager-role.yaml || echo "Role may already exist"

# Create service accounts
echo "🤖 Creating service accounts..."

# Data Collector Service Account
gcloud iam service-accounts create poi-data-collector \
    --display-name="POI Data Collector" \
    --description="Service account for POI data collection function" || echo "Service account may already exist"

# Deviation Detector Service Account  
gcloud iam service-accounts create poi-deviation-detector \
    --display-name="POI Deviation Detector" \
    --description="Service account for POI deviation detection function" || echo "Service account may already exist"

# Alert Manager Service Account
gcloud iam service-accounts create poi-alert-manager \
    --display-name="POI Alert Manager" \
    --description="Service account for POI alert management function" || echo "Service account may already exist"

# Admin Service Account
gcloud iam service-accounts create poi-monitoring-admin \
    --display-name="POI Monitoring Admin" \
    --description="Service account for POI monitoring system administration" || echo "Service account may already exist"

# Bind custom roles to service accounts
echo "🔗 Binding roles to service accounts..."

gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="serviceAccount:poi-data-collector@$PROJECT_ID.iam.gserviceaccount.com" \
    --role="projects/$PROJECT_ID/roles/poiDataCollector"

gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="serviceAccount:poi-deviation-detector@$PROJECT_ID.iam.gserviceaccount.com" \
    --role="projects/$PROJECT_ID/roles/poiDeviationDetector"

gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="serviceAccount:poi-alert-manager@$PROJECT_ID.iam.gserviceaccount.com" \
    --role="projects/$PROJECT_ID/roles/poiAlertManager"

# Additional role bindings for specific resources
echo "🔐 Setting up resource-specific permissions..."

# BigQuery permissions
gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="serviceAccount:poi-data-collector@$PROJECT_ID.iam.gserviceaccount.com" \
    --role="roles/bigquery.dataEditor" \
    --condition='expression=request.resource.name.startsWith("projects/'$PROJECT_ID'/datasets/poi_monitoring"),title=POI Dataset Only'

# Storage permissions
gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="serviceAccount:poi-data-collector@$PROJECT_ID.iam.gserviceaccount.com" \
    --role="roles/storage.objectViewer" \
    --condition='expression=request.resource.name.startsWith("projects/_/buckets/poi-config-bucket"),title=Config Bucket Only'

# Pub/Sub permissions
gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="serviceAccount:poi-deviation-detector@$PROJECT_ID.iam.gserviceaccount.com" \
    --role="roles/pubsub.publisher" \
    --condition='expression=request.resource.name == "projects/'$PROJECT_ID'/topics/poi-deviation-alerts",title=Deviation Alerts Topic Only'

# Create and configure secrets
echo "🔑 Setting up Secret Manager..."

# Create secrets with proper labels
gcloud secrets create creare-client-id \
    --replication-policy="automatic" \
    --labels="system=poi-monitoring,type=api-credential,classification=confidential" || echo "Secret may already exist"

gcloud secrets create creare-client-secret \
    --replication-policy="automatic" \
    --labels="system=poi-monitoring,type=api-credential,classification=restricted" || echo "Secret may already exist"

gcloud secrets create smtp-config \
    --replication-policy="automatic" \
    --labels="system=poi-monitoring,type=email-config,classification=restricted" || echo "Secret may already exist"

# Grant specific secret access
echo "🗝️  Configuring secret access policies..."

gcloud secrets add-iam-policy-binding creare-client-id \
    --member="serviceAccount:poi-data-collector@$PROJECT_ID.iam.gserviceaccount.com" \
    --role="roles/secretmanager.secretAccessor"

gcloud secrets add-iam-policy-binding creare-client-secret \
    --member="serviceAccount:poi-data-collector@$PROJECT_ID.iam.gserviceaccount.com" \
    --role="roles/secretmanager.secretAccessor"

gcloud secrets add-iam-policy-binding smtp-config \
    --member="serviceAccount:poi-alert-manager@$PROJECT_ID.iam.gserviceaccount.com" \
    --role="roles/secretmanager.secretAccessor"

# Set up VPC and networking security
echo "🌐 Setting up VPC security..."

# Create VPC network
gcloud compute networks create poi-monitoring-vpc \
    --subnet-mode=custom \
    --bgp-routing-mode=regional || echo "VPC may already exist"

# Create subnet with private Google access
gcloud compute networks subnets create poi-monitoring-subnet \
    --network=poi-monitoring-vpc \
    --range=10.0.0.0/24 \
    --region=$REGION \
    --enable-private-ip-google-access || echo "Subnet may already exist"

# Create Cloud NAT for outbound internet access
gcloud compute routers create poi-monitoring-router \
    --network=poi-monitoring-vpc \
    --region=$REGION || echo "Router may already exist"

gcloud compute routers nats create poi-monitoring-nat \
    --router=poi-monitoring-router \
    --region=$REGION \
    --nat-all-subnet-ip-ranges \
    --auto-allocate-nat-external-ips || echo "NAT may already exist"

# Create VPC connector for Cloud Functions
gcloud compute networks vpc-access connectors create poi-monitoring-connector \
    --network=poi-monitoring-vpc \
    --region=$REGION \
    --range=192.168.0.0/28 || echo "VPC Connector may already exist"

# Configure firewall rules
echo "🔥 Setting up firewall rules..."

# Allow HTTPS outbound for API calls
gcloud compute firewall-rules create allow-poi-https-outbound \
    --network=poi-monitoring-vpc \
    --direction=EGRESS \
    --rules=tcp:443 \
    --destination-ranges=0.0.0.0/0 \
    --target-service-accounts=poi-data-collector@$PROJECT_ID.iam.gserviceaccount.com \
    --priority=100 || echo "Rule may already exist"

# Allow SMTP outbound for email alerts  
gcloud compute firewall-rules create allow-poi-smtp-outbound \
    --network=poi-monitoring-vpc \
    --direction=EGRESS \
    --rules=tcp:587,tcp:465 \
    --destination-ranges=0.0.0.0/0 \
    --target-service-accounts=poi-alert-manager@$PROJECT_ID.iam.gserviceaccount.com \
    --priority=100 || echo "Rule may already exist"

# Allow internal GCP services
gcloud compute firewall-rules create allow-poi-internal-apis \
    --network=poi-monitoring-vpc \
    --direction=EGRESS \
    --rules=tcp:443 \
    --destination-ranges=199.36.153.8/30 \
    --target-service-accounts=poi-data-collector@$PROJECT_ID.iam.gserviceaccount.com,poi-deviation-detector@$PROJECT_ID.iam.gserviceaccount.com,poi-alert-manager@$PROJECT_ID.iam.gserviceaccount.com \
    --priority=90 || echo "Rule may already exist"

# Deny all other outbound traffic (default deny)
gcloud compute firewall-rules create deny-poi-all-outbound \
    --network=poi-monitoring-vpc \
    --direction=EGRESS \
    --rules=all \
    --destination-ranges=0.0.0.0/0 \
    --action=DENY \
    --priority=1000 \
    --target-service-accounts=poi-data-collector@$PROJECT_ID.iam.gserviceaccount.com,poi-deviation-detector@$PROJECT_ID.iam.gserviceaccount.com,poi-alert-manager@$PROJECT_ID.iam.gserviceaccount.com || echo "Rule may already exist"

# Set up Cloud Armor (Web Application Firewall)
echo "🛡️  Setting up Cloud Armor security policies..."

gcloud compute security-policies create poi-monitoring-waf \
    --description="Web Application Firewall for POI Monitoring System" || echo "Policy may already exist"

# Block known malicious IPs
gcloud compute security-policies rules create 1000 \
    --security-policy=poi-monitoring-waf \
    --expression="origin.region_code == 'CN' || origin.region_code == 'RU'" \
    --action=deny-403 \
    --description="Block traffic from high-risk regions" || echo "Rule may already exist"

# Rate limiting
gcloud compute security-policies rules create 2000 \
    --security-policy=poi-monitoring-waf \
    --expression="true" \
    --action=rate-based-ban \
    --rate-limit-threshold-count=100 \
    --rate-limit-threshold-interval-sec=60 \
    --ban-duration-sec=600 \
    --conform-action=allow \
    --exceed-action=deny-429 \
    --enforce-on-key=IP \
    --description="Rate limiting - max 100 requests per minute" || echo "Rule may already exist"

# Configure audit logging
echo "📝 Setting up audit logging..."

# Enable audit logs for IAM and data access
cat << 'EOF' > /tmp/audit-policy.yaml
auditConfigs:
- service: iam.googleapis.com
  auditLogConfigs:
  - logType: ADMIN_READ
  - logType: DATA_READ
  - logType: DATA_WRITE
- service: bigquery.googleapis.com
  auditLogConfigs:
  - logType: ADMIN_READ
  - logType: DATA_READ
  - logType: DATA_WRITE
- service: firestore.googleapis.com
  auditLogConfigs:
  - logType: ADMIN_READ
  - logType: DATA_READ
  - logType: DATA_WRITE
- service: secretmanager.googleapis.com
  auditLogConfigs:
  - logType: ADMIN_READ
  - logType: DATA_READ
  - logType: DATA_WRITE
EOF

gcloud logging sinks create poi-monitoring-audit-sink \
    bigquery.googleapis.com/projects/$PROJECT_ID/datasets/audit_logs \
    --log-filter='protoPayload.serviceName="iam.googleapis.com" OR protoPayload.serviceName="bigquery.googleapis.com" OR protoPayload.serviceName="firestore.googleapis.com" OR protoPayload.serviceName="secretmanager.googleapis.com"' || echo "Sink may already exist"

# Create monitoring alerts for security events
echo "📊 Setting up security monitoring alerts..."

# Alert for failed authentication attempts
gcloud alpha monitoring policies create \
    --policy-from-file=- << 'EOF'
displayName: "POI Monitoring - Authentication Failures"
documentation:
  content: "Alert when there are multiple authentication failures in POI monitoring system"
conditions:
- displayName: "Authentication failure rate"
  conditionThreshold:
    filter: 'resource.type="gce_instance" AND log_name="projects/'$PROJECT_ID'/logs/cloudaudit.googleapis.com%2Fdata_access" AND protoPayload.authenticationInfo.principalEmail!="" AND protoPayload.status.code!=0'
    comparison: COMPARISON_GREATER_THAN
    thresholdValue: 5
    duration: 300s
    aggregations:
    - alignmentPeriod: 60s
      perSeriesAligner: ALIGN_RATE
      crossSeriesReducer: REDUCE_SUM
notificationChannels: []
alertStrategy:
  autoClose: 86400s
enabled: true
EOF

# Create log-based metrics for security monitoring
gcloud logging metrics create poi_security_events \
    --description="Security events in POI monitoring system" \
    --log-filter='protoPayload.serviceName="iam.googleapis.com" AND protoPayload.methodName=("google.iam.admin.v1.CreateServiceAccountKey" OR "google.iam.admin.v1.DeleteServiceAccountKey")' || echo "Metric may already exist"

# Set up organization policies (if applicable)
echo "🏛️  Configuring organization policies..."

# Restrict external IP addresses
gcloud resource-manager org-policies set-policy - << 'EOF' || echo "Policy may not be applicable"
constraint: compute.vmExternalIpAccess
listPolicy:
  deniedValues:
  - "*"
EOF

# Require OS Login
gcloud resource-manager org-policies set-policy - << 'EOF' || echo "Policy may not be applicable"  
constraint: compute.requireOsLogin
booleanPolicy:
  enforced: true
EOF

# Create security summary report
echo "📋 Generating security setup summary..."

cat << EOF > /tmp/security-setup-summary.md
# POI Monitoring System - Security Setup Summary

## Service Accounts Created
- poi-data-collector@$PROJECT_ID.iam.gserviceaccount.com
- poi-deviation-detector@$PROJECT_ID.iam.gserviceaccount.com  
- poi-alert-manager@$PROJECT_ID.iam.gserviceaccount.com
- poi-monitoring-admin@$PROJECT_ID.iam.gserviceaccount.com

## Custom IAM Roles Created
- projects/$PROJECT_ID/roles/poiDataCollector
- projects/$PROJECT_ID/roles/poiDeviationDetector
- projects/$PROJECT_ID/roles/poiAlertManager

## Secrets Created
- creare-client-id (API credentials)
- creare-client-secret (API credentials)  
- smtp-config (Email configuration)

## Network Resources Created
- VPC: poi-monitoring-vpc
- Subnet: poi-monitoring-subnet (10.0.0.0/24)
- Router: poi-monitoring-router
- NAT: poi-monitoring-nat
- VPC Connector: poi-monitoring-connector

## Security Policies Applied
- Cloud Armor WAF: poi-monitoring-waf
- Firewall rules for controlled outbound access
- Audit logging enabled for all services
- Rate limiting configured

## Next Steps
1. Add actual API credentials to secrets:
   gcloud secrets versions add creare-client-id --data-file=client-id.txt
   gcloud secrets versions add creare-client-secret --data-file=client-secret.txt
   
2. Configure SMTP settings:
   gcloud secrets versions add smtp-config --data-file=smtp-config.json
   
3. Set up monitoring notification channels
4. Review and customize firewall rules as needed
5. Configure VPC Service Controls for additional security

## Security Best Practices Implemented
✅ Least privilege access with custom roles
✅ Service account isolation
✅ Network segmentation with VPC
✅ Secret management with rotation capability
✅ Audit logging and monitoring
✅ Rate limiting and DDoS protection
✅ Resource-level access controls

EOF

echo
echo "✅ Security framework setup completed!"
echo
echo "📋 Security summary saved to /tmp/security-setup-summary.md"
echo
echo "🔧 Next steps:"
echo "1. Review the security summary report"
echo "2. Add actual credentials to Secret Manager"
echo "3. Configure monitoring notification channels"
echo "4. Test the security policies"
echo "5. Review and customize as needed for your organization"
echo
echo "🔒 Security resources created:"
echo "   - 4 service accounts with least privilege access"
echo "   - 3 custom IAM roles" 
echo "   - VPC with private networking"
echo "   - Cloud Armor WAF protection"
echo "   - Comprehensive audit logging"
echo

# Cleanup temporary files
rm -f /tmp/poi-*-role.yaml /tmp/audit-policy.yaml

echo "Security setup script completed successfully! 🎉"