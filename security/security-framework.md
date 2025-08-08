# Security Framework - POI Monitoring System

## Security Architecture Overview

This security framework implements defense-in-depth principles with:
- **Identity & Access Management (IAM)** with least privilege access
- **Service Account Security** with dedicated accounts per function
- **API Security** with OAuth2 and token management
- **Data Security** with encryption and access controls
- **Network Security** with VPC and firewall rules
- **Audit & Compliance** with comprehensive logging

## 1. Identity & Access Management (IAM)

### Service Accounts Strategy

#### Primary Service Accounts
```yaml
poi-data-collector@PROJECT_ID.iam.gserviceaccount.com:
  purpose: Data collection from Creare Cloud API
  permissions:
    - bigquery.dataEditor (poi_monitoring dataset only)
    - firestore.user (system_settings collection only)
    - secretmanager.secretAccessor (API credentials only)
    - storage.objectViewer (config bucket only)
  
poi-deviation-detector@PROJECT_ID.iam.gserviceaccount.com:
  purpose: Deviation detection and analysis
  permissions:
    - bigquery.dataViewer (poi_monitoring dataset)
    - bigquery.dataEditor (poi_deviations table only)
    - firestore.user (alert_states collection)
    - pubsub.publisher (poi-deviation-alerts topic only)

poi-alert-manager@PROJECT_ID.iam.gserviceaccount.com:
  purpose: Alert delivery and management
  permissions:
    - bigquery.dataEditor (alert_history table only)
    - firestore.user (alert_states, system_settings collections)
    - secretmanager.secretAccessor (SMTP credentials only)

poi-monitoring-admin@PROJECT_ID.iam.gserviceaccount.com:
  purpose: System administration and maintenance
  permissions:
    - bigquery.admin (poi_monitoring dataset only)
    - firestore.datastore.owner
    - storage.admin (config bucket only)
    - secretmanager.admin
```

#### Custom IAM Roles

**POI Data Collector Role**
```json
{
  "title": "POI Data Collector",
  "description": "Custom role for POI data collection function",
  "stage": "GA",
  "includedPermissions": [
    "bigquery.datasets.get",
    "bigquery.tables.create",
    "bigquery.tables.updateData",
    "bigquery.jobs.create",
    "firestore.documents.get",
    "firestore.documents.list",
    "secretmanager.versions.access",
    "storage.objects.get"
  ]
}
```

**POI Deviation Detector Role**
```json
{
  "title": "POI Deviation Detector", 
  "description": "Custom role for POI deviation detection function",
  "stage": "GA",
  "includedPermissions": [
    "bigquery.datasets.get",
    "bigquery.tables.get",
    "bigquery.tables.getData", 
    "bigquery.tables.updateData",
    "bigquery.jobs.create",
    "firestore.documents.get",
    "firestore.documents.list",
    "firestore.documents.write",
    "pubsub.topics.publish"
  ]
}
```

**POI Alert Manager Role**
```json
{
  "title": "POI Alert Manager",
  "description": "Custom role for POI alert management function",
  "stage": "GA", 
  "includedPermissions": [
    "bigquery.datasets.get",
    "bigquery.tables.updateData",
    "bigquery.jobs.create",
    "firestore.documents.get",
    "firestore.documents.list",
    "firestore.documents.write",
    "secretmanager.versions.access"
  ]
}
```

### IAM Binding Strategy

```bash
# Bind custom roles to service accounts
gcloud projects add-iam-policy-binding PROJECT_ID \
    --member="serviceAccount:poi-data-collector@PROJECT_ID.iam.gserviceaccount.com" \
    --role="projects/PROJECT_ID/roles/poiDataCollector"

gcloud projects add-iam-policy-binding PROJECT_ID \
    --member="serviceAccount:poi-deviation-detector@PROJECT_ID.iam.gserviceaccount.com" \
    --role="projects/PROJECT_ID/roles/poiDeviationDetector"

gcloud projects add-iam-policy-binding PROJECT_ID \
    --member="serviceAccount:poi-alert-manager@PROJECT_ID.iam.gserviceaccount.com" \
    --role="projects/PROJECT_ID/roles/poiAlertManager"
```

