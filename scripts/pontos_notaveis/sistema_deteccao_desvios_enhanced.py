#!/usr/bin/env python3
"""
Sistema de Detecção de Desvios Enhanced - Sentinela BD
Versão aprimorada com integração BigQuery, escalonamento N1-N4 e persistência

Esta versão estende o sistema original com:
- Integração completa com BigQuery
- Escalonamento automático N1-N4 com persistência
- Logs estruturados
- Métricas de monitoramento
- Tratamento robusto de erros
"""

import json
import base64
import urllib.request
import urllib.parse
from datetime import datetime, timezone, timedelta
from collections import defaultdict
from zoneinfo import ZoneInfo
import logging
import asyncio
from typing import Dict, List, Optional, Tuple
import os

# Google Cloud imports
from google.cloud import bigquery
from google.cloud import logging as gcp_logging
from google.cloud import monitoring_v3
from google.cloud import secretmanager
import structlog

# Configurar logging estruturado
logger = structlog.get_logger()

# Configurações
CAMPO_GRANDE_TZ = ZoneInfo("America/Campo_Grande")

class SistemaDeteccaoDesvios:
    """Sistema principal de detecção de desvios com integração GCP"""
    
    def __init__(self, projeto_gcp: str, dataset_id: str = "sentinela_bd"):
        self.projeto_gcp = projeto_gcp
        self.dataset_id = dataset_id
        
        # Configurar clientes GCP
        self.bq_client = bigquery.Client(project=projeto_gcp)
        self.secret_client = secretmanager.SecretManagerServiceClient()
        self.monitoring_client = monitoring_v3.MetricServiceClient()
        
        # Configurar logging do GCP
        gcp_log_client = gcp_logging.Client(project=projeto_gcp)
        gcp_log_client.setup_logging()
        
        # Mapeamento POI → Grupo (do script original)
        self.mapeamento_poi_grupo = {
            # TLS - apenas grupos com SLA definido
            "Oficina Central JSL": "Manutenção",
            "Carregamento Fabrica": "Fábrica", 
            "FILA DESCARGA APT": "Terminal",
            "Descarga TAP": "Terminal",
            "PA Celulose": "Ponto Apoio",
            "CEMAVI": "Manutenção",
            "JDIESEL": "Manutenção",
            "MONTANINI": "Manutenção",
            "PB Lopes": "Manutenção",
            "PB LOPES SCANIA": "Manutenção",
            "MS3 LAVA JATO": "Manutenção",
            "ADEVAR": "Manutenção",
            "REBUCCI": "Manutenção",
            "FEISCAR": "Manutenção",
            "LM RADIADORES": "Manutenção",
            "ALBINO": "Manutenção",
            "DIESELTRONIC": "Manutenção",
            "Manutencao Celulose": "Manutenção",
            
            # RRP - apenas grupos com SLA
            "Descarga Inocencia": "Terminal",
            "Carregamento Fabrica RRP": "Fábrica",
            "Manutencao JSL RRP": "Manutenção",
            "Oficina JSL": "Manutenção", 
            "Manuten¿¿o Geral JSL RRP": "Manutenção",
            "PA AGUA CLARA": "Ponto Apoio"
        }
        
        # SLA por Filial e Grupo
        self.sla_limites = {
            "RRP": {
                "Fábrica": 6,
                "Terminal": 12,
                "Manutenção": 12,
                "Ponto Apoio": 6
            },
            "TLS": {
                "Fábrica": 5,
                "Terminal": 5,
                "Manutenção": 10,
                "Ponto Apoio": 5
            }
        }
        
        # POIs por filial
        self.pois_rrp = {
            "Manutencao JSL RRP", "Carregamento Fabrica RRP", "Buffer Frotas", 
            "Abastecimento Frotas RRP", "Oficina JSL", "Posto Mutum", "Agua Clara", 
            "PA AGUA CLARA", "Descarga Inocencia", "Manuten¿¿o Geral JSL RRP"
        }
        
        self.pois_tls = {
            "Carregamento Fabrica", "AREA EXTERNA SUZANO", "POSTO DE ABASTECIMENTO", 
            "Fila abastecimento posto", "PA Celulose", "Manutencao Celulose", 
            "MONTANINI", "SELVIRIA", "FILA DESCARGA APT", "Descarga TAP", 
            "Oficina Central JSL", "PB Lopes", "PB LOPES SCANIA", "MS3 LAVA JATO", 
            "REBUCCI", "CEMAVI", "FEISCAR", "DIESELTRONIC", "LM RADIADORES", 
            "ALBINO", "JDIESEL", "ADEVAR"
        }
        
        self.pois_filtrados = self.pois_rrp | self.pois_tls
        
        # Configuração de escalonamento N1-N4
        self.niveis_escalonamento = {
            "N1": {"horas_limite": 1, "acao": "registro_sistema"},
            "N2": {"horas_limite": 2, "acao": "notificacao_supervisor"}, 
            "N3": {"horas_limite": 4, "acao": "escalonamento_gerencial"},
            "N4": {"horas_limite": float('inf'), "acao": "escalonamento_executivo"}
        }

    async def obter_credenciais_api(self) -> Dict[str, str]:
        """Obtém credenciais da API do Secret Manager"""
        try:
            secret_name = f"projects/{self.projeto_gcp}/secrets/frotalog-api-credentials/versions/latest"
            response = self.secret_client.access_secret_version(request={"name": secret_name})
            
            credentials = json.loads(response.payload.data.decode("UTF-8"))
            logger.info("Credenciais obtidas do Secret Manager")
            return credentials
        except Exception as e:
            logger.error("Erro ao obter credenciais", error=str(e))
            # Fallback para credenciais hardcoded (desenvolvimento)
            return {"client_id": "56963", "client_secret": "1MSiBaH879w="}

    async def obter_token_oauth(self) -> Optional[str]:
        """Obtém token OAuth2 da API externa"""
        try:
            credentials = await self.obter_credenciais_api()
            oauth_url = "https://openid-provider.crearecloud.com.br/auth/v1/token?lang=pt-BR"
            
            client_credentials = f"{credentials['client_id']}:{credentials['client_secret']}"
            encoded_credentials = base64.b64encode(client_credentials.encode()).decode()
            
            headers = {
                'Authorization': f'Basic {encoded_credentials}',
                'Content-Type': 'application/json'
            }
            
            data = json.dumps({"grant_type": "client_credentials"}).encode('utf-8')
            request = urllib.request.Request(oauth_url, data=data, headers=headers, method='POST')
            
            with urllib.request.urlopen(request, timeout=30) as response:
                token_data = json.loads(response.read().decode('utf-8'))
                logger.info("Token OAuth obtido com sucesso")
                return token_data.get('id_token')
                
        except Exception as e:
            logger.error("Erro ao obter token OAuth", error=str(e))
            return None

    def obter_filial_poi(self, poi_name: str) -> str:
        """Determina a filial baseada no POI"""
        if poi_name in self.pois_rrp:
            return "RRP"
        elif poi_name in self.pois_tls:
            return "TLS"
        return "DESCONHECIDA"

    def obter_grupo_poi(self, poi_name: str) -> str:
        """Obtém grupo do POI usando mapeamento"""
        # Tratamento especial para POI com caracteres quebrados
        if "Geral JSL RRP" in poi_name and "Manuten" in poi_name:
            return "Manutenção"
        
        return self.mapeamento_poi_grupo.get(poi_name, "Não Mapeado")

    async def buscar_veiculos_ativos(self) -> List[Dict]:
        """Busca veículos ativos nos POIs com estratégia adaptativa"""
        logger.info("Iniciando busca de veículos ativos")
        
        token = await self.obter_token_oauth()
        if not token:
            logger.error("Falha ao obter token - abortando busca")
            return []
        
        headers = {
            'Authorization': f'Bearer {token}',
            'Accept': 'application/json'
        }
        
        endpoint = "https://api.crearecloud.com.br/frotalog/specialized-services/v3/pontos-notaveis/by-updated"
        
        # Configurar janelas temporais por grupo
        agora_local = datetime.now(CAMPO_GRANDE_TZ)
        agora_utc = agora_local.astimezone(timezone.utc)
        
        janelas_grupo = {
            "Terminal": 24,
            "Fábrica": 24,
            "Ponto Apoio": 24,
            "Manutenção": 72
        }
        
        # Tentar janelas progressivas
        for janela_horas in [2, 6, 24, 72, 168]:
            logger.info(f"Tentando janela de {janela_horas}h")
            
            inicio_local = agora_local - timedelta(hours=janela_horas)
            inicio_utc = inicio_local.astimezone(timezone.utc)
            
            params = {
                "startUpdatedAtTimestamp": inicio_utc.strftime('%Y-%m-%dT%H:%M:%S.%f')[:-3] + 'Z',
                "endUpdatedAtTimestamp": agora_utc.strftime('%Y-%m-%dT%H:%M:%S.%f')[:-3] + 'Z',
                "page": 1,
                "size": 1000,
                "sort": "updatedAt,desc"
            }
            
            try:
                param_string = urllib.parse.urlencode(params)
                full_url = f"{endpoint}?{param_string}"
                
                request = urllib.request.Request(full_url, headers=headers)
                
                with urllib.request.urlopen(request, timeout=60) as response:
                    if response.status == 200:
                        data = json.loads(response.read().decode('utf-8'))
                        eventos = data.get('content', [])
                        
                        logger.info(f"Obtidos {len(eventos)} eventos da API")
                        
                        # Processar eventos
                        veiculos_ativos = await self.processar_eventos_api(eventos, janelas_grupo, agora_local)
                        
                        # Verificar se obteve dados suficientes
                        if len(veiculos_ativos) >= 10:  # Critério mínimo
                            logger.info(f"Critério atingido com {len(veiculos_ativos)} veículos")
                            return veiculos_ativos
                        
            except Exception as e:
                logger.error(f"Erro na janela {janela_horas}h", error=str(e))
                continue
        
        logger.warning("Nenhuma janela retornou dados suficientes")
        return []

    async def processar_eventos_api(self, eventos: List[Dict], janelas_grupo: Dict, agora_local: datetime) -> List[Dict]:
        """Processa eventos da API aplicando filtros"""
        veiculos_ativos = []
        
        for evento in eventos:
            poi = evento.get('fenceDescription', '')
            status = evento.get('status', 0)
            
            # Filtrar apenas POIs monitorados e veículos ativos (status = 1)
            if poi not in self.pois_filtrados or status != 1:
                continue
            
            placa = evento.get('vehiclePlate', '')
            entrada = evento.get('dateInFence', '')
            
            if not placa or not entrada:
                continue
            
            try:
                # Converter entrada para timezone local
                dt_entrada = datetime.fromisoformat(entrada.replace('Z', '+00:00'))
                entrada_local = dt_entrada.astimezone(CAMPO_GRANDE_TZ)
                
                # Calcular tempo de permanência
                tempo_permanencia = (agora_local - entrada_local).total_seconds() / 3600
                
                filial = self.obter_filial_poi(poi)
                grupo = self.obter_grupo_poi(poi)
                
                # Ignorar grupos sem SLA definido
                if grupo == "Não Mapeado":
                    continue
                
                # Aplicar janela temporal específica do grupo
                janela_grupo = janelas_grupo.get(grupo, 24)
                if tempo_permanencia > janela_grupo:
                    continue
                
                veiculo_info = {
                    'placa': placa,
                    'poi': poi,
                    'filial': filial,
                    'grupo': grupo,
                    'entrada': entrada_local,
                    'tempo_permanencia_horas': tempo_permanencia,
                    'evento_id': evento.get('pontoNotavelId')
                }
                
                veiculos_ativos.append(veiculo_info)
                
            except Exception as e:
                logger.error(f"Erro ao processar evento", evento_id=evento.get('pontoNotavelId'), error=str(e))
                continue
        
        logger.info(f"Processados {len(veiculos_ativos)} veículos válidos")
        return veiculos_ativos

    async def analisar_desvios_sla(self, veiculos_ativos: List[Dict], timestamp_verificacao: datetime) -> List[Dict]:
        """Analisa desvios de SLA por grupo"""
        logger.info("Iniciando análise de desvios SLA")
        
        # Agrupar veículos por filial e grupo
        grupos_veiculo = defaultdict(list)
        for veiculo in veiculos_ativos:
            chave = f"{veiculo['filial']}_{veiculo['grupo']}"
            grupos_veiculo[chave].append(veiculo)
        
        desvios_detectados = []
        
        # Verificar cada grupo
        for chave_grupo, veiculos in grupos_veiculo.items():
            filial, grupo = chave_grupo.split('_', 1)
            qtd_veiculos = len(veiculos)
            
            # Obter limite SLA
            limite_sla = self.sla_limites.get(filial, {}).get(grupo)
            if limite_sla is None:
                continue
            
            # Verificar se há desvio
            if qtd_veiculos > limite_sla:
                logger.warning(f"Desvio detectado: {filial}-{grupo}", 
                             qtd=qtd_veiculos, limite=limite_sla)
                
                desvio_info = {
                    'filial': filial,
                    'grupo': grupo,
                    'qtd_veiculos': qtd_veiculos,
                    'limite_sla': limite_sla,
                    'excesso': qtd_veiculos - limite_sla,
                    'veiculos': veiculos,
                    'timestamp_verificacao': timestamp_verificacao
                }
                desvios_detectados.append(desvio_info)
        
        logger.info(f"Detectados {len(desvios_detectados)} desvios SLA")
        return desvios_detectados

    async def processar_escalonamento_niveis(self, desvios_detectados: List[Dict], execution_id: str) -> List[Dict]:
        """Processa escalonamento N1-N4 com persistência"""
        logger.info("Processando escalonamento de níveis")
        
        eventos_gerados = []
        
        for desvio in desvios_detectados:
            desvio_key = f"{desvio['filial']}_{desvio['grupo']}_{desvio['timestamp_verificacao'].strftime('%Y%m%d')}"
            
            # Verificar escalonamento existente no BigQuery
            nivel_atual = await self.obter_nivel_escalonamento_atual(desvio_key)
            
            if nivel_atual is None:
                # Primeiro desvio - nível N1
                nivel_atual = "N1"
                horas_desvio = 1
                await self.criar_escalacao_inicial(desvio_key, desvio, execution_id)
            else:
                # Desvio contínuo - verificar se deve escalonar
                horas_desvio = await self.obter_horas_desvio(desvio_key)
                nivel_atual = self.calcular_proximo_nivel(horas_desvio)
                await self.atualizar_escalacao(desvio_key, nivel_atual, horas_desvio, execution_id)
            
            # Gerar eventos para cada veículo
            for veiculo in desvio['veiculos']:
                evento = {
                    'evento_id': f"{desvio_key}_{nivel_atual}_{execution_id}",
                    'execution_id': execution_id,
                    'timestamp_verificacao': desvio['timestamp_verificacao'],
                    'filial': desvio['filial'],
                    'grupo': desvio['grupo'],
                    'placa_veiculo': veiculo['placa'],
                    'poi': veiculo['poi'],
                    'qtd_veiculos_grupo': desvio['qtd_veiculos'],
                    'limite_sla': desvio['limite_sla'],
                    'excesso': desvio['excesso'],
                    'data_entrada': veiculo['entrada'],
                    'tempo_permanencia_horas': veiculo['tempo_permanencia_horas'],
                    'nivel_alerta': nivel_atual,
                    'status_evento': 'ATIVO',
                    'acao_realizada': self.niveis_escalonamento[nivel_atual]['acao'],
                    'horas_em_desvio': horas_desvio
                }
                eventos_gerados.append(evento)
        
        logger.info(f"Gerados {len(eventos_gerados)} eventos de escalonamento")
        return eventos_gerados

    async def obter_nivel_escalonamento_atual(self, desvio_key: str) -> Optional[str]:
        """Obtém o nível atual de escalonamento do BigQuery"""
        try:
            query = f"""
                SELECT nivel_atual
                FROM `{self.projeto_gcp}.{self.dataset_id}.escalacoes_niveis`
                WHERE desvio_key = @desvio_key
                AND status = 'ATIVO'
                ORDER BY updated_at DESC
                LIMIT 1
            """
            
            job_config = bigquery.QueryJobConfig(
                query_parameters=[
                    bigquery.ScalarQueryParameter("desvio_key", "STRING", desvio_key)
                ]
            )
            
            query_job = self.bq_client.query(query, job_config=job_config)
            results = query_job.result()
            
            for row in results:
                return row.nivel_atual
                
            return None
            
        except Exception as e:
            logger.error("Erro ao consultar nível atual", desvio_key=desvio_key, error=str(e))
            return None

    async def obter_horas_desvio(self, desvio_key: str) -> int:
        """Obtém quantas horas o desvio está ativo"""
        try:
            query = f"""
                SELECT 
                    timestamp_inicio_desvio,
                    quantidade_verificacoes
                FROM `{self.projeto_gcp}.{self.dataset_id}.escalacoes_niveis`
                WHERE desvio_key = @desvio_key
                AND status = 'ATIVO'
                ORDER BY updated_at DESC
                LIMIT 1
            """
            
            job_config = bigquery.QueryJobConfig(
                query_parameters=[
                    bigquery.ScalarQueryParameter("desvio_key", "STRING", desvio_key)
                ]
            )
            
            query_job = self.bq_client.query(query, job_config=job_config)
            results = query_job.result()
            
            for row in results:
                inicio = row.timestamp_inicio_desvio
                agora = datetime.now(timezone.utc)
                horas_decorridas = (agora - inicio).total_seconds() / 3600
                return int(horas_decorridas) + 1
                
            return 1  # Default para primeiro desvio
            
        except Exception as e:
            logger.error("Erro ao calcular horas de desvio", error=str(e))
            return 1

    def calcular_proximo_nivel(self, horas_desvio: int) -> str:
        """Calcula o próximo nível baseado nas horas em desvio"""
        if horas_desvio >= 4:
            return "N4"
        elif horas_desvio >= 2:
            return "N3"
        elif horas_desvio >= 1:
            return "N2"
        else:
            return "N1"

    async def criar_escalacao_inicial(self, desvio_key: str, desvio: Dict, execution_id: str):
        """Cria registro inicial de escalonamento"""
        try:
            table_id = f"{self.projeto_gcp}.{self.dataset_id}.escalacoes_niveis"
            
            rows_to_insert = [{
                "desvio_key": desvio_key,
                "execution_id": execution_id,
                "filial": desvio['filial'],
                "grupo": desvio['grupo'],
                "timestamp_inicio_desvio": desvio['timestamp_verificacao'].isoformat(),
                "timestamp_ultima_verificacao": desvio['timestamp_verificacao'].isoformat(),
                "nivel_atual": "N1",
                "horas_em_desvio": 1,
                "quantidade_verificacoes": 1,
                "historico_niveis": [{
                    "nivel": "N1",
                    "timestamp_nivel": desvio['timestamp_verificacao'].isoformat(),
                    "acao_realizada": "registro_sistema",
                    "responsavel": "sistema_automatico"
                }],
                "proximo_nivel": "N2",
                "proximo_nivel_em": (desvio['timestamp_verificacao'] + timedelta(hours=1)).isoformat(),
                "status": "ATIVO"
            }]
            
            errors = self.bq_client.insert_rows_json(table_id, rows_to_insert)
            
            if errors:
                logger.error("Erro ao inserir escalonamento inicial", errors=errors)
            else:
                logger.info("Escalonamento inicial criado", desvio_key=desvio_key)
                
        except Exception as e:
            logger.error("Erro ao criar escalonamento inicial", error=str(e))

    async def atualizar_escalacao(self, desvio_key: str, nivel_atual: str, horas_desvio: int, execution_id: str):
        """Atualiza registro de escalonamento existente"""
        try:
            # Query para atualizar o registro
            query = f"""
                UPDATE `{self.projeto_gcp}.{self.dataset_id}.escalacoes_niveis`
                SET 
                    nivel_atual = @nivel_atual,
                    horas_em_desvio = @horas_desvio,
                    quantidade_verificacoes = quantidade_verificacoes + 1,
                    timestamp_ultima_verificacao = CURRENT_TIMESTAMP(),
                    updated_at = CURRENT_TIMESTAMP()
                WHERE desvio_key = @desvio_key
                AND status = 'ATIVO'
            """
            
            job_config = bigquery.QueryJobConfig(
                query_parameters=[
                    bigquery.ScalarQueryParameter("desvio_key", "STRING", desvio_key),
                    bigquery.ScalarQueryParameter("nivel_atual", "STRING", nivel_atual),
                    bigquery.ScalarQueryParameter("horas_desvio", "INTEGER", horas_desvio)
                ]
            )
            
            query_job = self.bq_client.query(query, job_config=job_config)
            query_job.result()
            
            logger.info("Escalonamento atualizado", desvio_key=desvio_key, nivel=nivel_atual)
            
        except Exception as e:
            logger.error("Erro ao atualizar escalonamento", error=str(e))

    async def persistir_dados_bigquery(self, veiculos_ativos: List[Dict], eventos_desvio: List[Dict], 
                                     metricas: Dict, execution_id: str, timestamp_verificacao: datetime):
        """Persiste todos os dados no BigQuery"""
        logger.info("Iniciando persistência no BigQuery")
        
        try:
            # 1. Persistir veículos ativos
            await self.persistir_veiculos_ativos(veiculos_ativos, execution_id, timestamp_verificacao)
            
            # 2. Persistir eventos de desvio
            if eventos_desvio:
                await self.persistir_eventos_desvio(eventos_desvio)
            
            # 3. Persistir métricas consolidadas
            await self.persistir_metricas_sla(metricas, execution_id, timestamp_verificacao)
            
            logger.info("Persistência BigQuery concluída com sucesso")
            
        except Exception as e:
            logger.error("Erro na persistência BigQuery", error=str(e))
            raise

    async def persistir_veiculos_ativos(self, veiculos_ativos: List[Dict], execution_id: str, timestamp_verificacao: datetime):
        """Persiste dados de veículos ativos"""
        if not veiculos_ativos:
            return
        
        try:
            table_id = f"{self.projeto_gcp}.{self.dataset_id}.veiculos_ativos"
            
            # Agrupar para calcular status SLA
            grupos_info = defaultdict(list)
            for veiculo in veiculos_ativos:
                chave = f"{veiculo['filial']}_{veiculo['grupo']}"
                grupos_info[chave].append(veiculo)
            
            rows_to_insert = []
            for veiculo in veiculos_ativos:
                filial = veiculo['filial']
                grupo = veiculo['grupo']
                chave_grupo = f"{filial}_{grupo}"
                
                limite_sla = self.sla_limites.get(filial, {}).get(grupo, 0)
                qtd_grupo = len(grupos_info[chave_grupo])
                em_desvio = qtd_grupo > limite_sla
                status_sla = "DESVIO" if em_desvio else "OK"
                
                row = {
                    "timestamp_verificacao": timestamp_verificacao.isoformat(),
                    "execution_id": execution_id,
                    "placa_veiculo": veiculo['placa'],
                    "evento_id": veiculo.get('evento_id'),
                    "poi": veiculo['poi'],
                    "filial": filial,
                    "grupo": grupo,
                    "data_entrada": veiculo['entrada'].isoformat(),
                    "tempo_permanencia_horas": veiculo['tempo_permanencia_horas'],
                    "limite_sla": limite_sla,
                    "qtd_grupo": qtd_grupo,
                    "status_sla": status_sla,
                    "em_desvio": em_desvio
                }
                rows_to_insert.append(row)
            
            errors = self.bq_client.insert_rows_json(table_id, rows_to_insert)
            
            if errors:
                logger.error("Erro ao inserir veículos ativos", errors=errors)
            else:
                logger.info(f"Inseridos {len(rows_to_insert)} veículos ativos")
                
        except Exception as e:
            logger.error("Erro ao persistir veículos ativos", error=str(e))
            raise

    async def persistir_eventos_desvio(self, eventos_desvio: List[Dict]):
        """Persiste eventos de desvio"""
        try:
            table_id = f"{self.projeto_gcp}.{self.dataset_id}.eventos_desvio"
            
            rows_to_insert = []
            for evento in eventos_desvio:
                row = {
                    "evento_id": evento['evento_id'],
                    "execution_id": evento['execution_id'],
                    "timestamp_verificacao": evento['timestamp_verificacao'].isoformat(),
                    "filial": evento['filial'],
                    "grupo": evento['grupo'],
                    "placa_veiculo": evento['placa_veiculo'],
                    "poi": evento['poi'],
                    "qtd_veiculos_grupo": evento['qtd_veiculos_grupo'],
                    "limite_sla": evento['limite_sla'],
                    "excesso": evento['excesso'],
                    "data_entrada": evento['data_entrada'].isoformat(),
                    "tempo_permanencia_horas": evento['tempo_permanencia_horas'],
                    "nivel_alerta": evento['nivel_alerta'],
                    "status_evento": evento['status_evento'],
                    "acao_realizada": evento['acao_realizada']
                }
                rows_to_insert.append(row)
            
            errors = self.bq_client.insert_rows_json(table_id, rows_to_insert)
            
            if errors:
                logger.error("Erro ao inserir eventos de desvio", errors=errors)
            else:
                logger.info(f"Inseridos {len(rows_to_insert)} eventos de desvio")
                
        except Exception as e:
            logger.error("Erro ao persistir eventos de desvio", error=str(e))
            raise

    async def persistir_metricas_sla(self, metricas: Dict, execution_id: str, timestamp_verificacao: datetime):
        """Persiste métricas consolidadas"""
        try:
            table_id = f"{self.projeto_gcp}.{self.dataset_id}.metricas_sla"
            
            rows_to_insert = []
            for chave_grupo, dados in metricas.items():
                filial, grupo = chave_grupo.split('_', 1)
                
                row = {
                    "timestamp_verificacao": timestamp_verificacao.isoformat(),
                    "data_verificacao": timestamp_verificacao.date().isoformat(),
                    "hora_verificacao": timestamp_verificacao.hour,
                    "execution_id": execution_id,
                    "filial": filial,
                    "grupo": grupo,
                    "limite_sla": dados['limite_sla'],
                    "qtd_veiculos_ativos": dados['qtd_veiculos'],
                    "percentual_ocupacao": dados['percentual_ocupacao'],
                    "em_desvio": dados['em_desvio'],
                    "nivel_desvio": dados.get('nivel_desvio'),
                    "horas_consecutivas_desvio": dados.get('horas_consecutivas', 0),
                    "tempo_processamento_segundos": dados.get('tempo_processamento', 0),
                    "total_pois_monitorados": len(self.pois_filtrados),
                    "total_eventos_api": dados.get('total_eventos_api', 0)
                }
                rows_to_insert.append(row)
            
            errors = self.bq_client.insert_rows_json(table_id, rows_to_insert)
            
            if errors:
                logger.error("Erro ao inserir métricas SLA", errors=errors)
            else:
                logger.info(f"Inseridas {len(rows_to_insert)} métricas SLA")
                
        except Exception as e:
            logger.error("Erro ao persistir métricas SLA", error=str(e))
            raise

    async def enviar_metricas_monitoring(self, metricas: Dict):
        """Envia métricas customizadas para Cloud Monitoring"""
        try:
            project_name = f"projects/{self.projeto_gcp}"
            
            for chave_grupo, dados in metricas.items():
                filial, grupo = chave_grupo.split('_', 1)
                
                # Métrica: Veículos ativos por grupo
                series = monitoring_v3.TimeSeries()
                series.metric.type = "custom.googleapis.com/sentinela/veiculos_ativos"
                series.resource.type = "global"
                series.metric.labels["filial"] = filial
                series.metric.labels["grupo"] = grupo
                
                now = datetime.now(timezone.utc)
                seconds = int(now.timestamp())
                nanos = int((now.timestamp() - seconds) * 10**9)
                
                interval = monitoring_v3.TimeInterval(
                    {"end_time": {"seconds": seconds, "nanos": nanos}}
                )
                
                point = monitoring_v3.Point({
                    "interval": interval,
                    "value": {"int64_value": dados['qtd_veiculos']}
                })
                
                series.points = [point]
                
                self.monitoring_client.create_time_series(
                    name=project_name, 
                    time_series=[series]
                )
            
            logger.info("Métricas enviadas para Cloud Monitoring")
            
        except Exception as e:
            logger.error("Erro ao enviar métricas", error=str(e))

    async def executar_deteccao_completa(self) -> Dict:
        """Executa o ciclo completo de detecção"""
        inicio_processamento = datetime.now(timezone.utc)
        execution_id = f"exec_{inicio_processamento.strftime('%Y%m%d_%H%M%S')}"
        
        logger.info("Iniciando detecção completa", execution_id=execution_id)
        
        try:
            # Obter timestamp para verificação (hora fechada)
            agora = datetime.now(CAMPO_GRANDE_TZ)
            hora_verificacao = agora.replace(minute=0, second=0, microsecond=0)
            
            # 1. Buscar veículos ativos
            veiculos_ativos = await self.buscar_veiculos_ativos()
            
            if not veiculos_ativos:
                logger.warning("Nenhum veículo ativo encontrado")
                return {"total_veiculos": 0, "total_desvios": 0, "total_eventos": 0}
            
            # 2. Analisar desvios SLA
            desvios_detectados = await self.analisar_desvios_sla(veiculos_ativos, hora_verificacao)
            
            # 3. Processar escalonamento N1-N4
            eventos_desvio = []
            if desvios_detectados:
                eventos_desvio = await self.processar_escalonamento_niveis(desvios_detectados, execution_id)
            
            # 4. Calcular métricas
            metricas = await self.calcular_metricas(veiculos_ativos, desvios_detectados)
            
            # 5. Persistir dados no BigQuery
            await self.persistir_dados_bigquery(
                veiculos_ativos, eventos_desvio, metricas, 
                execution_id, hora_verificacao
            )
            
            # 6. Enviar métricas para Cloud Monitoring
            await self.enviar_metricas_monitoring(metricas)
            
            # Calcular tempo de processamento
            fim_processamento = datetime.now(timezone.utc)
            tempo_processamento = (fim_processamento - inicio_processamento).total_seconds()
            
            resultado = {
                "execution_id": execution_id,
                "timestamp_verificacao": hora_verificacao.isoformat(),
                "total_veiculos": len(veiculos_ativos),
                "total_desvios": len(desvios_detectados),
                "total_eventos": len(eventos_desvio),
                "tempo_processamento_segundos": tempo_processamento,
                "status": "sucesso"
            }
            
            logger.info("Detecção completa finalizada", **resultado)
            return resultado
            
        except Exception as e:
            logger.error("Erro na detecção completa", execution_id=execution_id, error=str(e))
            raise

    async def calcular_metricas(self, veiculos_ativos: List[Dict], desvios_detectados: List[Dict]) -> Dict:
        """Calcula métricas consolidadas"""
        metricas = {}
        
        # Agrupar veículos por filial/grupo
        grupos_veiculo = defaultdict(list)
        for veiculo in veiculos_ativos:
            chave = f"{veiculo['filial']}_{veiculo['grupo']}"
            grupos_veiculo[chave].append(veiculo)
        
        # Calcular métricas para todos os grupos com SLA
        for filial, grupos_sla in self.sla_limites.items():
            for grupo, limite in grupos_sla.items():
                chave_grupo = f"{filial}_{grupo}"
                veiculos_grupo = grupos_veiculo.get(chave_grupo, [])
                qtd = len(veiculos_grupo)
                
                percentual = (qtd / limite * 100) if limite > 0 else 0
                em_desvio = qtd > limite
                
                # Buscar nível de desvio se existir
                nivel_desvio = None
                if em_desvio:
                    for desvio in desvios_detectados:
                        if desvio['filial'] == filial and desvio['grupo'] == grupo:
                            nivel_desvio = "N1"  # Simplificado - implementar lógica completa
                            break
                
                metricas[chave_grupo] = {
                    "limite_sla": limite,
                    "qtd_veiculos": qtd,
                    "percentual_ocupacao": percentual,
                    "em_desvio": em_desvio,
                    "nivel_desvio": nivel_desvio
                }
        
        return metricas

    async def obter_status(self) -> Dict:
        """Obtém status atual do sistema"""
        try:
            # Consultar última execução
            query = f"""
                SELECT 
                    execution_id,
                    timestamp_verificacao,
                    COUNT(*) as total_registros
                FROM `{self.projeto_gcp}.{self.dataset_id}.veiculos_ativos`
                WHERE DATE(timestamp_verificacao) = CURRENT_DATE()
                GROUP BY execution_id, timestamp_verificacao
                ORDER BY timestamp_verificacao DESC
                LIMIT 1
            """
            
            query_job = self.bq_client.query(query)
            results = query_job.result()
            
            ultima_execucao = None
            for row in results:
                ultima_execucao = {
                    "execution_id": row.execution_id,
                    "timestamp": row.timestamp_verificacao.isoformat(),
                    "total_registros": row.total_registros
                }
                break
            
            return {
                "status": "operacional",
                "projeto_gcp": self.projeto_gcp,
                "dataset_id": self.dataset_id,
                "ultima_execucao": ultima_execucao,
                "timestamp_consulta": datetime.now(timezone.utc).isoformat()
            }
            
        except Exception as e:
            logger.error("Erro ao obter status", error=str(e))
            return {"status": "erro", "error": str(e)}

    async def obter_metricas(self) -> Dict:
        """Obtém métricas do sistema"""
        try:
            # Métricas das últimas 24 horas
            query = f"""
                SELECT 
                    filial,
                    grupo,
                    AVG(percentual_ocupacao) as media_ocupacao,
                    MAX(percentual_ocupacao) as pico_ocupacao,
                    SUM(CASE WHEN em_desvio THEN 1 ELSE 0 END) as horas_desvio,
                    COUNT(*) as total_verificacoes
                FROM `{self.projeto_gcp}.{self.dataset_id}.metricas_sla`
                WHERE timestamp_verificacao >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 24 HOUR)
                GROUP BY filial, grupo
                ORDER BY filial, grupo
            """
            
            query_job = self.bq_client.query(query)
            results = query_job.result()
            
            metricas = []
            for row in results:
                metricas.append({
                    "filial": row.filial,
                    "grupo": row.grupo,
                    "media_ocupacao": float(row.media_ocupacao),
                    "pico_ocupacao": float(row.pico_ocupacao),
                    "horas_desvio": int(row.horas_desvio),
                    "total_verificacoes": int(row.total_verificacoes),
                    "taxa_desvio": (row.horas_desvio / row.total_verificacoes * 100) if row.total_verificacoes > 0 else 0
                })
            
            return {
                "metricas_24h": metricas,
                "timestamp_consulta": datetime.now(timezone.utc).isoformat()
            }
            
        except Exception as e:
            logger.error("Erro ao obter métricas", error=str(e))
            return {"error": str(e)}

    async def testar_bigquery(self) -> Dict:
        """Testa conectividade com BigQuery"""
        try:
            # Teste simples de conexão
            query = f"""
                SELECT COUNT(*) as total_tabelas
                FROM `{self.projeto_gcp}.{self.dataset_id}.INFORMATION_SCHEMA.TABLES`
            """
            
            query_job = self.bq_client.query(query)
            results = query_job.result()
            
            for row in results:
                return {
                    "status": "ok",
                    "total_tabelas": int(row.total_tabelas),
                    "projeto": self.projeto_gcp,
                    "dataset": self.dataset_id,
                    "timestamp": datetime.now(timezone.utc).isoformat()
                }
            
        except Exception as e:
            logger.error("Erro no teste BigQuery", error=str(e))
            return {"status": "erro", "error": str(e)}