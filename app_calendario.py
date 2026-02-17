"""
Calendario de Disponibilidade de Aeronaves - REVO
Layout com visualizacao Gantt detalhada por dia
"""

from flask import Flask, render_template_string, jsonify, request
import os
import time

# Carregar .env do diretório do script (garante funcionar de qualquer cwd)
_app_dir = os.path.dirname(os.path.abspath(__file__))
_env_path = os.path.join(_app_dir, '.env')
if os.path.exists(_env_path):
    from dotenv import load_dotenv
    load_dotenv(_env_path)
from datetime import datetime, timedelta
from simple_salesforce import Salesforce
import logging
import calendar
from math import radians, cos, sin, asin, sqrt
import json
import threading

app = Flask(__name__)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# ===== CACHE =====
_cache = {'data': None, 'stats': None, 'timestamp': 0, 'raw_json': None}
_cache_lock = threading.Lock()
CACHE_TTL = 120  # 2 minutos

HELICOPTEROS = {
    'PR-OMB': {'modelo': 'EC155', 'cor': '#3B82F6', 'velocidade_kmh': 259.28},
    'PR-OMH': {'modelo': 'EC155', 'cor': '#10B981', 'velocidade_kmh': 259.28},
    'PR-OOE': {'modelo': 'EC135', 'cor': '#F59E0B', 'velocidade_kmh': 222.24}
}

# Helipontos/aeródromos: nome, lat, lon.
# Códigos não cadastrados: consultar ROTAER (AISWEB) https://aisweb.decea.mil.br/?i=aerodromos&p=rotaer
HELIPONTOS = {
    'SIAV': {'nome': 'Helipark', 'lat': -23.5647, 'lon': -46.8303},
    'SBGR': {'nome': 'Aeroporto de Guarulhos', 'lat': -23.4356, 'lon': -46.4731},
    'SBSP': {'nome': 'Aeroporto de Congonhas', 'lat': -23.6261, 'lon': -46.6564},
    'SBMT': {'nome': 'Campo de Marte', 'lat': -23.5091, 'lon': -46.6378},
    'SDMN': {'nome': 'Continental Tower', 'lat': -23.6017, 'lon': -46.6992},
    'SDOF': {'nome': 'Edificio Palladio', 'lat': -23.5947, 'lon': -46.6856},
    'SDXQ': {'nome': 'Internacional Plaza II', 'lat': -23.5911, 'lon': -46.6822},
    'SIJF': {'nome': 'Ed. Faria Lima Financial Center', 'lat': -23.5861, 'lon': -46.6833},
    'SNGL': {'nome': 'Boa Vista (Porto Feliz)', 'lat': -23.3319, 'lon': -47.5594},
    'SSJN': {'nome': 'Faz. Santa Helena (Braganca Paulista)', 'lat': -22.9706, 'lon': -46.6803},
    'SDLA': {'nome': 'Cond. Laranjeiras (Paraty)', 'lat': -23.3433, 'lon': -44.6631},
    'SDUB': {'nome': 'Aeroporto de Ubatuba', 'lat': -23.4411, 'lon': -45.0756},
    'SJCG': {'nome': 'Iate Clube de Santos (Angra)', 'lat': -22.9781, 'lon': -44.4336},
    'SBJH': {'nome': 'SP Catarina Aeroporto Executivo', 'lat': -23.4269, 'lon': -47.1658},
    'SWWD': {'nome': 'Dom Pedro Business Park (Atibaia)', 'lat': -23.0506, 'lon': -46.6728},
    'SJWD': {'nome': 'RDP (Mangaratiba)', 'lat': -22.9936, 'lon': -44.0939},
    'SDTK': {'nome': 'Aeroporto de Paraty', 'lat': -23.2239, 'lon': -44.7233},
    'SIIR': {'nome': 'Brascan Century Plaza', 'lat': -23.5842, 'lon': -46.6756},
    'SBOP': {'nome': 'Aeroporto de Porto Seguro', 'lat': -16.4386, 'lon': -39.0653},
    'SITO': {'nome': 'Berrini One', 'lat': -23.5983, 'lon': -46.6906},
    'SDTN': {'nome': 'REC Berrini TNU', 'lat': -23.6081, 'lon': -46.6967},
    'SDBR': {'nome': 'REC Berrini', 'lat': -23.6081, 'lon': -46.6942},
    'SDLF': {'nome': 'SBT (Osasco)', 'lat': -23.4767, 'lon': -46.7781},
    'SJTY': {'nome': 'Tivoli Mofarrej', 'lat': -23.5642, 'lon': -46.6558},
    'SI4L': {'nome': 'Ilha Grande', 'lat': -23.1500, 'lon': -44.2300},
    'SIBH': {'nome': 'Helicidade', 'lat': -23.5467, 'lon': -46.7369},
    'SBJD': {'nome': 'Aeroporto de Jundiai', 'lat': -23.1814, 'lon': -46.9436},
    'SBSJ': {'nome': 'Sao Jose dos Campos', 'lat': -23.2292, 'lon': -45.8711},
    'SBRJ': {'nome': 'Santos Dumont (Rio)', 'lat': -22.9106, 'lon': -43.1631},
    'SBKP': {'nome': 'Aeroporto de Campinas', 'lat': -23.0074, 'lon': -47.1345},
    'SDCY': {'nome': 'SP Corporate Towers', 'lat': -23.5917, 'lon': -46.6878},
    'SDGG': {'nome': 'Ache Faria Lima', 'lat': -23.5608, 'lon': -46.6942},
    'SSOA': {'nome': 'Blue Tree Tower Faria Lima', 'lat': -23.5911, 'lon': -46.6808},
    'SIRZ': {'nome': 'Cond. Faria Lima Pinheiros', 'lat': -23.5694, 'lon': -46.6911},
}

HANGAR_BASE = 'SIAV'

# ROTAER (AISWEB/DECEA): consulta de aeródromos por código ICAO
# https://aisweb.decea.mil.br/?i=aerodromos&p=rotaer
ROTAER_URL = 'https://aisweb.decea.mil.br/?i=aerodromos&codigo='
ROTAER_PAGE = 'https://aisweb.decea.mil.br/?i=aerodromos&p=rotaer'

ICONS_BASE64 = {
    'PR-OMB': 'data:image/png;base64,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',
    'PR-OMH': 'data:image/png;base64,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',
    'PR-OOE': 'data:image/png;base64,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',
}


def haversine_distance(lat1, lon1, lat2, lon2):
    R = 6371
    lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
    c = 2 * asin(sqrt(a))
    return R * c


def calcular_tempo_retorno(destino_icao, prefixo):
    if destino_icao not in HELIPONTOS or HANGAR_BASE not in HELIPONTOS:
        return 0.5
    dest = HELIPONTOS[destino_icao]
    hangar = HELIPONTOS[HANGAR_BASE]
    distancia = haversine_distance(dest['lat'], dest['lon'], hangar['lat'], hangar['lon'])
    velocidade = HELICOPTEROS.get(prefixo, {}).get('velocidade_kmh', 250)
    tempo_voo = distancia / velocidade
    return tempo_voo + (5/60)


def conectar_salesforce():
    try:
        sf = Salesforce(
            username=os.environ.get('SF_USERNAME'),
            password=os.environ.get('SF_PASSWORD'),
            security_token=os.environ.get('SF_SECURITY_TOKEN'),
            domain=os.environ.get('SF_DOMAIN', 'login')
        )
        logging.info("Conectado ao Salesforce!")
        return sf
    except Exception as e:
        logging.error(f"Erro ao conectar ao Salesforce: {e}")
        return None


def normalizar_prefixo(prefixo_raw):
    """Aceita OMB, PR OMB, PR-OMB etc e retorna PR-OMB, PR-OMH ou PR-OOE."""
    if not prefixo_raw:
        return None
    p = str(prefixo_raw).upper().strip()
    p = p.replace(' ', '-').replace('_', '-')
    if p in HELICOPTEROS:
        return p
    for k in HELICOPTEROS:
        if p == k.replace('PR-', '') or p.endswith(k) or k.endswith(p):
            return k
    return None


def _parsear_partes_rota(rota):
    """Retorna lista de codigos ICAO da rota (ex: SIAV-SDUB-SDLA -> ['SIAV','SDUB','SDLA'])."""
    if not rota:
        return []
    rota = str(rota).upper().strip()
    partes = rota.replace('/', '-').replace('X', '-').replace(' ', '-').split('-')
    return [p.strip()[:4] for p in partes if p.strip() and len(p.strip()) >= 4]


def extrair_icao_da_rota(rota):
    partes = _parsear_partes_rota(rota)
    if len(partes) >= 2:
        return partes[0], partes[-1]
    elif len(partes) == 1:
        return partes[0], partes[0]
    return 'N/A', 'N/A'


def extrair_pernas_da_rota(rota):
    """Retorna lista de (origem, destino) para cada perna. Ex: SIAV-SDUB-SDLA -> [(SIAV,SDUB),(SDUB,SDLA)]."""
    partes = _parsear_partes_rota(rota)
    if len(partes) < 2:
        return []
    return [(partes[i], partes[i + 1]) for i in range(len(partes) - 1)]


def rota_ja_inclui_perna_vazia(rota):
    """Ex: SIAV-SBGR-SDLA-SIAV indica que a perna vazia (retorno a base) ja esta na rota."""
    if not rota:
        return False
    rota = str(rota).upper().strip()
    partes = rota.replace('/', '-').replace('X', '-').replace(' ', '-').split('-')
    partes = [p.strip()[:4] for p in partes if p.strip()]
    return len(partes) >= 2 and partes[-1] == HANGAR_BASE


def buscar_voos(sf):
    """Busca TODOS os voos cadastrados (sem filtro de status)."""
    hoje = datetime.now()
    data_inicio = (hoje - timedelta(days=730)).strftime('%Y-%m-%d')  # 2 anos atras
    data_fim = (hoje + timedelta(days=730)).strftime('%Y-%m-%d')      # 2 anos a frente
    query = f"""
    SELECT Id, Name, Tipo__c, Status__c, DataHoraVoo__c, 
           Rota__c, RotaAbreviada__c, Prefixo__c, PrefixoTexto__c,
           ContadorPassageiros__c, ReceitaVoo__c, PerspectivaReceitaVoo__c, Duracao__c
    FROM Voo__c 
    WHERE DataHoraVoo__c >= {data_inicio}T00:00:00Z
    AND DataHoraVoo__c <= {data_fim}T23:59:59Z
    ORDER BY DataHoraVoo__c ASC
    """
    try:
        result = sf.query_all(query)
        voos = result.get('records', [])
        logging.info(f"Encontrados {len(voos)} voos")
        return voos
    except Exception as e:
        logging.error(f"Erro na query: {e}")
        return []


