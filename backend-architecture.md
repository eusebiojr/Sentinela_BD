# Backend System Architecture - POI Deviation Detection

## Current System Analysis

### Existing Implementation Strengths
Based on `/scripts/pontos_notaveis/gerar_relatorio_pontos_notaveis.py`:

✅ **OAuth2 Authentication**: Robust token management with Creare Cloud API  
✅ **POI Filtering**: Efficient filtering for RRP (11 POIs) and TLS (18 POIs)  
✅ **Data Processing**: Comprehensive event consolidation and timezone handling  
✅ **Group Classification**: Dynamic POI-to-group mapping from `Grupos.csv`  
✅ **Business Logic**: Duration calculations and event status management  
✅ **Error Handling**: API timeouts, retry logic, and graceful degradation  

### Enhancement Requirements
🔄 **Continuous Operation**: Transform from on-demand to 24/7 scheduled execution  
🔄 **Alert Generation**: Add escalation logic with N1-N4 levels  
🔄 **State Management**: Persistent tracking of alert states and history  
🔄 **Cloud Native**: Adapt for Cloud Functions and managed services  
🔄 **Scalability**: Handle increased load and parallel processing  

## Enhanced Backend Architecture

### 1. API Integration Layer

#### Enhanced OAuth2 Manager
```python
class CreareCloudAuthManager:
    """Enhanced authentication with token caching and rotation"""
    
    def __init__(self, secret_manager: SecretManager):
        self.secret_manager = secret_manager
        self.token_cache = None
        self.token_expiry = None
        
    async def get_valid_token(self) -> str:
        """Get valid token with automatic refresh"""
        if self._is_token_valid():
            return self.token_cache
            
        return await self._refresh_token()
    
    def _is_token_valid(self) -> bool:
        """Check token validity with 5-minute buffer"""
        if not self.token_cache or not self.token_expiry:
            return False
        return datetime.now() < (self.token_expiry - timedelta(minutes=5))
    
    async def _refresh_token(self) -> str:
        """Refresh OAuth2 token with retry logic"""
        credentials = await self.secret_manager.get_credentials()
        
        for attempt in range(3):
            try:
                token_data = await self._request_token(credentials)
                self.token_cache = token_data['id_token']
                # Parse JWT to get expiry
                self.token_expiry = self._extract_token_expiry(self.token_cache)
                return self.token_cache
                
            except Exception as e:
                if attempt == 2:
                    raise AuthenticationError(f"Failed to refresh token: {e}")
                await asyncio.sleep(2 ** attempt)
```

#### Enhanced API Client
```python
class CreareCloudAPIClient:
    """Enhanced API client with rate limiting and circuit breaker"""
    
    def __init__(self, auth_manager: CreareCloudAuthManager):
        self.auth_manager = auth_manager
        self.rate_limiter = RateLimiter(60, 60)  # 60 requests per minute
        self.circuit_breaker = CircuitBreaker(failure_threshold=5)
        
    async def fetch_poi_events(
        self, 
        start_time: datetime, 
        end_time: datetime,
        batch_size: int = 1000
    ) -> List[Dict]:
        """Fetch POI events with enhanced error handling"""
        
        await self.rate_limiter.acquire()
        
        with self.circuit_breaker:
            token = await self.auth_manager.get_valid_token()
            
            all_events = []
            page = 1
            
            while True:
                events_batch = await self._fetch_page(
                    token, start_time, end_time, page, batch_size
                )
                
                if not events_batch:
                    break
                    
                # Apply POI filtering (preserve existing logic)
                filtered_events = self._filter_poi_events(events_batch)
                all_events.extend(filtered_events)
                
                if len(events_batch) < batch_size:
                    break
                    
                page += 1
                await asyncio.sleep(0.1)  # Rate limiting courtesy delay
                
            return all_events
    
    def _filter_poi_events(self, events: List[Dict]) -> List[Dict]:
        """Filter events by POI (preserve existing business logic)"""
        filtered = []
        
        for event in events:
            poi_name = event.get('fenceDescription', '')
            
            # Use existing POI sets
            if poi_name in POIS_RRP or poi_name in POIS_TLS:
                filtered.append(event)
            elif 'Geral JSL RRP' in poi_name and 'Manuten' in poi_name:
                # Handle corrupted characters
                filtered.append(event)
                
        return filtered
```

### 2. Data Processing Layer

