#!/usr/bin/env python3
"""
Integração BigQuery para Sistema Sentinela BD
Gerencia tabelas e envio de dados de desvios
"""

import logging
from datetime import datetime
from google.cloud import bigquery
from google.cloud.exceptions import NotFound
import os
from zoneinfo import ZoneInfo

logger = logging.getLogger(__name__)

# Configurações
PROJECT_ID = os.environ.get('GOOGLE_CLOUD_PROJECT', 'sz-wsp-00009')
DATASET_ID = 'sentinela_bd'
CAMPO_GRANDE_TZ = ZoneInfo("America/Campo_Grande")

# Esquemas das tabelas
SCHEMA_VEICULOS_ATIVOS = [
    bigquery.SchemaField("timestamp_verificacao", "TIMESTAMP", mode="REQUIRED"),
    bigquery.SchemaField("filial", "STRING", mode="REQUIRED"),
    bigquery.SchemaField("grupo", "STRING", mode="REQUIRED"), 
    bigquery.SchemaField("poi", "STRING", mode="REQUIRED"),
    bigquery.SchemaField("placa_veiculo", "STRING", mode="REQUIRED"),
    bigquery.SchemaField("data_entrada", "TIMESTAMP", mode="REQUIRED"),
    bigquery.SchemaField("tempo_permanencia_horas", "FLOAT", mode="REQUIRED"),
    bigquery.SchemaField("sla_limite", "INTEGER", mode="REQUIRED"),
    bigquery.SchemaField("qtd_grupo", "INTEGER", mode="REQUIRED"),
    bigquery.SchemaField("status_sla", "STRING", mode="REQUIRED"),
    bigquery.SchemaField("em_desvio", "BOOLEAN", mode="REQUIRED"),
    bigquery.SchemaField("evento_id", "STRING", mode="NULLABLE")
]

SCHEMA_EVENTOS_DESVIO = [
    bigquery.SchemaField("evento_id", "STRING", mode="REQUIRED"),
    bigquery.SchemaField("timestamp_verificacao", "TIMESTAMP", mode="REQUIRED"),
    bigquery.SchemaField("filial", "STRING", mode="REQUIRED"),
    bigquery.SchemaField("grupo", "STRING", mode="REQUIRED"),
    bigquery.SchemaField("placa_veiculo", "STRING", mode="REQUIRED"),
    bigquery.SchemaField("poi", "STRING", mode="REQUIRED"),
    bigquery.SchemaField("data_entrada", "TIMESTAMP", mode="REQUIRED"),
    bigquery.SchemaField("tempo_permanencia_horas", "FLOAT", mode="REQUIRED"),
    bigquery.SchemaField("nivel_alerta", "STRING", mode="REQUIRED"),
    bigquery.SchemaField("qtd_veiculos_grupo", "INTEGER", mode="REQUIRED"),
    bigquery.SchemaField("sla_limite", "INTEGER", mode="REQUIRED"),
    bigquery.SchemaField("nivel_escalonamento", "INTEGER", mode="REQUIRED"),
    bigquery.SchemaField("processado", "BOOLEAN", mode="REQUIRED", default_value_expression="FALSE")
]

SCHEMA_HISTORICO_SLA = [
    bigquery.SchemaField("timestamp_verificacao", "TIMESTAMP", mode="REQUIRED"),
    bigquery.SchemaField("filial", "STRING", mode="REQUIRED"),
    bigquery.SchemaField("grupo", "STRING", mode="REQUIRED"),
    bigquery.SchemaField("qtd_veiculos", "INTEGER", mode="REQUIRED"),
    bigquery.SchemaField("sla_limite", "INTEGER", mode="REQUIRED"),
    bigquery.SchemaField("percentual_ocupacao", "FLOAT", mode="REQUIRED"),
    bigquery.SchemaField("em_desvio", "BOOLEAN", mode="REQUIRED"),
    bigquery.SchemaField("data_particao", "DATE", mode="REQUIRED")
]