## 2. Secret Management

### Secret Manager Configuration

#### API Credentials
```bash
# Creare Cloud API credentials
gcloud secrets create creare-client-id \
    --replication-policy="automatic" \
    --labels="system=poi-monitoring,type=api-credential"

gcloud secrets create creare-client-secret \
    --replication-policy="automatic" \
    --labels="system=poi-monitoring,type=api-credential"

# SMTP Configuration
gcloud secrets create smtp-config \
    --replication-policy="automatic" \
    --labels="system=poi-monitoring,type=email-config"

# Database passwords (if using Cloud SQL)
gcloud secrets create db-password \
    --replication-policy="automatic" \
    --labels="system=poi-monitoring,type=db-credential"
```

#### Secret Access Policies
```bash
# Grant specific access to secrets
gcloud secrets add-iam-policy-binding creare-client-id \
    --member="serviceAccount:poi-data-collector@PROJECT_ID.iam.gserviceaccount.com" \
    --role="roles/secretmanager.secretAccessor"

gcloud secrets add-iam-policy-binding smtp-config \
    --member="serviceAccount:poi-alert-manager@PROJECT_ID.iam.gserviceaccount.com" \
    --role="roles/secretmanager.secretAccessor"
```

#### Secret Rotation Policy
```json
{
  "rotation_policy": {
    "rotation_period": "2592000s",
    "next_rotation_time": "2025-09-08T00:00:00Z"
  },
  "automatic_rotation": true,
  "notification_topics": [
    "projects/PROJECT_ID/topics/secret-rotation-alerts"
  ]
}
```

## 3. Data Security

### BigQuery Security

#### Dataset-Level Security
```sql
-- Create dataset with proper labels and location
CREATE SCHEMA `poi_monitoring`
OPTIONS(
  description="POI monitoring system data - CONFIDENTIAL",
  location="us-central1",
  default_table_expiration_days=730,
  labels=[
    ("classification", "confidential"),
    ("system", "poi-monitoring"),
    ("data-retention", "2-years")
  ]
);

-- Grant dataset access to service accounts
GRANT `roles/bigquery.dataViewer` 
ON SCHEMA `poi_monitoring` 
TO "serviceAccount:poi-deviation-detector@PROJECT_ID.iam.gserviceaccount.com";

GRANT `roles/bigquery.dataEditor` 
ON SCHEMA `poi_monitoring` 
TO "serviceAccount:poi-data-collector@PROJECT_ID.iam.gserviceaccount.com";
```

#### Table-Level Security
```sql
-- Row-level security for multi-tenant data
CREATE OR REPLACE ROW ACCESS POLICY poi_events_filial_policy
ON `poi_monitoring.poi_events_processed`
GRANT TO ("serviceAccount:rrp-reader@PROJECT_ID.iam.gserviceaccount.com")
FILTER USING (filial = "RRP");

CREATE OR REPLACE ROW ACCESS POLICY poi_events_tls_policy  
ON `poi_monitoring.poi_events_processed`
GRANT TO ("serviceAccount:tls-reader@PROJECT_ID.iam.gserviceaccount.com")
FILTER USING (filial = "TLS");

-- Column-level security for sensitive data
CREATE OR REPLACE VIEW `poi_monitoring.poi_events_public` AS
SELECT 
  processed_event_id,
  poi_name,
  poi_group, 
  filial,
  entry_timestamp,
  exit_timestamp,
  duration_hours
FROM `poi_monitoring.poi_events_processed`;

-- Grant view access instead of table access for restricted users
GRANT `roles/bigquery.dataViewer` 
ON TABLE `poi_monitoring.poi_events_public`
TO "serviceAccount:poi-dashboard@PROJECT_ID.iam.gserviceaccount.com";
```

