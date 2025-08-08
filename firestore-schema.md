# Firestore Schema Design - POI Monitoring System

## Overview
Firestore is used for real-time state management, configuration, and fast lookups that complement BigQuery's analytical capabilities.

## Database Structure

### Collection: `alert_states`
Real-time tracking of active alerts and escalation states.

```javascript
// Document ID: {filial}_{poi_normalized}_{vehicle_plate}
// Example: "RRP_CarregamentoFabricaRRP_ABC1234"
{
  // Primary identifiers
  "filial": "RRP",
  "poi_name": "Carregamento Fabrica RRP",
  "poi_normalized": "CarregamentoFabricaRRP", // For alert titles
  "poi_group": "Fábrica",
  "vehicle_plate": "ABC1234",
  "vehicle_id": "12345",
  
  // Current state
  "current_level": "N2", // null, "N1", "N2", "N3", "N4"
  "state": "active", // "inactive", "active", "resolved", "suppressed"
  "first_detection": "2025-08-08T14:00:00Z",
  "last_updated": "2025-08-08T16:00:00Z",
  "last_alert_sent": "2025-08-08T15:00:00Z",
  
  // Escalation tracking
  "escalation_history": [
    {
      "level": "N1",
      "timestamp": "2025-08-08T14:00:00Z",
      "duration_hours": 2,
      "alert_sent": true
    },
    {
      "level": "N2", 
      "timestamp": "2025-08-08T16:00:00Z",
      "duration_hours": 0,
      "alert_sent": true
    }
  ],
  
  // Alert metadata
  "alert_count": 2,
  "last_alert_title": "RRP_CarregamentoFabricaRRP_N2_08082025_160000",
  "consecutive_hours": 2,
  "threshold_hours": {
    "N1": 2,
    "N2": 4,
    "N3": 8,
    "N4": 12
  },
  
  // Business context
  "entry_timestamp": "2025-08-08T12:00:00Z",
  "expected_duration_hours": 1.5,
  "actual_duration_hours": 4.0,
  "deviation_magnitude": 2.5,
  
  // Resolution tracking
  "resolution_timestamp": null,
  "resolution_reason": null,
  "auto_resolved": false,
  
  // System metadata
  "created_at": "2025-08-08T14:00:00Z",
  "updated_at": "2025-08-08T16:00:00Z",
  "ttl": "2025-08-15T16:00:00Z" // Auto-cleanup after 7 days
}
```

### Collection: `poi_configurations`
POI mappings, groups, and business rules.

```javascript
// Document ID: {poi_name_normalized}
// Example: "CarregamentoFabricaRRP"
{
  "poi_name": "Carregamento Fabrica RRP",
  "poi_normalized": "CarregamentoFabricaRRP",
  "filial": "RRP",
  "group": "Fábrica",
  "group_normalized": "Fabrica",
  
  // Thresholds
  "deviation_thresholds": {
    "max_duration_hours": 3.0,
    "max_consecutive_visits": 5,
    "escalation_hours": {
      "N1": 2,
      "N2": 4, 
      "N3": 8,
      "N4": 12
    }
  },
  
  // Business rules
  "operating_hours": {
    "start": "06:00",
    "end": "18:00",
    "timezone": "America/Campo_Grande"
  },
  "alert_suppression": {
    "maintenance_windows": [],
    "holiday_schedule": false,
    "weekend_alerts": true
  },
  
  // Related POIs for group-based detection
  "related_pois": [
    "Buffer Frotas",
    "Abastecimento Frotas RRP"
  ],
  "consolidation_group": "fabricacao_rrp",
  
  // Configuration metadata
  "active": true,
  "version": "1.0",
  "last_updated": "2025-08-08T10:00:00Z",
  "updated_by": "system_admin"
}
```

### Collection: `system_settings`
Global system configuration and parameters.