def obter_cliente_bigquery():
    """Obtém cliente BigQuery autenticado"""
    try:
        return bigquery.Client(project=PROJECT_ID)
    except Exception as e:
        logger.error(f"Erro ao criar cliente BigQuery: {e}")
        return None

def configurar_tabelas_bigquery():
    """Configura dataset e tabelas BigQuery se não existirem"""
    try:
        client = obter_cliente_bigquery()
        if not client:
            return False

        # Criar dataset se não existir
        dataset_ref = client.dataset(DATASET_ID)
        try:
            client.get_dataset(dataset_ref)
            logger.info(f"Dataset {DATASET_ID} já existe")
        except NotFound:
            dataset = bigquery.Dataset(dataset_ref)
            dataset.location = "US"
            dataset.description = "Dados do Sistema Sentinela BD - Monitoramento de Desvios"
            client.create_dataset(dataset)
            logger.info(f"Dataset {DATASET_ID} criado com sucesso")

        # Definir tabelas para criar
        tabelas = [
            ("veiculos_ativos", SCHEMA_VEICULOS_ATIVOS, "Veículos ativos por verificação"),
            ("eventos_desvio", SCHEMA_EVENTOS_DESVIO, "Eventos de desvio de SLA"),
            ("historico_sla", SCHEMA_HISTORICO_SLA, "Histórico de ocupação por grupo")
        ]

        # Criar tabelas
        for nome_tabela, schema, descricao in tabelas:
            table_ref = dataset_ref.table(nome_tabela)
            try:
                client.get_table(table_ref)
                logger.info(f"Tabela {nome_tabela} já existe")
            except NotFound:
                table = bigquery.Table(table_ref, schema=schema)
                table.description = descricao
                
                # Configurar particionamento para historico_sla
                if nome_tabela == "historico_sla":
                    table.time_partitioning = bigquery.TimePartitioning(
                        type_=bigquery.TimePartitioningType.DAY,
                        field="data_particao"
                    )
                
                client.create_table(table)
                logger.info(f"Tabela {nome_tabela} criada com sucesso")

        return True

    except Exception as e:
        logger.error(f"Erro ao configurar tabelas BigQuery: {e}")
        return False