def buscar_trechos(sf):
    """Busca Trechos (pernas) com dados reais: Decolagem/Pouso, CodigoOrigem/Destino, passageiros por perna."""
    hoje = datetime.now()
    data_inicio = (hoje - timedelta(days=730)).strftime('%Y-%m-%d')
    data_fim = (hoje + timedelta(days=730)).strftime('%Y-%m-%d')
    query = (
        f"SELECT Id, Voo__c, Decolagem__c, Pouso__c, PrevisaoDecolagem__c, PrevisaoPouso__c, TempoCruzeiro__c, "
        f"CodigoOrigem__c, CodigoDestino__c, PrefixoAeronave__c, OrdemExecucao__c, "
        f"PassageirosEmbarcando__c, QtdPassageiros__c, "
        f"Voo__r.DataHoraVoo__c, Voo__r.Name, Voo__r.Status__c, Voo__r.Tipo__c, "
        f"Voo__r.ContadorPassageiros__c, Voo__r.ReceitaVoo__c, Voo__r.PerspectivaReceitaVoo__c "
        f"FROM Trecho__c "
        f"WHERE Voo__r.DataHoraVoo__c >= {data_inicio}T00:00:00Z "
        f"AND Voo__r.DataHoraVoo__c <= {data_fim}T23:59:59Z "
        f"ORDER BY Voo__r.DataHoraVoo__c, OrdemExecucao__c"
    )
    try:
        result = sf.query_all(query)
        trechos = result.get('records', [])
        logging.info(f"Encontrados {len(trechos)} trechos")
        return trechos
    except Exception as e:
        logging.error(f"Erro na query Trecho__c: {e}")
        return []


def processar_trechos(trechos):
    """Processa Trecho__c em voo_info: dados reais por perna (Decolagem, Pouso, passageiros)."""
    from collections import defaultdict
    voos_por_dia = {}
    voo_ids_com_trechos = set()
    stats = {
        'total_voos': 0,
        'total_retornos': 0,
        'por_aeronave': {'PR-OMB': 0, 'PR-OMH': 0, 'PR-OOE': 0},
        'total_horas': 0.0,
        'total_shuttle': 0,
        'total_charter': 0
    }
    retornos_cadastrados = set()

    # Agrupar trechos por Voo__c, ordenados por OrdemExecucao
    por_voo = defaultdict(list)
    for t in trechos:
        vid = t.get('Voo__c')
        if vid:
            por_voo[vid].append(t)
    for vid in por_voo:
        por_voo[vid].sort(key=lambda x: (float(x.get('OrdemExecucao__c') or 0), x.get('Id') or ''))

    for voo_id, lista_trechos in por_voo.items():
        if not lista_trechos:
            continue
        primeiro = lista_trechos[0]
        vr = primeiro.get('Voo__r') or {}
        prefixo = normalizar_prefixo(
            primeiro.get('PrefixoAeronave__c') or vr.get('PrefixoTexto__c') or ''
        )
        if prefixo is None or prefixo not in HELICOPTEROS:
            continue
        status = vr.get('Status__c', '')
        is_pago = 'pago' in status.lower() if status else False
        tipo_str = vr.get('Tipo__c', 'Charter')
        tipo_lower = (tipo_str or '').lower()
        receita_total = float(vr.get('ReceitaVoo__c', 0) or 0) or float(vr.get('PerspectivaReceitaVoo__c', 0) or 0)

        voo_ids_com_trechos.add(voo_id)
        dt_voo_str = vr.get('DataHoraVoo__c')
        try:
            dt_voo = datetime.fromisoformat(dt_voo_str.replace('Z', '+00:00')) if dt_voo_str else None
            dt_voo_local = dt_voo - timedelta(hours=3) if (dt_voo and dt_voo.tzinfo) else dt_voo
        except Exception:
            dt_voo_local = None

        pouso_anterior = None
        for idx, t in enumerate(lista_trechos):
            origem = (t.get('CodigoOrigem__c') or '').strip().upper()[:4]
            destino = (t.get('CodigoDestino__c') or '').strip().upper()[:4]
            if not origem or not destino or origem == destino:
                continue

            dep_dt = None
            for f in ('Decolagem__c', 'PrevisaoDecolagem__c'):
                val = t.get(f)
                if val:
                    try:
                        dep_dt = datetime.fromisoformat(val.replace('Z', '+00:00'))
                        dep_dt = dep_dt - timedelta(hours=3) if dep_dt.tzinfo else dep_dt
                        break
                    except Exception:
                        pass
            if dep_dt is None and pouso_anterior is not None:
                dep_dt = pouso_anterior + timedelta(minutes=15)
            elif dep_dt is None and dt_voo_local and idx == 0:
                dep_dt = dt_voo_local

            arr_dt = None
            for f in ('Pouso__c', 'PrevisaoPouso__c'):
                val = t.get(f)
                if val:
                    try:
                        arr_dt = datetime.fromisoformat(val.replace('Z', '+00:00'))
                        arr_dt = arr_dt - timedelta(hours=3) if arr_dt.tzinfo else arr_dt
                        break
                    except Exception:
                        pass
            if arr_dt is None and dep_dt is not None:
                tempo_cruzeiro = float(t.get('TempoCruzeiro__c', 0) or 0)
                if tempo_cruzeiro > 0:
                    arr_dt = dep_dt + timedelta(minutes=tempo_cruzeiro)
                else:
                    arr_dt = dep_dt + timedelta(minutes=20)

            if dep_dt is None or arr_dt is None:
                continue

            pouso_anterior = arr_dt
            origem_nome = HELIPONTOS.get(origem, {}).get('nome', origem)
            destino_nome = HELIPONTOS.get(destino, {}).get('nome', destino)
            duracao_min = int((arr_dt - dep_dt).total_seconds() / 60)
            data_str = dep_dt.strftime('%Y-%m-%d')
            pax = int(t.get('PassageirosEmbarcando__c') or t.get('QtdPassageiros__c') or 0)
            receita = receita_total / len(lista_trechos) if idx == 0 else 0

            voo_info = {
                'id': t.get('Id'),
                'name': vr.get('Name', ''),
                'prefixo': prefixo,
                'origem': origem,
                'destino': destino,
                'origem_nome': origem_nome,
                'destino_nome': destino_nome,
                'inicio': dep_dt,
                'fim': arr_dt,
                'duracao_min': duracao_min,
                'tipo': tipo_str,
                'status': status,
                'is_pago': is_pago,
                'passageiros': pax,
                'receita': receita,
                'is_retorno': False,
                'retorno_info': None,
                'fonte': 'trecho'
            }

            if destino != HANGAR_BASE:
                ultimo_trecho = lista_trechos[-1]
                ultimo_dest = (ultimo_trecho.get('CodigoDestino__c') or '').strip().upper()[:4]
                if ultimo_dest != HANGAR_BASE and idx == len(lista_trechos) - 1:
                    chave_retorno = (prefixo, data_str, destino)
                    if chave_retorno not in retornos_cadastrados:
                        tempo_retorno = calcular_tempo_retorno(destino, prefixo)
                        retorno_inicio = arr_dt + timedelta(minutes=10)
                        retorno_fim = retorno_inicio + timedelta(hours=tempo_retorno)
                        voo_info['retorno_info'] = {
                            'inicio': retorno_inicio,
                            'fim': retorno_fim,
                            'duracao_min': int((retorno_fim - retorno_inicio).total_seconds() / 60),
                            'origem': destino,
                            'destino': HANGAR_BASE,
                            'origem_nome': destino_nome,
                            'destino_nome': HELIPONTOS.get(HANGAR_BASE, {}).get('nome', HANGAR_BASE)
                        }
                        retornos_cadastrados.add(chave_retorno)
                        stats['total_retornos'] += 1

            if data_str not in voos_por_dia:
                voos_por_dia[data_str] = []
            voos_por_dia[data_str].append(voo_info)
            stats['total_voos'] += 1
            stats['por_aeronave'][prefixo] += 1
            if 'shuttle' in tipo_lower:
                stats['total_shuttle'] += 1
            else:
                stats['total_charter'] += 1
            stats['total_horas'] += duracao_min / 60.0
            if voo_info.get('retorno_info'):
                stats['total_horas'] += voo_info['retorno_info']['duracao_min'] / 60.0

    for data in voos_por_dia:
        voos_por_dia[data].sort(key=lambda x: x['inicio'])
    return voos_por_dia, stats, voo_ids_com_trechos, retornos_cadastrados


