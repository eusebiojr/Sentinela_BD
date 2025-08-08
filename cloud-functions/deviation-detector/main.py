#!/usr/bin/env python3
"""
Cloud Function: POI Deviation Detector
Analyzes POI events for deviations and manages N1-N4 escalation
Implements business logic for alert level determination
"""

import json
import logging
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Optional, NamedTuple
from google.cloud import bigquery
from google.cloud import firestore
from google.cloud import pubsub_v1
import functions_framework

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Campo Grande timezone
CAMPO_GRANDE_TZ = timezone(timedelta(hours=-4))

class Deviation(NamedTuple):
    """Deviation detection result"""
    deviation_id: str
    filial: str
    poi_name: str
    poi_normalized: str
    vehicle_plate: str
    vehicle_id: str
    current_level: str
    duration_hours: float
    threshold_breached: float
    detection_timestamp: datetime
    entry_timestamp: datetime
    previous_state: Optional[Dict]
    confidence_score: float

class DeviationDetectionEngine:
    """Core deviation detection logic with N1-N4 escalation"""
    
    def __init__(
        self,
        bigquery_client: bigquery.Client,
        firestore_client: firestore.Client,
        pubsub_publisher: pubsub_v1.PublisherClient
    ):
        self.bigquery = bigquery_client
        self.firestore = firestore_client
        self.publisher = pubsub_publisher
        self.project_id = bigquery_client.project
        
    def normalize_poi_name(self, poi_name: str) -> str:
        """Normalize POI name for alert titles"""
        # Remove spaces and special characters
        normalized = poi_name.replace(' ', '')
        special_chars = ['¿', '?', '-', '.', '/', '\\', '(', ')', '[', ']']
        for char in special_chars:
            normalized = normalized.replace(char, '')
        return normalized
    
    async def detect_deviations(self) -> List[Deviation]:
        """Main deviation detection logic"""
        logger.info("Starting deviation detection")
        
        detection_timestamp = datetime.now()
        
        # Get active POI sessions (vehicles currently in POIs)
        active_sessions = await self._get_active_poi_sessions()
        logger.info(f"Found {len(active_sessions)} active POI sessions")
        
        # Get current alert states
        current_states = await self._get_current_alert_states()
        logger.info(f"Found {len(current_states)} existing alert states")
        
        # Get POI thresholds
        poi_thresholds = await self._get_poi_thresholds()
        
        deviations = []
        
        for session in active_sessions:
            try:
                deviation = await self._analyze_session_for_deviation(
                    session, current_states, poi_thresholds, detection_timestamp
                )
                
                if deviation:
                    deviations.append(deviation)
                    
            except Exception as e:
                logger.error(f"Error analyzing session {session.get('session_key', 'unknown')}: {e}")
                continue
        
        logger.info(f"Detected {len(deviations)} deviations")
        return deviations
    
    async def _get_active_poi_sessions(self) -> List[Dict]:
        """Get vehicles currently in POIs (no exit timestamp)"""
        query = f"""
        WITH latest_events AS (
            SELECT 
                vehicle_plate,
                vehicle_id,
                poi_name,
                poi_group,
                filial,
                entry_timestamp,
                exit_timestamp,
                processed_at,
                ROW_NUMBER() OVER (
                    PARTITION BY vehicle_plate, poi_name 
                    ORDER BY processed_at DESC
                ) as rn
            FROM `{self.project_id}.poi_monitoring.poi_events_processed`
            WHERE event_date >= DATE_SUB(CURRENT_DATE(), INTERVAL 3 DAY)
        )
        SELECT 
            vehicle_plate,
            vehicle_id,
            poi_name,
            poi_group,
            filial,
            entry_timestamp,
            exit_timestamp,
            processed_at,
            DATETIME_DIFF(CURRENT_DATETIME(), entry_timestamp, HOUR) as duration_hours
        FROM latest_events
        WHERE rn = 1 
        AND exit_timestamp IS NULL
        AND entry_timestamp IS NOT NULL
        ORDER BY duration_hours DESC
        """
        
        try:
            query_job = self.bigquery.query(query)
            results = query_job.result()
            
            sessions = []
            for row in results:
                session = {
                    'vehicle_plate': row.vehicle_plate,
                    'vehicle_id': row.vehicle_id,
                    'poi_name': row.poi_name,
                    'poi_group': row.poi_group or 'Unknown',
                    'filial': row.filial,
                    'entry_timestamp': row.entry_timestamp,
                    'exit_timestamp': row.exit_timestamp,
                    'duration_hours': float(row.duration_hours or 0),
                    'session_key': f"{row.filial}_{self.normalize_poi_name(row.poi_name)}_{row.vehicle_plate}"
                }
                sessions.append(session)
            
            return sessions
            
        except Exception as e:
            logger.error(f"Error getting active sessions: {e}")
            return []
    
    async def _get_current_alert_states(self) -> Dict[str, Dict]:
        """Get current alert states from Firestore"""
        try:
            alert_states = {}
            
            # Query active alert states
            docs = self.firestore.collection('alert_states').where(
                'state', '==', 'active'
            ).stream()
            
            for doc in docs:
                data = doc.to_dict()
                alert_states[doc.id] = data
            
            return alert_states
            
        except Exception as e:
            logger.error(f"Error getting alert states: {e}")
            return {}
    
    async def _get_poi_thresholds(self) -> Dict[str, Dict]:
        """Get POI-specific thresholds from Firestore"""
        try:
            thresholds = {}
            
            docs = self.firestore.collection('poi_configurations').stream()
            
            for doc in docs:
                data = doc.to_dict()
                poi_name = data.get('poi_name')
                if poi_name:
                    escalation_hours = data.get('deviation_thresholds', {}).get('escalation_hours', {
                        'N1': 2, 'N2': 4, 'N3': 8, 'N4': 12
                    })
                    thresholds[poi_name] = escalation_hours
            
            return thresholds
            
        except Exception as e:
            logger.error(f"Error getting POI thresholds: {e}")
            return {}
    
    async def _analyze_session_for_deviation(
        self,
        session: Dict,
        current_states: Dict[str, Dict],
        poi_thresholds: Dict[str, Dict],
        detection_timestamp: datetime
    ) -> Optional[Deviation]:
        """Analyze individual session for deviation"""
        
        session_key = session['session_key']
        duration_hours = session['duration_hours']
        poi_name = session['poi_name']
        
        # Get thresholds for this POI (with defaults)
        thresholds = poi_thresholds.get(poi_name, {
            'N1': 2, 'N2': 4, 'N3': 8, 'N4': 12
        })
        
        # Determine alert level based on duration
        current_level = self._calculate_alert_level(duration_hours, thresholds)
        
        if not current_level:
            return None  # No threshold breached
        
        # Get current state for this session
        current_state = current_states.get(session_key)
        
        # Check if escalation is needed
        if not self._should_escalate(current_level, current_state, detection_timestamp):
            return None
        
        # Calculate confidence score based on data quality
        confidence_score = self._calculate_confidence_score(session, current_state)
        
        # Generate deviation
        deviation_id = f"{session_key}_{current_level}_{detection_timestamp.strftime('%Y%m%d_%H%M%S')}"
        
        return Deviation(
            deviation_id=deviation_id,
            filial=session['filial'],
            poi_name=session['poi_name'],
            poi_normalized=self.normalize_poi_name(session['poi_name']),
            vehicle_plate=session['vehicle_plate'],
            vehicle_id=session['vehicle_id'],
            current_level=current_level,
            duration_hours=duration_hours,
            threshold_breached=thresholds[current_level],
            detection_timestamp=detection_timestamp,
            entry_timestamp=session['entry_timestamp'],
            previous_state=current_state,
            confidence_score=confidence_score
        )
    
    def _calculate_alert_level(self, duration_hours: float, thresholds: Dict[str, float]) -> Optional[str]:
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
    
    def _should_escalate(
        self, 
        new_level: str, 
        current_state: Optional[Dict], 
        detection_timestamp: datetime
    ) -> bool:
        """Determine if escalation is needed based on business rules"""
        
        if not current_state:
            return True  # First alert
        
        current_level = current_state.get('current_level')
        last_alert_sent = current_state.get('last_alert_sent')
        
        # Level hierarchy
        level_hierarchy = {'N1': 1, 'N2': 2, 'N3': 3, 'N4': 4}
        
        # Always escalate if level increased
        if not current_level or level_hierarchy[new_level] > level_hierarchy[current_level]:
            return True
        
        # For same level, check time-based rules
        if new_level == current_level and last_alert_sent:
            try:
                last_alert_dt = datetime.fromisoformat(last_alert_sent.replace('Z', '+00:00'))
                hours_since_last_alert = (detection_timestamp - last_alert_dt).total_seconds() / 3600
                
                # Re-alert rules based on level
                if new_level == 'N1' and hours_since_last_alert >= 4:  # Re-alert N1 every 4 hours
                    return True
                elif new_level == 'N2' and hours_since_last_alert >= 2:  # Re-alert N2 every 2 hours
                    return True
                elif new_level in ['N3', 'N4'] and hours_since_last_alert >= 1:  # Re-alert N3/N4 every hour
                    return True
                    
            except Exception as e:
                logger.error(f"Error parsing last alert timestamp: {e}")
                return True  # Default to sending alert if timestamp parsing fails
        
        return False
    
    def _calculate_confidence_score(self, session: Dict, current_state: Optional[Dict]) -> float:
        """Calculate confidence score for the deviation"""
        score = 1.0
        
        # Reduce confidence if data is incomplete
        if not session.get('entry_timestamp'):
            score *= 0.7
        
        if not session.get('poi_group') or session.get('poi_group') == 'Unknown':
            score *= 0.9
        
        # Increase confidence if this is a repeated pattern
        if current_state:
            escalation_history = current_state.get('escalation_history', [])
            if len(escalation_history) > 1:
                score *= 1.1
        
        return min(score, 1.0)
    
    async def store_deviation(self, deviation: Deviation) -> bool:
        """Store deviation in BigQuery and update Firestore state"""
        try:
            # Store in BigQuery
            deviation_record = {
                'deviation_id': deviation.deviation_id,
                'detection_timestamp': deviation.detection_timestamp,
                'filial': deviation.filial,
                'poi_name': deviation.poi_name,
                'poi_group': 'Unknown',  # TODO: Get from session
                'affected_vehicles': [deviation.vehicle_plate],
                'deviation_type': 'prolonged_stay',
                'severity_level': deviation.current_level,
                'threshold_breached': str(deviation.threshold_breached),
                'actual_value': deviation.duration_hours,
                'expected_value': deviation.threshold_breached,
                'analysis_window_start': deviation.entry_timestamp,
                'analysis_window_end': deviation.detection_timestamp,
                'detection_date': deviation.detection_timestamp.date(),
                'alert_count': 1,
                'is_resolved': False,
                'confidence_score': deviation.confidence_score,
                'alert_title': self._generate_alert_title(deviation),
                'alert_message': self._generate_alert_message(deviation)
            }
            
            table_id = f"{self.project_id}.poi_monitoring.poi_deviations"
            
            job_config = bigquery.LoadJobConfig(
                write_disposition=bigquery.WriteDisposition.WRITE_APPEND
            )
            
            job = self.bigquery.load_table_from_json([deviation_record], table_id, job_config=job_config)
            job.result()
            
            # Update Firestore state
            await self._update_alert_state(deviation)
            
            logger.info(f"Stored deviation {deviation.deviation_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error storing deviation: {e}")
            return False
    
    def _generate_alert_title(self, deviation: Deviation) -> str:
        """Generate alert title: {FILIAL}_{POI_SEM_ESPACOS}_{NIVEL}_{DDMMYYYY}_{HHMMSS}"""
        
        # Use closed hour (even if detection at 16:10 -> 16:00:00)
        closed_hour = deviation.detection_timestamp.replace(minute=0, second=0, microsecond=0)
        
        # Convert to Campo Grande timezone
        local_time = closed_hour.astimezone(CAMPO_GRANDE_TZ)
        
        # Brazilian date format
        date_str = local_time.strftime('%d%m%Y')
        time_str = local_time.strftime('%H%M%S')
        
        return f"{deviation.filial}_{deviation.poi_normalized}_{deviation.current_level}_{date_str}_{time_str}"
    
    def _generate_alert_message(self, deviation: Deviation) -> str:
        """Generate alert message content"""
        
        return f"""
        🚨 ALERTA POI - {deviation.current_level}
        
        Filial: {deviation.filial}
        POI: {deviation.poi_name}
        Veículo: {deviation.vehicle_plate}
        
        Duração: {deviation.duration_hours:.1f} horas
        Limite: {deviation.threshold_breached} horas
        Excesso: {deviation.duration_hours - deviation.threshold_breached:.1f} horas
        
        Entrada: {deviation.entry_timestamp.strftime('%d/%m/%Y %H:%M')}
        Detectado: {deviation.detection_timestamp.strftime('%d/%m/%Y %H:%M')}
        
        Sistema: Sentinela BD - POI Monitoring
        """
    
    async def _update_alert_state(self, deviation: Deviation):
        """Update or create alert state in Firestore"""
        try:
            session_key = f"{deviation.filial}_{deviation.poi_normalized}_{deviation.vehicle_plate}"
            
            # Prepare escalation history entry
            escalation_entry = {
                'level': deviation.current_level,
                'timestamp': deviation.detection_timestamp.isoformat(),
                'duration_hours': int(deviation.duration_hours),
                'alert_sent': False  # Will be updated by alert manager
            }
            
            # Get existing state or create new
            doc_ref = self.firestore.collection('alert_states').document(session_key)
            doc = doc_ref.get()
            
            if doc.exists:
                # Update existing state
                current_data = doc.to_dict()
                escalation_history = current_data.get('escalation_history', [])
                escalation_history.append(escalation_entry)
                
                update_data = {
                    'current_level': deviation.current_level,
                    'last_updated': deviation.detection_timestamp,
                    'escalation_history': escalation_history,
                    'alert_count': current_data.get('alert_count', 0) + 1,
                    'consecutive_hours': int(deviation.duration_hours),
                    'last_alert_title': self._generate_alert_title(deviation),
                    'actual_duration_hours': deviation.duration_hours,
                    'deviation_magnitude': deviation.duration_hours - deviation.threshold_breached
                }
                
                doc_ref.update(update_data)
                
            else:
                # Create new state
                new_state = {
                    'filial': deviation.filial,
                    'poi_name': deviation.poi_name,
                    'poi_normalized': deviation.poi_normalized,
                    'poi_group': 'Unknown',  # TODO: Get from session
                    'vehicle_plate': deviation.vehicle_plate,
                    'vehicle_id': deviation.vehicle_id,
                    'current_level': deviation.current_level,
                    'state': 'active',
                    'first_detection': deviation.detection_timestamp,
                    'last_updated': deviation.detection_timestamp,
                    'escalation_history': [escalation_entry],
                    'alert_count': 1,
                    'last_alert_title': self._generate_alert_title(deviation),
                    'consecutive_hours': int(deviation.duration_hours),
                    'threshold_hours': {
                        'N1': 2, 'N2': 4, 'N3': 8, 'N4': 12
                    },
                    'entry_timestamp': deviation.entry_timestamp,
                    'actual_duration_hours': deviation.duration_hours,
                    'deviation_magnitude': deviation.duration_hours - deviation.threshold_breached,
                    'created_at': deviation.detection_timestamp,
                    'updated_at': deviation.detection_timestamp,
                    'ttl': deviation.detection_timestamp + timedelta(days=7)  # Auto cleanup
                }
                
                doc_ref.set(new_state)
            
        except Exception as e:
            logger.error(f"Error updating alert state: {e}")
    
    async def publish_deviation_alerts(self, deviations: List[Deviation]) -> int:
        """Publish deviations to Pub/Sub for alert manager"""
        if not deviations:
            return 0
        
        try:
            topic_path = self.publisher.topic_path(self.project_id, 'poi-deviation-alerts')
            
            published_count = 0
            
            for deviation in deviations:
                message_data = {
                    'deviation_id': deviation.deviation_id,
                    'filial': deviation.filial,
                    'poi_name': deviation.poi_name,
                    'poi_normalized': deviation.poi_normalized,
                    'vehicle_plate': deviation.vehicle_plate,
                    'current_level': deviation.current_level,
                    'duration_hours': deviation.duration_hours,
                    'alert_title': self._generate_alert_title(deviation),
                    'alert_message': self._generate_alert_message(deviation),
                    'detection_timestamp': deviation.detection_timestamp.isoformat(),
                    'confidence_score': deviation.confidence_score
                }
                
                # Publish message
                future = self.publisher.publish(
                    topic_path,
                    json.dumps(message_data).encode('utf-8'),
                    filial=deviation.filial,
                    level=deviation.current_level,
                    poi=deviation.poi_name
                )
                
                # Wait for publish to complete
                future.result()
                published_count += 1
                
            logger.info(f"Published {published_count} deviation alerts to Pub/Sub")
            return published_count
            
        except Exception as e:
            logger.error(f"Error publishing deviation alerts: {e}")
            return 0

