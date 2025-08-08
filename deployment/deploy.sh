#!/bin/bash

# POI Monitoring System - Cloud Functions Deployment Script
# This script deploys all three Cloud Functions and sets up the required infrastructure

set -e

# Configuration
PROJECT_ID="poi-monitoring-prod"  # Update with your project ID
REGION="us-central1"
BUCKET_NAME="poi-config-bucket"
PUBSUB_TOPIC="poi-deviation-alerts"

echo "🚀 Deploying POI Monitoring System"
echo "Project: $PROJECT_ID"
echo "Region: $REGION"
echo

# Set the project
gcloud config set project $PROJECT_ID

# Create Cloud Storage bucket for configuration
echo "📦 Creating Cloud Storage bucket..."
gsutil mb -p $PROJECT_ID -l $REGION gs://$BUCKET_NAME || echo "Bucket may already exist"

# Upload POI groups configuration
echo "📋 Uploading POI groups configuration..."
gsutil cp ../Grupos.csv gs://$BUCKET_NAME/poi_groups.csv

# Create Pub/Sub topic for deviation alerts
echo "📢 Creating Pub/Sub topic..."
gcloud pubsub topics create $PUBSUB_TOPIC || echo "Topic may already exist"

# Create BigQuery dataset
echo "📊 Creating BigQuery dataset..."
bq mk --location=$REGION poi_monitoring || echo "Dataset may already exist"

# Create BigQuery tables
echo "🗃️ Creating BigQuery tables..."
bq query --use_legacy_sql=false < ../database-schema.sql || echo "Tables may already exist"

# Enable required APIs
echo "🔧 Enabling required APIs..."
gcloud services enable cloudfunctions.googleapis.com
gcloud services enable bigquery.googleapis.com
gcloud services enable firestore.googleapis.com
gcloud services enable secretmanager.googleapis.com
gcloud services enable pubsub.googleapis.com
gcloud services enable cloudscheduler.googleapis.com

# Create service account for Cloud Functions
echo "🔐 Creating service account..."
gcloud iam service-accounts create poi-monitoring-functions \
    --display-name="POI Monitoring Cloud Functions" \
    --description="Service account for POI monitoring system Cloud Functions" || echo "Service account may already exist"

# Grant required permissions
echo "🔒 Granting IAM permissions..."
gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="serviceAccount:poi-monitoring-functions@$PROJECT_ID.iam.gserviceaccount.com" \
    --role="roles/bigquery.dataEditor"

gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="serviceAccount:poi-monitoring-functions@$PROJECT_ID.iam.gserviceaccount.com" \
    --role="roles/datastore.user"

gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="serviceAccount:poi-monitoring-functions@$PROJECT_ID.iam.gserviceaccount.com" \
    --role="roles/secretmanager.secretAccessor"

gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="serviceAccount:poi-monitoring-functions@$PROJECT_ID.iam.gserviceaccount.com" \
    --role="roles/pubsub.publisher"

gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="serviceAccount:poi-monitoring-functions@$PROJECT_ID.iam.gserviceaccount.com" \
    --role="roles/storage.objectViewer"

# Deploy Data Collector Function
echo "📡 Deploying Data Collector Function..."
gcloud functions deploy poi-data-collector \
    --source=../cloud-functions/data-collector \
    --entry-point=collect_poi_data \
    --runtime=python311 \
    --trigger-topic=hourly-data-collection \
    --memory=512MB \
    --timeout=300s \
    --region=$REGION \
    --service-account=poi-monitoring-functions@$PROJECT_ID.iam.gserviceaccount.com \
    --set-env-vars="PROJECT_ID=$PROJECT_ID,BUCKET_NAME=$BUCKET_NAME" \
    --max-instances=1

# Deploy Deviation Detector Function
echo "🔍 Deploying Deviation Detector Function..."
gcloud functions deploy poi-deviation-detector \
    --source=../cloud-functions/deviation-detector \
    --entry-point=detect_poi_deviations \
    --runtime=python311 \
    --trigger-topic=hourly-deviation-detection \
    --memory=1GB \
    --timeout=600s \
    --region=$REGION \
    --service-account=poi-monitoring-functions@$PROJECT_ID.iam.gserviceaccount.com \
    --set-env-vars="PROJECT_ID=$PROJECT_ID,PUBSUB_TOPIC=$PUBSUB_TOPIC" \
    --max-instances=2