def enviar_dados_bigquery(resultado_deteccao):
    """Envia dados da detecção para BigQuery"""
    try:
        client = obter_cliente_bigquery()
        if not client:
            return False

        dataset_ref = client.dataset(DATASET_ID)
        timestamp_verificacao = datetime.now(CAMPO_GRANDE_TZ)

        # 1. Inserir veículos ativos
        if resultado_deteccao.get('veiculos_ativos'):
            rows_veiculos = []
            for veiculo in resultado_deteccao['veiculos_ativos']:
                rows_veiculos.append({
                    "timestamp_verificacao": timestamp_verificacao,
                    "filial": veiculo['filial'],
                    "grupo": veiculo['grupo'],
                    "poi": veiculo['poi'],
                    "placa_veiculo": veiculo['placa'],
                    "data_entrada": veiculo['entrada'],
                    "tempo_permanencia_horas": veiculo['tempo_permanencia_horas'],
                    "sla_limite": resultado_deteccao.get('sla_limites', {}).get(f"{veiculo['filial']}_{veiculo['grupo']}", 0),
                    "qtd_grupo": resultado_deteccao.get('qtd_por_grupo', {}).get(f"{veiculo['filial']}_{veiculo['grupo']}", 0),
                    "status_sla": "DESVIO" if veiculo.get('em_desvio', False) else "OK",
                    "em_desvio": veiculo.get('em_desvio', False),
                    "evento_id": veiculo.get('evento_id')
                })

            table_veiculos = dataset_ref.table("veiculos_ativos")
            errors = client.insert_rows_json(table_veiculos, rows_veiculos)
            if errors:
                logger.error(f"Erro ao inserir veículos ativos: {errors}")
            else:
                logger.info(f"Inseridos {len(rows_veiculos)} veículos ativos")

        # 2. Inserir eventos de desvio
        if resultado_deteccao.get('desvios'):
            rows_eventos = []
            for desvio in resultado_deteccao['desvios']:
                nivel_escalonamento = calcular_nivel_escalonamento(desvio)
                
                for veiculo in desvio['veiculos']:
                    evento_id = f"{desvio['filial']}_{desvio['grupo']}_N{nivel_escalonamento}_{timestamp_verificacao.strftime('%d%m%Y_%H%M%S')}"
                    
                    rows_eventos.append({
                        "evento_id": evento_id,
                        "timestamp_verificacao": timestamp_verificacao,
                        "filial": desvio['filial'],
                        "grupo": desvio['grupo'],
                        "placa_veiculo": veiculo['placa'],
                        "poi": veiculo['poi'],
                        "data_entrada": veiculo['entrada'],
                        "tempo_permanencia_horas": veiculo['tempo_permanencia_horas'],
                        "nivel_alerta": f"N{nivel_escalonamento}",
                        "qtd_veiculos_grupo": desvio['qtd_veiculos'],
                        "sla_limite": desvio['limite_sla'],
                        "nivel_escalonamento": nivel_escalonamento,
                        "processado": False
                    })

            if rows_eventos:
                table_eventos = dataset_ref.table("eventos_desvio")
                errors = client.insert_rows_json(table_eventos, rows_eventos)
                if errors:
                    logger.error(f"Erro ao inserir eventos de desvio: {errors}")
                else:
                    logger.info(f"Inseridos {len(rows_eventos)} eventos de desvio")

        # 3. Inserir histórico de SLA
        if resultado_deteccao.get('resumo_grupos'):
            rows_historico = []
            data_particao = timestamp_verificacao.date()
            
            for grupo_info in resultado_deteccao['resumo_grupos']:
                rows_historico.append({
                    "timestamp_verificacao": timestamp_verificacao,
                    "filial": grupo_info['filial'],
                    "grupo": grupo_info['grupo'],
                    "qtd_veiculos": grupo_info['qtd_veiculos'],
                    "sla_limite": grupo_info['sla_limite'],
                    "percentual_ocupacao": grupo_info['percentual_ocupacao'],
                    "em_desvio": grupo_info['em_desvio'],
                    "data_particao": data_particao
                })

            table_historico = dataset_ref.table("historico_sla")
            errors = client.insert_rows_json(table_historico, rows_historico)
            if errors:
                logger.error(f"Erro ao inserir histórico SLA: {errors}")
            else:
                logger.info(f"Inseridos {len(rows_historico)} registros de histórico")

        return True

    except Exception as e:
        logger.error(f"Erro ao enviar dados para BigQuery: {e}")
        return False

def calcular_nivel_escalonamento(desvio):
    """
    Calcula nível de escalonamento baseado na gravidade do desvio
    N1: 1-25% acima do limite
    N2: 26-50% acima do limite  
    N3: 51-100% acima do limite
    N4: Mais de 100% acima do limite
    """
    qtd = desvio['qtd_veiculos']
    limite = desvio['limite_sla']
    
    if limite == 0:
        return 4
    
    percentual_excesso = ((qtd - limite) / limite) * 100
    
    if percentual_excesso <= 25:
        return 1
    elif percentual_excesso <= 50:
        return 2
    elif percentual_excesso <= 100:
        return 3
    else:
        return 4

def consultar_historico_desvios(horas=24):
    """Consulta histórico de desvios das últimas N horas"""
    try:
        client = obter_cliente_bigquery()
        if not client:
            return []

        query = f"""
        SELECT 
            evento_id,
            timestamp_verificacao,
            filial,
            grupo,
            placa_veiculo,
            poi,
            nivel_alerta,
            qtd_veiculos_grupo,
            sla_limite,
            nivel_escalonamento,
            processado
        FROM `{PROJECT_ID}.{DATASET_ID}.eventos_desvio`
        WHERE timestamp_verificacao >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL {horas} HOUR)
        ORDER BY timestamp_verificacao DESC, nivel_escalonamento DESC
        """
        
        return list(client.query(query))

    except Exception as e:
        logger.error(f"Erro ao consultar histórico: {e}")
        return []