@functions_framework.cloud_event
def detect_poi_deviations(cloud_event):
    """Main Cloud Function entry point"""
    logger.info("POI Deviation Detector started")
    
    try:
        # Initialize clients
        bigquery_client = bigquery.Client()
        firestore_client = firestore.Client()
        publisher = pubsub_v1.PublisherClient()
        
        # Initialize detection engine
        detector = DeviationDetectionEngine(bigquery_client, firestore_client, publisher)
        
        # Detect deviations
        logger.info("Detecting POI deviations")
        deviations = asyncio.run(detector.detect_deviations())
        
        if not deviations:
            logger.info("No deviations detected")
            return {"status": "success", "message": "No deviations detected", "deviations_count": 0}
        
        # Store deviations
        logger.info(f"Storing {len(deviations)} deviations")
        stored_count = 0
        for deviation in deviations:
            if asyncio.run(detector.store_deviation(deviation)):
                stored_count += 1
        
        # Publish alerts
        logger.info("Publishing deviation alerts")
        published_count = asyncio.run(detector.publish_deviation_alerts(deviations))
        
        logger.info("POI Deviation Detector completed successfully")
        
        return {
            "status": "success",
            "message": f"Detected {len(deviations)} deviations, stored {stored_count}, published {published_count} alerts",
            "deviations_count": len(deviations),
            "stored_count": stored_count,
            "published_count": published_count
        }
        
    except Exception as e:
        logger.error(f"POI Deviation Detector failed: {e}")
        return {
            "status": "error",
            "message": str(e)
        }

# For local testing
if __name__ == "__main__":
    import asyncio
    
    class MockCloudEvent:
        pass
    
    result = detect_poi_deviations(MockCloudEvent())
    print(json.dumps(result, indent=2))