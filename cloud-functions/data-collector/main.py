#!/usr/bin/env python3
"""
Cloud Function: POI Data Collector
Collects POI events from Creare Cloud API every hour
Based on existing gerar_relatorio_pontos_notaveis.py
"""

import json
import base64
import urllib.request
import urllib.parse
import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Optional, Tuple
from google.cloud import bigquery
from google.cloud import firestore
from google.cloud import secretmanager
from google.cloud import storage
import functions_framework

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Timezone de Campo Grande/MS (UTC-4) - preserve existing logic
CAMPO_GRANDE_TZ = timezone(timedelta(hours=-4))

# POI filters - preserve existing business logic
POIS_RRP = {
    'Manutencao JSL RRP',
    'Carregamento Fabrica RRP', 
    'Buffer Frotas',
    'Abastecimento Frotas RRP',
    'Oficina JSL',
    'Posto Mutum',
    'Agua Clara',
    'PA AGUA CLARA',
    'Descarga Inocencia',
    'Manuten¿¿o Geral JSL RRP'  # POI with broken characters
}

POIS_TLS = {
    'Carregamento Fabrica',
    'AREA EXTERNA SUZANO',
    'POSTO DE ABASTECIMENTO',
    'Fila abastecimento posto',
    'PA Celulose',
    'Manutencao Celulose',
    'MONTANINI',
    'SELVIRIA',
    'FILA DESCARGA APT',
    'Descarga TAP',
    'PB Lopes',
    'Oficina Central JSL',
    'PB LOPES SCANIA',
    'MS3 LAVA JATO',
    'REBUCCI',
    'CEMAVI',
    'FEISCAR',
    'DIESELTRONIC',
    'LM RADIADORES',
    'ALBINO',
    'JDIESEL',
    'TRUCK LAZER'
}

POIS_FILTRADOS = POIS_RRP | POIS_TLS

