#!/usr/bin/env python3
"""
Sistema de Detecção de Desvios - Sentinela BD
Aplicação Cloud Run com integração BigQuery e Cloud Scheduler

Este módulo serve como wrapper HTTP para o sistema de detecção de desvios,
permitindo execução via Cloud Scheduler e Cloud Run.
"""

import os
import sys
import json
import asyncio
import logging
from datetime import datetime, timezone
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse
import uvicorn

# Configurar logging estruturado
import structlog

# Configurar path para imports locais
sys.path.append(os.path.join(os.path.dirname(__file__), 'scripts/pontos_notaveis'))

# Importar sistema de detecção
from sistema_deteccao_desvios_enhanced import SistemaDeteccaoDesvios

# Configurar logging estruturado
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        structlog.processors.JSONRenderer()
    ],
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger()

# Configurar FastAPI
app = FastAPI(
    title="Sistema de Detecção de Desvios - Sentinela BD",
    description="API para monitoramento de veículos em POIs com alertas de SLA",
    version="1.0.0"
)

# Instância global do sistema
sistema_deteccao = None

@app.on_event("startup")
async def startup_event():
    """Inicializa o sistema na startup"""
    global sistema_deteccao
    
    logger.info("Iniciando Sistema de Detecção de Desvios")
    
    try:
        # Configurações do GCP
        projeto_gcp = os.getenv('GCP_PROJECT_ID', 'sz-wsp-00009')
        dataset_id = os.getenv('BIGQUERY_DATASET', 'sentinela_bd')
        
        # Inicializar sistema
        sistema_deteccao = SistemaDeteccaoDesvios(
            projeto_gcp=projeto_gcp,
            dataset_id=dataset_id
        )
        
        logger.info("Sistema inicializado com sucesso", 
                   projeto=projeto_gcp, dataset=dataset_id)
        
    except Exception as e:
        logger.error("Erro na inicialização do sistema", error=str(e))
        raise

@app.get("/health")
async def health_check():
    """Health check endpoint para Cloud Run"""
    return {
        "status": "healthy",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "service": "sentinela-bd-detection",
        "version": "1.0.0"
    }

@app.post("/execute")
async def execute_detection(background_tasks: BackgroundTasks):
    """
    Endpoint principal para execução do sistema de detecção
    Chamado pelo Cloud Scheduler de hora em hora
    """
    if not sistema_deteccao:
        raise HTTPException(status_code=500, detail="Sistema não inicializado")
    
    execution_id = f"exec_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    
    logger.info("Iniciando execução de detecção", execution_id=execution_id)
    
    try:
        # Executar em background para resposta rápida ao scheduler
        background_tasks.add_task(
            executar_deteccao_completa, 
            execution_id
        )
        
        return {
            "status": "started",
            "execution_id": execution_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "message": "Detecção iniciada em background"
        }
        
    except Exception as e:
        logger.error("Erro ao iniciar detecção", 
                    execution_id=execution_id, error=str(e))
        raise HTTPException(status_code=500, detail=str(e))

async def executar_deteccao_completa(execution_id: str):
    """Executa o sistema de detecção completo"""
    try:
        logger.info("Executando detecção completa", execution_id=execution_id)
        
        # Executar detecção
        resultado = await sistema_deteccao.executar_deteccao_completa()
        
        logger.info("Detecção concluída com sucesso",
                   execution_id=execution_id,
                   veiculos_ativos=resultado['total_veiculos'],
                   desvios_detectados=resultado['total_desvios'],
                   eventos_gerados=resultado['total_eventos'])
        
    except Exception as e:
        logger.error("Erro na execução da detecção completa",
                    execution_id=execution_id, error=str(e))

@app.get("/status")
async def get_status():
    """Endpoint para verificar status do sistema"""
    if not sistema_deteccao:
        raise HTTPException(status_code=500, detail="Sistema não inicializado")
    
    try:
        status_info = await sistema_deteccao.obter_status()
        return status_info
    except Exception as e:
        logger.error("Erro ao obter status", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/metrics")
async def get_metrics():
    """Endpoint para métricas de monitoramento"""
    if not sistema_deteccao:
        raise HTTPException(status_code=500, detail="Sistema não inicializado")
    
    try:
        metricas = await sistema_deteccao.obter_metricas()
        return metricas
    except Exception as e:
        logger.error("Erro ao obter métricas", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/test-bigquery")
async def test_bigquery():
    """Endpoint para testar conectividade com BigQuery"""
    if not sistema_deteccao:
        raise HTTPException(status_code=500, detail="Sistema não inicializado")
    
    try:
        resultado = await sistema_deteccao.testar_bigquery()
        return resultado
    except Exception as e:
        logger.error("Erro no teste BigQuery", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    # Configuração para execução local e produção
    port = int(os.getenv("PORT", 8080))
    host = os.getenv("HOST", "0.0.0.0")
    
    logger.info("Iniciando servidor", host=host, port=port)
    
    uvicorn.run(
        "app:app",
        host=host,
        port=port,
        log_level="info",
        access_log=True
    )