#### Enhanced Event Processor
```python
class POIEventProcessor:
    """Enhanced event processing with state management"""
    
    def __init__(
        self, 
        bigquery_client: BigQueryClient,
        firestore_client: FirestoreClient,
        config_manager: ConfigurationManager
    ):
        self.bigquery = bigquery_client
        self.firestore = firestore_client
        self.config = config_manager
        
    async def process_events_batch(
        self, 
        raw_events: List[Dict],
        processing_timestamp: datetime
    ) -> ProcessingResult:
        """Process events with enhanced consolidation"""
        
        # Preserve existing processing logic with enhancements
        processed_events = []
        
        for event in raw_events:
            processed_event = await self._process_single_event(
                event, processing_timestamp
            )
            processed_events.append(processed_event)
        
        # Apply existing consolidation logic
        consolidated_events = self._consolidate_consecutive_events(
            processed_events
        )
        
        # Store in BigQuery
        await self._store_processed_events(consolidated_events)
        
        # Update real-time state in Firestore
        await self._update_realtime_state(consolidated_events)
        
        return ProcessingResult(
            raw_count=len(raw_events),
            processed_count=len(processed_events),
            consolidated_count=len(consolidated_events)
        )
    
    def _process_single_event(self, event: Dict, timestamp: datetime) -> Dict:
        """Process single event (enhanced existing logic)"""
        
        # Preserve existing field mapping
        poi_name = event.get('fenceDescription', '')
        filial = self._get_poi_filial(poi_name)  # Existing logic
        grupo = self._get_poi_group(poi_name)   # Existing logic
        
        processed = {
            'processed_event_id': self._generate_event_id(),
            'original_event_ids': [event.get('id', '')],
            'vehicle_plate': event.get('vehiclePlate', ''),
            'vehicle_id': str(event.get('vehicleId', '')),
            'poi_name': poi_name,
            'poi_group': grupo,
            'filial': filial,
            'entry_timestamp': self._parse_timestamp(event.get('dateInFence')),
            'exit_timestamp': self._parse_timestamp(event.get('dateOutFence')),
            'duration_hours': self._calculate_duration_hours(
                event.get('dateInFence'),
                event.get('dateOutFence')
            ),
            'processed_at': timestamp,
            'source_system': 'creare_cloud'
        }
        
        return processed
```

### 3. Deviation Detection Engine

#### Alert Level Calculator
```python
class DeviationDetectionEngine:
    """Advanced deviation detection with escalation logic"""
    
    def __init__(
        self,
        bigquery_client: BigQueryClient,
        firestore_client: FirestoreClient,
        config_manager: ConfigurationManager
    ):
        self.bigquery = bigquery_client
        self.firestore = firestore_client
        self.config = config_manager
        
    async def detect_deviations(self, analysis_timestamp: datetime) -> List[Deviation]:
        """Detect deviations with N1-N4 escalation logic"""
        
        # Get current hour data
        current_hour_events = await self._get_current_hour_events(analysis_timestamp)
        
        # Get historical context for comparison
        historical_context = await self._get_historical_context(analysis_timestamp)
        
        # Get current alert states
        current_states = await self._get_current_alert_states()
        
        deviations = []
        
        # Group events by filial/POI/vehicle for analysis
        grouped_events = self._group_events_for_analysis(current_hour_events)
        
        for group_key, events in grouped_events.items():
            deviation = await self._analyze_group_deviation(
                group_key, events, historical_context, current_states
            )
            
            if deviation:
                deviations.append(deviation)
        
        return deviations
    
    async def _analyze_group_deviation(
        self,
        group_key: str,
        events: List[Dict],
        historical_context: Dict,
        current_states: Dict
    ) -> Optional[Deviation]:
        """Analyze specific group for deviation patterns"""
        
        filial, poi_name, vehicle_plate = group_key.split('|')
        
        # Check if vehicle has been in POI too long
        ongoing_events = [e for e in events if not e['exit_timestamp']]
        
        for event in ongoing_events:
            duration_hours = self._calculate_current_duration(event)
            
            # Get thresholds for this POI
            thresholds = await self.config.get_poi_thresholds(filial, poi_name)
            
            # Determine alert level based on duration
            current_level = self._calculate_alert_level(duration_hours, thresholds)
            
            if current_level:
                # Check current state to determine if escalation is needed
                state_key = f"{filial}_{self._normalize_poi_name(poi_name)}_{vehicle_plate}"
                current_state = current_states.get(state_key)
                
                if self._should_escalate(current_level, current_state):
                    return Deviation(
                        filial=filial,
                        poi_name=poi_name,
                        vehicle_plate=vehicle_plate,
                        level=current_level,
                        duration_hours=duration_hours,
                        threshold_breached=thresholds[current_level],
                        detection_timestamp=datetime.now(),
                        previous_state=current_state
                    )
        
        return None
    
    def _calculate_alert_level(self, duration_hours: float, thresholds: Dict) -> Optional[str]:
        """Calculate alert level based on duration and thresholds"""
        
        if duration_hours >= thresholds.get('N4', 12):
            return 'N4'
        elif duration_hours >= thresholds.get('N3', 8):
            return 'N3'
        elif duration_hours >= thresholds.get('N2', 4):
            return 'N2'
        elif duration_hours >= thresholds.get('N1', 2):
            return 'N1'
        
        return None
    
    def _should_escalate(self, new_level: str, current_state: Optional[Dict]) -> bool:
        """Determine if escalation is needed"""
        
        if not current_state:
            return True  # First alert
        
        current_level = current_state.get('current_level')
        
        # Escalate if level increased
        level_hierarchy = {'N1': 1, 'N2': 2, 'N3': 3, 'N4': 4}
        
        if not current_level:
            return True
            
        return level_hierarchy[new_level] > level_hierarchy[current_level]
```