### Firestore Security Rules

```javascript
rules_version = '2';
service cloud.firestore {
  match /databases/{database}/documents {
    
    // System service accounts have full access
    match /{document=**} {
      allow read, write: if isSystemServiceAccount();
    }
    
    // Alert states - read-only for monitoring users
    match /alert_states/{alertId} {
      allow read: if isAuthenticated();
      allow write: if isSystemServiceAccount();
      
      // Filial-based access control
      allow read: if isAuthenticated() && 
                     (resource.data.filial == getUserFilial() || 
                      hasRole('admin'));
    }
    
    // System settings - admin only
    match /system_settings/{configId} {
      allow read: if hasRole('admin') || isSystemServiceAccount();
      allow write: if hasRole('admin') || isSystemServiceAccount();
    }
    
    // POI configurations - operations can read, admin can write
    match /poi_configurations/{poiId} {
      allow read: if hasRole('operations') || hasRole('admin') || isSystemServiceAccount();
      allow write: if hasRole('admin') || isSystemServiceAccount();
    }
    
    // Audit log - read-only for admins
    match /audit_log/{logId} {
      allow read: if hasRole('admin');
      allow write: if isSystemServiceAccount();
    }
    
    // Processing locks - system only
    match /processing_locks/{lockId} {
      allow read, write: if isSystemServiceAccount();
    }
    
    // Helper functions
    function isAuthenticated() {
      return request.auth != null;
    }
    
    function isSystemServiceAccount() {
      return request.auth != null && 
             request.auth.token.email.matches('.*poi-.*@PROJECT_ID\\.iam\\.gserviceaccount\\.com');
    }
    
    function hasRole(role) {
      return request.auth != null && 
             request.auth.token.get('custom_claims', {}).get('roles', []).hasAny([role]);
    }
    
    function getUserFilial() {
      return request.auth.token.get('custom_claims', {}).get('filial', '');
    }
  }
}
```

### Cloud Storage Security

```yaml
# Bucket IAM policy
bucket: poi-config-bucket
iam_bindings:
  - role: roles/storage.objectViewer
    members:
      - serviceAccount:poi-data-collector@PROJECT_ID.iam.gserviceaccount.com
      
  - role: roles/storage.objectAdmin  
    members:
      - serviceAccount:poi-monitoring-admin@PROJECT_ID.iam.gserviceaccount.com

# Bucket-level configuration
bucket_policy:
  uniform_bucket_level_access: true
  public_access_prevention: enforced
  versioning: enabled
  lifecycle_rules:
    - action: Delete
      condition:
        age: 90  # days
        matches_storage_class: ["STANDARD"]
```

## 4. Network Security

### VPC Configuration

```bash
# Create VPC network
gcloud compute networks create poi-monitoring-vpc \
    --subnet-mode=custom \
    --bgp-routing-mode=regional

# Create subnet
gcloud compute networks subnets create poi-monitoring-subnet \
    --network=poi-monitoring-vpc \
    --range=10.0.0.0/24 \
    --region=us-central1 \
    --enable-private-ip-google-access

# Create NAT gateway for outbound internet access
gcloud compute routers create poi-monitoring-router \
    --network=poi-monitoring-vpc \
    --region=us-central1

gcloud compute routers nats create poi-monitoring-nat \
    --router=poi-monitoring-router \
    --region=us-central1 \
    --nat-all-subnet-ip-ranges \
    --auto-allocate-nat-external-ips
```

### Firewall Rules

