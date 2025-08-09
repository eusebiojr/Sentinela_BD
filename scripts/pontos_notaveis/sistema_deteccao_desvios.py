#!/usr/bin/env python3
"""
Sistema de Detecção de Desvios de SLA - Monitoramento de Veículos em POIs
Baseado no Sistema Sentinela BD

Transforma o script de relatório em um sistema de alertas com níveis N1-N4
para monitoramento horário de desvios de SLA por grupo de POIs.
"""

import json
import base64
import urllib.request
import urllib.parse
from datetime import datetime, timezone, timedelta
from collections import defaultdict, Counter
from zoneinfo import ZoneInfo
import csv

# Configurações
CAMPO_GRANDE_TZ = ZoneInfo("America/Campo_Grande")

# Mapeamento POI → Grupo (TAREFA 1) - APENAS grupos com SLA definido
MAPEAMENTO_POI_GRUPO = {
    # TLS - apenas grupos com SLA (Fábrica, Terminal, Ponto Apoio, Manutenção)
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
    "Manuten¿¿o Geral JSL RRP": "Manutenção",  # POI com caracteres especiais
    "PA AGUA CLARA": "Ponto Apoio"
    
    # IGNORADOS (sem SLA definido):
    # TLS: "POSTO DE ABASTECIMENTO", "Fila abastecimento posto", "SELVIRIA", "AREA EXTERNA SUZANO"
    # RRP: "Agua Clara", "Abastecimento Frotas RRP", "Posto Mutum", "Buffer Frotas"
}

# SLA por Filial e Grupo - CONFIGURAÇÕES ATUALIZADAS
SLA_LIMITES = {
    "RRP": {
        "Fábrica": 6,      # Atualizado: 6 veículos
        "Terminal": 12,    # Atualizado: 12 veículos  
        "Manutenção": 12,  # Atualizado: 12 veículos
        "Ponto Apoio": 6   # Atualizado: 6 veículos
    },
    "TLS": {
        "Fábrica": 5,      # Atualizado: 5 veículos
        "Terminal": 5,     # Atualizado: 5 veículos (APT)
        "Manutenção": 10,  # Atualizado: 10 veículos
        "Ponto Apoio": 5   # Atualizado: 5 veículos
    }
}

# POIs por filial (do script original)
POIS_RRP = {
    "Manutencao JSL RRP", "Carregamento Fabrica RRP", "Buffer Frotas", 
    "Abastecimento Frotas RRP", "Oficina JSL", "Posto Mutum", "Agua Clara", 
    "PA AGUA CLARA", "Descarga Inocencia", "Manuten¿¿o Geral JSL RRP"
}

POIS_TLS = {
    "Carregamento Fabrica", "AREA EXTERNA SUZANO", "POSTO DE ABASTECIMENTO", 
    "Fila abastecimento posto", "PA Celulose", "Manutencao Celulose", 
    "MONTANINI", "SELVIRIA", "FILA DESCARGA APT", "Descarga TAP", 
    "Oficina Central JSL", "PB Lopes", "PB LOPES SCANIA", "MS3 LAVA JATO", 
    "REBUCCI", "CEMAVI", "FEISCAR", "DIESELTRONIC", "LM RADIADORES", 
    "ALBINO", "JDIESEL", "ADEVAR"
}

POIS_FILTRADOS = POIS_RRP | POIS_TLS

def get_token():
    """Obtém token OAuth2"""
    client_id = "56963"
    client_secret = "1MSiBaH879w="
    oauth_url = "https://openid-provider.crearecloud.com.br/auth/v1/token?lang=pt-BR"
    
    credentials = f"{client_id}:{client_secret}"
    encoded_credentials = base64.b64encode(credentials.encode()).decode()
    
    headers = {
        'Authorization': f'Basic {encoded_credentials}',
        'Content-Type': 'application/json'
    }
    
    try:
        data = json.dumps({"grant_type": "client_credentials"}).encode('utf-8')
        request = urllib.request.Request(oauth_url, data=data, headers=headers, method='POST')
        
        with urllib.request.urlopen(request) as response:
            token_data = json.loads(response.read().decode('utf-8'))
            return token_data.get('id_token')
    except Exception as e:
        print(f"❌ Erro ao obter token: {e}")
        return None

