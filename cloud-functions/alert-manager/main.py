#!/usr/bin/env python3
"""
Cloud Function: POI Alert Manager
Handles alert delivery via multiple channels (email, SMS, webhook)
Implements alert formatting and delivery tracking
"""

import json
import base64
import logging
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Optional, NamedTuple
from google.cloud import firestore
from google.cloud import bigquery
from google.cloud import secretmanager
import smtplib
from email.mime.text import MimeText
from email.mime.multipart import MimeMultipart
import functions_framework

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class AlertDeliveryResult(NamedTuple):
    """Alert delivery result"""
    channel: str
    recipient: str
    success: bool
    message_id: Optional[str]
    error: Optional[str]
    delivery_time: datetime

class AlertManager:
    """Manages alert delivery across multiple channels"""
    
    def __init__(
        self,
        firestore_client: firestore.Client,
        bigquery_client: bigquery.Client,
        secret_client: secretmanager.SecretManagerServiceClient
    ):
        self.firestore = firestore_client
        self.bigquery = bigquery_client
        self.secret_client = secret_client
        self.project_id = bigquery_client.project
    
    async def process_deviation_alert(self, alert_data: Dict) -> Dict:
        """Process deviation alert from Pub/Sub message"""
        logger.info(f"Processing alert: {alert_data.get('alert_title', 'Unknown')}")
        
        try:
            # Get alert configuration
            alert_config = await self._get_alert_configuration(
                alert_data.get('filial'),
                alert_data.get('current_level')
            )
            
            # Get recipients for this alert
            recipients = await self._get_alert_recipients(
                alert_data.get('filial'),
                alert_data.get('current_level')
            )
            
            if not recipients:
                logger.warning(f"No recipients found for {alert_data.get('filial')} {alert_data.get('current_level')}")
                return {"status": "warning", "message": "No recipients configured"}
            
            # Format alert content
            formatted_alert = self._format_alert_content(alert_data, alert_config)
            
            # Send alerts through configured channels
            delivery_results = await self._send_multi_channel_alert(
                formatted_alert,
                recipients,
                alert_config
            )
            
            # Update alert state in Firestore
            await self._update_alert_delivery_state(alert_data, delivery_results)
            
            # Log alert history in BigQuery
            await self._log_alert_history(alert_data, delivery_results)
            
            # Calculate success metrics
            total_deliveries = len(delivery_results)
            successful_deliveries = sum(1 for r in delivery_results if r.success)
            
            logger.info(f"Alert delivery completed: {successful_deliveries}/{total_deliveries} successful")
            
            return {
                "status": "success",
                "alert_title": alert_data.get('alert_title'),
                "total_deliveries": total_deliveries,
                "successful_deliveries": successful_deliveries,
                "delivery_results": [
                    {
                        "channel": r.channel,
                        "recipient": r.recipient,
                        "success": r.success,
                        "error": r.error
                    } for r in delivery_results
                ]
            }
            
        except Exception as e:
            logger.error(f"Error processing alert: {e}")
            return {"status": "error", "message": str(e)}
    
    async def _get_alert_configuration(self, filial: str, level: str) -> Dict:
        """Get alert configuration from Firestore"""
        try:
            # Get global alert config
            config_doc = self.firestore.collection('system_settings').document('global_config').get()
            
            if config_doc.exists:
                config_data = config_doc.to_dict()
                alert_config = config_data.get('alert_config', {})
                
                # Get level-specific configuration
                escalation_matrix = config_data.get('alert_recipients', {}).get('escalation_matrix', {})
                level_config = escalation_matrix.get(level, {})
                
                # Merge configurations
                return {
                    'channels': alert_config.get('channels', {}),
                    'delivery_config': alert_config.get('delivery_config', {}),
                    'level_channels': level_config.get('channels', ['email']),
                    'delay_minutes': level_config.get('delay_minutes', 0)
                }
            
            # Default configuration
            return {
                'channels': {
                    'email': {'enabled': True},
                    'sms': {'enabled': False}
                },
                'delivery_config': {
                    'max_retries': 3,
                    'retry_delay_minutes': 5
                },
                'level_channels': ['email'],
                'delay_minutes': 0
            }
            
        except Exception as e:
            logger.error(f"Error getting alert configuration: {e}")
            return {}
    
    async def _get_alert_recipients(self, filial: str, level: str) -> Dict[str, List[str]]:
        """Get alert recipients by filial and level"""
        try:
            recipients_doc = self.firestore.collection('system_settings').document('alert_recipients').get()
            
            if not recipients_doc.exists:
                logger.warning("No alert recipients configuration found")
                return {}
            
            recipients_data = recipients_doc.to_dict()
            
            # Get filial-specific recipients
            filial_recipients = recipients_data.get('by_filial', {}).get(filial, {})
            
            # Get level-specific recipient categories
            level_categories = recipients_data.get('by_level', {}).get(level, ['operations'])
            
            # Build final recipient list
            final_recipients = {'email': [], 'sms': []}
            
            for category in level_categories:
                if category in filial_recipients:
                    category_recipients = filial_recipients[category]
                    
                    if isinstance(category_recipients, dict):
                        final_recipients['email'].extend(category_recipients.get('email', []))
                        final_recipients['sms'].extend(category_recipients.get('sms', []))
            
            # Also add direct filial recipients
            final_recipients['email'].extend(filial_recipients.get('email', []))
            final_recipients['sms'].extend(filial_recipients.get('sms', []))
            
            # Remove duplicates
            final_recipients['email'] = list(set(final_recipients['email']))
            final_recipients['sms'] = list(set(final_recipients['sms']))
            
            return final_recipients
            
        except Exception as e:
            logger.error(f"Error getting alert recipients: {e}")
            return {}
    
    def _format_alert_content(self, alert_data: Dict, alert_config: Dict) -> Dict:
        """Format alert content for delivery"""
        
        # Get alert details
        alert_title = alert_data.get('alert_title', 'POI Alert')
        filial = alert_data.get('filial', 'Unknown')
        poi_name = alert_data.get('poi_name', 'Unknown POI')
        vehicle_plate = alert_data.get('vehicle_plate', 'Unknown')
        level = alert_data.get('current_level', 'N1')
        duration_hours = alert_data.get('duration_hours', 0)
        detection_timestamp = alert_data.get('detection_timestamp')
        
        # Format detection time
        if detection_timestamp:
            try:
                dt = datetime.fromisoformat(detection_timestamp.replace('Z', '+00:00'))
                # Convert to Campo Grande timezone
                campo_grande_tz = timezone(timedelta(hours=-4))
                local_dt = dt.astimezone(campo_grande_tz)
                formatted_time = local_dt.strftime('%d/%m/%Y %H:%M:%S')
            except:
                formatted_time = detection_timestamp
        else:
            formatted_time = datetime.now().strftime('%d/%m/%Y %H:%M:%S')
        
        # Generate content
        subject = f"🚨 {alert_title}"
        
        html_body = f"""
        <html>
        <body style="font-family: Arial, sans-serif; margin: 20px;">
            <div style="background-color: #f44336; color: white; padding: 15px; border-radius: 5px;">
                <h2 style="margin: 0;">🚨 ALERTA POI - NÍVEL {level}</h2>
            </div>
            
            <div style="margin: 20px 0;">
                <h3>Detalhes do Alerta</h3>
                <table style="width: 100%; border-collapse: collapse;">
                    <tr style="background-color: #f5f5f5;">
                        <td style="padding: 8px; border: 1px solid #ddd;"><strong>Título:</strong></td>
                        <td style="padding: 8px; border: 1px solid #ddd;">{alert_title}</td>
                    </tr>
                    <tr>
                        <td style="padding: 8px; border: 1px solid #ddd;"><strong>Filial:</strong></td>
                        <td style="padding: 8px; border: 1px solid #ddd;">{filial}</td>
                    </tr>
                    <tr style="background-color: #f5f5f5;">
                        <td style="padding: 8px; border: 1px solid #ddd;"><strong>POI:</strong></td>
                        <td style="padding: 8px; border: 1px solid #ddd;">{poi_name}</td>
                    </tr>
                    <tr>
                        <td style="padding: 8px; border: 1px solid #ddd;"><strong>Veículo:</strong></td>
                        <td style="padding: 8px; border: 1px solid #ddd;">{vehicle_plate}</td>
                    </tr>
                    <tr style="background-color: #f5f5f5;">
                        <td style="padding: 8px; border: 1px solid #ddd;"><strong>Duração:</strong></td>
                        <td style="padding: 8px; border: 1px solid #ddd;">{duration_hours:.1f} horas</td>
                    </tr>
                    <tr>
                        <td style="padding: 8px; border: 1px solid #ddd;"><strong>Detectado em:</strong></td>
                        <td style="padding: 8px; border: 1px solid #ddd;">{formatted_time}</td>
                    </tr>
                </table>
            </div>
            
            <div style="background-color: #fff3cd; padding: 15px; border-radius: 5px; margin: 20px 0;">
                <h4 style="margin-top: 0;">ℹ️ Informações do Sistema</h4>
                <p><strong>Sistema:</strong> Sentinela BD - POI Monitoring</p>
                <p><strong>Nível de Alerta:</strong> {level}</p>
                <p><strong>Confiabilidade:</strong> {alert_data.get('confidence_score', 1.0):.0%}</p>
            </div>
            
            <div style="font-size: 12px; color: #666; margin-top: 30px; border-top: 1px solid #ddd; padding-top: 15px;">
                <p>Este é um alerta automático do sistema de monitoramento POI.</p>
                <p>Para dúvidas ou suporte, entre em contato com a equipe de TI.</p>
            </div>
        </body>
        </html>
        """
        
        text_body = f"""
🚨 ALERTA POI - NÍVEL {level}

Título: {alert_title}
Filial: {filial}
POI: {poi_name}
Veículo: {vehicle_plate}

Duração: {duration_hours:.1f} horas
Detectado em: {formatted_time}

Sistema: Sentinela BD - POI Monitoring
Nível de Alerta: {level}
Confiabilidade: {alert_data.get('confidence_score', 1.0):.0%}

---
Este é um alerta automático do sistema de monitoramento POI.
        """
        
        sms_body = f"""
🚨 ALERTA POI {level}
Filial: {filial}
POI: {poi_name[:30]}...
Veículo: {vehicle_plate}
Duração: {duration_hours:.1f}h
Detectado: {formatted_time[:16]}
Sistema: Sentinela BD
        """
        
        return {
            'subject': subject,
            'html_body': html_body,
            'text_body': text_body,
            'sms_body': sms_body
        }
    
    async def _send_multi_channel_alert(
        self,
        formatted_alert: Dict,
        recipients: Dict[str, List[str]],
        alert_config: Dict
    ) -> List[AlertDeliveryResult]:
        """Send alerts through multiple channels"""
        
        delivery_results = []
        channels_config = alert_config.get('channels', {})
        level_channels = alert_config.get('level_channels', ['email'])
        
        # Send email alerts
        if 'email' in level_channels and channels_config.get('email', {}).get('enabled', True):
            email_recipients = recipients.get('email', [])
            for recipient in email_recipients:
                try:
                    result = await self._send_email_alert(recipient, formatted_alert)
                    delivery_results.append(result)
                except Exception as e:
                    delivery_results.append(AlertDeliveryResult(
                        channel='email',
                        recipient=recipient,
                        success=False,
                        message_id=None,
                        error=str(e),
                        delivery_time=datetime.now()
                    ))
        
        # Send SMS alerts
        if 'sms' in level_channels and channels_config.get('sms', {}).get('enabled', False):
            sms_recipients = recipients.get('sms', [])
            for recipient in sms_recipients:
                try:
                    result = await self._send_sms_alert(recipient, formatted_alert)
                    delivery_results.append(result)
                except Exception as e:
                    delivery_results.append(AlertDeliveryResult(
                        channel='sms',
                        recipient=recipient,
                        success=False,
                        message_id=None,
                        error=str(e),
                        delivery_time=datetime.now()
                    ))
        
        return delivery_results
    
    async def _send_email_alert(self, recipient: str, formatted_alert: Dict) -> AlertDeliveryResult:
        """Send email alert using SMTP"""
        try:
            # Get email credentials from Secret Manager
            smtp_config = await self._get_smtp_configuration()
            
            # Create message
            msg = MimeMultipart('alternative')
            msg['Subject'] = formatted_alert['subject']
            msg['From'] = smtp_config['from_address']
            msg['To'] = recipient
            
            # Add text and HTML parts
            text_part = MimeText(formatted_alert['text_body'], 'plain', 'utf-8')
            html_part = MimeText(formatted_alert['html_body'], 'html', 'utf-8')
            
            msg.attach(text_part)
            msg.attach(html_part)
            
            # Send email
            with smtplib.SMTP(smtp_config['smtp_server'], smtp_config['smtp_port']) as server:
                server.starttls()
                server.login(smtp_config['username'], smtp_config['password'])
                
                text = msg.as_string()
                server.sendmail(smtp_config['from_address'], recipient, text)
            
            logger.info(f"Email sent successfully to {recipient}")
            
            return AlertDeliveryResult(
                channel='email',
                recipient=recipient,
                success=True,
                message_id=msg['Message-ID'],
                error=None,
                delivery_time=datetime.now()
            )
            
        except Exception as e:
            logger.error(f"Failed to send email to {recipient}: {e}")
            return AlertDeliveryResult(
                channel='email',
                recipient=recipient,
                success=False,
                message_id=None,
                error=str(e),
                delivery_time=datetime.now()
            )
    
    async def _send_sms_alert(self, recipient: str, formatted_alert: Dict) -> AlertDeliveryResult:
        """Send SMS alert (placeholder implementation)"""
        
        # TODO: Implement SMS sending using Twilio or similar service
        # For now, just log the SMS that would be sent
        
        logger.info(f"SMS would be sent to {recipient}: {formatted_alert['sms_body'][:100]}...")
        
        return AlertDeliveryResult(
            channel='sms',
            recipient=recipient,
            success=True,  # Simulated success
            message_id=f"sms_{datetime.now().timestamp()}",
            error=None,
            delivery_time=datetime.now()
        )
    
    async def _get_smtp_configuration(self) -> Dict:
        """Get SMTP configuration from Secret Manager"""
        try:
            # Get SMTP settings from Secret Manager
            smtp_config_name = f"projects/{self.project_id}/secrets/smtp-config/versions/latest"
            response = self.secret_client.access_secret_version(request={"name": smtp_config_name})
            smtp_config = json.loads(response.payload.data.decode("UTF-8"))
            
            return smtp_config
            
        except Exception as e:
            logger.error(f"Error getting SMTP configuration: {e}")
            # Return default configuration for testing
            return {
                'smtp_server': 'smtp.gmail.com',
                'smtp_port': 587,
                'username': 'alerts@company.com',
                'password': 'app_password',
                'from_address': 'alerts@company.com'
            }
    
    async def _update_alert_delivery_state(self, alert_data: Dict, delivery_results: List[AlertDeliveryResult]):
        """Update alert delivery state in Firestore"""
        try:
            # Generate session key
            filial = alert_data.get('filial')
            poi_normalized = alert_data.get('poi_normalized')
            vehicle_plate = alert_data.get('vehicle_plate')
            session_key = f"{filial}_{poi_normalized}_{vehicle_plate}"
            
            # Update alert state
            doc_ref = self.firestore.collection('alert_states').document(session_key)
            
            successful_deliveries = [r for r in delivery_results if r.success]
            
            update_data = {
                'last_alert_sent': datetime.now(),
                'last_delivery_results': [
                    {
                        'channel': r.channel,
                        'recipient': r.recipient,
                        'success': r.success,
                        'delivery_time': r.delivery_time,
                        'error': r.error
                    } for r in delivery_results
                ],
                'successful_deliveries': len(successful_deliveries),
                'total_delivery_attempts': len(delivery_results),
                'updated_at': datetime.now()
            }
            
            # Update escalation history with delivery status
            doc = doc_ref.get()
            if doc.exists:
                data = doc.to_dict()
                escalation_history = data.get('escalation_history', [])
                
                if escalation_history:
                    # Update the latest escalation entry
                    escalation_history[-1]['alert_sent'] = len(successful_deliveries) > 0
                    escalation_history[-1]['delivery_channels'] = [r.channel for r in successful_deliveries]
                    update_data['escalation_history'] = escalation_history
            
            doc_ref.update(update_data)
            
        except Exception as e:
            logger.error(f"Error updating alert delivery state: {e}")
    
    async def _log_alert_history(self, alert_data: Dict, delivery_results: List[AlertDeliveryResult]):
        """Log alert history in BigQuery"""
        try:
            alert_id = f"{alert_data.get('alert_title', '')}_{datetime.now().timestamp()}"
            
            # Create alert history records for each delivery attempt
            history_records = []
            
            for result in delivery_results:
                record = {
                    'alert_id': alert_id,
                    'deviation_id': alert_data.get('deviation_id'),
                    'alert_timestamp': datetime.now(),
                    'alert_title': alert_data.get('alert_title'),
                    'alert_level': alert_data.get('current_level'),
                    'filial': alert_data.get('filial'),
                    'poi_name': alert_data.get('poi_name'),
                    'vehicle_plates': [alert_data.get('vehicle_plate')],
                    'delivery_channels': [result.channel],
                    'recipients': [result.recipient],
                    'delivery_status': 'delivered' if result.success else 'failed',
                    'delivery_attempts': 1,
                    'alert_date': datetime.now().date(),
                    'sent_at': result.delivery_time,
                    'delivered_at': result.delivery_time if result.success else None,
                    'external_message_id': result.message_id,
                    'delivery_errors': [result.error] if result.error else [],
                    'retry_count': 0
                }
                
                history_records.append(record)
            
            if history_records:
                table_id = f"{self.project_id}.poi_monitoring.alert_history"
                
                job_config = bigquery.LoadJobConfig(
                    write_disposition=bigquery.WriteDisposition.WRITE_APPEND
                )
                
                job = self.bigquery.load_table_from_json(history_records, table_id, job_config=job_config)
                job.result()
                
                logger.info(f"Logged {len(history_records)} alert history records")
            
        except Exception as e:
            logger.error(f"Error logging alert history: {e}")