def processar_voos(voos, voo_ids_com_trechos=None, retornos_cadastrados_in=None):
    """Processa Voo__c. Exclui voos cujos trechos ja foram processados (voo_ids_com_trechos)."""
    voo_ids_com_trechos = voo_ids_com_trechos or set()
    retornos_cadastrados = set(retornos_cadastrados_in) if retornos_cadastrados_in else set()
    voos_por_dia = {}
    stats = {
        'total_voos': 0,
        'total_retornos': 0,
        'por_aeronave': {'PR-OMB': 0, 'PR-OMH': 0, 'PR-OOE': 0},
        'total_horas': 0.0,
        'total_shuttle': 0,
        'total_charter': 0
    }
    
    # Perna vazia ja registrada no SF: (prefixo, data, origem) para voos destino=SIAV
    for v in voos:
        if v.get('Id') in voo_ids_com_trechos:
            continue
        pref = normalizar_prefixo(v.get('PrefixoTexto__c') or v.get('Prefixo__c') or '')
        if pref not in HELICOPTEROS:
            continue
        dt_s = v.get('DataHoraVoo__c')
        if not dt_s:
            continue
        try:
            dt = datetime.fromisoformat(dt_s.replace('Z', '+00:00'))
            dt_local = dt - timedelta(hours=3) if dt.tzinfo else dt
        except:
            continue
        rota = v.get('RotaAbreviada__c') or v.get('Rota__c') or ''
        orig, dest = extrair_icao_da_rota(rota)
        if dest == HANGAR_BASE and orig in HELIPONTOS and orig != HANGAR_BASE:
            retornos_cadastrados.add((pref, dt_local.strftime('%Y-%m-%d'), orig))
    
    for voo in voos:
        if voo.get('Id') in voo_ids_com_trechos:
            continue
        prefixo = normalizar_prefixo(voo.get('PrefixoTexto__c') or voo.get('Prefixo__c') or '')
        if prefixo is None or prefixo not in HELICOPTEROS:
            continue
            
        dt_str = voo.get('DataHoraVoo__c')
        if not dt_str:
            continue
            
        try:
            dt = datetime.fromisoformat(dt_str.replace('Z', '+00:00'))
            dt_local = dt - timedelta(hours=3) if dt.tzinfo else dt
        except:
            continue
        
        rota = voo.get('RotaAbreviada__c') or voo.get('Rota__c') or ''
        pernas = extrair_pernas_da_rota(rota)
        duracao_total = float(voo.get('Duracao__c', 0) or 0) or 0.5
        status = voo.get('Status__c', '')
        is_pago = 'pago' in status.lower() if status else False
        tipo_lower = (voo.get('Tipo__c', '') or '').lower()
        passageiros_total = voo.get('ContadorPassageiros__c', 0) or 0
        receita_total = float(voo.get('ReceitaVoo__c', 0) or 0) or float(voo.get('PerspectivaReceitaVoo__c', 0) or 0)
        
        # Se rota tem multiplas pernas, criar um bloco por perna com horarios estimados
        if len(pernas) >= 2:
            buffer_min_entre_pernas = 10
            horas_voo = duracao_total - (len(pernas) - 1) * (buffer_min_entre_pernas / 60.0)
            duracao_por_perna_h = max(0.15, horas_voo / len(pernas)) if horas_voo > 0 else 0.5
            dep_atual = dt_local
            for idx, (origem, destino) in enumerate(pernas):
                arr_atual = dep_atual + timedelta(hours=duracao_por_perna_h)
                origem_nome = HELIPONTOS.get(origem, {}).get('nome', origem)
                destino_nome = HELIPONTOS.get(destino, {}).get('nome', destino)
                duracao_min = int((arr_atual - dep_atual).total_seconds() / 60)
                data_str = dep_atual.strftime('%Y-%m-%d')
                # Passageiros/receita apenas na primeira perna (SF nao detalha por perna)
                pax = passageiros_total if idx == 0 else 0
                rec = receita_total if idx == 0 else 0
                voo_info = {
                    'id': voo.get('Id'),
                    'name': voo.get('Name', ''),
                    'prefixo': prefixo,
                    'origem': origem,
                    'destino': destino,
                    'origem_nome': origem_nome,
                    'destino_nome': destino_nome,
                    'inicio': dep_atual,
                    'fim': arr_atual,
                    'duracao_min': duracao_min,
                    'tipo': voo.get('Tipo__c', 'Charter'),
                    'status': status,
                    'is_pago': is_pago,
                    'passageiros': pax,
                    'receita': rec,
                    'is_retorno': False,
                    'retorno_info': None
                }
                if destino != HANGAR_BASE and not rota_ja_inclui_perna_vazia(rota):
                    chave_retorno = (prefixo, data_str, destino)
                    if chave_retorno not in retornos_cadastrados and idx == len(pernas) - 1:
                        tempo_retorno = calcular_tempo_retorno(destino, prefixo)
                        retorno_inicio = arr_atual + timedelta(minutes=10)
                        retorno_fim = retorno_inicio + timedelta(hours=tempo_retorno)
                        voo_info['retorno_info'] = {
                            'inicio': retorno_inicio,
                            'fim': retorno_fim,
                            'duracao_min': int((retorno_fim - retorno_inicio).total_seconds() / 60),
                            'origem': destino,
                            'destino': HANGAR_BASE,
                            'origem_nome': destino_nome,
                            'destino_nome': HELIPONTOS.get(HANGAR_BASE, {}).get('nome', HANGAR_BASE)
                        }
                        stats['total_retornos'] += 1
                if data_str not in voos_por_dia:
                    voos_por_dia[data_str] = []
                voos_por_dia[data_str].append(voo_info)
                stats['total_voos'] += 1
                stats['por_aeronave'][prefixo] += 1
                if 'shuttle' in tipo_lower:
                    stats['total_shuttle'] += 1
                else:
                    stats['total_charter'] += 1
                stats['total_horas'] += duracao_por_perna_h
                if voo_info.get('retorno_info'):
                    stats['total_horas'] += voo_info['retorno_info']['duracao_min'] / 60.0
                dep_atual = arr_atual + timedelta(minutes=buffer_min_entre_pernas)
        else:
            # Rota simples (1 perna) - logica original
            origem, destino = extrair_icao_da_rota(rota)
            duracao_estimada = duracao_total
            dep_time = dt_local
            arr_time = dt_local + timedelta(hours=duracao_estimada)
            origem_nome = HELIPONTOS.get(origem, {}).get('nome', origem)
            destino_nome = HELIPONTOS.get(destino, {}).get('nome', destino)
            duracao_min = int((arr_time - dep_time).total_seconds() / 60)
            data_str = dep_time.strftime('%Y-%m-%d')
            voo_info = {
                'id': voo.get('Id'),
                'name': voo.get('Name', ''),
                'prefixo': prefixo,
                'origem': origem,
                'destino': destino,
                'origem_nome': origem_nome,
                'destino_nome': destino_nome,
                'inicio': dep_time,
                'fim': arr_time,
                'duracao_min': duracao_min,
                'tipo': voo.get('Tipo__c', 'Charter'),
                'status': status,
                'is_pago': is_pago,
                'passageiros': passageiros_total,
                'receita': receita_total,
                'is_retorno': False,
                'retorno_info': None
            }
            if destino != HANGAR_BASE and not rota_ja_inclui_perna_vazia(rota):
                chave_retorno = (prefixo, data_str, destino)
                if chave_retorno not in retornos_cadastrados:
                    tempo_retorno = calcular_tempo_retorno(destino, prefixo)
                    retorno_inicio = arr_time + timedelta(minutes=10)
                    retorno_fim = retorno_inicio + timedelta(hours=tempo_retorno)
                    duracao_ret = int((retorno_fim - retorno_inicio).total_seconds() / 60)
                    voo_info['retorno_info'] = {
                        'inicio': retorno_inicio,
                        'fim': retorno_fim,
                        'duracao_min': duracao_ret,
                        'origem': destino,
                        'destino': HANGAR_BASE,
                        'origem_nome': destino_nome,
                        'destino_nome': HELIPONTOS.get(HANGAR_BASE, {}).get('nome', HANGAR_BASE)
                    }
                    stats['total_retornos'] += 1
            if data_str not in voos_por_dia:
                voos_por_dia[data_str] = []
            voos_por_dia[data_str].append(voo_info)
            stats['total_voos'] += 1
            stats['por_aeronave'][prefixo] += 1
            if 'shuttle' in tipo_lower:
                stats['total_shuttle'] += 1
            else:
                stats['total_charter'] += 1
            stats['total_horas'] += duracao_estimada
            if voo_info.get('retorno_info'):
                ret_dur = voo_info['retorno_info']['duracao_min'] / 60.0
                stats['total_horas'] += ret_dur
    
    for data in voos_por_dia:
        voos_por_dia[data].sort(key=lambda x: x['inicio'])
    
    return voos_por_dia, stats