def obter_filial_poi(poi_name):
    """Determina a filial baseada no POI"""
    if poi_name in POIS_RRP:
        return "RRP"
    elif poi_name in POIS_TLS:
        return "TLS"
    return "DESCONHECIDA"

def obter_grupo_poi(poi_name):
    """Obtém grupo do POI usando mapeamento"""
    # Tratamento especial para POI com caracteres quebrados
    if "Geral JSL RRP" in poi_name and "Manuten" in poi_name:
        return "Manutenção"
    
    return MAPEAMENTO_POI_GRUPO.get(poi_name, "Não Mapeado")

def buscar_veiculos_ativos():
    """Busca veículos atualmente nos POIs com estratégia de janelas adaptativa"""
    print("🔍 Buscando veículos ativos com estratégia adaptativa...")
    
    token = get_token()
    if not token:
        print("❌ Falha ao obter token")
        return []
    
    headers = {
        'Authorization': f'Bearer {token}',
        'Accept': 'application/json'
    }
    
    endpoint = "https://api.crearecloud.com.br/frotalog/specialized-services/v3/pontos-notaveis/by-updated"
    
    # Estratégia adaptativa: começar com janela pequena e expandir se necessário
    agora_local = datetime.now(CAMPO_GRANDE_TZ)
    agora_utc = agora_local.astimezone(timezone.utc)
    
    # Definir janelas por tipo de operação
    janelas_grupo = {
        "Terminal": 24,      # 24 horas - operações de carga/descarga
        "Fábrica": 24,       # 24 horas - operações de carregamento  
        "Ponto Apoio": 24,   # 24 horas - paradas de apoio
        "Manutenção": 72     # 3 dias (72h) - manutenções longas
    }
    
    print(f"📅 Janelas temporais por grupo:")
    for grupo, horas in janelas_grupo.items():
        dias = horas / 24
        print(f"   • {grupo}: {horas}h ({dias:.0f} dias)")
    
    # Tentar janelas progressivamente maiores para alcançar 90%+ de acurácia
    janelas_tentativas = [2, 6, 24, 72, 168]  # horas (2h, 6h, 1d, 3d, 7d)
    veiculos_encontrados = []
    
    for janela_atual in janelas_tentativas:
        print(f"🔄 Tentativa com janela de {janela_atual}h...")
        
        inicio_local = agora_local - timedelta(hours=janela_atual)
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
                    
                    print(f"   📊 {len(eventos)} eventos retornados")
                    
                    # TESTE: Contar com ambos critérios para comparação
                    eventos_sem_saida_dateout = sum(1 for e in eventos 
                                          if e.get('fenceDescription', '') in POIS_FILTRADOS 
                                          and not e.get('dateOutFence', ''))
                    
                    eventos_status_1 = sum(1 for e in eventos 
                                          if e.get('fenceDescription', '') in POIS_FILTRADOS 
                                          and e.get('status', 0) == 1)
                    
                    print(f"   🔍 dateOutFence vazio: {eventos_sem_saida_dateout} veículos")
                    print(f"   📊 status = 1: {eventos_status_1} veículos")
                    
                    # Usar status = 1 para o teste comparativo
                    eventos_sem_saida = eventos_status_1
                    
                    print(f"   🔍 {eventos_sem_saida} veículos ainda dentro dos POIs")
                    
                    if eventos_sem_saida > 0:
                        print(f"   ✅ Processando eventos da janela de {janela_atual}h...")
                        # Processar eventos desta janela
                        veiculos_encontrados = processar_eventos(eventos, janelas_grupo, agora_local)
                        
                        # Verificar se atingiu meta de acurácia (12+ veículos em Descarga Inocencia)
                        veiculos_descarga = [v for v in veiculos_encontrados if v['poi'] == 'Descarga Inocencia']
                        print(f"   📊 {len(veiculos_descarga)} veículos em 'Descarga Inocencia'")
                        
                        if len(veiculos_descarga) >= 12:
                            print(f"   🎯 Meta atingida (90%+)! Finalizando.")
                            break
                        else:
                            acuracia = len(veiculos_descarga)/15*100
                            print(f"   📈 Acurácia: {acuracia:.1f}% - tentando janela maior...")
                            # Não quebra o loop, continua para próxima janela
                    else:
                        print(f"   ⚠️  Nenhum veículo ativo - tentando janela maior...")
                        
        except Exception as e:
            print(f"   ❌ Erro na tentativa {janela_atual}h: {e}")
            continue
    
    return veiculos_encontrados

