#!/usr/bin/env python3
"""
Script de investigação para entender o comportamento da API Creare
com diferentes janelas de tempo
"""

import json
import base64
import urllib.request
import urllib.parse
from datetime import datetime, timedelta, timezone
from collections import defaultdict
import os

# Carregar variáveis de ambiente do .env manualmente
def load_env():
    env_path = '../../.env'
    if os.path.exists(env_path):
        with open(env_path, 'r') as f:
            for line in f:
                if '=' in line and not line.startswith('#'):
                    key, value = line.strip().split('=', 1)
                    os.environ[key] = value

load_env()

# Timezone de Campo Grande (UTC-4)
from zoneinfo import ZoneInfo
CAMPO_GRANDE_TZ = ZoneInfo("America/Campo_Grande")

# POIs para teste (apenas alguns)
POIS_TESTE = [
    "Carregamento Fabrica RRP",
    "Manutencao JSL RRP", 
    "Agua Clara",
    "Carregamento Fabrica",
    "Oficina Central JSL"
]

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

def buscar_eventos_janela(horas_atras):
    """Busca eventos para uma janela específica de tempo"""
    token = get_token()
    if not token:
        return []
    
    headers = {
        'Authorization': f'Bearer {token}',
        'Accept': 'application/json'
    }
    
    endpoint = "https://api.crearecloud.com.br/frotalog/specialized-services/v3/pontos-notaveis/by-updated"
    
    # Definir janela de tempo
    agora_local = datetime.now(CAMPO_GRANDE_TZ)
    agora_utc = agora_local.astimezone(timezone.utc)
    inicio_local = agora_local - timedelta(hours=horas_atras)
    inicio_utc = inicio_local.astimezone(timezone.utc)
    
    params = {
        "startUpdatedAtTimestamp": inicio_utc.strftime('%Y-%m-%dT%H:%M:%S.%f')[:-3] + 'Z',
        "endUpdatedAtTimestamp": agora_utc.strftime('%Y-%m-%dT%H:%M:%S.%f')[:-3] + 'Z',
        "page": 1,
        "size": 1000,
        "sort": "updatedAt,desc"
    }
    
    todos_eventos = []
    
    try:
        param_string = urllib.parse.urlencode(params)
        full_url = f"{endpoint}?{param_string}"
        
        request = urllib.request.Request(full_url, headers=headers)
        
        with urllib.request.urlopen(request, timeout=60) as response:
            if response.status == 200:
                data = json.loads(response.read().decode('utf-8'))
                eventos = data.get('content', [])
                
                # Filtrar apenas POIs de teste
                for evento in eventos:
                    descricao_poi = evento.get('fenceDescription', '')
                    if descricao_poi in POIS_TESTE:
                        todos_eventos.append(evento)
                
                return todos_eventos
                    
    except Exception as e:
        print(f"❌ Erro: {e}")
        return []

def analisar_veiculos_ativos(eventos):
    """Analisa quais veículos estão atualmente nos POIs"""
    veiculos_por_poi = defaultdict(set)
    veiculos_ativos = {}
    
    # Ordenar eventos por veículo e data
    eventos_ordenados = sorted(eventos, key=lambda x: (
        x.get('vehicle', {}).get('licensePlate', ''),
        x.get('updatedAt', '')
    ))
    
    for evento in eventos_ordenados:
        placa = evento.get('vehicle', {}).get('licensePlate', 'N/A')
        poi = evento.get('fenceDescription', 'N/A')
        status = evento.get('action', '')
        data_utc = evento.get('updatedAt', '')
        
        # Converter para horário local
        if data_utc:
            dt_utc = datetime.fromisoformat(data_utc.replace('Z', '+00:00'))
            dt_local = dt_utc.astimezone(CAMPO_GRANDE_TZ)
        else:
            dt_local = None
        
        # Rastrear último status de cada veículo
        if status == 'E':  # Entrou
            veiculos_ativos[placa] = {
                'poi': poi,
                'entrada': dt_local,
                'status': 'DENTRO'
            }
            veiculos_por_poi[poi].add(placa)
        elif status == 'S':  # Saiu
            if placa in veiculos_ativos and veiculos_ativos[placa]['poi'] == poi:
                veiculos_ativos[placa]['status'] = 'FORA'
                veiculos_por_poi[poi].discard(placa)
    
    # Filtrar apenas veículos que ainda estão dentro
    veiculos_dentro = {
        placa: info 
        for placa, info in veiculos_ativos.items() 
        if info['status'] == 'DENTRO'
    }
    
    return veiculos_dentro, veiculos_por_poi