HTML_TEMPLATE = '''
<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Calendario de Disponibilidade - REVO</title>
    <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: #0f172a;
            min-height: 100vh;
            color: #e2e8f0;
        }
        
        .container { max-width: 1600px; margin: 0 auto; padding: 20px; }
        .header { text-align: center; margin-bottom: 20px; color: #94a3b8; font-size: 0.9rem; }
        
        .legend {
            display: flex; justify-content: center; align-items: center; gap: 30px;
            margin-bottom: 25px; flex-wrap: wrap;
        }
        .legend-item {
            display: flex; align-items: center; gap: 10px;
            background: #1e293b; padding: 8px 16px; border-radius: 8px;
        }
        .legend-icon { width: 32px; height: 32px; border-radius: 6px; }
        .legend-item.retorno { border: 2px dashed #eab308; background: transparent; }
        
        .stats-grid {
            display: grid; grid-template-columns: repeat(7, 1fr); gap: 15px;
            margin-bottom: 20px;
        }
        .stat-card {
            background: #1e293b; border-radius: 12px; padding: 16px; text-align: center;
            border: 1px solid #334155;
        }
        .stat-number { font-size: 2.2rem; font-weight: 700; margin-bottom: 5px; }
        .stat-label { font-size: 0.8rem; color: #94a3b8; }
        .stat-card.blue .stat-number { color: #3B82F6; }
        .stat-card.green .stat-number { color: #10B981; }
        .stat-card.orange .stat-number { color: #F59E0B; }
        
        /* ===== FILTROS ===== */
        .filters-bar {
            display: flex; align-items: center; gap: 10px; margin-bottom: 20px;
            flex-wrap: wrap;
        }
        .filter-btn {
            background: #334155; border: 2px solid #475569; color: #94a3b8;
            padding: 6px 16px; border-radius: 20px; cursor: pointer;
            font-size: 0.85rem; font-weight: 500; transition: all 0.2s;
        }
        .filter-btn:hover { background: #475569; color: #e2e8f0; }
        .filter-btn.active { background: #1e40af; border-color: #3b82f6; color: white; }
        .filter-btn.active-green { background: #065f46; border-color: #10b981; color: white; }
        .filter-btn.active-orange { background: #78350f; border-color: #f59e0b; color: white; }
        .filter-btn.active-blue { background: #1e3a5f; border-color: #3b82f6; color: white; }
        .filter-btn.active-purple { background: #4c1d95; border-color: #7c3aed; color: white; }
        .filter-btn.active-teal { background: #164e63; border-color: #0891b2; color: white; }
        .filter-label { color: #64748b; font-size: 0.8rem; font-weight: 600; text-transform: uppercase; letter-spacing: 0.05em; }
        .filter-separator { width: 1px; height: 24px; background: #475569; }
        
        /* ===== PROXIMOS VOOS ===== */
        .next-flights {
            background: #1e293b; border-radius: 16px; padding: 20px; margin-bottom: 20px;
            border: 1px solid #334155;
        }
        .next-flights-title {
            font-size: 1rem; font-weight: 700; color: #94a3b8; margin-bottom: 15px;
            display: flex; align-items: center; gap: 8px;
        }
        .next-flights-title .pulse { display: inline-block; width: 8px; height: 8px; background: #22c55e; border-radius: 50%; animation: pulse 2s infinite; }
        @keyframes pulse { 0%,100% { opacity: 1; } 50% { opacity: 0.3; } }
        .next-flights-grid { display: flex; gap: 12px; overflow-x: auto; padding-bottom: 5px; }
        .nf-card {
            background: #0f172a; border-radius: 10px; padding: 14px; min-width: 220px; flex-shrink: 0;
            border-left: 3px solid #475569; transition: all 0.2s; cursor: pointer;
        }
        .nf-card:hover { background: #1e3a5f; transform: translateY(-2px); }
        .nf-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px; }
        .nf-date { font-size: 0.75rem; color: #64748b; }
        .nf-prefix { font-weight: 700; font-size: 0.9rem; }
        .nf-route { font-size: 0.85rem; color: #e2e8f0; margin-bottom: 4px; }
        .nf-time { font-size: 0.8rem; color: #94a3b8; }
        .nf-badge { font-size: 0.65rem; padding: 2px 8px; border-radius: 10px; font-weight: 600; }
        .nf-badge.shuttle { background: #7c3aed; color: white; }
        .nf-badge.charter { background: #0369a1; color: white; }
        
        /* ===== AUTO-REFRESH INDICATOR ===== */
        .refresh-bar {
            display: flex; align-items: center; gap: 10px; justify-content: center;
            margin-bottom: 10px;
        }
        .refresh-indicator {
            font-size: 0.75rem; color: #475569; display: flex; align-items: center; gap: 6px;
        }
        .refresh-spinner { display: none; width: 14px; height: 14px; border: 2px solid #475569; border-top: 2px solid #3b82f6; border-radius: 50%; animation: spin 1s linear infinite; }
        .refresh-spinner.active { display: inline-block; }
        @keyframes spin { to { transform: rotate(360deg); } }
        
        .calendar-wrapper { background: #1e293b; border-radius: 16px; padding: 20px; }
        
        .month-nav {
            display: flex; justify-content: space-between; align-items: center;
            margin-bottom: 20px; padding-bottom: 15px; border-bottom: 1px solid #334155;
        }
        .month-title { font-size: 1.3rem; font-weight: 600; }
        .nav-btn {
            background: #334155; border: none; color: white; padding: 8px 16px;
            border-radius: 6px; cursor: pointer; font-size: 0.9rem;
        }
        .nav-btn:hover { background: #475569; }
        
        .weekdays-header {
            display: grid; grid-template-columns: repeat(7, 1fr); gap: 8px;
            margin-bottom: 10px;
        }
        .weekday-label {
            text-align: center; font-weight: 600; color: #64748b;
            padding: 10px; font-size: 0.9rem;
        }
        
        .calendar-grid { display: grid; grid-template-columns: repeat(7, 1fr); gap: 8px; }
        
        .day-cell {
            background: #0f172a; border-radius: 10px; min-height: 180px;
            padding: 10px; cursor: pointer; transition: all 0.2s;
        }
        .day-cell:hover { background: #1e3a5f; transform: scale(1.02); }
        .day-cell.empty { background: transparent; min-height: auto; cursor: default; }
        .day-cell.empty:hover { transform: none; }
        .day-cell.today { border: 2px solid #F59E0B; }
        
        .day-number { font-size: 1.1rem; font-weight: 600; color: #64748b; margin-bottom: 8px; }
        .day-cell.today .day-number { color: #F59E0B; }
        
        .flights-list { display: flex; flex-direction: column; gap: 4px; }
        
        .flight-item {
            display: flex; align-items: center; gap: 6px; padding: 4px 6px;
            border-radius: 4px; font-size: 0.75rem;
            transition: all 0.15s; background: rgba(255,255,255,0.03);
        }
        .flight-item:hover { background: rgba(255,255,255,0.1); }
        .flight-item { position: relative; }
        .flight-tooltip {
            display: none; position: absolute; bottom: 100%; left: 50%; transform: translateX(-50%);
            background: #1e293b; border: 1px solid #475569; border-radius: 8px; padding: 8px 12px;
            font-size: 0.75rem; color: #e2e8f0; white-space: nowrap; z-index: 100;
            box-shadow: 0 4px 12px rgba(0,0,0,0.5); pointer-events: none;
        }
        .flight-item:hover .flight-tooltip { display: block; }
        .day-tooltip {
            display: none; position: absolute; bottom: 100%; left: 50%; transform: translateX(-50%);
            background: #0f172a; border: 1px solid #475569; border-radius: 10px; padding: 10px 14px;
            font-size: 0.75rem; color: #e2e8f0; z-index: 200; min-width: 180px;
            box-shadow: 0 4px 16px rgba(0,0,0,0.6); pointer-events: none;
        }
        .day-cell:hover .day-tooltip { display: block; }
        
        .flight-icon { width: 18px; height: 18px; border-radius: 3px; flex-shrink: 0; }
        .flight-time { color: #94a3b8; font-weight: 500; min-width: 38px; }
        .flight-route { color: #e2e8f0; flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
        
        /* Dias passados - menor destaque mas legivel */
        .day-cell.past .flight-item { opacity: 0.6; }
        .day-cell.past .flight-icon { opacity: 0.7; }
        .day-cell.past .flight-time { color: #64748b; }
        .day-cell.past .flight-route { color: #94a3b8; }
        .day-cell.past .day-number { color: #475569; }
        .day-cell.past { background: #0b1120; }
        
        .flight-ret-tag {
            background: #eab308; color: #000; font-size: 0.6rem; font-weight: 700;
            padding: 2px 5px; border-radius: 3px; flex-shrink: 0;
        }
        
        /* ===== MODAL DETALHES DO DIA ===== */
        .modal-overlay {
            position: fixed; top: 0; left: 0; width: 100%; height: 100%;
            background: rgba(0,0,0,0.9); z-index: 1000; display: none;
            overflow-y: auto; padding: 20px;
        }
        .modal-overlay.active { display: block; }
        
        .modal-container {
            max-width: 1400px; margin: 0 auto; background: #1e293b;
            border-radius: 16px; overflow: hidden;
        }
        
        .modal-header {
            display: flex; justify-content: space-between; align-items: center;
            padding: 20px 30px; background: #0f172a; border-bottom: 2px solid #334155;
        }
        .modal-title { font-size: 1.5rem; font-weight: 700; }
        .modal-subtitle { color: #94a3b8; font-size: 0.9rem; margin-top: 4px; }
        .modal-close {
            background: #ef4444; border: none; color: white; width: 40px; height: 40px;
            border-radius: 50%; cursor: pointer; font-size: 1.5rem;
            display: flex; align-items: center; justify-content: center;
        }
        .modal-close:hover { background: #dc2626; }
        
        .modal-legend {
            display: flex; gap: 30px; padding: 15px 30px; background: #162032;
            border-bottom: 1px solid #334155;
        }
        .modal-legend-item { display: flex; align-items: center; gap: 8px; font-size: 0.85rem; }
        .modal-legend-color { width: 40px; height: 20px; border-radius: 4px; }
        .modal-legend-color.voo { background: #dc2626; }
        .modal-legend-color.retorno { background: #eab308; }
        
        .modal-body { padding: 20px 30px; }
        
        /* Timeline Header - 1 linha por aeronave */
        .timeline-header {
            display: flex; margin-bottom: 10px; padding-left: 140px;
            border-bottom: 1px solid #334155; padding-bottom: 10px;
        }
        .timeline-hours {
            display: flex; flex: 1; justify-content: space-between;
        }
        .timeline-hour { font-size: 0.75rem; color: #64748b; width: 50px; text-align: center; }
        
        /* Gantt Row - 1 aeronave por linha */
        .gantt-row {
            display: flex; margin-bottom: 6px; min-height: 48px;
            background: #0f172a; border-radius: 10px; overflow: visible;
            align-items: stretch;
        }
        
        .gantt-info {
            width: 140px; min-width: 140px; padding: 12px 16px;
            border-right: 2px solid #334155; font-size: 0.85rem;
            display: flex; align-items: center; gap: 10px;
        }
        .gantt-info-icon { width: 44px; height: 44px; border-radius: 8px; flex-shrink: 0; }
        .gantt-info-ref { font-weight: 700; font-size: 1.1rem; }
        
        .gantt-timeline {
            flex: 1; position: relative; min-height: 48px; padding: 0;
        }
        
        .gantt-bar {
            position: absolute; top: 4px; height: calc(100% - 8px);
            border-radius: 5px; display: flex; flex-direction: row;
            align-items: center; justify-content: center; padding: 2px 6px; gap: 4px;
            font-size: 0.72rem; font-weight: 600; z-index: 2; overflow: hidden;
            box-shadow: 0 2px 8px rgba(0,0,0,0.35); text-align: center;
            white-space: nowrap; text-overflow: ellipsis; cursor: pointer;
        }
        .gantt-bar.voo { color: white; z-index: 3; }
        .gantt-bar.retorno { background: #eab308; color: #000; z-index: 2; }
        .gantt-bar-route { font-weight: 700; overflow: hidden; text-overflow: ellipsis; }
        .gantt-bar-pax { font-size: 0.65rem; opacity: 0.95; }
        .gantt-bar-popup {
            display: none; position: fixed; z-index: 9999;
            min-width: 300px; max-width: 380px; padding: 18px 20px;
            background: #0f172a; border: 2px solid #475569;
            border-radius: 12px; box-shadow: 0 12px 40px rgba(0,0,0,0.7);
            font-size: 1rem; line-height: 1.65; color: #e2e8f0;
            pointer-events: none; white-space: normal; text-align: left;
        }
        /* Popup visibilidade controlada por JS */
        .gantt-bar-popup-title { font-size: 1.15rem; font-weight: 700; margin-bottom: 12px; padding-bottom: 10px; border-bottom: 2px solid #334155; }
        .gantt-bar-popup-row { margin-bottom: 8px; display: flex; gap: 10px; font-size: 0.95rem; }
        .gantt-bar-popup-label { color: #94a3b8; min-width: 95px; flex-shrink: 0; }
        .gantt-bar-popup-value { font-weight: 600; }
        .gantt-bar-popup-rota { margin-top: 8px; padding-top: 8px; border-top: 1px dashed #334155; font-size: 0.9rem; }
        
        .gantt-grid-lines {
            position: absolute; top: 0; left: 0; right: 0; bottom: 0;
            display: flex; z-index: 1;
        }
        .gantt-grid-line {
            flex: 1; border-right: 1px dashed #334155;
        }
        
        .no-flights {
            text-align: center; padding: 50px; color: #64748b; font-size: 1.1rem;
        }
        
        @media (max-width: 1200px) {
            .stats-grid { grid-template-columns: repeat(3, 1fr); }
            .gantt-info { width: 120px; min-width: 120px; }
            .timeline-header { padding-left: 120px; }
        }
        @media (max-width: 768px) {
            .stats-grid { grid-template-columns: repeat(2, 1fr); }
            .calendar-grid { grid-template-columns: repeat(2, 1fr); }
        }
        
        /* ===== MAPA DE VOOS ===== */
        .map-section {
            margin-top: 25px; background: #1e293b; border-radius: 16px;
            padding: 20px; border: 1px solid #334155;
        }
        .map-section-title {
            font-size: 1.2rem; font-weight: 700; margin-bottom: 15px;
            display: flex; align-items: center; gap: 15px; flex-wrap: wrap;
        }
        .map-day-selector {
            display: flex; gap: 8px; align-items: center;
        }
        .map-day-btn {
            background: #334155; border: 2px solid #475569; color: #e2e8f0;
            padding: 6px 14px; border-radius: 8px; cursor: pointer; font-size: 0.85rem;
        }
        .map-day-btn:hover { background: #475569; }
        .map-day-btn.active { background: #1e40af; border-color: #3b82f6; }
        #flight-map { height: 480px; border-radius: 12px; background: #0f172a; }
        .leaflet-container { font-family: inherit; }
        .arrow-icon { background: none !important; border: none !important; }
    </style>
</head>
<body>
    <div class="container" id="main-container">
        <div class="header">Atualizado em {{ data_atualizacao }} · Layout v2 (pop-up nos blocos)</div>
        
        <div class="legend">
            {% for prefixo, info in helicopteros.items() %}
            <div class="legend-item">
                <img class="legend-icon" src="{{ icons[prefixo] }}" alt="{{ prefixo }}">
                <span style="color: {{ info.cor }}; font-weight: 600;">{{ prefixo }}</span>
                <span style="color: #64748b;">({{ info.modelo }})</span>
            </div>
            {% endfor %}
            <div class="legend-item retorno">
                <div class="legend-icon" style="background: #eab308; border-radius: 4px;"></div>
                <span style="color: #eab308;">Retorno (Empty Leg)</span>
            </div>
        </div>
        
        <div class="stats-grid">
            <div class="stat-card">
                <div class="stat-number" style="color: #e2e8f0;">{{ stats.total_voos }}</div>
                <div class="stat-label">Voos Programados</div>
            </div>
            <div class="stat-card">
                <div class="stat-number" style="color: #eab308;">{{ stats.total_retornos }}</div>
                <div class="stat-label">Retornos Estimados</div>
            </div>
            <div class="stat-card">
                <div class="stat-number" style="color: #38bdf8;">{{ "%.1f"|format(stats.total_horas) }}h</div>
                <div class="stat-label">Horas de Voo</div>
            </div>
            <div class="stat-card blue">
                <div class="stat-number">{{ stats.por_aeronave['PR-OMB'] }}</div>
                <div class="stat-label">PR-OMB</div>
            </div>
            <div class="stat-card green">
                <div class="stat-number">{{ stats.por_aeronave['PR-OMH'] }}</div>
                <div class="stat-label">PR-OMH</div>
            </div>
            <div class="stat-card orange">
                <div class="stat-number">{{ stats.por_aeronave['PR-OOE'] }}</div>
                <div class="stat-label">PR-OOE</div>
            </div>
            <div class="stat-card">
                <div class="stat-number" style="color: #a78bfa;">{{ stats.total_shuttle }}<span style="color:#64748b;font-size:1.2rem;"> / </span><span style="color:#60a5fa;">{{ stats.total_charter }}</span></div>
                <div class="stat-label">Shuttle / Charter</div>
            </div>
        </div>
        
        <!-- Proximos Voos -->
        <div class="next-flights" id="next-flights-panel">
            <div class="next-flights-title"><span class="pulse"></span> Proximos Voos</div>
            <div class="next-flights-grid" id="next-flights-grid"></div>
        </div>
        
        <!-- Filtros -->
        <div class="filters-bar" id="filters-bar">
            <span class="filter-label">Filtrar:</span>
            <button class="filter-btn active" data-filter="all" onclick="toggleFilter('all')">Todos</button>
            <div class="filter-separator"></div>
            <button class="filter-btn" data-filter="PR-OMB" onclick="toggleFilter('PR-OMB')" style="border-color:#3B82F6;">PR-OMB</button>
            <button class="filter-btn" data-filter="PR-OMH" onclick="toggleFilter('PR-OMH')" style="border-color:#10B981;">PR-OMH</button>
            <button class="filter-btn" data-filter="PR-OOE" onclick="toggleFilter('PR-OOE')" style="border-color:#F59E0B;">PR-OOE</button>
            <div class="filter-separator"></div>
            <button class="filter-btn" data-filter="shuttle" onclick="toggleFilter('shuttle')" style="border-color:#7c3aed;">Shuttle</button>
            <button class="filter-btn" data-filter="fullcabin" onclick="toggleFilter('fullcabin')" style="border-color:#0891b2;">Full Cabin</button>
            <button class="filter-btn" data-filter="charter" onclick="toggleFilter('charter')" style="border-color:#2563eb;">Charter</button>
        </div>
        
        <!-- Refresh bar -->
        <div class="refresh-bar">
            <div class="refresh-indicator">
                <div class="refresh-spinner" id="refresh-spinner"></div>
                <span id="refresh-text">Atualizado em {{ data_atualizacao }}</span>
            </div>
        </div>
        
        <div class="calendar-wrapper">
            <div class="month-nav">
                <button class="nav-btn" onclick="mudarMes(-1)">&larr; Anterior</button>
                <div style="display:flex;align-items:center;gap:12px;">
                    <div class="month-title" id="month-title"></div>
                    <button class="nav-btn" onclick="irParaHoje()" style="background:#F59E0B;color:#000;font-weight:600;">Hoje</button>
                </div>
                <button class="nav-btn" onclick="mudarMes(1)">Proximo &rarr;</button>
            </div>
            
            <div class="weekdays-header">
                <div class="weekday-label">Dom</div>
                <div class="weekday-label">Seg</div>
                <div class="weekday-label">Ter</div>
                <div class="weekday-label">Qua</div>
                <div class="weekday-label">Qui</div>
                <div class="weekday-label">Sex</div>
                <div class="weekday-label">Sab</div>
            </div>
            
            <div class="calendar-grid" id="calendar-grid"></div>
        </div>
        
        <!-- Mapa de Voos do Dia -->
        <div class="map-section">
            <div class="map-section-title">
                <span>Mapa de Voos</span>
                <div class="map-day-selector" id="map-day-selector"></div>
            </div>
            <div id="flight-map"></div>
            <div id="map-legend" style="display:flex;flex-wrap:wrap;gap:16px;margin-top:12px;padding:8px 4px;"></div>
        </div>
    </div>
    
    <!-- Modal de Detalhes do Dia -->
    <div class="modal-overlay" id="day-modal">
        <div class="modal-container">
            <div class="modal-header">
                <div style="display:flex;align-items:center;gap:15px;">
                    <button class="nav-btn" onclick="navegarDia(-1)" style="padding:8px 12px;" title="Dia anterior (←)">&larr;</button>
                    <div>
                        <div class="modal-title" id="modal-day-title"></div>
                        <div class="modal-subtitle" id="modal-day-subtitle"></div>
                    </div>
                    <button class="nav-btn" onclick="navegarDia(1)" style="padding:8px 12px;" title="Proximo dia (→)">&rarr;</button>
                </div>
                <button class="modal-close" onclick="fecharModal()">&times;</button>
            </div>
            
            <div class="modal-legend">
                <div class="modal-legend-item">
                    <div class="modal-legend-color" style="background:#2563eb;"></div>
                    <span>Charter</span>
                </div>
                <div class="modal-legend-item">
                    <div class="modal-legend-color" style="background:#0891b2;"></div>
                    <span>Full Cabin</span>
                </div>
                <div class="modal-legend-item">
                    <div class="modal-legend-color" style="background:#7c3aed;"></div>
                    <span>Shuttle Seat</span>
                </div>
                <div class="modal-legend-item">
                    <div class="modal-legend-color" style="background:#6d28d9;"></div>
                    <span>Shuttle Full Cabin</span>
                </div>
                <div class="modal-legend-item">
                    <div class="modal-legend-color retorno"></div>
                    <span>Retorno / Empty Leg</span>
                </div>
            </div>
            
            <div class="modal-body" id="modal-body"></div>
        </div>
    </div>
    
    <div id="gantt-popup-global" class="gantt-bar-popup" style="display:none;"></div>
    
    <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
    <script>
        let voosPorDia = {{ voos_json|safe }};
        const helicopteros = {{ helicopteros_json|safe }};
        const helipontos = {{ helipontos_json|safe }};
        const icons = {{ icons_json|safe }};
        const ROTAER_URL = {{ rotaer_url|tojson }};
        const ROTAER_PAGE = {{ rotaer_page|tojson }};
        
        const TIPO_CORES = {
            'shuttleseat':     {cor: '#7c3aed', label: 'Shuttle Seat',      badge: 'SHUTTLE SEAT'},
            'shuttlefullcabin':{cor: '#6d28d9', label: 'Shuttle Full Cabin',badge: 'SHUTTLE FC'},
            'fullcabin':       {cor: '#0891b2', label: 'Full Cabin',        badge: 'FULL CABIN'},
            'charter':         {cor: '#2563eb', label: 'Charter',           badge: 'CHARTER'}
        };
        function tipoInfo(tipo) {
            const k = (tipo || '').toLowerCase().replace(/[\s_-]/g, '');
            return TIPO_CORES[k] || TIPO_CORES['charter'];
        }
        
        let mesAtual = new Date().getMonth();
        let anoAtual = new Date().getFullYear();
        const hoje = new Date();
        let activeFilter = 'all';
        let currentModalDate = null;
        
        const mesesNome = ['Janeiro', 'Fevereiro', 'Marco', 'Abril', 'Maio', 'Junho',
                          'Julho', 'Agosto', 'Setembro', 'Outubro', 'Novembro', 'Dezembro'];
        
        const diasSemana = ['Domingo', 'Segunda-feira', 'Terca-feira', 'Quarta-feira', 
                           'Quinta-feira', 'Sexta-feira', 'Sabado'];
        
        // ===== FILTROS =====
        function matchesFilter(voo) {
            if (activeFilter === 'all') return true;
            const t = (voo.tipo || '').toLowerCase().replace(/[\s_-]/g, '');
            if (activeFilter === 'shuttle') return t.includes('shuttle');
            if (activeFilter === 'fullcabin') return t.includes('fullcabin');
            if (activeFilter === 'charter') return t === 'charter' || t === '';
            return voo.prefixo === activeFilter;
        }
        
        function toggleFilter(filter) {
            activeFilter = filter;
            document.querySelectorAll('.filter-btn').forEach(b => {
                b.classList.remove('active', 'active-blue', 'active-green', 'active-orange', 'active-purple', 'active-teal');
            });
            const btn = document.querySelector(`[data-filter="${filter}"]`);
            if (filter === 'PR-OMB') btn.classList.add('active-blue');
            else if (filter === 'PR-OMH') btn.classList.add('active-green');
            else if (filter === 'PR-OOE') btn.classList.add('active-orange');
            else if (filter === 'shuttle') btn.classList.add('active-purple');
            else if (filter === 'fullcabin') btn.classList.add('active-teal');
            else if (filter === 'charter') btn.classList.add('active-blue');
            else btn.classList.add('active');
            renderCalendario();
            renderProximosVoos();
            if (currentModalDate) abrirModal(currentModalDate);
        }
        
        // ===== PROXIMOS VOOS =====
        function renderProximosVoos() {
            const grid = document.getElementById('next-flights-grid');
            const now = new Date();
            const allVoos = [];
            
            Object.entries(voosPorDia).forEach(([data, voos]) => {
                voos.filter(v => !v.is_retorno && matchesFilter(v)).forEach(v => {
                    const dt = new Date(v.inicio);
                    if (dt >= new Date(now.getFullYear(), now.getMonth(), now.getDate())) {
                        allVoos.push({...v, _date: data, _dt: dt});
                    }
                });
            });
            
            allVoos.sort((a, b) => a._dt - b._dt);
            const proximos = allVoos.slice(0, 8);
            
            if (proximos.length === 0) {
                grid.innerHTML = '<div style="color:#64748b;padding:20px;">Nenhum voo futuro encontrado</div>';
                return;
            }
            
            grid.innerHTML = proximos.map(voo => {
                const cor = helicopteros[voo.prefixo]?.cor || '#666';
                const hora = voo._dt.toTimeString().slice(0, 5);
                const dataObj = voo._dt;
                const isHoje = dataObj.toDateString() === now.toDateString();
                const amanha = new Date(now); amanha.setDate(amanha.getDate() + 1);
                const isAmanha = dataObj.toDateString() === amanha.toDateString();
                const dataLabel = isHoje ? 'HOJE' : isAmanha ? 'AMANHA' : `${dataObj.getDate()}/${dataObj.getMonth()+1}`;
                const tiNf = tipoInfo(voo.tipo);
                const badge = `<span class="nf-badge" style="background:${tiNf.cor};color:#fff;">${tiNf.badge}</span>`;
                
                return `
                <div class="nf-card" style="border-left-color:${cor};" onclick="abrirModal('${voo._date}')">
                    <div class="nf-header">
                        <span class="nf-prefix" style="color:${cor};">${voo.prefixo}</span>
                        <span class="nf-date" style="${isHoje ? 'color:#22c55e;font-weight:700;' : ''}">${dataLabel}</span>
                    </div>
                    <div class="nf-route">${voo.origem_nome} → ${voo.destino_nome}</div>
                    <div class="nf-time">${hora} · ${voo.duracao_min}min · ${voo.passageiros} pax ${badge}</div>
                </div>`;
            }).join('');
        }
        
        // ===== CALENDARIO =====
        function renderCalendario() {
            const grid = document.getElementById('calendar-grid');
            const titulo = document.getElementById('month-title');
            
            titulo.textContent = `${mesesNome[mesAtual]} ${anoAtual}`;
            
            const primeiroDia = new Date(anoAtual, mesAtual, 1);
            const ultimoDia = new Date(anoAtual, mesAtual + 1, 0);
            const diasNoMes = ultimoDia.getDate();
            const diaInicio = primeiroDia.getDay();
            
            let html = '';
            
            for (let i = 0; i < diaInicio; i++) {
                html += '<div class="day-cell empty"></div>';
            }
            
            for (let dia = 1; dia <= diasNoMes; dia++) {
                const dataStr = `${anoAtual}-${String(mesAtual + 1).padStart(2, '0')}-${String(dia).padStart(2, '0')}`;
                const voosDia = (voosPorDia[dataStr] || []).filter(v => matchesFilter(v));
                
                const isHoje = (dia === hoje.getDate() && mesAtual === hoje.getMonth() && anoAtual === hoje.getFullYear());
                const dataCell = new Date(anoAtual, mesAtual, dia);
                const isPast = dataCell < new Date(hoje.getFullYear(), hoje.getMonth(), hoje.getDate());
                const classeHoje = isHoje ? ' today' : '';
                const classePast = isPast ? ' past' : '';
                
                html += `<div class="day-cell${classeHoje}${classePast}" onclick="abrirModal('${dataStr}')" style="position:relative;">`;
                html += `<div class="day-number">${dia}</div>`;
                html += '<div class="flights-list">';
                
                const mergedDia = agruparPorMissao(voosDia);
                const voosReais = mergedDia.filter(v => !v.is_retorno);
                
                voosReais.slice(0, 6).forEach(voo => {
                    const icon = icons[voo.prefixo] || '';
                    const inicio = new Date(voo.inicio);
                    const hora = inicio.toTimeString().slice(0, 5);
                    const rotaLabel = voo._rotaFull || `${voo.origem}-${voo.destino}`;
                    const durMin = voo.duracao_min;
                    const tiCal = tipoInfo(voo.tipo);
                    
                    html += `
                    <div class="flight-item" style="border-left: 3px solid ${tiCal.cor};">
                        <img class="flight-icon" src="${icon}" alt="${voo.prefixo}">
                        <span class="flight-time">${hora}</span>
                        <span class="flight-route">${rotaLabel}</span>
                        <div class="flight-tooltip">
                            <strong>${voo.prefixo}</strong> · <span style="color:${tiCal.cor};font-weight:600;">${tiCal.badge}</span><br>
                            ${voo.origem_nome} → ${voo.destino_nome}<br>
                            ${hora} - ${durMin}min · ${voo.passageiros || 0} pax
                            ${voo._numLegs > 1 ? '<br><span style="color:#94a3b8;">' + voo._numLegs + ' trechos</span>' : ''}
                            ${voo.retorno_info ? '<br><span style="color:#eab308;">+ Retorno estimado</span>' : ''}
                        </div>
                    </div>`;
                });
                
                if (voosReais.length > 6) {
                    html += `<div style="text-align:center;color:#64748b;font-size:0.7rem;">+${voosReais.length - 6} mais</div>`;
                }
                
                if (voosReais.length > 0) {
                    const aeronaves = {};
                    voosReais.forEach(v => {
                        if (!aeronaves[v.prefixo]) aeronaves[v.prefixo] = 0;
                        aeronaves[v.prefixo]++;
                    });
                    let snap = `<div class="day-tooltip"><strong>${voosReais.length} missao(oes)</strong><br>`;
                    Object.entries(aeronaves).forEach(([pref, count]) => {
                        const cor = helicopteros[pref]?.cor || '#fff';
                        snap += `<span style="color:${cor};">${pref}: ${count}</span><br>`;
                    });
                    snap += '</div>';
                    html += snap;
                }
                
                html += '</div></div>';
            }
            
            grid.innerHTML = html;
        }
        
        function agruparPorMissao(voosDia) {
            const grupos = {};
            const retornos = [];
            voosDia.forEach(v => {
                if (v.is_retorno) { retornos.push(v); return; }
                const chave = v.name || v.inicio;
                if (!grupos[chave]) grupos[chave] = [];
                grupos[chave].push(v);
            });
            const merged = [];
            Object.values(grupos).forEach(legs => {
                legs.sort((a, b) => new Date(a.inicio) - new Date(b.inicio));
                const first = legs[0];
                const last = legs[legs.length - 1];
                const iniDt = new Date(first.inicio);
                const fimDt = new Date(last.fim);
                const icaos = [legs[0].origem];
                legs.forEach(l => icaos.push(l.destino));
                const rotaFull = icaos.join('-');
                const paxTotal = legs.reduce((s, l) => s + (l.passageiros || 0), 0);
                const durTotal = Math.round((fimDt - iniDt) / 60000);
                const trechosList = legs.map(l => `${l.origem_nome} → ${l.destino_nome}`);
                merged.push({
                    ...first,
                    inicio: first.inicio,
                    fim: last.fim,
                    origem: first.origem,
                    destino: last.destino,
                    origem_nome: first.origem_nome,
                    destino_nome: last.destino_nome,
                    passageiros: paxTotal,
                    duracao_min: durTotal,
                    _rotaFull: rotaFull,
                    _trechosList: trechosList,
                    _numLegs: legs.length,
                    retorno_info: last.retorno_info
                });
            });
            retornos.forEach(r => {
                const chaveRet = Object.keys(grupos).find(k => {
                    const legs = grupos[k];
                    return legs[0].prefixo === r.prefixo && Math.abs(new Date(legs[legs.length-1].fim) - new Date(r.inicio)) < 1800000;
                });
                if (chaveRet) {
                    const m = merged.find(x => x.name === chaveRet || x.inicio === chaveRet);
                    if (m && !m.retorno_info) m.retorno_info = r.retorno_info || {
                        inicio: r.inicio, fim: r.fim, duracao_min: r.duracao_min,
                        origem: r.origem, destino: r.destino,
                        origem_nome: r.origem_nome, destino_nome: r.destino_nome
                    };
                } else {
                    merged.push(r);
                }
            });
            return merged;
        }
        
        function mudarMes(delta) {
            mesAtual += delta;
            if (mesAtual > 11) { mesAtual = 0; anoAtual++; }
            if (mesAtual < 0) { mesAtual = 11; anoAtual--; }
            renderCalendario();
        }
        
        function irParaHoje() {
            mesAtual = hoje.getMonth();
            anoAtual = hoje.getFullYear();
            renderCalendario();
        }
        
        // ===== MODAL COM NAVEGACAO =====
        function abrirModal(dataStr) {
            currentModalDate = dataStr;
            const voos = (voosPorDia[dataStr] || []).filter(v => matchesFilter(v));
            const modal = document.getElementById('day-modal');
            const titulo = document.getElementById('modal-day-title');
            const subtitulo = document.getElementById('modal-day-subtitle');
            const body = document.getElementById('modal-body');
            
            const dataObj = new Date(dataStr + 'T12:00:00');
            const diaSemana = diasSemana[dataObj.getDay()];
            const diaNum = dataObj.getDate();
            const mesNome = mesesNome[dataObj.getMonth()];
            const ano = dataObj.getFullYear();
            
            const mergedVoos = agruparPorMissao(voos);
            const voosReais = mergedVoos.filter(v => !v.is_retorno);
            titulo.textContent = `${diaSemana}, ${diaNum} de ${mesNome} de ${ano}`;
            subtitulo.textContent = `${voosReais.length} missao(oes) · 3 aeronaves`;
            
            {
                const AERONAVES = ['PR-OMB', 'PR-OMH', 'PR-OOE'];
                let html = '';
                
                html += '<div class="timeline-header"><div class="timeline-hours">';
                for (let h = 5; h <= 23; h++) {
                    html += `<div class="timeline-hour">${String(h).padStart(2, '0')}:00</div>`;
                }
                html += '</div></div>';
                
                AERONAVES.forEach(prefixo => {
                    const cor = helicopteros[prefixo]?.cor || '#666';
                    const icon = icons[prefixo] || '';
                    const voosAeronave = mergedVoos.filter(v => v.prefixo === prefixo);
                    
                    const blocks = [];
                    voosAeronave.forEach(voo => {
                        if (voo.is_retorno) return;
                        const iniVoo = new Date(voo.inicio);
                        const fimVoo = new Date(voo.fim);
                        const horaIni = iniVoo.toTimeString().slice(0, 5);
                        const horaFim = fimVoo.toTimeString().slice(0, 5);
                        const ti = tipoInfo(voo.tipo);
                        const rotaLabel = voo._rotaFull || (voo.origem + '-' + voo.destino);
                        blocks.push({
                            inicio: iniVoo, fim: fimVoo,
                            rota: rotaLabel,
                            origem: voo.origem, destino: voo.destino,
                            origemNome: voo.origem_nome || voo.origem,
                            destinoNome: voo.destino_nome || voo.destino,
                            pax: voo.passageiros || 0,
                            isRetorno: false, corAeronave: cor, corTipo: ti.cor,
                            name: voo.name || '', tipo: ti.label, tipoBadge: ti.badge, tipoRaw: voo.tipo,
                            isPago: voo.is_pago, duracaoMin: voo.duracao_min,
                            horaInicio: horaIni, horaFim: horaFim,
                            fonte: voo.fonte || 'voo',
                            _trechosList: voo._trechosList || [`${voo.origem_nome} → ${voo.destino_nome}`],
                            _numLegs: voo._numLegs || 1
                        });
                        const parentIdx = blocks.length - 1;
                        if (voo.retorno_info) {
                            const ret = voo.retorno_info;
                            blocks.push({
                                inicio: new Date(ret.inicio), fim: new Date(ret.fim),
                                rota: ret.origem + '-' + ret.destino,
                                origem: ret.origem, destino: ret.destino,
                                origemNome: ret.origem_nome || ret.origem,
                                destinoNome: ret.destino_nome || ret.destino,
                                pax: 0, isRetorno: true, corAeronave: cor,
                                duracaoMin: ret.duracao_min,
                                horaInicio: new Date(ret.inicio).toTimeString().slice(0, 5),
                                horaFim: new Date(ret.fim).toTimeString().slice(0, 5),
                                fonte: 'voo',
                                _parentIdx: parentIdx
                            });
                        }
                    });
                    // Guardar indice original antes de ordenar
                    blocks.forEach((bl, i) => bl._origIdx = i);
                    blocks.sort((a, b) => a.inicio - b.inicio);
                    
                    // Detectar sobreposicoes e atribuir lanes (retorno herda lane do pai)
                    const laneEnds = [];
                    const origLaneMap = {};
                    blocks.forEach(bl => {
                        if (bl.isRetorno && bl._parentIdx !== undefined && origLaneMap[bl._parentIdx] !== undefined) {
                            bl._lane = origLaneMap[bl._parentIdx];
                            laneEnds[bl._lane] = Math.max(laneEnds[bl._lane] || 0, bl.fim.getTime());
                        } else {
                            const s = bl.inicio.getTime();
                            const e = bl.fim.getTime();
                            let lane = 0;
                            for (lane = 0; lane < laneEnds.length; lane++) {
                                if (s >= (laneEnds[lane] || 0)) break;
                            }
                            bl._lane = lane;
                            laneEnds[lane] = e;
                        }
                        origLaneMap[bl._origIdx] = bl._lane;
                    });
                    const maxLanes = Math.max(1, laneEnds.length);
                    const rowH = maxLanes > 1 ? (maxLanes * 28 + 8) : 48;
                    
                    let barsHtml = '<div class="gantt-grid-lines">' + Array(18).fill('<div class="gantt-grid-line"></div>').join('') + '</div>';
                    blocks.forEach(bl => {
                        const startHour = bl.inicio.getHours() + bl.inicio.getMinutes() / 60;
                        const endHour = bl.fim.getHours() + bl.fim.getMinutes() / 60;
                        const leftPercent = Math.max(0, ((startHour - 5) / 18) * 100);
                        const endPercent = Math.min(100, ((endHour - 5) / 18) * 100);
                        const width = Math.max(endPercent - leftPercent, 2);
                        const barClass = bl.isRetorno ? 'retorno' : 'voo';
                        const barBg = bl.isRetorno ? '' : `background: ${bl.corTipo}; border-left: 3px solid ${cor};`;
                        const laneTop = maxLanes > 1 ? (4 + bl._lane * 28) : 4;
                        const laneH = maxLanes > 1 ? 24 : 'calc(100% - 8px)';
                        const barStyle = `left: ${leftPercent}%; width: ${width}%; top: ${laneTop}px; height: ${typeof laneH === 'number' ? laneH + 'px' : laneH}; ${barBg}`;
                        const paxText = bl.isRetorno ? 'RET' : (bl.pax + ' pax');
                        const linkIfUnknown = (cod, nome) => helipontos[cod] ? nome : `<a href="${ROTAER_URL}${cod}" target="_blank" rel="noopener" title="Consultar no ROTAER (AISWEB)">${nome}</a>`;
                        const origLink = linkIfUnknown(bl.origem, bl.origemNome);
                        const destLink = linkIfUnknown(bl.destino, bl.destinoNome);
                        const hasUnknown = !helipontos[bl.origem] || !helipontos[bl.destino];
                        const rotaerHint = hasUnknown ? `<div class="gantt-bar-popup-row"><span class="gantt-bar-popup-label"></span><span class="gantt-bar-popup-value" style="font-size:0.8rem;color:#94a3b8;"><a href="${ROTAER_PAGE}" target="_blank" rel="noopener">ROTAER (AISWEB)</a></span></div>` : '';
                        let popupHtml = '';
                        if (bl.isRetorno) {
                            popupHtml = `<div class="gantt-bar-popup">
                                <div class="gantt-bar-popup-title" style="color:#eab308;">Retorno (Empty Leg)</div>
                                <div class="gantt-bar-popup-row"><span class="gantt-bar-popup-label">Rota:</span><span class="gantt-bar-popup-value">${origLink} → ${destLink}</span></div>
                                <div class="gantt-bar-popup-row"><span class="gantt-bar-popup-label">Horário:</span><span class="gantt-bar-popup-value">${bl.horaInicio} - ${bl.horaFim}</span></div>
                                <div class="gantt-bar-popup-row"><span class="gantt-bar-popup-label">Duração:</span><span class="gantt-bar-popup-value">${bl.duracaoMin} min</span></div>
                                ${rotaerHint}
                            </div>`;
                        } else {
                            const statusText = bl.isPago ? 'PAGO' : 'Pgto. pendente';
                            const tipoBadgeHtml = `<span style="display:inline-block;background:${bl.corTipo};color:#fff;font-size:0.7rem;font-weight:700;padding:2px 8px;border-radius:4px;">${bl.tipoBadge}</span>`;
                            const trechosHtml = (bl._trechosList || []).map(t => `<div style="font-size:0.85rem;color:#cbd5e1;padding-left:10px;">• ${t}</div>`).join('');
                            popupHtml = `<div class="gantt-bar-popup" style="border-left:4px solid ${bl.corTipo};">
                                <div class="gantt-bar-popup-title" style="color:${cor};">${bl.rota} <span style="float:right;">${tipoBadgeHtml}</span></div>
                                <div class="gantt-bar-popup-row"><span class="gantt-bar-popup-label">Horário:</span><span class="gantt-bar-popup-value">${bl.horaInicio} - ${bl.horaFim}</span></div>
                                <div class="gantt-bar-popup-row"><span class="gantt-bar-popup-label">Duração:</span><span class="gantt-bar-popup-value">${bl.duracaoMin} min</span></div>
                                <div class="gantt-bar-popup-row"><span class="gantt-bar-popup-label">Passageiros:</span><span class="gantt-bar-popup-value">${bl.pax} pax</span></div>
                                ${bl._numLegs > 1 ? '<div class="gantt-bar-popup-row"><span class="gantt-bar-popup-label">Pernas:</span><span class="gantt-bar-popup-value">' + bl._numLegs + ' trechos</span></div>' : ''}
                                ${bl._numLegs > 1 ? '<div style="margin:6px 0 4px;">' + trechosHtml + '</div>' : ''}
                                <div class="gantt-bar-popup-row"><span class="gantt-bar-popup-label">Tipo:</span><span class="gantt-bar-popup-value">${bl.tipo}</span></div>
                                <div class="gantt-bar-popup-row"><span class="gantt-bar-popup-label">Status:</span><span class="gantt-bar-popup-value">${statusText}</span></div>
                                ${bl.name ? '<div class="gantt-bar-popup-row"><span class="gantt-bar-popup-label">Ref:</span><span class="gantt-bar-popup-value">' + bl.name + '</span></div>' : ''}
                                ${bl.fonte === 'trecho' ? '<div class="gantt-bar-popup-row"><span class="gantt-bar-popup-label"></span><span class="gantt-bar-popup-value" style="font-size:0.75rem;color:#10b981;">Dados do Trecho (cadastrado)</span></div>' : ''}
                                ${rotaerHint}
                            </div>`;
                        }
                        barsHtml += `<div class="gantt-bar ${barClass}" style="${barStyle}">
                            <span class="gantt-bar-route">${bl.rota}</span>
                            <span class="gantt-bar-pax">${paxText}</span>
                            ${popupHtml}
                        </div>`;
                    });
                    
                    html += `
                    <div class="gantt-row" style="height:${rowH}px;">
                        <div class="gantt-info">
                            <img class="gantt-info-icon" src="${icon}" alt="${prefixo}">
                            <span class="gantt-info-ref" style="color: ${cor};">${prefixo}</span>
                        </div>
                        <div class="gantt-timeline" style="height:${rowH}px;">${barsHtml}</div>
                    </div>`;
                });
                
                body.innerHTML = html;
                
                const globalPopup = document.getElementById('gantt-popup-global');
                document.querySelectorAll('.gantt-bar').forEach(bar => {
                    const popup = bar.querySelector('.gantt-bar-popup');
                    if (!popup) return;
                    bar.addEventListener('mouseenter', function() {
                        globalPopup.innerHTML = popup.innerHTML;
                        globalPopup.style.display = 'block';
                        globalPopup.style.borderLeft = popup.style.borderLeft || '';
                        const barRect = bar.getBoundingClientRect();
                        let left = barRect.right + 12;
                        let top = barRect.top + 8;
                        if (left + 380 > window.innerWidth) left = barRect.left - 380 - 12;
                        if (top < 10) top = 10;
                        if (top + 200 > window.innerHeight - 10) top = window.innerHeight - 220;
                        globalPopup.style.left = left + 'px';
                        globalPopup.style.top = top + 'px';
                    });
                    bar.addEventListener('mouseleave', function() {
                        globalPopup.style.display = 'none';
                    });
                });
            }
            
            modal.classList.add('active');
            document.body.style.overflow = 'hidden';
        }
        
        function navegarDia(delta) {
            if (!currentModalDate) return;
            const d = new Date(currentModalDate + 'T12:00:00');
            d.setDate(d.getDate() + delta);
            const newDate = `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}-${String(d.getDate()).padStart(2,'0')}`;
            abrirModal(newDate);
        }
        
        function fecharModal() {
            document.getElementById('day-modal').classList.remove('active');
            document.body.style.overflow = '';
            currentModalDate = null;
        }
        
        document.getElementById('day-modal').addEventListener('click', function(e) {
            if (e.target === this) fecharModal();
        });
        
        document.addEventListener('keydown', function(e) {
            if (e.key === 'Escape') fecharModal();
            if (currentModalDate) {
                if (e.key === 'ArrowLeft') navegarDia(-1);
                if (e.key === 'ArrowRight') navegarDia(1);
            }
        });
        
        // ===== AUTO-REFRESH =====
        async function autoRefresh() {
            try {
                const spinner = document.getElementById('refresh-spinner');
                const text = document.getElementById('refresh-text');
                spinner.classList.add('active');
                
                const resp = await fetch('/api/voos');
                if (resp.ok) {
                    const data = await resp.json();
                    voosPorDia = data.voos;
                    renderCalendario();
                    renderProximosVoos();
                    renderMapDaySelector();
                    if (flightMap && mapSelectedDate) renderMapaVoos(mapSelectedDate);
                    text.textContent = `Atualizado em ${data.atualizado_em}`;
                }
                spinner.classList.remove('active');
            } catch(e) {
                document.getElementById('refresh-spinner').classList.remove('active');
            }
        }
        
        // Refresh a cada 2 min
        setInterval(autoRefresh, 120000);
        
        // ===== MAPA DE VOOS =====
        let flightMap = null;
        let mapLayers = [];
        let mapSelectedDate = null;
        
        function offsetLatLng(lat, lon, dx, dy) {
            const earth = 6371000;
            const dLat = (dy / earth) * (180 / Math.PI);
            const dLon = (dx / (earth * Math.cos(lat * Math.PI / 180))) * (180 / Math.PI);
            return [lat + dLat, lon + dLon];
        }
        
        function perpendicularOffset(a, b, offsetMeters) {
            const midLat = (a[0] + b[0]) / 2;
            const midLon = (a[1] + b[1]) / 2;
            const bearing = Math.atan2(b[1] - a[1], (b[0] - a[0]) * Math.cos(midLat * Math.PI / 180));
            const perpBearing = bearing + Math.PI / 2;
            const dx = offsetMeters * Math.sin(perpBearing);
            const dy = offsetMeters * Math.cos(perpBearing);
            return [offsetLatLng(a[0], a[1], dx, dy), offsetLatLng(b[0], b[1], dx, dy)];
        }
        
        function createArrowIcon(color, bearingDeg) {
            return L.divIcon({
                html: `<div style="transform:rotate(${bearingDeg}deg);line-height:0"><svg width="14" height="14" viewBox="0 0 16 16"><polygon fill="${color}" stroke="#0f172a" stroke-width="1" points="2,3 16,8 2,13 6,8"/></svg></div>`,
                className: 'arrow-icon',
                iconSize: [14, 14],
                iconAnchor: [7, 7]
            });
        }
        
        function renderMapaVoos(dataStr) {
            if (!flightMap) return;
            mapLayers.forEach(l => flightMap.removeLayer(l));
            mapLayers = [];
            
            const voos = (voosPorDia[dataStr] || []).filter(v => !v.is_retorno && matchesFilter(v));
            const routeCount = {};
            const legs = [];
            
            function addLeg(origem, destino, vooRef, isRetorno) {
                const orig = helipontos[origem];
                const dest = helipontos[destino];
                if (!orig || !dest || origem === destino) return;
                const key = origem + '-' + destino;
                routeCount[key] = (routeCount[key] || 0) + 1;
                legs.push({ voo: vooRef, orig, dest, key, idx: routeCount[key] - 1, isRetorno });
            }
            
            voos.forEach(voo => {
                addLeg(voo.origem, voo.destino, voo, false);
                if (voo.retorno_info) {
                    addLeg(voo.retorno_info.origem, voo.retorno_info.destino, { ...voo, prefixo: voo.prefixo, origem_nome: voo.retorno_info.origem_nome, destino_nome: voo.retorno_info.destino_nome, passageiros: 0 }, true);
                }
            });
            
            const totalPerRoute = {};
            legs.forEach(l => { totalPerRoute[l.key] = (totalPerRoute[l.key] || 0) + 1; });
            
            const usedTipos = new Set();
            const usedAeronaves = new Set();
            legs.forEach(({ voo, orig, dest, idx, key, isRetorno }) => {
                const total = totalPerRoute[key];
                const offsetIdx = total > 1 ? (idx - (total - 1) / 2) : 0;
                const offsetM = offsetIdx * 180;
                
                let a = [orig.lat, orig.lon];
                let b = [dest.lat, dest.lon];
                if (offsetM !== 0) {
                    [a, b] = perpendicularOffset(a, b, offsetM);
                }
                
                const ti = tipoInfo(voo.tipo);
                const corAeronave = helicopteros[voo.prefixo]?.cor || '#666';
                const cor = isRetorno ? '#eab308' : ti.cor;
                const dashArray = isRetorno ? '8, 8' : null;
                const line = L.polyline([a, b], { color: cor, weight: 4, opacity: 0.9, dashArray: dashArray });
                line.addTo(flightMap);
                mapLayers.push(line);
                
                if (!isRetorno) { usedTipos.add(ti.label); usedAeronaves.add(voo.prefixo); }
                
                const tooltip = isRetorno 
                    ? `${voo.prefixo} RET: ${voo.origem_nome} → ${voo.destino_nome}` 
                    : `${voo.prefixo}: ${voo.origem_nome} → ${voo.destino_nome} (${voo.passageiros} pax) · ${ti.badge}`;
                line.bindTooltip(tooltip, { permanent: false, direction: 'top' });
                
                const bearing = Math.atan2(b[1] - a[1], (b[0] - a[0]) * Math.cos(b[0] * Math.PI / 180)) * 180 / Math.PI;
                const arrowIcon = createArrowIcon(cor, bearing);
                const arrow = L.marker(b, { icon: arrowIcon }).addTo(flightMap);
                mapLayers.push(arrow);
            });
            
            // Legenda do mapa
            const legendEl = document.getElementById('map-legend');
            let legHtml = '<span style="color:#94a3b8;font-size:0.8rem;font-weight:600;">TIPO:</span>';
            Object.values(TIPO_CORES).forEach(t => {
                const used = usedTipos.has(t.label);
                legHtml += `<div style="display:flex;align-items:center;gap:6px;opacity:${used ? 1 : 0.35};">
                    <div style="width:24px;height:4px;background:${t.cor};border-radius:2px;"></div>
                    <span style="font-size:0.78rem;color:#e2e8f0;">${t.label}</span>
                </div>`;
            });
            legHtml += `<div style="display:flex;align-items:center;gap:6px;">
                <div style="width:24px;height:4px;background:#eab308;border-radius:2px;border:1px dashed #eab308;"></div>
                <span style="font-size:0.78rem;color:#eab308;">Retorno</span>
            </div>`;
            legHtml += '<span style="color:#94a3b8;font-size:0.8rem;font-weight:600;margin-left:12px;">AERONAVE:</span>';
            ['PR-OMB','PR-OMH','PR-OOE'].forEach(p => {
                const c = helicopteros[p]?.cor || '#666';
                const used = usedAeronaves.has(p);
                legHtml += `<div style="display:flex;align-items:center;gap:6px;opacity:${used ? 1 : 0.35};">
                    <div style="width:10px;height:10px;border-radius:50%;background:${c};border:2px solid #fff;"></div>
                    <span style="font-size:0.78rem;color:${c};font-weight:600;">${p}</span>
                </div>`;
            });
            legHtml += `<div style="display:flex;align-items:center;gap:6px;">
                <div style="width:10px;height:10px;border-radius:50%;background:#22c55e;border:2px solid #fff;"></div>
                <span style="font-size:0.78rem;color:#e2e8f0;">Heliponto</span>
            </div>`;
            legendEl.innerHTML = legHtml;
            
            const usedHelipontos = new Set();
            voos.forEach(v => { usedHelipontos.add(v.origem); usedHelipontos.add(v.destino); });
            
            usedHelipontos.forEach(icao => {
                const h = helipontos[icao];
                if (!h) return;
                const marker = L.circleMarker([h.lat, h.lon], {
                    radius: 9,
                    fillColor: '#22c55e',
                    color: '#fff',
                    weight: 2,
                    fillOpacity: 0.95
                }).addTo(flightMap);
                marker.bindTooltip(`<strong>${icao}</strong><br>${h.nome}`, { permanent: false, direction: 'top' });
                mapLayers.push(marker);
            });
            
            const allLat = legs.flatMap(l => [l.orig.lat, l.dest.lat]);
            const allLon = legs.flatMap(l => [l.orig.lon, l.dest.lon]);
            if (allLat.length && allLon.length) {
                const bounds = L.latLngBounds(
                    [Math.min(...allLat) - 0.08, Math.min(...allLon) - 0.08],
                    [Math.max(...allLat) + 0.08, Math.max(...allLon) + 0.08]
                );
                flightMap.fitBounds(bounds, { padding: [40, 40], maxZoom: 11 });
            } else {
                flightMap.setView([-23.55, -46.64], 9);
            }
        }
        
        function renderMapDaySelector() {
            const sel = document.getElementById('map-day-selector');
            const days = [];
            const today = new Date();
            for (let i = 0; i < 14; i++) {
                const d = new Date(today);
                d.setDate(d.getDate() + i);
                const ds = d.toISOString().slice(0, 10);
                const hasVoos = voosPorDia[ds] && voosPorDia[ds].filter(v => !v.is_retorno).length > 0;
                days.push({ date: ds, label: i === 0 ? 'Hoje' : (i === 1 ? 'Amanha' : `${d.getDate()}/${d.getMonth()+1}`), hasVoos });
            }
            const initialDate = mapSelectedDate || days[0].date;
            mapSelectedDate = initialDate;
            sel.innerHTML = days.map(({ date, label, hasVoos }) => 
                `<button class="map-day-btn ${date === initialDate ? 'active' : ''}" onclick="selectMapDay('${date}')" data-date="${date}">${label}${hasVoos ? '' : ' (−)'}</button>`
            ).join('');
        }
        
        function selectMapDay(date) {
            mapSelectedDate = date;
            document.querySelectorAll('.map-day-btn').forEach(b => {
                b.classList.toggle('active', b.dataset.date === date);
            });
            renderMapaVoos(date);
        }
        
        function initMap() {
            if (flightMap) return;
            flightMap = L.map('flight-map', { attributionControl: false }).setView([-23.55, -46.64], 9);
            L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
                maxZoom: 19
            }).addTo(flightMap);
            mapLayers = [];
            renderMapDaySelector();
            renderMapaVoos(mapSelectedDate || new Date().toISOString().slice(0, 10));
        }
        
        document.addEventListener('DOMContentLoaded', () => {
            renderCalendario();
            renderProximosVoos();
            setTimeout(initMap, 100);
        });
    </script>
</body>
</html>
'''