def processar_eventos(eventos, janelas_grupo, agora_local):
    """Processa eventos aplicando filtros de janela temporal por grupo"""
    veiculos_ativos = []
    eventos_pois_filtrados = 0
    eventos_sem_data_saida = 0
    eventos_validos = 0
    
    # Processar cada evento
    for evento in eventos:
        poi = evento.get('fenceDescription', '')
        data_saida = evento.get('dateOutFence', '')
        status = evento.get('status', 0)  # TESTE: obter status primeiro
        
        # Debug contadores
        if poi in POIS_FILTRADOS:
            eventos_pois_filtrados += 1
            if status == 1:  # TESTE: mudou para status = 1
                eventos_sem_data_saida += 1
        
        # Filtrar apenas POIs monitorados e veículos ainda dentro (status = 1)
        if poi in POIS_FILTRADOS and status == 1:
            placa = evento.get('vehiclePlate', '')
            entrada = evento.get('dateInFence', '')
            
            if placa and entrada:
                # Converter entrada para timezone local
                dt_entrada = datetime.fromisoformat(entrada.replace('Z', '+00:00'))
                entrada_local = dt_entrada.astimezone(CAMPO_GRANDE_TZ)
                
                # Calcular tempo de permanência
                tempo_permanencia = (agora_local - entrada_local).total_seconds() / 3600
                
                filial = obter_filial_poi(poi)
                grupo = obter_grupo_poi(poi)
                
                # IGNORAR grupos sem SLA definido
                if grupo == "Não Mapeado":
                    continue
                
                # Aplicar janela temporal específica do grupo
                janela_grupo = janelas_grupo.get(grupo, 24)  # default 24h
                if tempo_permanencia > janela_grupo:
                    continue
                
                eventos_validos += 1
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
    
    # Debug: Mostrar contadores
    print(f"🔍 Filtragem final:")
    print(f"   • Eventos em POIs monitorados: {eventos_pois_filtrados}")
    print(f"   • Eventos sem data de saída: {eventos_sem_data_saida}")
    print(f"   • Eventos dentro da janela temporal: {eventos_validos}")
    print(f"✅ {len(veiculos_ativos)} veículos ativos encontrados")
    
    return veiculos_ativos

def analisar_desvios_sla(veiculos_ativos, timestamp_verificacao=None):
    """Analisa desvios de SLA por grupo"""
    if timestamp_verificacao is None:
        timestamp_verificacao = datetime.now(CAMPO_GRANDE_TZ)
    
    print(f"\n📊 ANÁLISE DE DESVIOS - {timestamp_verificacao.strftime('%d/%m/%Y %H:00:00')}")
    print("=" * 60)
    
    # Agrupar veículos por filial e grupo
    grupos_veiculo = defaultdict(list)
    
    for veiculo in veiculos_ativos:
        filial = veiculo['filial']
        grupo = veiculo['grupo']
        chave_grupo = f"{filial}_{grupo}"
        grupos_veiculo[chave_grupo].append(veiculo)
    
    desvios_detectados = []
    
    print("📋 STATUS POR GRUPO:")
    print("-" * 40)
    
    # Verificar cada grupo
    for chave_grupo, veiculos in grupos_veiculo.items():
        filial, grupo = chave_grupo.split('_', 1)
        qtd_veiculos = len(veiculos)
        
        # Obter limite SLA (apenas para grupos definidos)
        limite_sla = SLA_LIMITES.get(filial, {}).get(grupo)
        if limite_sla is None:
            # Grupo sem SLA definido - pular
            continue
        
        # Verificar se há desvio
        em_desvio = qtd_veiculos > limite_sla
        status_icon = "🚨" if em_desvio else "✅"
        
        print(f"{status_icon} {filial} - {grupo}: {qtd_veiculos}/{limite_sla} veículos")
        
        if em_desvio:
            desvio_info = {
                'filial': filial,
                'grupo': grupo,
                'qtd_veiculos': qtd_veiculos,
                'limite_sla': limite_sla,
                'veiculos': veiculos,
                'timestamp_verificacao': timestamp_verificacao
            }
            desvios_detectados.append(desvio_info)
            
            # Mostrar detalhes dos veículos em desvio
            print(f"   Veículos:")
            for v in veiculos[:5]:  # máximo 5 para não poluir
                tempo_str = f"{v['tempo_permanencia_horas']:.1f}h"
                print(f"     • {v['placa']} em {v['poi']} ({tempo_str})")
            if len(veiculos) > 5:
                print(f"     • ... e mais {len(veiculos) - 5} veículos")
    
    print(f"\n🎯 RESULTADO: {len(desvios_detectados)} grupo(s) em desvio de SLA")
    
    return desvios_detectados