class CreareCloudClient:
    """Enhanced API client based on existing code"""
    
    def __init__(self, secret_manager_client: secretmanager.SecretManagerServiceClient):
        self.secret_manager = secret_manager_client
        self.project_id = "poi-monitoring-prod"  # Update with your project
        
    def get_credentials(self) -> Tuple[str, str]:
        """Get API credentials from Secret Manager"""
        try:
            # Get client ID
            client_id_name = f"projects/{self.project_id}/secrets/creare-client-id/versions/latest"
            client_id_response = self.secret_manager.access_secret_version(request={"name": client_id_name})
            client_id = client_id_response.payload.data.decode("UTF-8")
            
            # Get client secret
            client_secret_name = f"projects/{self.project_id}/secrets/creare-client-secret/versions/latest"
            client_secret_response = self.secret_manager.access_secret_version(request={"name": client_secret_name})
            client_secret = client_secret_response.payload.data.decode("UTF-8")
            
            return client_id, client_secret
        except Exception as e:
            logger.error(f"Failed to get credentials: {e}")
            # Fallback to existing hardcoded values for testing
            return "56963", "1MSiBaH879w="
    
    def get_token(self) -> Optional[str]:
        """Get OAuth2 token - enhanced existing logic"""
        try:
            client_id, client_secret = self.get_credentials()
            oauth_url = "https://openid-provider.crearecloud.com.br/auth/v1/token?lang=pt-BR"
            
            credentials = f"{client_id}:{client_secret}"
            encoded_credentials = base64.b64encode(credentials.encode()).decode()
            
            headers = {
                'Authorization': f'Basic {encoded_credentials}',
                'Content-Type': 'application/json'
            }
            
            data = json.dumps({"grant_type": "client_credentials"}).encode('utf-8')
            request = urllib.request.Request(oauth_url, data=data, headers=headers, method='POST')
            
            with urllib.request.urlopen(request, timeout=30) as response:
                token_data = json.loads(response.read().decode('utf-8'))
                return token_data.get('id_token')
                
        except Exception as e:
            logger.error(f"Failed to get token: {e}")
            return None
    
    def fetch_poi_events(self, hours_back: int = 1) -> List[Dict]:
        """Fetch POI events - enhanced existing logic"""
        logger.info(f"Fetching POI events for last {hours_back} hour(s)")
        
        token = self.get_token()
        if not token:
            logger.error("Failed to obtain token")
            return []
        
        headers = {
            'Authorization': f'Bearer {token}',
            'Accept': 'application/json'
        }
        
        endpoint = "https://api.crearecloud.com.br/frotalog/specialized-services/v3/pontos-notaveis/by-updated"
        
        # Calculate time range - preserve existing timezone logic
        agora_local = datetime.now(CAMPO_GRANDE_TZ)
        agora_utc = agora_local.astimezone(timezone.utc)
        inicio_local = agora_local - timedelta(hours=hours_back)
        inicio_utc = inicio_local.astimezone(timezone.utc)
        
        logger.info(f"Time range: {inicio_utc} to {agora_utc} UTC")
        
        params = {
            "startUpdatedAtTimestamp": inicio_utc.strftime('%Y-%m-%dT%H:%M:%S.%f')[:-3] + 'Z',
            "endUpdatedAtTimestamp": agora_utc.strftime('%Y-%m-%dT%H:%M:%S.%f')[:-3] + 'Z',
            "page": 1,
            "size": 1000,
            "sort": "updatedAt,desc"
        }
        
        all_events = []
        page = 1
        
        try:
            while True:
                params['page'] = page
                param_string = urllib.parse.urlencode(params)
                full_url = f"{endpoint}?{param_string}"
                
                request = urllib.request.Request(full_url, headers=headers)
                
                with urllib.request.urlopen(request, timeout=60) as response:
                    if response.status == 200:
                        data = json.loads(response.read().decode('utf-8'))
                        
                        events = data.get('content', [])
                        total_elements = data.get('totalElements', 0)
                        total_pages = data.get('totalPages', 1)
                        
                        if page == 1:
                            logger.info(f"Total events found: {total_elements}")
                        
                        # Apply POI filtering - preserve existing logic
                        filtered_events = self._filter_poi_events(events)
                        all_events.extend(filtered_events)
                        
                        logger.info(f"Page {page}/{total_pages}: {len(events)} events received, {len(filtered_events)} after POI filter")
                        
                        if page >= total_pages or len(events) < params['size']:
                            break
                        
                        page += 1
                    else:
                        logger.error(f"API request failed with status {response.status}")
                        break
            
            logger.info(f"Total filtered events collected: {len(all_events)}")
            return all_events
            
        except Exception as e:
            logger.error(f"Error fetching events: {e}")
            return all_events
    
    def _filter_poi_events(self, events: List[Dict]) -> List[Dict]:
        """Filter events by POI - preserve existing business logic"""
        filtered = []
        
        for event in events:
            poi_name = event.get('fenceDescription', '')
            
            # Apply existing POI filters
            if poi_name in POIS_FILTRADOS:
                filtered.append(event)
            elif 'Geral JSL RRP' in poi_name and 'Manuten' in poi_name:
                # Handle corrupted characters
                filtered.append(event)
        
        return filtered