def _serialize_voos(voos_por_dia):
    """Serializa voos para JSON (sem receita)"""
    voos_json = {}
    for data, lista in voos_por_dia.items():
        voos_json[data] = []
        for v in lista:
            voo_dict = {
                'prefixo': v['prefixo'],
                'origem': v['origem'],
                'destino': v['destino'],
                'origem_nome': v['origem_nome'],
                'destino_nome': v['destino_nome'],
                'inicio': v['inicio'].isoformat(),
                'fim': v['fim'].isoformat(),
                'duracao_min': v['duracao_min'],
                'tipo': v['tipo'],
                'status': v['status'],
                'is_pago': v['is_pago'],
                'passageiros': v['passageiros'],
                'name': v['name'],
                'is_retorno': v['is_retorno'],
                'retorno_info': None,
                'fonte': v.get('fonte', 'voo')
            }
            if v['retorno_info']:
                voo_dict['retorno_info'] = {
                    'inicio': v['retorno_info']['inicio'].isoformat(),
                    'fim': v['retorno_info']['fim'].isoformat(),
                    'duracao_min': v['retorno_info']['duracao_min'],
                    'origem': v['retorno_info']['origem'],
                    'destino': v['retorno_info']['destino'],
                    'origem_nome': v['retorno_info']['origem_nome'],
                    'destino_nome': v['retorno_info']['destino_nome']
                }
            voos_json[data].append(voo_dict)
    return voos_json