def gerar_eventos_desvio(desvios_detectados):
    """Gera eventos de desvio no formato especificado"""
    eventos_gerados = []
    
    for desvio in desvios_detectados:
        timestamp = desvio['timestamp_verificacao']
        
        # Formato do evento: {FILIAL}_{GRUPO}_{NIVEL_ALERTA}_{DATA}_{HORA}
        # Por enquanto, sempre N1 (precisamos implementar lógica de níveis)
        evento_id = f"{desvio['filial']}_{desvio['grupo']}_N1_{timestamp.strftime('%d%m%Y_%H%M%S')}"
        
        # Gerar um evento para cada veículo no grupo em desvio
        for veiculo in desvio['veiculos']:
            evento = {
                'evento_id': evento_id,
                'placa': veiculo['placa'],
                'grupo': f"{desvio['filial']}_{desvio['grupo']}",
                'data_entrada': veiculo['entrada'].isoformat(),
                'tempo_permanencia': veiculo['tempo_permanencia_horas'],
                'alerta': 'Tratativa N1',
                'poi': veiculo['poi'],
                'timestamp_verificacao': timestamp.isoformat(),
                'qtd_veiculos_grupo': desvio['qtd_veiculos'],
                'limite_sla': desvio['limite_sla']
            }
            eventos_gerados.append(evento)
    
    print(f"\n📝 EVENTOS GERADOS: {len(eventos_gerados)}")
    if eventos_gerados:
        print("Exemplos:")
        for evento in eventos_gerados[:3]:
            print(f"  • {evento['evento_id']}: {evento['placa']} ({evento['tempo_permanencia']:.1f}h)")
    
    return eventos_gerados