class POIDataProcessor:
    """Process and store POI events"""
    
    def __init__(self, bigquery_client: bigquery.Client, firestore_client: firestore.Client):
        self.bigquery = bigquery_client
        self.firestore = firestore_client
        self.poi_groups_cache = None
    
    async def load_poi_groups(self) -> Dict[str, str]:
        """Load POI groups from Firestore or CSV"""
        if self.poi_groups_cache:
            return self.poi_groups_cache
        
        try:
            # Try to get from Firestore cache first
            doc_ref = self.firestore.collection('system_settings').document('poi_groups_cache')
            doc = doc_ref.get()
            
            if doc.exists:
                self.poi_groups_cache = doc.to_dict().get('groups', {})
                logger.info(f"Loaded {len(self.poi_groups_cache)} POI groups from Firestore cache")
            else:
                # Load from Cloud Storage and cache
                self.poi_groups_cache = await self._load_poi_groups_from_storage()
                
            return self.poi_groups_cache
            
        except Exception as e:
            logger.error(f"Error loading POI groups: {e}")
            return {}
    
    async def _load_poi_groups_from_storage(self) -> Dict[str, str]:
        """Load POI groups from Cloud Storage CSV"""
        try:
            storage_client = storage.Client()
            bucket = storage_client.bucket('poi-config-bucket')
            blob = bucket.blob('poi_groups.csv')
            
            csv_content = blob.download_as_text()
            
            groups = {}
            lines = csv_content.strip().split('\n')
            
            # Skip header and process rows
            for line in lines[1:]:
                if line.strip():
                    parts = line.split(';')
                    if len(parts) >= 2:
                        poi = parts[0].strip()
                        grupo = parts[1].strip()
                        if poi and grupo:
                            groups[poi] = grupo
            
            # Cache in Firestore
            doc_ref = self.firestore.collection('system_settings').document('poi_groups_cache')
            doc_ref.set({
                'groups': groups,
                'last_updated': datetime.now(),
                'source': 'cloud_storage'
            })
            
            logger.info(f"Loaded and cached {len(groups)} POI groups from CSV")
            return groups
            
        except Exception as e:
            logger.error(f"Error loading POI groups from storage: {e}")
            return {}
    
    def get_poi_filial(self, poi_name: str) -> str:
        """Get filial based on POI - preserve existing logic"""
        if poi_name in POIS_RRP:
            return 'RRP'
        elif poi_name in POIS_TLS:
            return 'TLS'
        elif 'Geral JSL RRP' in poi_name and 'Manuten' in poi_name:
            return 'RRP'
        else:
            return 'Desconhecida'
    
    def get_poi_group(self, poi_name: str) -> str:
        """Get POI group - preserve existing logic"""
        if not self.poi_groups_cache:
            return "Não Classificado"
        
        # Exact match first
        if poi_name in self.poi_groups_cache:
            return self.poi_groups_cache[poi_name]
        
        # Partial match (case insensitive)
        poi_lower = poi_name.lower()
        for poi, group in self.poi_groups_cache.items():
            if poi.lower() in poi_lower or poi_lower in poi.lower():
                return group
        
        return "Não Mapeado"
    
    def format_timestamp(self, iso_timestamp: Optional[str]) -> Optional[str]:
        """Format ISO timestamp to local time - preserve existing logic"""
        if not iso_timestamp:
            return None
        
        try:
            dt_utc = datetime.fromisoformat(iso_timestamp.replace('Z', '+00:00'))
            dt_local = dt_utc.astimezone(CAMPO_GRANDE_TZ)
            return dt_local.strftime('%Y-%m-%d %H:%M:%S')
        except:
            return iso_timestamp
    
    async def process_and_store_events(self, raw_events: List[Dict]) -> Dict:
        """Process events and store in BigQuery"""
        if not raw_events:
            logger.info("No events to process")
            return {"processed": 0, "stored": 0}
        
        # Load POI groups
        await self.load_poi_groups()
        
        processed_events = []
        processing_timestamp = datetime.now()
        
        for event in raw_events:
            try:
                processed_event = self._process_single_event(event, processing_timestamp)
                processed_events.append(processed_event)
            except Exception as e:
                logger.error(f"Error processing event {event.get('id', 'unknown')}: {e}")
                continue
        
        # Store in BigQuery
        stored_count = await self._store_in_bigquery(processed_events)
        
        # Update processing statistics
        await self._update_processing_stats(len(raw_events), len(processed_events), stored_count)
        
        logger.info(f"Processed {len(processed_events)} events, stored {stored_count}")
        
        return {
            "raw_count": len(raw_events),
            "processed": len(processed_events),
            "stored": stored_count
        }
    
    def _process_single_event(self, event: Dict, processing_timestamp: datetime) -> Dict:
        """Process single event - preserve existing business logic"""
        poi_name = event.get('fenceDescription', '')
        filial = self.get_poi_filial(poi_name)
        grupo = self.get_poi_group(poi_name)
        
        # Map status
        status_code = str(event.get('status', ''))
        status_desc = "Entrou na cerca" if status_code == '1' else "Saiu da cerca"
        
        # Generate unique event ID
        event_id = f"{event.get('vehicleId', '')}-{event.get('fenceId', '')}-{event.get('updatedAt', '')}"
        
        return {
            'processed_event_id': event_id,
            'original_event_ids': [str(event.get('id', ''))],
            'vehicle_plate': event.get('vehiclePlate', ''),
            'vehicle_id': str(event.get('vehicleId', '')),
            'fence_id': str(event.get('fenceId', '')),
            'customer_child_id': str(event.get('customerChildId', '')),
            'poi_name': poi_name,
            'poi_group': grupo,
            'filial': filial,
            'event_date': processing_timestamp.date(),
            'entry_timestamp': self.format_timestamp(event.get('dateInFence')),
            'exit_timestamp': self.format_timestamp(event.get('dateOutFence')),
            'updated_at': self.format_timestamp(event.get('updatedAt')),
            'status': status_code,
            'status_description': status_desc,
            'processed_at': processing_timestamp,
            'api_fetch_timestamp': processing_timestamp,
            'source_system': 'creare_cloud',
            'raw_payload': json.dumps(event)
        }
    
    async def _store_in_bigquery(self, processed_events: List[Dict]) -> int:
        """Store processed events in BigQuery"""
        if not processed_events:
            return 0
        
        try:
            table_id = f"{self.bigquery.project}.poi_monitoring.poi_events_raw"
            
            # Configure job
            job_config = bigquery.LoadJobConfig(
                write_disposition=bigquery.WriteDisposition.WRITE_APPEND,
                schema_update_options=[bigquery.SchemaUpdateOption.ALLOW_FIELD_ADDITION]
            )
            
            # Insert data
            job = self.bigquery.load_table_from_json(
                processed_events,
                table_id,
                job_config=job_config
            )
            
            job.result()  # Wait for completion
            
            logger.info(f"Successfully stored {len(processed_events)} events in BigQuery")
            return len(processed_events)
            
        except Exception as e:
            logger.error(f"Error storing events in BigQuery: {e}")
            return 0
    
    async def _update_processing_stats(self, raw_count: int, processed_count: int, stored_count: int):
        """Update processing statistics"""
        try:
            current_time = datetime.now()
            
            stats = {
                'stats_id': f"{current_time.strftime('%Y%m%d_%H')}_{current_time.minute}",
                'processing_date': current_time.date(),
                'processing_hour': current_time.hour,
                'processing_timestamp': current_time,
                'events_fetched': raw_count,
                'events_processed': processed_count,
                'events_stored': stored_count,
                'api_response_time_ms': 0,  # TODO: Track this
                'processing_duration_ms': 0,  # TODO: Track this
                'data_quality_issues': raw_count - processed_count,
                'rrp_events': len([e for e in processed_events if e.get('filial') == 'RRP']),
                'tls_events': len([e for e in processed_events if e.get('filial') == 'TLS'])
            }
            
            table_id = f"{self.bigquery.project}.poi_monitoring.processing_statistics"
            
            job_config = bigquery.LoadJobConfig(
                write_disposition=bigquery.WriteDisposition.WRITE_APPEND
            )
            
            job = self.bigquery.load_table_from_json([stats], table_id, job_config=job_config)
            job.result()
            
        except Exception as e:
            logger.error(f"Error updating processing stats: {e}")

