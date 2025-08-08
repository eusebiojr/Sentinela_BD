#!/usr/bin/env python3
"""
Script para buscar pontos notáveis das últimas 12 horas
APENAS para os IDs específicos: 16619, 44459, 40452, 16622, 39450
Com timezone corrigido (Campo Grande UTC-4)
"""
import json
import base64
import urllib.request
import urllib.parse
import csv
from datetime import datetime, timedelta, timezone
from collections import Counter
import os

# Timezone de Campo Grande/MS (UTC-4)
CAMPO_GRANDE_TZ = timezone(timedelta(hours=-4))

# IDs ESPECÍFICOS para filtrar
IDS_PERMITIDOS = {'16619', '44459', '40452', '16622', '39450'}

# Cache para armazenar o mapeamento de grupos
GRUPOS_CACHE = None

def carregar_grupos():
    """Carrega o mapeamento de POI para Grupos do arquivo Grupos.csv"""
    global GRUPOS_CACHE
    
    if GRUPOS_CACHE is not None:
        return GRUPOS_CACHE
    
    grupos = {}
    arquivo_grupos = "Grupos.csv"
    
    try:
        if os.path.exists(arquivo_grupos):
            with open(arquivo_grupos, 'r', encoding='utf-8-sig') as f:
                reader = csv.DictReader(f, delimiter=';')
                for row in reader:
                    poi = row.get('POI', '').strip()
                    grupo = row.get('GRUPO', '').strip()
                    if poi and grupo:
                        grupos[poi] = grupo
            
            print(f"✅ Carregados {len(grupos)} mapeamentos de grupos do arquivo {arquivo_grupos}")
        else:
            print(f"⚠️ Arquivo {arquivo_grupos} não encontrado. Grupos não serão classificados.")
            
    except Exception as e:
        print(f"❌ Erro ao carregar grupos: {e}")
    
    GRUPOS_CACHE = grupos
    return grupos

def obter_grupo_poi(descricao_poi):
    """Obtém o grupo de um POI baseado na descrição"""
    grupos = carregar_grupos()
    
    if not grupos or not descricao_poi:
        return "Não Classificado"
    
    # Verificação especial para POI "Terminal" (sem outros qualificadores)
    if descricao_poi == "Terminal":
        return "Não Mapeado"
    
    # Busca exata primeiro
    if descricao_poi in grupos:
        return grupos[descricao_poi]
    
    # Se não encontrou, busca parcial (case insensitive)
    descricao_lower = descricao_poi.lower()
    for poi, grupo in grupos.items():
        if poi.lower() in descricao_lower or descricao_lower in poi.lower():
            return grupo
    
    return "Não Mapeado"

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
    
    data = json.dumps({"grant_type": "client_credentials"}).encode('utf-8')
    request = urllib.request.Request(oauth_url, data=data, headers=headers, method='POST')
    
    with urllib.request.urlopen(request) as response:
        token_data = json.loads(response.read().decode('utf-8'))
        return token_data.get('id_token')