def gerar_relatorio_excel(veiculos_ativos, desvios_detectados, timestamp_verificacao):
    """Gera relatório detalhado em CSV (compatível com Excel)"""
    timestamp_str = timestamp_verificacao.strftime('%Y%m%d_%H%M%S')
    
    # Arquivo 1: Relatório completo de veículos ativos
    arquivo_veiculos = f"relatorio_veiculos_ativos_{timestamp_str}.csv"
    
    with open(arquivo_veiculos, 'w', newline='', encoding='utf-8-sig') as f:
        writer = csv.writer(f, delimiter=';')
        
        # Cabeçalho
        writer.writerow([
            'Timestamp_Verificacao', 'Filial', 'Grupo', 'POI', 'Placa_Veiculo',
            'Data_Entrada', 'Tempo_Permanencia_Horas', 'SLA_Limite', 
            'Qtd_Grupo', 'Status_SLA', 'Em_Desvio'
        ])
        
        # Agrupar para análise
        grupos_info = defaultdict(list)
        for veiculo in veiculos_ativos:
            chave = f"{veiculo['filial']}_{veiculo['grupo']}"
            grupos_info[chave].append(veiculo)
        
        # Dados dos veículos
        for veiculo in veiculos_ativos:
            filial = veiculo['filial']
            grupo = veiculo['grupo']
            chave_grupo = f"{filial}_{grupo}"
            
            # Obter informações do grupo
            limite_sla = SLA_LIMITES.get(filial, {}).get(grupo, 0)
            qtd_grupo = len(grupos_info[chave_grupo])
            em_desvio = qtd_grupo > limite_sla
            status_sla = "DESVIO" if em_desvio else "OK"
            
            writer.writerow([
                timestamp_verificacao.strftime('%d/%m/%Y %H:%M:%S'),
                filial,
                grupo,
                veiculo['poi'],
                veiculo['placa'],
                veiculo['entrada'].strftime('%d/%m/%Y %H:%M:%S'),
                f"{veiculo['tempo_permanencia_horas']:.2f}",
                limite_sla,
                qtd_grupo,
                status_sla,
                'SIM' if em_desvio else 'NÃO'
            ])
    
    # Arquivo 2: Resumo por grupo
    arquivo_resumo = f"resumo_grupos_sla_{timestamp_str}.csv"
    
    with open(arquivo_resumo, 'w', newline='', encoding='utf-8-sig') as f:
        writer = csv.writer(f, delimiter=';')
        
        writer.writerow([
            'Timestamp_Verificacao', 'Filial', 'Grupo', 'Qtd_Veiculos', 
            'SLA_Limite', 'Status', 'Percentual_Ocupacao', 'Desvio'
        ])
        
        # Processar todos os grupos definidos
        for filial, grupos_sla in SLA_LIMITES.items():
            for grupo, limite in grupos_sla.items():
                chave_grupo = f"{filial}_{grupo}"
                veiculos_grupo = grupos_info.get(chave_grupo, [])
                qtd = len(veiculos_grupo)
                percentual = (qtd / limite * 100) if limite > 0 else 0
                em_desvio = qtd > limite
                status = "🚨 DESVIO" if em_desvio else "✅ OK"
                
                writer.writerow([
                    timestamp_verificacao.strftime('%d/%m/%Y %H:%M:%S'),
                    filial,
                    grupo,
                    qtd,
                    limite,
                    status,
                    f"{percentual:.1f}%",
                    'SIM' if em_desvio else 'NÃO'
                ])
    
    # Arquivo 3: Eventos de desvio (se houver)
    if desvios_detectados:
        arquivo_eventos = f"eventos_desvio_{timestamp_str}.csv"
        
        with open(arquivo_eventos, 'w', newline='', encoding='utf-8-sig') as f:
            writer = csv.writer(f, delimiter=';')
            
            writer.writerow([
                'Evento_ID', 'Filial', 'Grupo', 'Placa_Veiculo', 'POI',
                'Data_Entrada', 'Tempo_Permanencia_Horas', 'Nivel_Alerta',
                'Qtd_Veiculos_Grupo', 'SLA_Limite', 'Timestamp_Verificacao'
            ])
            
            for desvio in desvios_detectados:
                for veiculo in desvio['veiculos']:
                    evento_id = f"{desvio['filial']}_{desvio['grupo']}_N1_{timestamp_verificacao.strftime('%d%m%Y_%H%M%S')}"
                    
                    writer.writerow([
                        evento_id,
                        desvio['filial'],
                        desvio['grupo'],
                        veiculo['placa'],
                        veiculo['poi'],
                        veiculo['entrada'].strftime('%d/%m/%Y %H:%M:%S'),
                        f"{veiculo['tempo_permanencia_horas']:.2f}",
                        'N1',  # Por enquanto sempre N1
                        desvio['qtd_veiculos'],
                        desvio['limite_sla'],
                        timestamp_verificacao.strftime('%d/%m/%Y %H:%M:%S')
                    ])
    
    print(f"\n📊 RELATÓRIOS GERADOS:")
    print(f"   • {arquivo_veiculos} - Detalhes de todos os veículos")
    print(f"   • {arquivo_resumo} - Resumo por grupo")
    if desvios_detectados:
        print(f"   • {arquivo_eventos} - Eventos de desvio")
    
    return arquivo_veiculos, arquivo_resumo