```javascript
// Document ID: "global_config"
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
        "enabled": true,
        "smtp_server": "smtp.gmail.com",
        "from_address": "alerts@company.com"
      },
      "sms": {
        "enabled": true,
        "provider": "twilio",
        "sender_id": "+1234567890"
      },
      "webhook": {
        "enabled": false,
        "endpoints": []
      }
    },
    "delivery_config": {
      "max_retries": 3,
      "retry_delay_minutes": 5,
      "batch_size": 10
    }
  },
  
  "processing_config": {
    "data_collection": {
      "hours_lookback": 5,
      "batch_size": 1000,
      "consolidation_enabled": true
    },
    "deviation_detection": {
      "analysis_window_hours": 24,
      "confidence_threshold": 0.8,
      "auto_resolution_hours": 1
    }
  },
  
  "monitoring": {
    "health_check_interval_minutes": 5,
    "performance_alerts": true,
    "cost_monitoring": {
      "daily_budget_usd": 10,
      "alert_threshold": 0.8
    }
  },
  
  "maintenance": {
    "data_retention_days": 730,
    "cleanup_schedule": "0 2 * * 0", // Weekly cleanup
    "backup_enabled": true
  },
  
  "version": "1.0",
  "last_updated": "2025-08-08T10:00:00Z"
}

// Document ID: "alert_recipients"
{
  "by_filial": {
    "RRP": {
      "email": [
        "manager.rrp@company.com",
        "operations.rrp@company.com"
      ],
      "sms": [
        "+5567999999999"
      ]
    },
    "TLS": {
      "email": [
        "manager.tls@company.com",
        "operations.tls@company.com"
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
      "channels": ["email", "sms"],
      "delay_minutes": 5
    },
    "N3": {
      "channels": ["email", "sms"],
      "delay_minutes": 0
    },
    "N4": {
      "channels": ["email", "sms", "webhook"],
      "delay_minutes": 0
    }
  }
}

// Document ID: "feature_flags"
{
  "deviation_detection_enabled": true,
  "alert_suppression_enabled": true,
  "auto_resolution_enabled": true,
  "group_consolidation_enabled": true,
  "maintenance_mode": false,
  "debug_logging": false,
  "cost_optimization": true,
  "experimental_features": {
    "ml_predictions": false,
    "predictive_alerts": false,
    "smart_thresholds": false
  }
}
```

### Collection: `processing_locks`
Prevent concurrent processing and ensure data consistency.

```javascript
// Document ID: "data_collection_lock"
{
  "process_name": "data_collection",
  "locked_by": "poi-data-collector-instance-1",
  "locked_at": "2025-08-08T14:00:00Z",
  "lock_ttl": "2025-08-08T14:05:00Z", // 5 minute TTL
  "processing_hour": "2025-08-08T14:00:00Z",
  "status": "running", // "waiting", "running", "completed", "failed"
  "progress": {
    "total_expected": 1000,
    "processed": 750,
    "errors": 2
  },
  "metadata": {
    "function_execution_id": "12345",
    "retry_count": 0,
    "last_heartbeat": "2025-08-08T14:03:00Z"
  }
}

// Document ID: "deviation_detection_lock"
{
  "process_name": "deviation_detection",
  "locked_by": "poi-deviation-detector-instance-1",
  "locked_at": "2025-08-08T14:05:00Z",
  "lock_ttl": "2025-08-08T14:15:00Z", // 10 minute TTL
  "processing_hour": "2025-08-08T14:00:00Z",
  "status": "running",
  "depends_on": ["data_collection_lock"],
  "progress": {
    "pois_analyzed": 25,
    "deviations_found": 3,
    "alerts_generated": 2
  }
}
```

### Collection: `audit_log`
System audit trail for compliance and debugging.

```javascript
// Document ID: auto-generated
{
  "timestamp": "2025-08-08T14:00:00Z",
  "event_type": "alert_sent",
  "severity": "info", // "debug", "info", "warning", "error", "critical"
  "component": "alert_manager",
  "user": "system",
  
  "details": {
    "alert_id": "alert_123",
    "deviation_id": "dev_456",
    "filial": "RRP",
    "poi": "Carregamento Fabrica RRP",
    "level": "N2",
    "recipients": 3,
    "channels": ["email", "sms"],
    "delivery_status": "sent"
  },
  
  "metadata": {
    "function_name": "poi-alert-manager",
    "execution_id": "exec_789",
    "correlation_id": "corr_abc",
    "processing_time_ms": 250
  },
  
  "context": {
    "request_id": "req_xyz",
    "session_id": "sess_def",
    "ip_address": "10.0.0.1",
    "user_agent": "Cloud-Functions/1.0"
  }
}
```