@functions_framework.cloud_event
def manage_poi_alerts(cloud_event):
    """Main Cloud Function entry point triggered by Pub/Sub"""
    logger.info("POI Alert Manager started")
    
    try:
        # Decode Pub/Sub message
        if hasattr(cloud_event.data, 'message'):
            message_data = base64.b64decode(cloud_event.data['message']['data']).decode('utf-8')
            alert_data = json.loads(message_data)
        else:
            # For testing
            alert_data = {
                'alert_title': 'RRP_CarregamentoFabrica_N2_08082025_160000',
                'filial': 'RRP',
                'poi_name': 'Carregamento Fabrica RRP',
                'poi_normalized': 'CarregamentoFabrica',
                'vehicle_plate': 'ABC1234',
                'current_level': 'N2',
                'duration_hours': 4.5,
                'detection_timestamp': datetime.now().isoformat(),
                'confidence_score': 0.95
            }
        
        # Initialize clients
        firestore_client = firestore.Client()
        bigquery_client = bigquery.Client()
        secret_client = secretmanager.SecretManagerServiceClient()
        
        # Initialize alert manager
        alert_manager = AlertManager(firestore_client, bigquery_client, secret_client)
        
        # Process alert
        logger.info(f"Processing alert: {alert_data.get('alert_title')}")
        result = asyncio.run(alert_manager.process_deviation_alert(alert_data))
        
        logger.info("POI Alert Manager completed successfully")
        return result
        
    except Exception as e:
        logger.error(f"POI Alert Manager failed: {e}")
        return {"status": "error", "message": str(e)}

# For local testing
if __name__ == "__main__":
    import asyncio
    
    class MockCloudEvent:
        def __init__(self):
            self.data = {}
    
    result = manage_poi_alerts(MockCloudEvent())
    print(json.dumps(result, indent=2, default=str))