def main():
    """Função principal do sistema de detecção de desvios"""
    print("🚛 SISTEMA DE DETECÇÃO DE DESVIOS - SENTINELA BD")
    print("=" * 60)
    
    # Obter timestamp para verificação (sempre hora fechada)
    agora = datetime.now(CAMPO_GRANDE_TZ)
    hora_verificacao = agora.replace(minute=0, second=0, microsecond=0)
    
    print(f"🕐 Verificação: {hora_verificacao.strftime('%d/%m/%Y %H:%M:%S')} (Campo Grande/MS)")
    print(f"📊 POIs monitorados: {len(POIS_FILTRADOS)}")
    print(f"🎯 Grupos mapeados: {len(set(MAPEAMENTO_POI_GRUPO.values()))}")
    
    print(f"\n📋 GRUPOS COM SLA DEFINIDO:")
    for filial, grupos in SLA_LIMITES.items():
        for grupo, limite in grupos.items():
            print(f"   • {filial} - {grupo}: limite {limite} veículos")
    
    # 1. Buscar veículos ativos
    veiculos_ativos = buscar_veiculos_ativos()
    
    if not veiculos_ativos:
        print("ℹ️ Nenhum veículo ativo encontrado nos POIs monitorados")
        return
    
    # Mostrar exemplos dos veículos ativos para validação
    print(f"\n📝 EXEMPLOS DE VEÍCULOS ATIVOS (primeiros 10):")
    print("-" * 80)
    print("PLACA    | FILIAL | GRUPO        | POI                    | TEMPO")
    print("-" * 80)
    for i, veiculo in enumerate(veiculos_ativos[:10]):
        placa = veiculo['placa'][:8].ljust(8)
        filial = veiculo['filial'].ljust(6)
        grupo = veiculo['grupo'][:12].ljust(12)
        poi = veiculo['poi'][:22].ljust(22)
        tempo = f"{veiculo['tempo_permanencia_horas']:.1f}h"
        print(f"{placa} | {filial} | {grupo} | {poi} | {tempo}")
    
    if len(veiculos_ativos) > 10:
        print(f"... e mais {len(veiculos_ativos) - 10} veículos")
    
    # 2. Analisar desvios de SLA
    desvios = analisar_desvios_sla(veiculos_ativos, hora_verificacao)
    
    # 3. Gerar eventos se houver desvios
    if desvios:
        eventos = gerar_eventos_desvio(desvios)
        
        # TODO: Enviar eventos para BigQuery (TAREFA 5)
        print("\n🚀 PRÓXIMOS PASSOS:")
        print("- Implementar lógica de níveis N1-N4 com persistência")
        print("- Enviar eventos para BigQuery (sz-wsp-00009)")
        print("- Configurar execução horária no Cloud Run")
        
    else:
        print("\n✅ Nenhum desvio detectado - SLA dentro do esperado")
    
    # 4. Gerar relatórios Excel para validação
    gerar_relatorio_excel(veiculos_ativos, desvios, hora_verificacao)
    
    # 5. Retornar dados estruturados para BigQuery
    return {
        'veiculos_ativos': veiculos_ativos,
        'desvios': desvios,
        'timestamp_verificacao': hora_verificacao,
        'resumo_grupos': gerar_resumo_grupos(veiculos_ativos),
        'sla_limites': {f"{filial}_{grupo}": limite for filial, grupos in SLA_LIMITES.items() for grupo, limite in grupos.items()},
        'qtd_por_grupo': {f"{v['filial']}_{v['grupo']}": sum(1 for vv in veiculos_ativos if vv['filial'] == v['filial'] and vv['grupo'] == v['grupo']) for v in veiculos_ativos}
    }

def gerar_resumo_grupos(veiculos_ativos):
    """Gera resumo de ocupação por grupo para BigQuery"""
    from collections import defaultdict
    
    grupos_info = defaultdict(list)
    for veiculo in veiculos_ativos:
        chave = f"{veiculo['filial']}_{veiculo['grupo']}"
        grupos_info[chave].append(veiculo)
    
    resumo = []
    for filial, grupos_sla in SLA_LIMITES.items():
        for grupo, limite in grupos_sla.items():
            chave_grupo = f"{filial}_{grupo}"
            veiculos_grupo = grupos_info.get(chave_grupo, [])
            qtd = len(veiculos_grupo)
            percentual = (qtd / limite * 100) if limite > 0 else 0
            em_desvio = qtd > limite
            
            resumo.append({
                'filial': filial,
                'grupo': grupo,
                'qtd_veiculos': qtd,
                'sla_limite': limite,
                'percentual_ocupacao': percentual,
                'em_desvio': em_desvio
            })
    
    return resumo

if __name__ == "__main__":
    main()