### 4. Alert Management System

#### Alert Title Formatter
```python
class AlertTitleFormatter:
    """Format alerts according to specification"""
    
    @staticmethod
    def format_alert_title(
        filial: str,
        poi_name: str,
        level: str,
        timestamp: datetime
    ) -> str:
        """Format: {FILIAL}_{POI_SEM_ESPACOS}_{NIVEL}_{DDMMYYYY}_{HHMMSS}"""
        
        # Normalize POI name (remove spaces and special characters)
        poi_normalized = AlertTitleFormatter._normalize_poi_name(poi_name)
        
        # Format timestamp to closed hour (even if actual time is 16:10 -> 16:00:00)
        closed_hour = timestamp.replace(minute=0, second=0, microsecond=0)
        
        # Brazilian date format (DDMMYYYY)
        date_str = closed_hour.strftime('%d%m%Y')
        time_str = closed_hour.strftime('%H%M%S')
        
        return f"{filial}_{poi_normalized}_{level}_{date_str}_{time_str}"
    
    @staticmethod
    def _normalize_poi_name(poi_name: str) -> str:
        """Remove spaces and special characters from POI name"""
        # Replace spaces with empty string
        normalized = poi_name.replace(' ', '')
        
        # Remove common special characters
        special_chars = ['¿', '?', '-', '.', '/', '\\', '(', ')', '[', ']']
        for char in special_chars:
            normalized = normalized.replace(char, '')
        
        return normalized

#### Alert Manager
```python
class AlertManager:
    """Enhanced alert management with delivery tracking"""
    
    def __init__(
        self,
        firestore_client: FirestoreClient,
        email_service: EmailService,
        sms_service: SMSService,
        config_manager: ConfigurationManager
    ):
        self.firestore = firestore_client
        self.email_service = email_service
        self.sms_service = sms_service
        self.config = config_manager
        
    async def process_deviation_alert(self, deviation: Deviation) -> AlertResult:
        """Process deviation and send alerts"""
        
        # Format alert title according to specification
        alert_title = AlertTitleFormatter.format_alert_title(
            deviation.filial,
            deviation.poi_name,
            deviation.level,
            deviation.detection_timestamp
        )
        
        # Generate alert message
        alert_message = self._generate_alert_message(deviation, alert_title)
        
        # Get recipients for this filial and level
        recipients = await self.config.get_alert_recipients(
            deviation.filial, 
            deviation.level
        )
        
        # Send alerts through configured channels
        delivery_results = await self._send_multi_channel_alert(
            alert_title,
            alert_message,
            recipients,
            deviation.level
        )
        
        # Update alert state in Firestore
        await self._update_alert_state(deviation, alert_title)
        
        # Log alert history
        await self._log_alert_history(deviation, alert_title, delivery_results)
        
        return AlertResult(
            alert_title=alert_title,
            delivery_results=delivery_results,
            deviation=deviation
        )
    
    def _generate_alert_message(self, deviation: Deviation, alert_title: str) -> str:
        """Generate alert message content"""
        
        return f"""
        🚨 ALERTA POI - {deviation.level}
        
        Título: {alert_title}
        Filial: {deviation.filial}
        POI: {deviation.poi_name}
        Veículo: {deviation.vehicle_plate}
        
        Duração: {deviation.duration_hours:.1f} horas
        Limite: {deviation.threshold_breached} horas
        
        Detectado em: {deviation.detection_timestamp.strftime('%d/%m/%Y %H:%M:%S')}
        
        Sistema: POI Monitoring - Sentinela BD
        """
