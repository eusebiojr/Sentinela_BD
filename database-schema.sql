-- BigQuery Database Schema for POI Monitoring System
-- Optimized for time-series data and high-performance queries

-- Dataset Creation
CREATE SCHEMA IF NOT EXISTS `poi_monitoring`
OPTIONS(
  description="POI deviation detection system data",
  location="us-central1"
);

-- 1. Raw POI Events Table (Direct API Data)
CREATE OR REPLACE TABLE `poi_monitoring.poi_events_raw` (
  -- Primary identifiers
  event_id STRING NOT NULL,
  vehicle_id STRING NOT NULL,
  vehicle_plate STRING NOT NULL,
  fence_id STRING NOT NULL,
  customer_child_id STRING NOT NULL,
  
  -- POI information
  fence_description STRING NOT NULL,
  poi_group STRING,
  filial STRING NOT NULL,
  
  -- Event timestamps (partitioned column)
  event_date DATE NOT NULL,
  date_in_fence TIMESTAMP,
  date_out_fence TIMESTAMP,
  updated_at TIMESTAMP NOT NULL,
  
  -- Event details
  status INT64 NOT NULL, -- 0=exit, 1=entry
  status_description STRING,
  
  -- Processing metadata
  api_fetch_timestamp TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP(),
  raw_payload JSON,
  
  -- Data quality flags
  is_valid BOOLEAN DEFAULT TRUE,
  validation_errors ARRAY<STRING>
)
PARTITION BY event_date
CLUSTER BY filial, fence_description, vehicle_plate
OPTIONS(
  description="Raw POI events from Creare Cloud API",
  partition_expiration_days=730, -- 2 years retention
  require_partition_filter=TRUE
);

-- 2. Processed POI Events Table (Cleaned and Consolidated)
CREATE OR REPLACE TABLE `poi_monitoring.poi_events_processed` (
  -- Primary keys
  processed_event_id STRING NOT NULL,
  original_event_ids ARRAY<STRING> NOT NULL,
  
  -- Vehicle and location
  vehicle_plate STRING NOT NULL,
  vehicle_id STRING NOT NULL,
  poi_name STRING NOT NULL,
  poi_group STRING NOT NULL,
  filial STRING NOT NULL,
  
  -- Consolidated timestamps
  event_date DATE NOT NULL,
  entry_timestamp TIMESTAMP NOT NULL,
  exit_timestamp TIMESTAMP,
  
  -- Duration calculations
  duration_minutes INT64,
  duration_hours DECIMAL(10,2),
  
  -- Business logic fields
  is_consolidated BOOLEAN DEFAULT FALSE,
  consolidation_type STRING, -- 'consecutive_same_poi', 'group_related', etc.
  consolidated_event_count INT64 DEFAULT 1,
  
  -- Processing metadata
  processed_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP(),
  processing_version STRING DEFAULT 'v1.0',
  
  -- Escalation tracking
  has_deviation BOOLEAN DEFAULT FALSE,
  deviation_detected_at TIMESTAMP,
  current_alert_level STRING, -- 'N1', 'N2', 'N3', 'N4', NULL
  
  -- Data lineage
  source_system STRING DEFAULT 'creare_cloud',
  data_quality_score DECIMAL(3,2) DEFAULT 1.0
)
PARTITION BY event_date
CLUSTER BY filial, poi_group, vehicle_plate, entry_timestamp
OPTIONS(
  description="Processed and consolidated POI events",
  partition_expiration_days=730,
  require_partition_filter=TRUE
);

-- 3. POI Deviations Detection Table
CREATE OR REPLACE TABLE `poi_monitoring.poi_deviations` (
  -- Deviation identification
  deviation_id STRING NOT NULL,
  detection_timestamp TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP(),
  
  -- Location and scope
  filial STRING NOT NULL,
  poi_name STRING NOT NULL,
  poi_group STRING NOT NULL,
  affected_vehicles ARRAY<STRING> NOT NULL,
  
  -- Deviation details
  deviation_type STRING NOT NULL, -- 'prolonged_stay', 'excessive_visits', 'pattern_anomaly'
  severity_level STRING NOT NULL, -- 'N1', 'N2', 'N3', 'N4'
  threshold_breached STRING,
  actual_value DECIMAL(10,2),
  expected_value DECIMAL(10,2),
  
  -- Time window analysis
  analysis_window_start TIMESTAMP NOT NULL,
  analysis_window_end TIMESTAMP NOT NULL,
  detection_date DATE NOT NULL,
  
  -- Escalation tracking
  first_alert_sent_at TIMESTAMP,
  last_alert_sent_at TIMESTAMP,
  alert_count INT64 DEFAULT 0,
  escalation_history ARRAY<STRUCT<
    level STRING,
    timestamp TIMESTAMP,
    duration_hours INT64
  >>,
  
  -- Resolution tracking
  is_resolved BOOLEAN DEFAULT FALSE,
  resolved_at TIMESTAMP,
  resolution_reason STRING,
  auto_resolved BOOLEAN DEFAULT FALSE,
  
  -- Alert formatting data
  alert_title STRING, -- Pre-formatted: {FILIAL}_{POI_SEM_ESPACOS}_{NIVEL}_{DDMMYYYY}_{HHMMSS}
  alert_message TEXT,
  
  -- Processing metadata
  detection_algorithm_version STRING DEFAULT 'v1.0',
  confidence_score DECIMAL(3,2) DEFAULT 1.0
)
PARTITION BY detection_date
CLUSTER BY filial, poi_group, severity_level
OPTIONS(
  description="Detected POI deviations and alert states",
  partition_expiration_days=1095 -- 3 years for compliance
);

