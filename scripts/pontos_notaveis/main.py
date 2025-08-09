#!/usr/bin/env python3
"""
Main entry point para Cloud Run - Sistema Sentinela BD
Executa detecção de desvios e envia dados para BigQuery
"""

from flask import Flask, request, jsonify
import logging
import os
from datetime import datetime
from sistema_deteccao_desvios import main as detectar_desvios
from bigquery_integration import enviar_dados_bigquery, configurar_tabelas_bigquery
from zoneinfo import ZoneInfo

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Configurar timezone
CAMPO_GRANDE_TZ = ZoneInfo("America/Campo_Grande")

app = Flask(__name__)

@app.route('/', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'service': 'sentinela-bd',
        'timestamp': datetime.now(CAMPO_GRANDE_TZ).isoformat(),
        'version': '1.0.0'
    }), 200

@app.route('/execute', methods=['POST'])
def execute_monitoring():
    """
    Endpoint principal para execução do monitoramento
    Chamado pelo Cloud Scheduler a cada hora
    """
    try:
        logger.info("🚛 Iniciando execução do Sistema Sentinela BD")
        
        # Verificar se é uma execução programada do Scheduler
        if request.headers.get('X-CloudScheduler'):
            logger.info("📅 Execução iniciada pelo Cloud Scheduler")
        
        # Executar detecção de desvios
        resultado = detectar_desvios()
        
        if resultado:
            logger.info("✅ Detecção de desvios executada com sucesso")
            
            # Enviar dados para BigQuery
            sucesso_bigquery = enviar_dados_bigquery(resultado)
            
            if sucesso_bigquery:
                logger.info("📊 Dados enviados para BigQuery com sucesso")
            else:
                logger.warning("⚠️ Falha ao enviar dados para BigQuery")
            
            return jsonify({
                'status': 'success',
                'message': 'Monitoramento executado com sucesso',
                'timestamp': datetime.now(CAMPO_GRANDE_TZ).isoformat(),
                'veiculos_encontrados': len(resultado.get('veiculos_ativos', [])),
                'desvios_detectados': len(resultado.get('desvios', [])),
                'bigquery_status': 'success' if sucesso_bigquery else 'failed'
            }), 200
        else:
            logger.error("❌ Falha na execução da detecção de desvios")
            return jsonify({
                'status': 'error',
                'message': 'Falha na detecção de desvios',
                'timestamp': datetime.now(CAMPO_GRANDE_TZ).isoformat()
            }), 500
            
    except Exception as e:
        logger.error(f"❌ Erro na execução do monitoramento: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': f'Erro interno: {str(e)}',
            'timestamp': datetime.now(CAMPO_GRANDE_TZ).isoformat()
        }), 500

@app.route('/setup', methods=['POST'])
def setup_bigquery():
    """Endpoint para configurar tabelas BigQuery (execução única)"""
    try:
        logger.info("🔧 Configurando tabelas BigQuery...")
        sucesso = configurar_tabelas_bigquery()
        
        if sucesso:
            logger.info("✅ Tabelas BigQuery configuradas com sucesso")
            return jsonify({
                'status': 'success',
                'message': 'Tabelas BigQuery configuradas',
                'timestamp': datetime.now(CAMPO_GRANDE_TZ).isoformat()
            }), 200
        else:
            return jsonify({
                'status': 'error', 
                'message': 'Falha ao configurar tabelas BigQuery'
            }), 500
            
    except Exception as e:
        logger.error(f"❌ Erro na configuração BigQuery: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': f'Erro na configuração: {str(e)}'
        }), 500

@app.route('/status', methods=['GET'])
def status():
    """Status detalhado do sistema"""
    try:
        return jsonify({
            'service': 'Sistema Sentinela BD',
            'status': 'running',
            'environment': os.environ.get('ENVIRONMENT', 'development'),
            'project_id': os.environ.get('GOOGLE_CLOUD_PROJECT', 'sz-wsp-00009'),
            'timestamp': datetime.now(CAMPO_GRANDE_TZ).isoformat(),
            'timezone': 'America/Campo_Grande',
            'version': '1.0.0'
        }), 200
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    logger.info(f"🚀 Iniciando Sistema Sentinela BD na porta {port}")
    app.run(host='0.0.0.0', port=port, debug=False)