```bash
# Allow HTTPS outbound (for API calls)
gcloud compute firewall-rules create allow-poi-https-outbound \
    --network=poi-monitoring-vpc \
    --direction=EGRESS \
    --rules=tcp:443 \
    --destination-ranges=0.0.0.0/0 \
    --target-service-accounts=poi-data-collector@PROJECT_ID.iam.gserviceaccount.com

# Allow SMTP outbound (for email alerts)
gcloud compute firewall-rules create allow-poi-smtp-outbound \
    --network=poi-monitoring-vpc \
    --direction=EGRESS \
    --rules=tcp:587,tcp:465 \
    --destination-ranges=0.0.0.0/0 \
    --target-service-accounts=poi-alert-manager@PROJECT_ID.iam.gserviceaccount.com

# Deny all other outbound traffic
gcloud compute firewall-rules create deny-poi-all-outbound \
    --network=poi-monitoring-vpc \
    --direction=EGRESS \
    --rules=all \
    --destination-ranges=0.0.0.0/0 \
    --action=DENY \
    --priority=1000 \
    --target-service-accounts=poi-data-collector@PROJECT_ID.iam.gserviceaccount.com,poi-deviation-detector@PROJECT_ID.iam.gserviceaccount.com,poi-alert-manager@PROJECT_ID.iam.gserviceaccount.com
```

### VPC Service Controls

```json
{
  "name": "projects/PROJECT_ID/locations/global/servicePerimeters/poi-monitoring-perimeter",
  "title": "POI Monitoring Service Perimeter",
  "description": "Protects POI monitoring system resources",
  "perimeterType": "PERIMETER_TYPE_REGULAR",
  "spec": {
    "resources": [
      "projects/PROJECT_NUMBER"
    ],
    "restrictedServices": [
      "bigquery.googleapis.com",
      "firestore.googleapis.com", 
      "secretmanager.googleapis.com",
      "storage.googleapis.com"
    ],
    "accessLevels": [
      "accessPolicies/ACCESS_POLICY_ID/accessLevels/poi-monitoring-access-level"
    ],
    "vpcAccessibleServices": {
      "enableRestriction": true,
      "allowedServices": [
        "bigquery.googleapis.com",
        "firestore.googleapis.com",
        "secretmanager.googleapis.com",
        "storage.googleapis.com",
        "pubsub.googleapis.com"
      ]
    }
  }
}
```

## 5. Application Security

### Cloud Function Security

#### Function Configuration
```yaml
data_collector_function:
  runtime: python311
  memory: 512MB
  timeout: 300s
  max_instances: 1
  vpc_connector: poi-monitoring-connector
  service_account: poi-data-collector@PROJECT_ID.iam.gserviceaccount.com
  environment_variables:
    GOOGLE_CLOUD_PROJECT: PROJECT_ID
    ENVIRONMENT: production
  ingress_settings: ALLOW_INTERNAL_ONLY
  
deviation_detector_function:
  runtime: python311  
  memory: 1GB
  timeout: 600s
  max_instances: 2
  vpc_connector: poi-monitoring-connector
  service_account: poi-deviation-detector@PROJECT_ID.iam.gserviceaccount.com
  environment_variables:
    GOOGLE_CLOUD_PROJECT: PROJECT_ID
    ENVIRONMENT: production
  ingress_settings: ALLOW_INTERNAL_ONLY

alert_manager_function:
  runtime: python311
  memory: 256MB  
  timeout: 180s
  max_instances: 5
  vpc_connector: poi-monitoring-connector
  service_account: poi-alert-manager@PROJECT_ID.iam.gserviceaccount.com
  environment_variables:
    GOOGLE_CLOUD_PROJECT: PROJECT_ID
    ENVIRONMENT: production
  ingress_settings: ALLOW_INTERNAL_ONLY
```

#### Security Headers & Validation
```python
# Add to each Cloud Function
import os
import logging
from functools import wraps

def security_headers(func):
    """Add security headers and validation"""
    @wraps(func)
    def wrapper(*args, **kwargs):
        # Validate environment
        if os.environ.get('ENVIRONMENT') != 'production':
            logging.warning("Function running in non-production environment")
        
        # Validate service account
        if not os.environ.get('GOOGLE_CLOUD_PROJECT'):
            raise ValueError("GOOGLE_CLOUD_PROJECT environment variable not set")
        
        # Add request validation
        request = args[0] if args else None
        if hasattr(request, 'headers'):
            # Validate content type for POST requests
            if request.method == 'POST':
                content_type = request.headers.get('Content-Type', '')
                if not content_type.startswith('application/json'):
                    logging.warning(f"Unexpected content type: {content_type}")
        
        return func(*args, **kwargs)
    
    return wrapper
```