-- 4. Alert History Table
CREATE OR REPLACE TABLE `poi_monitoring.alert_history` (
  -- Alert identification
  alert_id STRING NOT NULL,
  deviation_id STRING NOT NULL,
  alert_timestamp TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP(),
  
  -- Alert details
  alert_title STRING NOT NULL,
  alert_level STRING NOT NULL, -- 'N1', 'N2', 'N3', 'N4'
  filial STRING NOT NULL,
  poi_name STRING NOT NULL,
  vehicle_plates ARRAY<STRING>,
  
  -- Delivery information
  delivery_channels ARRAY<STRING>, -- ['email', 'sms', 'webhook']
  recipients ARRAY<STRING>,
  delivery_status STRING NOT NULL, -- 'pending', 'sent', 'delivered', 'failed'
  delivery_attempts INT64 DEFAULT 0,
  
  -- Message content
  message_body TEXT,
  message_format STRING DEFAULT 'html',
  
  -- Timing information
  alert_date DATE NOT NULL,
  sent_at TIMESTAMP,
  delivered_at TIMESTAMP,
  acknowledged_at TIMESTAMP,
  
  -- Response tracking
  response_received BOOLEAN DEFAULT FALSE,
  response_type STRING,
  response_timestamp TIMESTAMP,
  
  -- Delivery metadata
  external_message_id STRING,
  delivery_provider STRING,
  delivery_cost_cents INT64,
  
  -- Error handling
  delivery_errors ARRAY<STRING>,
  retry_count INT64 DEFAULT 0,
  max_retries INT64 DEFAULT 3
)
PARTITION BY alert_date
CLUSTER BY filial, alert_level, delivery_status
OPTIONS(
  description="Complete history of alert deliveries",
  partition_expiration_days=1095 -- 3 years retention
);

-- 5. System Configuration Table
CREATE OR REPLACE TABLE `poi_monitoring.system_configuration` (
  config_key STRING NOT NULL,
  config_value JSON NOT NULL,
  config_type STRING NOT NULL, -- 'poi_mapping', 'threshold', 'alert_setting', 'system_param'
  filial STRING, -- NULL for global settings
  poi_name STRING, -- NULL for filial/global settings
  
  -- Version control
  version INT64 NOT NULL DEFAULT 1,
  is_active BOOLEAN DEFAULT TRUE,
  effective_from TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP(),
  effective_until TIMESTAMP,
  
  -- Change tracking
  created_by STRING DEFAULT 'system',
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP(),
  modified_by STRING,
  modified_at TIMESTAMP,
  
  -- Validation
  schema_version STRING DEFAULT 'v1.0',
  validation_status STRING DEFAULT 'valid'
)
CLUSTER BY config_type, filial, is_active
OPTIONS(
  description="System configuration and POI mappings"
);

-- 6. Processing Statistics Table
CREATE OR REPLACE TABLE `poi_monitoring.processing_statistics` (
  stats_id STRING NOT NULL,
  processing_date DATE NOT NULL,
  processing_hour INT64 NOT NULL, -- 0-23
  processing_timestamp TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP(),
  
  -- Volume metrics
  events_fetched INT64 DEFAULT 0,
  events_processed INT64 DEFAULT 0,
  events_consolidated INT64 DEFAULT 0,
  deviations_detected INT64 DEFAULT 0,
  alerts_sent INT64 DEFAULT 0,
  
  -- Performance metrics
  api_response_time_ms INT64,
  processing_duration_ms INT64,
  total_execution_time_ms INT64,
  
  -- Quality metrics
  data_quality_issues INT64 DEFAULT 0,
  api_errors INT64 DEFAULT 0,
  processing_errors INT64 DEFAULT 0,
  alert_failures INT64 DEFAULT 0,
  
  -- System health
  memory_usage_mb DECIMAL(10,2),
  cpu_usage_percent DECIMAL(5,2),
  function_timeout BOOLEAN DEFAULT FALSE,
  
  -- Business metrics by filial
  rrp_events INT64 DEFAULT 0,
  tls_events INT64 DEFAULT 0,
  unique_vehicles INT64 DEFAULT 0,
  unique_pois INT64 DEFAULT 0
)
PARTITION BY processing_date
CLUSTER BY processing_date, processing_hour
OPTIONS(
  description="System processing statistics and metrics",
  partition_expiration_days=365 -- 1 year retention
);