def buscar_eventos_12hrs(ids_filtro):
    """Busca eventos das últimas 12 horas para os IDs especificados"""
    print(f"🔍 Buscando eventos APENAS para IDs: {ids_filtro}")
    print("⏰ Período: últimas 12 horas (com timezone corrigido)")
    
    token = get_token()
    if not token:
        print("❌ Falha ao obter token")
        return []
    
    headers = {
        'Authorization': f'Bearer {token}',
        'Accept': 'application/json'
    }
    
    endpoint = "https://api.crearecloud.com.br/frotalog/specialized-services/v3/pontos-notaveis/by-updated"
    
    # Horários corretos com timezone
    agora_local = datetime.now(CAMPO_GRANDE_TZ)
    agora_utc = agora_local.astimezone(timezone.utc)
    inicio_local = agora_local - timedelta(hours=5)
    inicio_utc = inicio_local.astimezone(timezone.utc)
    
    print(f"\n📅 Período de busca:")
    print(f"   • Início UTC: {inicio_utc.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"   • Fim UTC: {agora_utc.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"   • Início Local (Campo Grande): {inicio_local.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"   • Fim Local (Campo Grande): {agora_local.strftime('%Y-%m-%d %H:%M:%S')}")
    
    params = {
        "startUpdatedAtTimestamp": inicio_utc.strftime('%Y-%m-%dT%H:%M:%S.%f')[:-3] + 'Z',
        "endUpdatedAtTimestamp": agora_utc.strftime('%Y-%m-%dT%H:%M:%S.%f')[:-3] + 'Z',
        "customerChildIds": ids_filtro,
        "page": 1,
        "size": 1000,
        "sort": "updatedAt,desc"
    }
    
    todos_eventos = []
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
                    
                    eventos = data.get('content', [])
                    total_elements = data.get('totalElements', len(eventos))
                    total_pages = data.get('totalPages', 1)
                    
                    if page == 1:
                        print(f"\n📊 Total de eventos encontrados: {total_elements}")
                    
                    # FILTRAR APENAS OS IDS ESPECIFICADOS
                    eventos_filtrados = []
                    for evento in eventos:
                        customer_id = str(evento.get('customerChildId', ''))
                        if customer_id in IDS_PERMITIDOS:
                            eventos_filtrados.append(evento)
                    
                    todos_eventos.extend(eventos_filtrados)
                    
                    print(f"   • Página {page}/{total_pages}: {len(eventos)} eventos recebidos, {len(eventos_filtrados)} após filtro")
                    
                    if page >= total_pages:
                        break
                    
                    page += 1
                    
                else:
                    print(f"❌ Status {response.status}")
                    break
        
        print(f"\n✅ Total de eventos após filtro de IDs: {len(todos_eventos)}")
        return todos_eventos
                    
    except Exception as e:
        print(f"❌ Erro na requisição: {e}")
        return todos_eventos

def calcular_duracao(data_entrada, data_saida):
    """Calcula duração entre entrada e saída"""
    if not data_entrada or not data_saida:
        return ""
    
    try:
        entrada = datetime.fromisoformat(data_entrada.replace('Z', '+00:00'))
        saida = datetime.fromisoformat(data_saida.replace('Z', '+00:00'))
        
        duracao = saida - entrada
        total_segundos = int(duracao.total_seconds())
        
        if total_segundos < 0:
            return "Duração negativa"
        
        dias = total_segundos // 86400
        horas = (total_segundos % 86400) // 3600
        minutos = (total_segundos % 3600) // 60
        
        if dias > 0:
            return f"{dias}d {horas}h {minutos}m"
        elif horas > 0:
            return f"{horas}h {minutos}m"
        else:
            return f"{minutos}m"
            
    except Exception as e:
        return f"Erro: {str(e)[:20]}"

def formatar_data_local(data_iso):
    """Formata data ISO para formato brasileiro em horário local"""
    if not data_iso:
        return ""
    try:
        dt_utc = datetime.fromisoformat(data_iso.replace('Z', '+00:00'))
        dt_local = dt_utc.astimezone(CAMPO_GRANDE_TZ)
        return dt_local.strftime('%d/%m/%Y %H:%M:%S')
    except:
        return data_iso

def consolidar_eventos_consecutivos(eventos_processados):
    """
    Consolida eventos usando duas estratégias:
    
    1. CONSOLIDAÇÃO POR GRUPOS RELACIONADOS (POIs sobrepostos):
       - Fábrica + Carregamento (consolidados juntos)
       - Terminal + Descarga (consolidados juntos)
       - Pega primeira entrada de QUALQUER grupo relacionado
       - Pega última saída do grupo ESPECÍFICO
    
    2. CONSOLIDAÇÃO POR SEQUÊNCIA (POIs distantes):
       - Outros grupos: 'Parada Operacional', 'Manutenção', etc.
       - Agrupa apenas sequências consecutivas do MESMO POI
       - Não une POIs diferentes mesmo sendo do mesmo grupo
    """
    if not eventos_processados:
        return []
    
    print("🔄 Iniciando consolidação com grupos relacionados...")
    
    # Definir grupos relacionados que devem ser consolidados juntos
    GRUPOS_RELACIONADOS = [
        {'Fábrica', 'Carregamento'},  # POIs de fábrica e carregamento são sobrepostos
        {'Terminal', 'Descarga'}       # POIs de terminal e descarga são sobrepostos
    ]
    
    # Agrupar eventos por veículo
    eventos_por_veiculo = {}
    for evento in eventos_processados:
        placa = evento['Placa_Veiculo']
        if placa not in eventos_por_veiculo:
            eventos_por_veiculo[placa] = []
        eventos_por_veiculo[placa].append(evento)
    
    eventos_consolidados = []
    total_original = len(eventos_processados)
    
    for placa, eventos_veiculo in eventos_por_veiculo.items():
        # Ordenar eventos por data de entrada
        def parse_data_entrada(evento):
            data_str = evento['Data_Entrada']
            if not data_str:
                return datetime.min.replace(tzinfo=CAMPO_GRANDE_TZ)
            try:
                return datetime.strptime(data_str, '%d/%m/%Y %H:%M:%S').replace(tzinfo=CAMPO_GRANDE_TZ)
            except:
                return datetime.min.replace(tzinfo=CAMPO_GRANDE_TZ)
        
        eventos_veiculo.sort(key=parse_data_entrada)
        
        # Separar eventos por tipo de consolidação
        eventos_grupos_relacionados = []
        eventos_restantes = []
        
        # Identificar quais eventos pertencem a grupos relacionados
        for evento in eventos_veiculo:
            grupo_atual = evento['Grupo_POI']
            pertence_grupo_relacionado = False
            
            for conjunto_relacionado in GRUPOS_RELACIONADOS:
                if grupo_atual in conjunto_relacionado:
                    pertence_grupo_relacionado = True
                    break
            
            if pertence_grupo_relacionado:
                eventos_grupos_relacionados.append(evento)
            else:
                eventos_restantes.append(evento)
        
        # ESTRATÉGIA 1: Consolidar grupos relacionados
        if eventos_grupos_relacionados:
            # Processar cada conjunto de grupos relacionados
            for conjunto_relacionado in GRUPOS_RELACIONADOS:
                # Coletar TODOS os eventos dos grupos relacionados
                todos_eventos_relacionados = [
                    e for e in eventos_grupos_relacionados 
                    if e['Grupo_POI'] in conjunto_relacionado
                ]
                
                if todos_eventos_relacionados:
                    # Consolidar por grupo específico dentro do conjunto relacionado
                    grupos_especificos = {}
                    for evento in todos_eventos_relacionados:
                        grupo = evento['Grupo_POI']
                        if grupo not in grupos_especificos:
                            grupos_especificos[grupo] = []
                        grupos_especificos[grupo].append(evento)
                    
                    # Para cada grupo específico, consolidar considerando TODOS os eventos relacionados
                    for grupo_nome, eventos_grupo in grupos_especificos.items():
                        if len(eventos_grupo) > 1 or len(todos_eventos_relacionados) > len(eventos_grupo):
                            # Consolidar usando todos os eventos relacionados para determinar entrada
                            evento_consolidado = consolidar_grupos_relacionados(
                                eventos_grupo, 
                                todos_eventos_relacionados,
                                grupo_nome
                            )
                            if evento_consolidado:
                                eventos_consolidados.append(evento_consolidado)
                        else:
                            eventos_consolidados.append(eventos_grupo[0])
        
        # ESTRATÉGIA 2: Consolidar sequências consecutivas do MESMO POI
        i = 0
        while i < len(eventos_restantes):
            evento_atual = eventos_restantes[i]
            poi_atual = evento_atual['Descricao_POI']
            
            # Encontrar eventos consecutivos do MESMO POI
            sequencia_poi = [evento_atual]
            j = i + 1
            
            while j < len(eventos_restantes):
                evento_seguinte = eventos_restantes[j]
                poi_seguinte = evento_seguinte['Descricao_POI']
                
                # Se é o mesmo POI, adiciona à sequência
                if poi_seguinte == poi_atual:
                    sequencia_poi.append(evento_seguinte)
                    j += 1
                else:
                    # POI diferente, quebra a sequência
                    break
            
            # Consolidar sequência se tiver múltiplos eventos
            if len(sequencia_poi) > 1:
                evento_consolidado = consolidar_sequencia_poi(sequencia_poi)
                if evento_consolidado:
                    eventos_consolidados.append(evento_consolidado)
            else:
                eventos_consolidados.append(evento_atual)
            
            # Avançar para próximo grupo
            i = j if j > i else i + 1
    
    print(f"✅ Consolidação com grupos relacionados concluída:")
    print(f"   • Eventos originais: {total_original}")
    print(f"   • Eventos consolidados: {len(eventos_consolidados)}")
    print(f"   • Eventos eliminados: {total_original - len(eventos_consolidados)}")
    
    return eventos_consolidados

def consolidar_grupos_relacionados(eventos_grupo, todos_eventos_relacionados, grupo_nome):
    """
    Consolida eventos de grupos relacionados (Fábrica+Carregamento ou Terminal+Descarga)
    
    Args:
        eventos_grupo: Eventos do grupo específico a consolidar
        todos_eventos_relacionados: TODOS os eventos de grupos relacionados (para determinar primeira entrada)
        grupo_nome: Nome do grupo específico
    
    Returns:
        Evento consolidado com:
        - Primeira entrada de QUALQUER grupo relacionado
        - Última saída do grupo ESPECÍFICO
    """
    if not eventos_grupo:
        return None
    
    # Função para parsing de datas
    def parse_data_entrada(evento):
        data_str = evento['Data_Entrada']
        if not data_str:
            return datetime.min.replace(tzinfo=CAMPO_GRANDE_TZ)
        try:
            return datetime.strptime(data_str, '%d/%m/%Y %H:%M:%S').replace(tzinfo=CAMPO_GRANDE_TZ)
        except:
            return datetime.min.replace(tzinfo=CAMPO_GRANDE_TZ)
    
    def parse_data_saida(evento):
        data_str = evento['Data_Saida']
        if not data_str:
            return datetime.min.replace(tzinfo=CAMPO_GRANDE_TZ)
        try:
            return datetime.strptime(data_str, '%d/%m/%Y %H:%M:%S').replace(tzinfo=CAMPO_GRANDE_TZ)
        except:
            return datetime.min.replace(tzinfo=CAMPO_GRANDE_TZ)
    
    # Encontrar a PRIMEIRA entrada de TODOS os eventos relacionados
    primeiro_evento_relacionado = min(todos_eventos_relacionados, key=parse_data_entrada)
    
    # Encontrar a ÚLTIMA saída do grupo ESPECÍFICO
    ultimo_evento_grupo = max(eventos_grupo, key=parse_data_saida)
    
    # Criar evento consolidado baseado no primeiro evento do grupo específico
    # mas usando a entrada do primeiro evento relacionado
    evento_consolidado = eventos_grupo[0].copy()
    
    # Usar a primeira entrada de qualquer grupo relacionado
    evento_consolidado['Data_Entrada'] = primeiro_evento_relacionado['Data_Entrada']
    
    # Usar a última saída do grupo específico
    evento_consolidado['Data_Saida'] = ultimo_evento_grupo['Data_Saida']
    evento_consolidado['Data_Atualizacao'] = ultimo_evento_grupo['Data_Atualizacao']
    
    # Recalcular duração
    entrada = primeiro_evento_relacionado['Data_Entrada']
    saida = ultimo_evento_grupo['Data_Saida']
    evento_consolidado['Duracao'] = calcular_duracao_formatada(entrada, saida)
    
    # Manter status original sem marcação
    evento_consolidado['Status'] = eventos_grupo[0]['Status'].replace(' (Consolidado)', '')
    
    # Usar nome do grupo sem marcação
    evento_consolidado['Descricao_POI'] = grupo_nome
    
    return evento_consolidado

def consolidar_grupo_total(eventos_grupo, grupo_nome):
    """
    Consolida TODOS os eventos de um grupo em um único evento
    
    Args:
        eventos_grupo: Lista de eventos do mesmo grupo/POI
        grupo_nome: Nome do grupo para identificação
    
    Returns:
        Evento consolidado com primeira entrada absoluta e última saída absoluta
    """
    if not eventos_grupo:
        return None
    
    # Função para parsing de datas
    def parse_data_entrada(evento):
        data_str = evento['Data_Entrada']
        if not data_str:
            return datetime.min.replace(tzinfo=CAMPO_GRANDE_TZ)
        try:
            return datetime.strptime(data_str, '%d/%m/%Y %H:%M:%S').replace(tzinfo=CAMPO_GRANDE_TZ)
        except:
            return datetime.min.replace(tzinfo=CAMPO_GRANDE_TZ)
    
    def parse_data_saida(evento):
        data_str = evento['Data_Saida']
        if not data_str:
            return datetime.min.replace(tzinfo=CAMPO_GRANDE_TZ)
        try:
            return datetime.strptime(data_str, '%d/%m/%Y %H:%M:%S').replace(tzinfo=CAMPO_GRANDE_TZ)
        except:
            return datetime.min.replace(tzinfo=CAMPO_GRANDE_TZ)
    
    # Encontrar evento com a PRIMEIRA entrada (mais antiga)
    primeiro_evento = min(eventos_grupo, key=parse_data_entrada)
    
    # Encontrar evento com a ÚLTIMA saída (mais recente)
    ultimo_evento_saida = max(eventos_grupo, key=parse_data_saida)
    
    # Criar evento consolidado baseado no primeiro evento
    evento_consolidado = primeiro_evento.copy()
    
    # Atualizar com a última saída
    evento_consolidado['Data_Saida'] = ultimo_evento_saida['Data_Saida']
    evento_consolidado['Data_Atualizacao'] = ultimo_evento_saida['Data_Atualizacao']
    
    # Recalcular duração total
    entrada = primeiro_evento['Data_Entrada']
    saida = ultimo_evento_saida['Data_Saida']
    evento_consolidado['Duracao'] = calcular_duracao_formatada(entrada, saida)
    
    # Marcar como consolidado para identificação
    evento_consolidado['Status'] = primeiro_evento['Status'].replace(' (Consolidado)', '')
    
    # Para grupos consolidados, usar nome do grupo
    if grupo_nome in ['Fábrica', 'Terminal', 'Carregamento', 'Descarga']:
        evento_consolidado['Descricao_POI'] = grupo_nome
    
    return evento_consolidado

def consolidar_sequencia_poi(sequencia_poi):
    """
    Consolida sequência consecutiva de eventos do MESMO POI
    
    Args:
        sequencia_poi: Lista de eventos consecutivos do mesmo POI
    
    Returns:
        Evento consolidado com primeira entrada e última saída da sequência
    """
    if not sequencia_poi:
        return None
    
    if len(sequencia_poi) == 1:
        return sequencia_poi[0]
    
    # Função para parsing de datas
    def parse_data_saida(evento):
        data_str = evento['Data_Saida']
        if not data_str:
            return datetime.min.replace(tzinfo=CAMPO_GRANDE_TZ)
        try:
            return datetime.strptime(data_str, '%d/%m/%Y %H:%M:%S').replace(tzinfo=CAMPO_GRANDE_TZ)
        except:
            return datetime.min.replace(tzinfo=CAMPO_GRANDE_TZ)
    
    # Pegar primeiro evento (já ordenado por entrada)
    primeiro_evento = sequencia_poi[0]
    
    # Encontrar evento com a última saída
    ultimo_evento_saida = max(sequencia_poi, key=parse_data_saida)
    
    # Criar evento consolidado
    evento_consolidado = primeiro_evento.copy()
    
    # Atualizar com a última saída
    evento_consolidado['Data_Saida'] = ultimo_evento_saida['Data_Saida']
    evento_consolidado['Data_Atualizacao'] = ultimo_evento_saida['Data_Atualizacao']
    
    # Recalcular duração
    entrada = primeiro_evento['Data_Entrada']
    saida = ultimo_evento_saida['Data_Saida']
    evento_consolidado['Duracao'] = calcular_duracao_formatada(entrada, saida)
    
    # Marcar como consolidado
    evento_consolidado['Status'] = primeiro_evento['Status'].replace(' (Consolidado)', '')
    
    return evento_consolidado

def calcular_duracao_formatada(data_entrada_str, data_saida_str):
    """Calcula duração entre strings de data formatadas e retorna em formato decimal"""
    if not data_entrada_str or not data_saida_str:
        return 0.0
    
    try:
        entrada = datetime.strptime(data_entrada_str, '%d/%m/%Y %H:%M:%S')
        saida = datetime.strptime(data_saida_str, '%d/%m/%Y %H:%M:%S')
        
        duracao = saida - entrada
        total_segundos = duracao.total_seconds()
        
        if total_segundos < 0:
            return 0.0
        
        # Converter para horas decimais (ex: 1h30m = 1.5)
        horas_decimais = total_segundos / 3600
        
        # Arredondar para 2 casas decimais
        return round(horas_decimais, 2)
            
    except Exception as e:
        return 0.0

def processar_eventos(eventos):
    """Processa eventos para formato CSV"""
    if not eventos:
        return []
    
    eventos_processados = []
    
    # Mapeamento de IDs para nomes de filiais
    filial_map = {
        '16619': 'TLS',
        '44459': 'RRP',
        '40452': 'FILIAL 40452',
        '16622': 'TLS',
        '39450': 'RRP'
    }
    
    for evento in eventos:
        # Verificar se o customerChildId está nos IDs permitidos
        customer_id = str(evento.get('customerChildId', ''))
        if customer_id not in IDS_PERMITIDOS:
            continue  # Pular eventos de outros IDs
        
        # Mapear status
        status_code = str(evento.get('status', ''))
        if status_code == '0':
            status_desc = "Saiu da cerca"
        elif status_code == '1':
            status_desc = "Entrou na cerca"
        else:
            status_desc = f"Status {status_code}"
        
        # Extrair datas
        data_entrada = evento.get('dateInFence', '')
        data_saida = evento.get('dateOutFence', '')
        data_update = evento.get('updatedAt', '')
        
        # Calcular duração em formato decimal
        duracao = calcular_duracao_formatada(formatar_data_local(data_entrada), formatar_data_local(data_saida))
        
        # Identificar filial
        filial_nome = filial_map.get(customer_id, f'ID {customer_id}')
        
        # Obter descrição POI e classificar grupo
        descricao_poi = evento.get('fenceDescription', '')
        grupo_poi = obter_grupo_poi(descricao_poi)
        
        # Criar registro com datas em horário local (modelo final)
        evento_processado = {
            'Filial': filial_nome,
            'Placa_Veiculo': evento.get('vehiclePlate', ''),
            'Descricao_POI': descricao_poi,
            'Grupo_POI': grupo_poi,
            'Data_Entrada': formatar_data_local(data_entrada),
            'Data_Saida': formatar_data_local(data_saida),
            'Status': status_desc,
            'Duracao': duracao,
            'Data_Atualizacao': formatar_data_local(data_update),
            'Customer_Child_Id': customer_id,
            'Vehicle_Id': evento.get('vehicleId', ''),
            'Fence_Id': evento.get('fenceId', '')
        }
        
        eventos_processados.append(evento_processado)
    
    return eventos_processados

def gerar_csv(todos_eventos):
    """Gera CSV com todos os eventos"""
    if not todos_eventos:
        print("⚠️ Nenhum evento para exportar")
        return ""
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"pontos_notaveis_final_{timestamp}.csv"
    
    fieldnames = [
        'Filial',
        'Placa_Veiculo',
        'Descricao_POI',
        'Grupo_POI',
        'Data_Entrada',
        'Data_Saida',
        'Status',
        'Duracao'
    ]
    
    # Filtrar apenas as colunas necessárias para o modelo final
    eventos_filtrados = []
    for evento in todos_eventos:
        evento_final = {
            'Filial': evento.get('Filial', ''),
            'Placa_Veiculo': evento.get('Placa_Veiculo', ''),
            'Descricao_POI': evento.get('Descricao_POI', ''),
            'Grupo_POI': evento.get('Grupo_POI', ''),
            'Data_Entrada': evento.get('Data_Entrada', ''),
            'Data_Saida': evento.get('Data_Saida', ''),
            'Status': evento.get('Status', ''),
            'Duracao': evento.get('Duracao', 0.0)
        }
        eventos_filtrados.append(evento_final)
    
    with open(filename, 'w', newline='', encoding='utf-8-sig') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(eventos_filtrados)
    
    print(f"📊 CSV gerado: {filename}")
    return filename

def gerar_relatorio(eventos):
    """Gera relatório detalhado dos eventos"""
    if not eventos:
        print("⚠️ Nenhum evento para gerar relatório")
        return
    
    print(f"\n" + "="*80)
    print("📈 RELATÓRIO DETALHADO - PONTOS NOTÁVEIS - ÚLTIMAS 5 HORAS")
    print("="*80)
    
    # Verificar IDs presentes
    ids_presentes = set(str(e['Customer_Child_Id']) for e in eventos)
    print(f"\n🆔 IDS PRESENTES NO RELATÓRIO:")
    for id_presente in sorted(ids_presentes):
        count = sum(1 for e in eventos if str(e['Customer_Child_Id']) == id_presente)
        print(f"   • ID {id_presente}: {count} eventos")
    
    # IDs sem eventos
    ids_sem_eventos = IDS_PERMITIDOS - ids_presentes
    if ids_sem_eventos:
        print(f"\n⚠️ IDS SEM EVENTOS NO PERÍODO:")
        for id_sem in sorted(ids_sem_eventos):
            print(f"   • ID {id_sem}")
    
    # Estatísticas por filial
    filiais_counter = Counter(e['Filial'] for e in eventos)
    print(f"\n🏢 EVENTOS POR FILIAL:")
    for filial, count in filiais_counter.most_common():
        print(f"   • {filial}: {count} eventos")
    
    # Veículos únicos
    placas = set(e['Placa_Veiculo'] for e in eventos if e['Placa_Veiculo'])
    print(f"\n🚛 VEÍCULOS ÚNICOS: {len(placas)}")
    
    # POIs mais visitados
    poi_counter = Counter(e['Descricao_POI'] for e in eventos if e['Descricao_POI'])
    print(f"\n🏭 TOP 10 PONTOS NOTÁVEIS MAIS VISITADOS:")
    for poi, count in poi_counter.most_common(10):
        print(f"   • {poi}: {count} eventos")
    
    # Grupos mais visitados
    grupo_counter = Counter(e['Grupo_POI'] for e in eventos if e['Grupo_POI'])
    print(f"\n📊 EVENTOS POR GRUPO:")
    for grupo, count in grupo_counter.most_common():
        print(f"   • {grupo}: {count} eventos")
    
    # Status dos eventos
    status_counter = Counter(e['Status'] for e in eventos)
    print(f"\n📊 STATUS DOS EVENTOS:")
    for status, count in status_counter.items():
        print(f"   • {status}: {count} eventos")
    
    # Primeiros eventos (ordem cronológica)
    print(f"\n📅 PRIMEIROS 10 EVENTOS (ordem cronológica por placa):")
    for evento in eventos[:10]:
        grupo = evento['Grupo_POI'][:15] if evento['Grupo_POI'] else 'Sem Grupo'
        print(f"   {evento['Placa_Veiculo']} - {evento['Data_Entrada']} - {evento['Descricao_POI'][:25]} - [{grupo}] - {evento['Status']}")
    
    # Mostrar organização por placa
    print(f"\n🚛 EVENTOS POR VEÍCULO (primeiros 5 veículos):")
    placas_processadas = set()
    for evento in eventos:
        placa = evento['Placa_Veiculo']
        if placa and placa not in placas_processadas:
            placas_processadas.add(placa)
            # Contar eventos desta placa
            eventos_placa = [e for e in eventos if e['Placa_Veiculo'] == placa]
            print(f"   • {placa}: {len(eventos_placa)} eventos")
            if len(placas_processadas) >= 5:
                break
    
    # Resumo geral
    print(f"\n📋 RESUMO GERAL:")
    print(f"   • Total de eventos: {len(eventos)}")
    print(f"   • Veículos únicos: {len(placas)}")
    print(f"   • POIs únicos: {len(poi_counter)}")
    print(f"   • Filiais com eventos: {len(filiais_counter)}")
    print(f"   • IDs com eventos: {len(ids_presentes)}/{len(IDS_PERMITIDOS)}")

def main():
    """Função principal"""
    print("="*80)
    print("🚛 PONTOS NOTÁVEIS - FILTRO ESPECÍFICO POR IDS - ÚLTIMAS 5 HORAS")
    print("="*80)
    
    agora = datetime.now(CAMPO_GRANDE_TZ)
    print(f"🕐 Horário atual: {agora.strftime('%d/%m/%Y %H:%M:%S')} (Campo Grande/MS)")
    print(f"🆔 IDs filtrados: {', '.join(sorted(IDS_PERMITIDOS))}")
    print()
    
    # IDs para filtrar conforme solicitado
    ids_filtro = ",".join(IDS_PERMITIDOS)
    
    try:
        # Buscar eventos
        print("🔄 Iniciando busca de eventos...")
        eventos_raw = buscar_eventos_12hrs(ids_filtro)
        
        if not eventos_raw:
            print("\n❌ Nenhum evento obtido da API para os IDs especificados")
            return
        
        # Processar eventos
        print("\n🔄 Processando eventos...")
        eventos_processados = processar_eventos(eventos_raw)
        
        if not eventos_processados:
            print("\n❌ Nenhum evento processado para os IDs especificados")
            return
        
        # Consolidar eventos consecutivos (limpeza de falhas do rastreador)
        print("\n🧹 Aplicando limpeza de dados...")
        eventos_processados = consolidar_eventos_consecutivos(eventos_processados)
        
        if not eventos_processados:
            print("\n❌ Nenhum evento após consolidação")
            return
        
        # Ordenar por Placa e depois por Data_Entrada (mais antigos primeiro)
        # Função para extrair datetime da string formatada
        def parse_data(data_str):
            if not data_str:
                return datetime.min.replace(tzinfo=CAMPO_GRANDE_TZ)
            try:
                # Parse do formato DD/MM/YYYY HH:MM:SS
                return datetime.strptime(data_str, '%d/%m/%Y %H:%M:%S').replace(tzinfo=CAMPO_GRANDE_TZ)
            except:
                return datetime.min.replace(tzinfo=CAMPO_GRANDE_TZ)
        
        # Ordenar primeiro por placa, depois por data de entrada (mais antigo primeiro)
        eventos_processados.sort(key=lambda x: (
            x['Placa_Veiculo'],
            parse_data(x['Data_Entrada'])
        ))
        
        # Gerar CSV
        filename = gerar_csv(eventos_processados)
        
        # Gerar relatório
        gerar_relatorio(eventos_processados)
        
        print(f"\n" + "="*80)
        print(f"🎉 PROCESSAMENTO CONCLUÍDO COM SUCESSO!")
        print(f"📊 Arquivo CSV: {filename}")
        print(f"📋 Total de eventos processados: {len(eventos_processados)}")
        print("="*80)
        
    except Exception as e:
        print(f"\n❌ Erro durante execução: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()