def main():
    print("🔍 INVESTIGAÇÃO DO COMPORTAMENTO DA API CREARE")
    print("=" * 60)
    
    # Testar diferentes janelas de tempo
    janelas = [1, 2, 3, 5, 24]  # horas
    
    for horas in janelas:
        print(f"\n📊 Testando janela de {horas} hora(s)")
        print("-" * 40)
        
        eventos = buscar_eventos_janela(horas)
        print(f"Total de eventos encontrados: {len(eventos)}")
        
        if eventos:
            # Mostrar estrutura completa do primeiro evento
            print(f"\nEstrutura do primeiro evento:")
            if eventos:
                primeiro = eventos[0]
                print(json.dumps(primeiro, indent=2, ensure_ascii=False))
            
            # Mostrar alguns eventos brutos primeiro
            print(f"\nPrimeiros 3 eventos (campos relevantes):")
            for i, evento in enumerate(eventos[:3]):
                print(f"  {i+1}. Evento: {json.dumps(evento, indent=4, ensure_ascii=False)[:200]}...")
                break  # Apenas o primeiro para não poluir
            
            veiculos_dentro, veiculos_por_poi = analisar_veiculos_ativos(eventos)
            
            print(f"\nVeículos atualmente nos POIs: {len(veiculos_dentro)}")
            
            # Mostrar resumo por POI
            print("\nResumo por POI:")
            for poi, veiculos in veiculos_por_poi.items():
                if veiculos:  # Apenas POIs com veículos
                    print(f"  • {poi}: {len(veiculos)} veículo(s)")
            
            # Se não há veículos dentro, mostrar últimas atividades
            if not veiculos_dentro:
                print("\nÚltimas atividades por POI:")
                poi_atividades = defaultdict(list)
                for evento in eventos:
                    poi = evento.get('fenceDescription', 'N/A')
                    poi_atividades[poi].append(evento)
                
                for poi, events in poi_atividades.items():
                    ultimo_evento = max(events, key=lambda x: x.get('updatedAt', ''))
                    placa = ultimo_evento.get('vehicle', {}).get('licensePlate', 'N/A')
                    action = "ENTROU" if ultimo_evento.get('action') == 'E' else "SAIU"
                    data = ultimo_evento.get('updatedAt', '')
                    print(f"  • {poi}: {placa} {action} ({data})")
            
            # Mostrar alguns exemplos
            if veiculos_dentro:
                print("\nExemplos de veículos dentro (máx 5):")
                for i, (placa, info) in enumerate(list(veiculos_dentro.items())[:5]):
                    if info['entrada']:
                        tempo_dentro = datetime.now(CAMPO_GRANDE_TZ) - info['entrada']
                        horas_dentro = tempo_dentro.total_seconds() / 3600
                        print(f"  • {placa} em {info['poi']}: {horas_dentro:.1f}h")
    
    print("\n" + "=" * 60)
    print("📋 CONCLUSÕES:")
    print("-" * 40)
    print("1. A API retorna eventos de ENTRADA (E) e SAÍDA (S)")
    print("2. Para saber quem está DENTRO agora, precisamos:")
    print("   - Buscar eventos suficientes para capturar a última entrada")
    print("   - Verificar se houve saída posterior")
    print("3. Janela ideal depende do tempo máximo de permanência esperado")
    print("\n💡 RECOMENDAÇÃO:")
    print("Para garantir captura de todos os veículos ativos,")
    print("usar janela de pelo menos 12-24 horas na primeira execução,")
    print("e depois manter estado em BigQuery para otimizar.")

if __name__ == "__main__":
    main()