### Collection: `performance_metrics`
Real-time system performance tracking.

```javascript
// Document ID: {date}_{hour}
// Example: "2025-08-08_14"
{
  "date": "2025-08-08",
  "hour": 14,
  "timestamp": "2025-08-08T14:00:00Z",
  
  "api_metrics": {
    "total_requests": 150,
    "successful_requests": 148,
    "failed_requests": 2,
    "avg_response_time_ms": 850,
    "max_response_time_ms": 2100,
    "rate_limit_hits": 0,
    "quota_usage_percent": 15.5
  },
  
  "processing_metrics": {
    "events_fetched": 1250,
    "events_processed": 1248,
    "events_filtered": 892,
    "consolidation_rate": 0.15,
    "deviations_detected": 5,
    "alerts_generated": 3
  },
  
  "system_metrics": {
    "function_executions": 3,
    "total_execution_time_ms": 12500,
    "memory_usage_mb": 750,
    "cpu_usage_percent": 65,
    "errors": 1,
    "timeouts": 0
  },
  
  "business_metrics": {
    "unique_vehicles": 85,
    "unique_pois": 29,
    "rrp_events": 580,
    "tls_events": 668,
    "avg_duration_hours": 2.3
  }
}
```

## Security Rules

```javascript
// Firestore Security Rules
rules_version = '2';
service cloud.firestore {
  match /databases/{database}/documents {
    // Allow system service accounts full access
    match /{document=**} {
      allow read, write: if request.auth.token.email.matches('.*@poi-monitoring-.*\.iam\.gserviceaccount\.com');
    }
    
    // Allow authenticated users read access to configurations
    match /poi_configurations/{document} {
      allow read: if request.auth != null;
      allow write: if request.auth.token.admin == true;
    }
    
    // Allow authenticated users read access to alert states
    match /alert_states/{document} {
      allow read: if request.auth != null;
      allow write: if false; // Only system can write
    }
    
    // Restrict system settings to admins only
    match /system_settings/{document} {
      allow read: if request.auth.token.admin == true;
      allow write: if request.auth.token.admin == true;
    }
    
    // Audit log - read only for admins
    match /audit_log/{document} {
      allow read: if request.auth.token.admin == true;
      allow write: if false; // Only system can write
    }
    
    // Performance metrics - read only
    match /performance_metrics/{document} {
      allow read: if request.auth != null;
      allow write: if false; // Only system can write
    }
  }
}
```

## Indexes for Performance

```javascript
// Composite indexes for common queries
[
  {
    "collectionGroup": "alert_states",
    "queryScope": "COLLECTION",
    "fields": [
      {"fieldPath": "filial", "order": "ASCENDING"},
      {"fieldPath": "state", "order": "ASCENDING"},
      {"fieldPath": "last_updated", "order": "DESCENDING"}
    ]
  },
  {
    "collectionGroup": "alert_states", 
    "queryScope": "COLLECTION",
    "fields": [
      {"fieldPath": "current_level", "order": "ASCENDING"},
      {"fieldPath": "consecutive_hours", "order": "DESCENDING"}
    ]
  },
  {
    "collectionGroup": "audit_log",
    "queryScope": "COLLECTION", 
    "fields": [
      {"fieldPath": "event_type", "order": "ASCENDING"},
      {"fieldPath": "timestamp", "order": "DESCENDING"}
    ]
  },
  {
    "collectionGroup": "performance_metrics",
    "queryScope": "COLLECTION",
    "fields": [
      {"fieldPath": "date", "order": "DESCENDING"},
      {"fieldPath": "hour", "order": "DESCENDING"}
    ]
  }
]
```

This Firestore schema provides:
1. **Real-time state management** for active alerts
2. **Configuration management** with versioning
3. **Process coordination** with distributed locks
4. **Audit compliance** with comprehensive logging
5. **Performance monitoring** with real-time metrics
6. **Security** with fine-grained access controls
7. **Scalability** with optimized indexes and TTL cleanup