def _merge_voos_e_stats(vpd_t, st_t, vpd_v, st_v):
    """Mescla dados de trechos + voos."""
    for data, lista in vpd_v.items():
        vpd_t.setdefault(data, []).extend(lista)
    for data in vpd_t:
        vpd_t[data].sort(key=lambda x: x['inicio'])
    st_t['total_voos'] += st_v['total_voos']
    st_t['total_retornos'] += st_v['total_retornos']
    st_t['total_horas'] += st_v['total_horas']
    st_t['total_shuttle'] += st_v['total_shuttle']
    st_t['total_charter'] += st_v['total_charter']
    for k in st_t['por_aeronave']:
        st_t['por_aeronave'][k] += st_v['por_aeronave'].get(k, 0)
    return vpd_t, st_t


def _get_cached_data():
    """Busca dados com cache de 2 minutos. Prioriza Trecho__c (dados reais), fallback em Voo__c."""
    now = time.time()
    with _cache_lock:
        if _cache['data'] and (now - _cache['timestamp']) < CACHE_TTL:
            return _cache['data'], _cache['stats'], _cache['raw_json']
    
    sf = conectar_salesforce()
    if not sf:
        return None, None, None
    
    voos = buscar_voos(sf)
    trechos = buscar_trechos(sf)
    
    if trechos:
        voos_por_dia, stats, voo_ids_com_trechos, retornos_trechos = processar_trechos(trechos)
        vpd_v, st_v = processar_voos(voos, voo_ids_com_trechos, retornos_trechos)
        voos_por_dia, stats = _merge_voos_e_stats(voos_por_dia, stats, vpd_v, st_v)
    else:
        voos_por_dia, stats = processar_voos(voos)
    
    voos_json = _serialize_voos(voos_por_dia)
    
    with _cache_lock:
        _cache['data'] = voos_por_dia
        _cache['stats'] = stats
        _cache['raw_json'] = voos_json
        _cache['timestamp'] = time.time()
    
    return voos_por_dia, stats, voos_json