```

### 5. Configuration Management

#### Enhanced Configuration Manager
```python
class ConfigurationManager:
    """Centralized configuration management"""
    
    def __init__(
        self,
        firestore_client: FirestoreClient,
        secret_manager: SecretManager,
        storage_client: StorageClient
    ):
        self.firestore = firestore_client
        self.secret_manager = secret_manager
        self.storage = storage_client
        self._config_cache = {}
        
    async def load_poi_groups_from_csv(self) -> Dict[str, str]:
        """Load POI groups from Cloud Storage (enhanced existing logic)"""
        
        # Download Grupos.csv from Cloud Storage
        csv_content = await self.storage.download_blob(
            'poi-config-bucket',
            'poi_groups.csv'
        )
        
        groups = {}
        reader = csv.DictReader(csv_content.splitlines(), delimiter=';')
        
        for row in reader:
            poi = row.get('POI', '').strip()
            grupo = row.get('GRUPO', '').strip()
            
            if poi and grupo:
                groups[poi] = grupo
        
        # Cache in Firestore for fast access
        await self._cache_poi_groups(groups)
        
        return groups
    
    async def get_poi_thresholds(self, filial: str, poi_name: str) -> Dict[str, float]:
        """Get deviation thresholds for specific POI"""
        
        # Check cache first
        cache_key = f"thresholds_{filial}_{poi_name}"
        if cache_key in self._config_cache:
            return self._config_cache[cache_key]
        
        # Get from Firestore
        poi_config = await self.firestore.collection('poi_configurations').document(
            self._normalize_poi_name(poi_name)
        ).get()
        
        if poi_config.exists:
            thresholds = poi_config.to_dict().get('deviation_thresholds', {})
            escalation_hours = thresholds.get('escalation_hours', {
                'N1': 2, 'N2': 4, 'N3': 8, 'N4': 12
            })
        else:
            # Default thresholds
            escalation_hours = {'N1': 2, 'N2': 4, 'N3': 8, 'N4': 12}
        
        self._config_cache[cache_key] = escalation_hours
        return escalation_hours
```

## Integration with Existing Code

### Preserving Business Logic
The enhanced architecture preserves all existing business logic:

1. **POI Filtering**: Maintains `POIS_RRP` and `POIS_TLS` sets
2. **Group Classification**: Enhances existing `obter_grupo_poi()` function
3. **Consolidation**: Preserves `consolidar_eventos_consecutivos()` logic
4. **Timezone Handling**: Maintains Campo Grande timezone (`CAMPO_GRANDE_TZ`)
5. **Duration Calculations**: Preserves existing calculation methods

### Migration Strategy
```python
# Gradual migration approach
class LegacyCodeAdapter:
    """Adapter to use existing code in new architecture"""
    
    def __init__(self):
        # Import existing functions
        from scripts.pontos_notaveis.gerar_relatorio_pontos_notaveis import (
            obter_filial_poi,
            obter_grupo_poi,
            consolidar_eventos_consecutivos,
            calcular_duracao_formatada
        )
        
        self.get_poi_filial = obter_filial_poi
        self.get_poi_group = obter_grupo_poi
        self.consolidate_events = consolidar_eventos_consecutivos
        self.calculate_duration = calcular_duracao_formatada
    
    def adapt_event_processing(self, events: List[Dict]) -> List[Dict]:
        """Use existing processing logic with new data structures"""
        
        # Convert new format to legacy format
        legacy_events = self._convert_to_legacy_format(events)
        
        # Apply existing consolidation
        consolidated = self.consolidate_events(legacy_events)
        
        # Convert back to new format
        return self._convert_to_new_format(consolidated)
```

This architecture provides a robust foundation that:
- Preserves your existing business logic
- Adds 24/7 capabilities with Cloud Functions
- Implements the required N1-N4 escalation system
- Formats alerts according to your specification
- Scales efficiently on GCP infrastructure
- Maintains data consistency and reliability