-- Views for Common Queries

-- Active Deviations View
CREATE OR REPLACE VIEW `poi_monitoring.active_deviations` AS
SELECT 
  deviation_id,
  filial,
  poi_name,
  poi_group,
  severity_level,
  deviation_type,
  affected_vehicles,
  detection_timestamp,
  TIMESTAMP_DIFF(CURRENT_TIMESTAMP(), detection_timestamp, HOUR) as hours_since_detection,
  alert_count,
  last_alert_sent_at
FROM `poi_monitoring.poi_deviations`
WHERE is_resolved = FALSE
AND detection_date >= DATE_SUB(CURRENT_DATE(), INTERVAL 7 DAY);

-- Hourly Processing Summary View
CREATE OR REPLACE VIEW `poi_monitoring.hourly_summary` AS
SELECT 
  processing_date,
  processing_hour,
  SUM(events_fetched) as total_events_fetched,
  SUM(events_processed) as total_events_processed,
  SUM(deviations_detected) as total_deviations,
  SUM(alerts_sent) as total_alerts,
  AVG(api_response_time_ms) as avg_api_response_time,
  AVG(processing_duration_ms) as avg_processing_time,
  SUM(api_errors + processing_errors) as total_errors
FROM `poi_monitoring.processing_statistics`
WHERE processing_date >= DATE_SUB(CURRENT_DATE(), INTERVAL 30 DAY)
GROUP BY processing_date, processing_hour
ORDER BY processing_date DESC, processing_hour DESC;

-- POI Performance View
CREATE OR REPLACE VIEW `poi_monitoring.poi_performance` AS
SELECT 
  filial,
  poi_name,
  poi_group,
  COUNT(*) as total_events,
  COUNT(DISTINCT vehicle_plate) as unique_vehicles,
  AVG(duration_hours) as avg_duration_hours,
  COUNT(CASE WHEN has_deviation THEN 1 END) as deviation_count,
  MAX(processed_at) as last_activity
FROM `poi_monitoring.poi_events_processed`
WHERE event_date >= DATE_SUB(CURRENT_DATE(), INTERVAL 30 DAY)
GROUP BY filial, poi_name, poi_group
ORDER BY deviation_count DESC, total_events DESC;

-- Data Retention Procedures
CREATE OR REPLACE PROCEDURE `poi_monitoring.cleanup_old_data`()
BEGIN
  -- Archive old raw events (older than 2 years)
  EXPORT DATA OPTIONS(
    uri='gs://poi-archive-bucket/raw_events/year=*',
    format='PARQUET',
    overwrite=true
  ) AS
  SELECT * FROM `poi_monitoring.poi_events_raw`
  WHERE event_date < DATE_SUB(CURRENT_DATE(), INTERVAL 730 DAY);
  
  -- Delete archived raw data
  DELETE FROM `poi_monitoring.poi_events_raw`
  WHERE event_date < DATE_SUB(CURRENT_DATE(), INTERVAL 730 DAY);
  
  -- Clean up resolved deviations older than 1 year
  DELETE FROM `poi_monitoring.poi_deviations`
  WHERE is_resolved = TRUE 
  AND resolved_at < TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 365 DAY);
  
END;

-- Performance Optimization Indexes
-- BigQuery automatically optimizes based on clustering, but we can add explicit recommendations:

-- Indexes for common query patterns:
-- 1. Real-time deviation detection: CLUSTER BY filial, poi_group, entry_timestamp
-- 2. Historical analysis: PARTITION BY event_date
-- 3. Vehicle tracking: CLUSTER BY vehicle_plate
-- 4. Alert management: CLUSTER BY severity_level, delivery_status

-- Sample data insertion procedure for testing
CREATE OR REPLACE PROCEDURE `poi_monitoring.insert_test_data`()
BEGIN
  -- Insert sample configuration
  INSERT INTO `poi_monitoring.system_configuration` 
  (config_key, config_value, config_type, filial)
  VALUES 
  ('deviation_threshold_hours', JSON '{"N1": 2, "N2": 4, "N3": 8, "N4": 12}', 'threshold', NULL),
  ('alert_channels', JSON '["email", "sms"]', 'alert_setting', NULL),
  ('max_hourly_events_per_poi', JSON '10', 'threshold', 'RRP'),
  ('max_hourly_events_per_poi', JSON '15', 'threshold', 'TLS');
  
END;