@app.route('/')
def index():
    voos_por_dia, stats, voos_json = _get_cached_data()
    
    if voos_por_dia is None:
        return render_template_string('''
        <!DOCTYPE html>
        <html><head><title>Erro</title></head>
        <body style="background:#0f172a;color:#ef4444;display:flex;justify-content:center;align-items:center;height:100vh;font-family:sans-serif;">
            <div style="text-align:center;">
                <h1>Erro de Conexao</h1>
                <p>Nao foi possivel conectar ao Salesforce. Verifique as credenciais.</p>
            </div>
        </body></html>
        ''')
    
    return render_template_string(
        HTML_TEMPLATE,
        voos_json=json.dumps(voos_json),
        helicopteros=HELICOPTEROS,
        helicopteros_json=json.dumps(HELICOPTEROS),
        helipontos_json=json.dumps(HELIPONTOS),
        icons=ICONS_BASE64,
        icons_json=json.dumps(ICONS_BASE64),
        stats=stats,
        data_atualizacao=datetime.now().strftime('%d/%m/%Y %H:%M'),
        rotaer_url=ROTAER_URL,
        rotaer_page=ROTAER_PAGE
    )


@app.route('/api/voos')
def api_voos():
    """API para auto-refresh sem recarregar a pagina"""
    voos_por_dia, stats, voos_json = _get_cached_data()
    if voos_json is None:
        return jsonify({'error': 'Erro ao conectar ao Salesforce. Verifique as credenciais no arquivo .env'}), 500
    return jsonify({
        'voos': voos_json,
        'stats': stats,
        'atualizado_em': datetime.now().strftime('%d/%m/%Y %H:%M')
    })


@app.route('/health')
def health():
    return jsonify({'status': 'ok', 'timestamp': datetime.now().isoformat()})


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port, debug=False)