### API Security

#### OAuth2 Token Management
```python
import time
import hashlib
from typing import Optional, Dict

class SecureTokenManager:
    """Secure OAuth2 token management with validation"""
    
    def __init__(self, secret_manager_client):
        self.secret_manager = secret_manager_client
        self.token_cache = {}
        self.max_cache_age = 3600  # 1 hour
        
    def get_token(self, client_id: str) -> Optional[str]:
        """Get token with security validations"""
        
        # Check cache first
        cache_key = hashlib.sha256(client_id.encode()).hexdigest()
        if cache_key in self.token_cache:
            cached_token, timestamp = self.token_cache[cache_key]
            if time.time() - timestamp < self.max_cache_age:
                return cached_token
        
        # Get fresh token
        token = self._request_token(client_id)
        
        if token and self._validate_token(token):
            # Cache with timestamp
            self.token_cache[cache_key] = (token, time.time())
            
            # Limit cache size
            if len(self.token_cache) > 10:
                oldest_key = min(self.token_cache.keys(), 
                               key=lambda k: self.token_cache[k][1])
                del self.token_cache[oldest_key]
            
            return token
        
        return None
    
    def _validate_token(self, token: str) -> bool:
        """Validate token format and claims"""
        try:
            # Basic format validation
            parts = token.split('.')
            if len(parts) != 3:
                return False
            
            # Decode and validate claims (simplified)
            import base64
            import json
            
            # Decode payload (add padding if needed)
            payload = parts[1]
            payload += '=' * (4 - len(payload) % 4)
            decoded = base64.b64decode(payload)
            claims = json.loads(decoded)
            
            # Validate expiration
            if 'exp' in claims:
                exp_time = claims['exp'] 
                if time.time() >= exp_time:
                    return False
            
            # Validate issuer
            if 'iss' in claims:
                expected_issuer = 'https://openid-provider.crearecloud.com.br'
                if claims['iss'] != expected_issuer:
                    return False
            
            return True
            
        except Exception as e:
            logging.error(f"Token validation failed: {e}")
            return False
```

## 6. Monitoring & Audit

### Security Monitoring

```python
# Security monitoring decorator
def security_monitor(operation_type: str):
    """Monitor security-related operations"""
    def decorator(func):
        @wraps(func) 
        def wrapper(*args, **kwargs):
            start_time = time.time()
            
            try:
                # Log operation start
                logging.info(f"Security operation started: {operation_type}")
                
                result = func(*args, **kwargs)
                
                # Log successful operation
                duration = time.time() - start_time
                logging.info(f"Security operation completed: {operation_type}, duration: {duration:.2f}s")
                
                return result
                
            except Exception as e:
                # Log security failures
                duration = time.time() - start_time
                logging.error(f"Security operation failed: {operation_type}, error: {e}, duration: {duration:.2f}s")
                
                # Send security alert for critical operations
                if operation_type in ['token_acquisition', 'secret_access', 'admin_operation']:
                    send_security_alert(operation_type, str(e))
                
                raise
        
        return wrapper
    return decorator

def send_security_alert(operation: str, error: str):
    """Send security alert to monitoring system"""
    try:
        from google.cloud import monitoring_v3
        
        client = monitoring_v3.MetricServiceClient()
        project_name = f"projects/{os.environ.get('GOOGLE_CLOUD_PROJECT')}"
        
        series = monitoring_v3.TimeSeries()
        series.metric.type = "custom.googleapis.com/poi_monitoring/security_alert"
        series.metric.labels["operation"] = operation
        series.metric.labels["severity"] = "high"
        
        now = time.time()
        seconds = int(now)
        nanos = int((now - seconds) * 10**9)
        interval = monitoring_v3.TimeInterval(
            {"end_time": {"seconds": seconds, "nanos": nanos}}
        )
        point = monitoring_v3.Point({
            "interval": interval,
            "value": {"double_value": 1.0},
        })
        series.points = [point]
        
        client.create_time_series(name=project_name, time_series=[series])
        
    except Exception as e:
        logging.error(f"Failed to send security alert: {e}")
```