# Deploy Alert Manager Function
echo "📢 Deploying Alert Manager Function..."
gcloud functions deploy poi-alert-manager \
    --source=../cloud-functions/alert-manager \
    --entry-point=manage_poi_alerts \
    --runtime=python311 \
    --trigger-topic=$PUBSUB_TOPIC \
    --memory=256MB \
    --timeout=180s \
    --region=$REGION \
    --service-account=poi-monitoring-functions@$PROJECT_ID.iam.gserviceaccount.com \
    --set-env-vars="PROJECT_ID=$PROJECT_ID" \
    --max-instances=5

# Create Cloud Scheduler jobs
echo "⏰ Creating Cloud Scheduler jobs..."

# Create Pub/Sub topics for scheduling
gcloud pubsub topics create hourly-data-collection || echo "Topic may already exist"
gcloud pubsub topics create hourly-deviation-detection || echo "Topic may already exist"

# Data Collection - every hour at :00
gcloud scheduler jobs create pubsub data-collection-schedule \
    --schedule="0 * * * *" \
    --topic=hourly-data-collection \
    --message-body='{"trigger": "scheduled"}' \
    --location=$REGION || echo "Job may already exist"

# Deviation Detection - every hour at :05
gcloud scheduler jobs create pubsub deviation-detection-schedule \
    --schedule="5 * * * *" \
    --topic=hourly-deviation-detection \
    --message-body='{"trigger": "scheduled"}' \
    --location=$REGION || echo "Job may already exist"

# Create secrets for API credentials
echo "🔑 Creating secrets (you'll need to update these with actual values)..."

# Create secret for Creare Cloud credentials
echo "56963" | gcloud secrets create creare-client-id --data-file=- || echo "Secret may already exist"
echo "1MSiBaH879w=" | gcloud secrets create creare-client-secret --data-file=- || echo "Secret may already exist"

# Create secret for SMTP configuration
cat << EOF | gcloud secrets create smtp-config --data-file=- || echo "Secret may already exist"
{
    "smtp_server": "smtp.gmail.com",
    "smtp_port": 587,
    "username": "alerts@yourcompany.com",
    "password": "your_app_password",
    "from_address": "alerts@yourcompany.com"
}
EOF

# Initialize Firestore configuration
echo "🔧 Initializing Firestore configuration..."
cat << EOF > /tmp/firestore-init.json
{
    "collections": {
        "system_settings": {
            "global_config": {
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
                            "enabled": true,
                            "smtp_server": "smtp.gmail.com",
                            "from_address": "alerts@yourcompany.com"
                        },
                        "sms": {
                            "enabled": false,
                            "provider": "twilio"
                        }
                    },
                    "delivery_config": {
                        "max_retries": 3,
                        "retry_delay_minutes": 5,
                        "batch_size": 10
                    }
                }
            },
            "alert_recipients": {
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
        }
    }
}
EOF

echo "📋 Firestore configuration saved to /tmp/firestore-init.json"
echo "   Please manually import this into Firestore or use the Firebase CLI"

echo
echo "✅ Deployment completed!"
echo
echo "🔧 Next steps:"
echo "1. Update the secrets with your actual API credentials:"
echo "   - gcloud secrets versions add creare-client-id --data-file=<your-client-id-file>"
echo "   - gcloud secrets versions add creare-client-secret --data-file=<your-client-secret-file>"
echo "   - gcloud secrets versions add smtp-config --data-file=<your-smtp-config.json>"
echo
echo "2. Import Firestore configuration:"
echo "   - Use Firebase CLI or Firestore console to import /tmp/firestore-init.json"
echo
echo "3. Update email recipients in Firestore system_settings/alert_recipients"
echo
echo "4. Test the system:"
echo "   - gcloud scheduler jobs run data-collection-schedule --location=$REGION"
echo "   - Check Cloud Functions logs for execution status"
echo
echo "📊 Monitoring:"
echo "   - Cloud Functions: https://console.cloud.google.com/functions"
echo "   - BigQuery: https://console.cloud.google.com/bigquery"
echo "   - Firestore: https://console.cloud.google.com/firestore"
echo "   - Scheduler: https://console.cloud.google.com/cloudscheduler"
echo