# POI Deviation Detection System - Technical Documentation

## 1. System Overview

### 1.1 Purpose
The POI Deviation Detection System is a real-time monitoring solution designed to track and analyze vehicle movements across Points of Interest (POIs) in transportation and logistics facilities. The system modernizes a legacy Selenium-based batch process into a robust, API-driven monitoring platform.

### 1.2 Key Objectives
- Real-time vehicle count monitoring
- Automated deviation detection
- Multi-level escalation for persistent anomalies
- Continuous 24/7 operational monitoring
- Precise reporting with business-specific formatting

## 2. System Architecture

### 2.1 Architecture Components
The system is composed of four primary components:

1. **Data Collector** (`src/data_collector.py`)
   - Responsible for API integration with Creare Cloud
   - Collects vehicle events from 32 specific POIs
   - Handles timezone complexities (Campo Grande UTC-4)
   - Generates hourly vehicle counts

2. **Deviation Detector** (`src/deviation_detector.py`)
   - Analyzes hourly vehicle counts
   - Implements multi-level escalation logic
   - Manages alert state and prevents duplicate notifications

3. **Alert Manager** (`src/alert_manager.py`)
   - Generates standardized alert titles
   - Manages escalation progression
   - Tracks historical alert states

4. **Reporting Engine** (`gerar_relatorio_desvios.py`)
   - Generates CSV reports
   - Formats data according to business requirements
   - Includes only current-hour vehicle information

### 2.2 Data Flow
```
[Creare Cloud API] 
    ↓ 
[Data Collector: OAuth2 Authentication]
    ↓
[Event Processing & Timezone Normalization]
    ↓
[SQLite Database Storage]
    ↓
[Deviation Detector]
    ↓
[Alert Manager]
    ↓
[CSV Report Generation]
```

## 3. Technical Implementation Details

### 3.1 Data Collection
- **Authentication**: OAuth2 with Creare Cloud
- **POI Filtering**: 32 predefined Points of Interest
- **Timezone Handling**: Campo Grande (UTC-4)
- **Data Points Collected**:
  - Vehicle identifier
  - POI location
  - Entry/exit timestamps
  - Vehicle direction

### 3.2 Deviation Detection Logic
#### Escalation Levels
- **N1**: Initial deviation detected
- **N2**: Deviation persists 1+ hours
- **N3**: Deviation persists 2+ hours
- **N4**: Deviation persists 3+ hours
- **Reset**: Automatically resets after 1+ hours without issues

#### Thresholds
Configurable via `config/thresholds.json`:
- Per-group vehicle count limits
- Escalation time windows
- Group-specific rules

### 3.3 Alert Generation
**Alert Title Format**:
`{FILIAL}_{GRUPO}_N{NIVEL}_{DDMMYYYY}_{HHMMSS}`

**Example**:
`RRP_Fábrica_N2_08082025_110000`

## 4. Configuration Management

### 4.1 Configuration Files
- `config/config.json`: API and system settings
- `config/thresholds.json`: Deviation rules
- `Grupos.csv`: POI-to-group mapping

### 4.2 POI Grouping
POIs are categorized into business groups:
- Fábrica (Factory)
- Manutenção (Maintenance)
- Terminal
- Abastecimento (Refueling)
- Buffer
- Others

## 5. Performance Characteristics

### 5.1 System Performance
- **API Response Time**: ~1.3 seconds
- **Deviation Detection**: ~0.7 seconds
- **Total Cycle Time**: ~2 seconds
- **Data Volume**: 100+ events/hour
- **Monitored POIs**: 32
- **Hourly Counts Generated**: 160

## 6. Deployment Strategy

### 6.1 Current State: Local Testing
- SQLite for local data storage
- Manual script execution
- Validated with real-world data

### 6.2 Planned GCP Migration
- **Serverless Compute**: Cloud Functions
- **Database**: BigQuery or Cloud SQL
- **Scheduling**: Cloud Scheduler
- **Storage**: Cloud Storage for reports
- **Monitoring**: Native GCP monitoring tools

## 7. Testing and Validation

### 7.1 Local Testing Achievements
- ✅ Real deviation detection validated
- ✅ Escalation logic confirmed
- ✅ CSV report generation verified
- ✅ Multi-facility monitoring (RRP, TLS)
- ✅ Timezone and API integration working

## 8. Future Enhancements
- Implement more granular alerting
- Add machine learning for predictive anomaly detection
- Enhance multi-facility support
- Develop advanced reporting dashboards

## 9. Troubleshooting
- Check API credentials in `config/config.json`
- Verify POI mappings in `Grupos.csv`
- Monitor system logs for detailed diagnostics

## 10. Security Considerations
- OAuth2 authentication
- Minimal data retention
- Configurable thresholds to prevent over-alerting

---

**Version**: 1.0
**Last Updated**: 2025-08-08
**Generated with**: Claude Code by Anthropic