### Audit Logging

```python
class AuditLogger:
    """Comprehensive audit logging"""
    
    def __init__(self, firestore_client):
        self.firestore = firestore_client
        
    def log_security_event(
        self,
        event_type: str,
        severity: str,
        details: Dict,
        user_id: Optional[str] = None,
        service_account: Optional[str] = None
    ):
        """Log security events to Firestore audit collection"""
        
        try:
            audit_record = {
                'timestamp': datetime.now(),
                'event_type': event_type,
                'severity': severity,
                'component': 'security_framework',
                'user_id': user_id,
                'service_account': service_account,
                'details': details,
                'metadata': {
                    'function_name': os.environ.get('K_SERVICE', 'unknown'),
                    'execution_id': os.environ.get('K_REVISION', 'unknown'),
                    'project_id': os.environ.get('GOOGLE_CLOUD_PROJECT'),
                    'environment': os.environ.get('ENVIRONMENT', 'unknown')
                }
            }
            
            # Store in Firestore
            self.firestore.collection('audit_log').add(audit_record)
            
            # Also log to Cloud Logging for integration with Security Command Center
            logging.info(f"AUDIT: {json.dumps(audit_record, default=str)}")
            
        except Exception as e:
            logging.error(f"Failed to log audit event: {e}")
```

## 7. Compliance & Governance

### Data Classification
```yaml
data_classification:
  PUBLIC:
    - POI names and locations
    - System performance metrics
    - Public configuration data
    
  INTERNAL:
    - Alert statistics and trends
    - System operational metrics
    - Non-sensitive vehicle data
    
  CONFIDENTIAL:
    - Vehicle tracking data
    - Alert recipient information
    - API credentials and tokens
    - Detailed operational logs
    
  RESTRICTED:
    - Database passwords
    - SMTP credentials
    - System administrator access keys
```

### Retention Policies
```sql
-- Automated data retention policies
CREATE OR REPLACE PROCEDURE `poi_monitoring.enforce_data_retention`()
BEGIN
  -- Delete old raw events (2 years)
  DELETE FROM `poi_monitoring.poi_events_raw`
  WHERE event_date < DATE_SUB(CURRENT_DATE(), INTERVAL 730 DAY);
  
  -- Delete old audit logs (7 years for compliance)
  DELETE FROM `poi_monitoring.audit_log` 
  WHERE DATE(timestamp) < DATE_SUB(CURRENT_DATE(), INTERVAL 2555 DAY);
  
  -- Archive old alert history (3 years retention, then archive)
  EXPORT DATA OPTIONS(
    uri='gs://poi-archive-bucket/alert_history/year=*',
    format='AVRO'
  ) AS
  SELECT * FROM `poi_monitoring.alert_history`
  WHERE alert_date < DATE_SUB(CURRENT_DATE(), INTERVAL 1095 DAY);
  
  DELETE FROM `poi_monitoring.alert_history`
  WHERE alert_date < DATE_SUB(CURRENT_DATE(), INTERVAL 1095 DAY);
END;
```

This comprehensive security framework provides:
- **Multi-layered access control** with service account isolation
- **Data protection** with encryption and access policies  
- **Network security** with VPC and firewall controls
- **Application security** with input validation and monitoring
- **Audit compliance** with comprehensive logging
- **Automated governance** with retention and cleanup policies