@functions_framework.cloud_event
def collect_poi_data(cloud_event):
    """Main Cloud Function entry point"""
    logger.info("POI Data Collector started")
    
    try:
        # Initialize clients
        bigquery_client = bigquery.Client()
        firestore_client = firestore.Client()
        secret_client = secretmanager.SecretManagerServiceClient()
        
        # Initialize services
        api_client = CreareCloudClient(secret_client)
        processor = POIDataProcessor(bigquery_client, firestore_client)
        
        # Fetch events
        logger.info("Fetching events from Creare Cloud API")
        raw_events = api_client.fetch_poi_events(hours_back=1)
        
        if not raw_events:
            logger.warning("No events fetched from API")
            return {"status": "success", "message": "No events to process"}
        
        # Process and store events
        logger.info(f"Processing {len(raw_events)} raw events")
        result = asyncio.run(processor.process_and_store_events(raw_events))
        
        logger.info("POI Data Collector completed successfully")
        return {
            "status": "success",
            "message": f"Processed {result['processed']} events, stored {result['stored']}",
            "metrics": result
        }
        
    except Exception as e:
        logger.error(f"POI Data Collector failed: {e}")
        return {
            "status": "error",
            "message": str(e)
        }

# For local testing
if __name__ == "__main__":
    # Mock cloud event for testing
    class MockCloudEvent:
        pass
    
    result = collect_poi_data(MockCloudEvent())
    print(json.dumps(result, indent=2))