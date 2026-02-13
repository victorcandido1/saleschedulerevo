"""
Calendario de Disponibilidade de Aeronaves - REVO
Layout com visualizacao Gantt detalhada por dia
"""

from flask import Flask, render_template_string, jsonify, request
import os
import time
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

ICONS_BASE64 = {
    'PR-OMB': 'data:image/png;base64,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',
    'PR-OMH': 'data:image/png;base64,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',
    'PR-OOE': 'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAEAAAAAjCAIAAACra5t9AAAQ90lEQVR42kWZW3BdZ3XH/2ut79v7XCVbsuWLZDu+5EacZMiFwKSlJSSU0LQPfcgwMC1Mp0zaGab0oS99oEPbaV86bYcyLWVaeoFJKLeSAJMGkpBCEicQEmzLNuRmx3dLsmRJRzo6Z+9vrdWH7zjoRXuOdPb+9rfX+q///7fp2LEjDhAR4O7uDiYiwNwdLiwAqdYgiqFQUzPNHyathYWZU0pExMzubnDyfDYyVyIiYjjU8jERwc1BxETqDjfhQISkSnDm4HDTRCzMbGbuxiwA3A15oQQ4EQGAmbE7iMjNVZVAImJmakrMzGKW3DSEQKC6rghgYnMHXDiYm5mKiMNVExEINNoGciJ2dzcFORMBjvwXJndTUyYiItVkZsycd8rdJES4p1QTIBzcLKUaDpYAd1N1GAiAuxsTk5sRU4yFudV1FWIMMarWcJNQEHNSJSYRNlMiEhZ3I/YgAYCaigSRoGYECjGMzgmIBBCZGTEHifmqAIRFWMwSAAkBBLN8iUDEmhIIMRYgmCUiFLEgoroegDzEgohU1QFmCW7GLA6r61qYJYRU1w4LEh2e6pqZmUhVhYVZkiZmZmY3N0/EzCBTBUCAu5oyAGJ2MzcnEBG5aYLmb7m7k7s7k7ibasqPwswAEBELu3ldVSzMIqZW1zUzF7E0t2o4YAkiwVTNNG9hAiAibqqqzMQcVBUEZlJNzCIStK6JWZjNXE2ZCQRTJWIADieQw92MCO65hOBuRGTuTGRqo2YzEEFNR7fnMDcCgeDmDgeQT5KSEsAi7lbVQwIzB8BTqpmEiBkAE+fNAxELgygXMeAOSIgAVGuJEQRVExl1GBzMAnJcrf7R/gEEJpC7ERMx5SWxsMGudmLuZAIccOa8CgBwmLp5PiFyrSsTB4nM1ChFiJgIrm4WAHcHETscnu8bDidnENzgpAAJi2liZgpiquYeJDjcTJkl9yczu5s7mMRc3UxE3MzdQxAzc3MhMVOM6srNjYhZWDXBPYQQYmCmKEGEU0rrgwruILibuccgjzz2w6dePF4URW9t/dbrd4VcALm3QHCAmOAUA4cg5q5mqU7ukCCqpmnIHIi50goOYTEzUNYWJyIHaq3LGM1dU2IJAOo6MQtgaolZhJmZRLgsCiJ3czVPKQ2r6uL84mpv4+LC4pWV3vS2Lbe+Yx8RAHb3sW7n2997/nNf/VFnYqtW/aHjXWUZ8saD8vI9P0QCLs4vLa2sNYrQaTW73XYRBY4iRmmUTCBCkDaI6pRUE4HNzNzhDqZmWaz0+kQY67ZTnRwoi0YIwkyaNCWrUlpZ6c8tLC8sXrmy2p+/sjK/sHR5qbe23gcgQjGEZrOxb9f2vbt2TE6M1VVdxDg3f/nL33l+05Zt0PSeB+7lgm6bsEAgYriTuxHIyUOQc5cuf+WxZxYWl808qTKhyD+RW42yLMKWic3tVlkWsdUsm41GoyxazbLbbjWKwMKPHzr8+qkLmtKBvTN33nodM6+u9y8vrpy/tDi3sDR/eam3vmFOzUYRo5QxbpncdMsN+yc3d6a2jI91Op1Wo1kW7XaDWVZ767n1m8345Ud/cmFFy1jd+O537jiw+6ePfnvfx++j2dnDWf9yLZmrcFAzIhDRsKpScjWr62ppeaUa1kXZ6A+q5dXecFgTsxCRMBx1Xa/2+r3+4JkXDp+5MD81udnhg0E1NdHdtmWi22mVReh2WtfMbNu3e8fWifHxbmus22k3myK0MRykpGYYDqs61e4gkqquiRBDSJqKIp45O/dHn/mPITV27tt95wd+5ezJs92V83/2e/fTL149rqqeJYdGvZBVBQBTlgoaDodu2mw2QwhlGZtlKcwrvbUrq2unz146f2lxudffGAxVdd+enRcuLnz9iefWNqob9s5cMzMFTWq2ZXLzyur6wtIKM5qNstVqtZtlp9WY2rJp57bJTWMdAsa6LRbRVBNxDIW7GcwM3Vbjr/7pv1+6lPbu37N5x1TRKNVs39rZBz90d+h2uisry+bGIBC5G5gI5ObEZIDWNRMTEYc4rOq1/uDNMxdfP3X+4tzlxaUVEG/fOjG9feL6/dPX7Nq5e8eWL33rqYefeKn2NjXHjp3vv/z6bKc7NtYq7uTw+w/e12415y8vLyytXJxfnF9cvriw9OrJc5eXVlJK97739gfe/y64x1ioabJaJFht7VbjuZ8ceasqf+PDv7m20rt89tyVSn9+6IX7//B+4RDm5+dCCCEEVbWURAJyPzDniZltDDNly7cxHL55+mJvfeP6/Xtu/MDMlsnxTqsx1m0Nh+mNU6e/9PxLn/3S9wYWGoUQizA1CtZq4/Jw8I2nL7xy7LW//tOPX79v177d28y8LEs3HwyHw7quqlQWASAnT1pzNpGpDjEONgaPPjd73d33FIX87OkfLp69uN4fHtjRvn7/7rX1Pp04MeuwlBITi8hVK0YwB4GIRjIFd3dmYZZGGYJIUh1WdQzBzJ859MqTh46feGtheb0WrwjmLM3OpGmqB2uhaJqrEPV6q+Oxvnbf9Cd/97dvvPaatX5/WFXCQUTcNReuuxNoZFfVOp3Gd7//4t8+/INtM9P9tf7a8kqjjIM67RiPn/+Lh4oY5KGHPgGQcCQitXR1tjsRMDqg7G2IOfuLwbDuDwZFER301rm5v//Xr3/xsUNnLvchodEoSVhVi2aXSEBw11h2OJYSG7Esli5fev3U+RePnDw/d3lyc3fXjm2NsmCBiEiQvPG5C1NKEnhtfeNvvvDogNrVRtVbWY6BakN30+TFxTUb9u6+/SAdO3YkT+s8BvI8uHqW0Rwnzu4CxJzqutks3fnZnxz98U9fefPkqdNza5WMi1CteaBQECaiZO7u4koSJJYgWF1ptV40O1SOry4vdiPuOHjNPe++aWpyc1mGKFzEUMbQajVazSYJd1rNz37xW//1xNGibMR66VMf+9BrJ89PjHf+8eGnNm+/RvtLn//0x+j48aM5GYDARADyeM9OhpkdMFMCOcHUxjrtty4s/OdXHjv9xlEDz/XiZJevVI1afaIcqrO7XxlEKjpj0lf3DW8ZxFLt5o7EeXK7CzsVreWl5anprXvfcf3Jw7PTe3a2Oq1WEVO/P1hZ7jRkrN16fvbMBjpbW+mj99/x+un5106dv+nAzJbJsS//7+GVDbvvndNBTYVFJJipmhOQg0g2W2YOZG9jmnTz2NgPXjz85a98s80rOydbr5ylA9uxfdxfeqsqA27aSbWCgJdOW6Xp4M7BRuVHFtvN7ngsYnaaw34/FoXEuLo4N+it3fFrd992768+++gTt9577+SOqbqqVpeWX37i6dWFuVC00rC/aWKSCi/Y19cH3zt0fLmO64NTH7z7Jq/6m8a3PXvkdBAO7pa0YmLOlg4A6G2L4e6mBuKxTus7Tz//yFe/ObMZ3XZr9pxubvm2cTYjNcSo7lB1gJwCGL1+urjRTihmZrZv2zPTaLd6i0tlq5nUQ1HO/t+Pxian3vfRB3/2zLOT09M3331XPRiY6WsvHbH1ta1T22NrfGN5PpTNSj0G2TU91W0V/eVhp9m+Ztf2EONGndql0OzsYSJmZjM1NyZGViEaebysQI0y/uCFo//8xUcOzjBJWBvoiQu4dsqYycGvzrMQtnRDP9HQpF8xx2ZgV+dqUG+Z3sFMkzu3LV9eao1115eW2pvHzxw/dss974X60oVLN7znDgc2+oOXn3r20qkzZUlwH986U60uStGIra5urNw43f7wb73/pSPH9+3a9rXHD53rhY313mce+hCdODHr7m+nUrMcUEYlBHeHmXsjxj/+y387+vNf7NraGtS2MSRvbhE2dXEOVlUQptAAnInTsCexSAljE+PT+3aHZpNhy3MLa8u9K3OX2t32zA3XTeyYmj9znorm/tsOVr3ecHV55fQpv7K0d8/2G/dNL15e/MK3XkRs2tp8aG2m2C6ounX/lrW1fijK54+emewWn/rI++6/5z1BzZiJWcwUlLNPLh7K2dkdwsEJv/PBuy7MzYtdmenySd7sjYarQp2ZlGqhyEhwA0jroanvvfXg9LV7261mXQ9Nq3anvHDqTKM9M33wllTXb7z8sw4GM7unZxZem5ncNLl9fPzOuycnNzcbRVILIr2N6tlXXrv25psPXrf7G0+9cn5x8NIvLtZVLUL33L7nDx6878YDexavLNOJE7NmBjixwEcBhZjNNIc1gNSSmXbaneXl1e//6MffffLZNxfUEGIUCYFciZhYiJAtVWt8/MAdt01s39oeG1udv3Tkye8nLgf9Pmm1fWpi97aJmbHyrttuvG7v9Nnz80lt795d7VZZVXVd1eZOBGEJInVdkYRuu3Fxfulz//4/27ZuvvHaPdftndm5bRLAYFgTEc0eO5wjldoofRLBbRT8zA1w5gD3pCkEaZblxfnln86+euLkubcuLF+aW1rurUksJERVZQ5jWycmd07V/X6McevOqTcOz14+e/5dt+zfMz11YM+O/bu3T23Z1Om2qyqlZGrJIAyYpqwdBKbsXkYpBWZeFrG/MXjhlZ/ffvN1k5u6G8Mqjypzo+MnZnPqY+aMQJgoR15zYxYmUk0OsAgcmlIMUpTR1ISpLMInPv0vN+zd+ZEHfnVppSciIcZ6MIgiZVlOjrUeefy55w+//vDf/QlL2BgM1/qDulZTIyE3azSaRYwbG/2kCSBmGS0rgytHBgLuHiU0ytgfDrPEuOWhi+CWUylpGrEJEGVeIBzMzMiIhd1d3eHE7KClpd6f/8PDe3Zt//W7blpY6k1u6p88t9AfDJk5908ejmUZzs6vzi2tP/rkj6tkM1MTB/bsgLsIA2i0OsNquL6+FmIIEs1MNYlIkKCqcGcRcyeAmZPWvX4SFs8zlwVwVaXjx49ml5ApoOX5z+JwH+1EthG/1CU1C8IvHn7ta48fml9aLhsNNauHA3eMJklGIu7CzEEkRKurtfXB/e995yc/9sD6+oBZmDnEsL6+FmOEI6U6wy8zVU0hFgBUVTIoAJjFVN09cxOYj5Z97NjRzDbMHQAzw8ldHSNn4Q4itxzZHIARi6m1GgURrQ8Gqna13TMWvUoXAWJycyAzIotFzFthntlRjk0GIgI7XFVFmEmu2kp2WGYN7prF0M0cYBAxacYq5sZETOxuqkoj6pJX4UScaSzcM2p1M7j1B8P83IIIjcweCOzk5EQgH3HYq6CAoybF22YxP9TMpQCzBJCIANBUEzNADoNTxq/MIWkiUKYbZkYGOAWAmMjhZomIRcRU1YyF397LbEZ9lJsd8JyD/apWjHYlq9bbPaCWPXlGQDB/e+kExwhjOYGyfQSRmwFgEYPDHQZmSBBNCUQiwd0zmKGrEIwBVzM4JGtlXRNziFHVUkrMwmDV5A7mkEUNYBjlYshkjUa/MQoPICImJs8rdLrKx0cWxQE4GOwGM2cS+IhSZgEky2pKZuqKECKB67p2h0hw8xhjtg4M5OIZfT+EYGZ1VQUJMRYp1WpJQiRC0gqASMhZm3gUoJgoV+kIjpGYWYb1TGyuZpoZR5YmhxOJA2opg8cs0yJirmbGLCCo6ehssKSJmEMIbqYpFUWxadNEXgnNHjuKHLsyWHXLrEQtwa9qvykBIQTVPBwyrx7B5KsgFr9sYsDVQM78dkYFE2Vome+TOaNfZWYiUrOR+rm5G0uAw0xBxJn35OMR37YQomZRonxlM8tiwmyWUkpMkpVLLTExs6SkZiYicKQ6jSQrt/ZV851flCCLHaB69d8cZva2y8pvFbJ/sdG7FSYgaQIRc9CUMhXP2TI/FnfPw4qIUko5Mf4/Az0MvLX+ZzoAAAAASUVORK5CYII=',
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


def extrair_icao_da_rota(rota):
    if not rota:
        return 'N/A', 'N/A'
    rota = str(rota).upper().strip()
    partes = rota.replace('/', '-').replace('X', '-').replace(' ', '-').split('-')
    partes = [p.strip() for p in partes if p.strip()]
    if len(partes) >= 2:
        return partes[0][:4], partes[-1][:4]
    elif len(partes) == 1:
        return partes[0][:4], partes[0][:4]
    return 'N/A', 'N/A'


def buscar_voos(sf):
    hoje = datetime.now().strftime('%Y-%m-%d')
    query = f"""
    SELECT Id, Name, Tipo__c, Status__c, DataHoraVoo__c, 
           Rota__c, RotaAbreviada__c, Prefixo__c, PrefixoTexto__c,
           ContadorPassageiros__c, ReceitaVoo__c, PerspectivaReceitaVoo__c, Duracao__c
    FROM Voo__c 
    WHERE DataHoraVoo__c >= {hoje}T00:00:00Z
    AND (Status__c LIKE '%Confirm%' OR Status__c LIKE '%Reserv%' OR Status__c LIKE '%Pago%')
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


def processar_voos(voos):
    voos_por_dia = {}
    stats = {
        'total_voos': 0,
        'total_retornos': 0,
        'por_aeronave': {'PR-OMB': 0, 'PR-OMH': 0, 'PR-OOE': 0},
        'total_horas': 0.0,
        'total_shuttle': 0,
        'total_charter': 0
    }
    
    for voo in voos:
        prefixo = voo.get('PrefixoTexto__c') or voo.get('Prefixo__c') or ''
        prefixo = str(prefixo).upper().strip()
        if prefixo not in HELICOPTEROS:
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
        origem, destino = extrair_icao_da_rota(rota)
        
        duracao_estimada = float(voo.get('Duracao__c', 0) or 0) or 0.5
        dep_time = dt_local
        arr_time = dt_local + timedelta(hours=duracao_estimada)
        
        origem_nome = HELIPONTOS.get(origem, {}).get('nome', origem)
        destino_nome = HELIPONTOS.get(destino, {}).get('nome', destino)
        
        duracao_min = int((arr_time - dep_time).total_seconds() / 60)
        
        status = voo.get('Status__c', '')
        is_pago = 'pago' in status.lower() if status else False
        
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
            'passageiros': voo.get('ContadorPassageiros__c', 0) or 0,
            'receita': float(voo.get('ReceitaVoo__c', 0) or 0) or float(voo.get('PerspectivaReceitaVoo__c', 0) or 0),
            'is_retorno': False,
            'retorno_info': None
        }
        
        if destino != HANGAR_BASE and destino in HELIPONTOS:
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
        
        data_str = dep_time.strftime('%Y-%m-%d')
        if data_str not in voos_por_dia:
            voos_por_dia[data_str] = []
        voos_por_dia[data_str].append(voo_info)
        
        stats['total_voos'] += 1
        stats['por_aeronave'][prefixo] += 1
        
        tipo_lower = (voo.get('Tipo__c', '') or '').lower()
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
        
        /* Timeline Header */
        .timeline-header {
            display: flex; margin-bottom: 10px; padding-left: 420px;
            border-bottom: 1px solid #334155; padding-bottom: 10px;
        }
        .timeline-hours {
            display: flex; flex: 1; justify-content: space-between;
        }
        .timeline-hour { font-size: 0.75rem; color: #64748b; width: 50px; text-align: center; }
        
        /* Gantt Row */
        .gantt-row {
            display: flex; margin-bottom: 10px; min-height: 130px;
            background: #0f172a; border-radius: 10px; overflow: hidden;
        }
        
        .gantt-info {
            width: 420px; min-width: 420px; padding: 15px 20px;
            border-right: 2px solid #334155; font-size: 0.85rem;
            display: flex; flex-direction: column; justify-content: center;
        }
        .gantt-info-header {
            display: flex; align-items: center; gap: 12px; margin-bottom: 8px;
        }
        .gantt-info-icon { width: 36px; height: 36px; border-radius: 6px; }
        .gantt-info-ref { font-weight: 700; color: #e2e8f0; font-size: 1rem; }
        .gantt-info-cliente { color: #94a3b8; font-size: 0.8rem; }
        .gantt-info-details { color: #64748b; line-height: 1.6; font-size: 0.85rem; }
        .gantt-info-details span { color: #e2e8f0; }
        .gantt-info-rota { margin-top: 6px; color: #94a3b8; font-size: 0.85rem; }
        .gantt-info-rota strong { color: #e2e8f0; }
        
        .gantt-status-tag {
            display: inline-block; padding: 3px 10px; border-radius: 4px;
            font-size: 0.75rem; font-weight: 600; margin-left: 10px;
        }
        .gantt-status-tag.pago { background: #16a34a; color: white; }
        .gantt-status-tag.pendente { background: #dc2626; color: white; }
        .gantt-tipo-tag {
            display: inline-block; padding: 3px 10px; border-radius: 4px;
            font-size: 0.75rem; font-weight: 600; margin-left: 6px;
        }
        .gantt-tipo-tag.shuttle { background: #7c3aed; color: white; }
        .gantt-tipo-tag.charter { background: #0369a1; color: white; }
        .gantt-tipo-tag.other { background: #475569; color: white; }
        
        .gantt-timeline {
            flex: 1; position: relative; min-height: 130px; padding: 8px 0;
        }
        
        .gantt-bar {
            position: absolute; top: 8px; bottom: 8px;
            border-radius: 6px; display: flex; align-items: center;
            justify-content: center; font-size: 0.85rem; font-weight: 700;
            color: white; z-index: 2; overflow: hidden;
            box-shadow: 0 2px 8px rgba(0,0,0,0.3);
        }
        .gantt-bar.voo { background: #dc2626; z-index: 3; border-right: 2px solid #0f172a; }
        .gantt-bar.retorno { background: #eab308; color: #000; z-index: 2; }
        
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
            .gantt-info { width: 300px; min-width: 300px; }
            .timeline-header { padding-left: 300px; }
        }
        @media (max-width: 768px) {
            .stats-grid { grid-template-columns: repeat(2, 1fr); }
            .calendar-grid { grid-template-columns: repeat(2, 1fr); }
        }
    </style>
</head>
<body>
    <div class="container" id="main-container">
        <div class="header">Atualizado em {{ data_atualizacao }}</div>
        
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
            <button class="filter-btn" data-filter="shuttle" onclick="toggleFilter('shuttle')">Shuttle</button>
            <button class="filter-btn" data-filter="charter" onclick="toggleFilter('charter')">Charter</button>
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
                    <div class="modal-legend-color voo"></div>
                    <span>Voo Ocupado</span>
                </div>
                <div class="modal-legend-item">
                    <div class="modal-legend-color retorno"></div>
                    <span>Retorno / Empty Leg</span>
                </div>
            </div>
            
            <div class="modal-body" id="modal-body"></div>
        </div>
    </div>
    
    <script>
        let voosPorDia = {{ voos_json|safe }};
        const helicopteros = {{ helicopteros_json|safe }};
        const icons = {{ icons_json|safe }};
        
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
            if (activeFilter === 'shuttle') return (voo.tipo || '').toLowerCase().includes('shuttle');
            if (activeFilter === 'charter') return !(voo.tipo || '').toLowerCase().includes('shuttle');
            return voo.prefixo === activeFilter;
        }
        
        function toggleFilter(filter) {
            activeFilter = filter;
            document.querySelectorAll('.filter-btn').forEach(b => {
                b.classList.remove('active', 'active-blue', 'active-green', 'active-orange');
            });
            const btn = document.querySelector(`[data-filter="${filter}"]`);
            if (filter === 'PR-OMB') btn.classList.add('active-blue');
            else if (filter === 'PR-OMH') btn.classList.add('active-green');
            else if (filter === 'PR-OOE') btn.classList.add('active-orange');
            else btn.classList.add('active');
            renderCalendario();
            renderProximosVoos();
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
                const tipoLower = (voo.tipo || '').toLowerCase();
                const badge = tipoLower.includes('shuttle') 
                    ? '<span class="nf-badge shuttle">SHUTTLE</span>' 
                    : '<span class="nf-badge charter">CHARTER</span>';
                
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
                const classeHoje = isHoje ? ' today' : '';
                
                html += `<div class="day-cell${classeHoje}" onclick="abrirModal('${dataStr}')" style="position:relative;">`;
                html += `<div class="day-number">${dia}</div>`;
                html += '<div class="flights-list">';
                
                const voosReais = voosDia.filter(v => !v.is_retorno);
                
                voosReais.slice(0, 6).forEach(voo => {
                    const icon = icons[voo.prefixo] || '';
                    const inicio = new Date(voo.inicio);
                    const hora = inicio.toTimeString().slice(0, 5);
                    const rota = `${voo.origem}-${voo.destino}`;
                    const durMin = voo.duracao_min;
                    
                    html += `
                    <div class="flight-item">
                        <img class="flight-icon" src="${icon}" alt="${voo.prefixo}">
                        <span class="flight-time">${hora}</span>
                        <span class="flight-route">${rota}</span>
                        <div class="flight-tooltip">
                            <strong>${voo.prefixo}</strong><br>
                            ${voo.origem_nome} → ${voo.destino_nome}<br>
                            ${hora} - ${durMin}min · ${voo.passageiros} pax
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
                    let snap = `<div class="day-tooltip"><strong>${voosReais.length} voo(s)</strong><br>`;
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
            
            titulo.textContent = `${diaSemana}, ${diaNum} de ${mesNome} de ${ano}`;
            subtitulo.textContent = `${voos.length} voo(s) programado(s)`;
            
            if (voos.length === 0) {
                body.innerHTML = '<div class="no-flights">Nenhum voo programado para este dia</div>';
            } else {
                let html = '';
                
                html += '<div class="timeline-header"><div class="timeline-hours">';
                for (let h = 5; h <= 23; h++) {
                    html += `<div class="timeline-hour">${String(h).padStart(2, '0')}:00</div>`;
                }
                html += '</div></div>';
                
                voos.forEach(voo => {
                    const cor = helicopteros[voo.prefixo]?.cor || '#666';
                    const icon = icons[voo.prefixo] || '';
                    const inicio = new Date(voo.inicio);
                    const fim = new Date(voo.fim);
                    const horaInicio = inicio.toTimeString().slice(0, 5);
                    const horaFim = fim.toTimeString().slice(0, 5);
                    
                    const statusTag = voo.is_pago 
                        ? '<span class="gantt-status-tag pago">PAGO</span>'
                        : '<span class="gantt-status-tag pendente">PGTO PENDENTE</span>';
                    
                    const tipoLower = (voo.tipo || '').toLowerCase();
                    let tipoTag = '';
                    if (tipoLower.includes('shuttle')) {
                        tipoTag = '<span class="gantt-tipo-tag shuttle">SHUTTLE</span>';
                    } else if (tipoLower.includes('charter')) {
                        tipoTag = '<span class="gantt-tipo-tag charter">CHARTER</span>';
                    } else if (voo.tipo) {
                        tipoTag = `<span class="gantt-tipo-tag other">${voo.tipo.toUpperCase()}</span>`;
                    }
                    
                    const startHour = inicio.getHours() + inicio.getMinutes() / 60;
                    const endHour = fim.getHours() + fim.getMinutes() / 60;
                    const leftPercent = Math.max(0, ((startHour - 5) / 18) * 100);
                    const vooEndPercent = Math.max(0, ((endHour - 5) / 18) * 100);
                    const rawWidth = vooEndPercent - leftPercent;
                    const vooWidth = Math.max(rawWidth, 3);
                    const vooVisualEnd = leftPercent + vooWidth;
                    
                    let retornoBar = '';
                    if (voo.retorno_info) {
                        const retFim = new Date(voo.retorno_info.fim);
                        const retEndHour = retFim.getHours() + retFim.getMinutes() / 60;
                        const retEndPercent = Math.min(100, ((retEndHour - 5) / 18) * 100);
                        const retLeftPercent = vooVisualEnd;
                        const retWidthPercent = Math.max(retEndPercent - retLeftPercent, 2);
                        
                        if (retEndPercent > retLeftPercent) {
                            retornoBar = `<div class="gantt-bar retorno" style="left: ${retLeftPercent}%; width: ${retWidthPercent}%;"></div>`;
                        }
                    }
                    
                    html += `
                    <div class="gantt-row">
                        <div class="gantt-info">
                            <div class="gantt-info-header">
                                <img class="gantt-info-icon" src="${icon}" alt="${voo.prefixo}" style="width:40px;height:40px;">
                                <div>
                                    <span class="gantt-info-ref" style="color: ${cor};font-weight:700;">${voo.prefixo}</span>
                                    <span class="gantt-info-ref" style="color: #94a3b8;font-size:0.75rem;">${voo.name || 'N/A'}</span>
                                    ${tipoTag}
                                    ${statusTag}
                                </div>
                            </div>
                            <div class="gantt-info-details">
                                Pax: <span>${voo.passageiros}</span> · 
                                <span>${horaInicio} - ${horaFim}</span> · 
                                <span>${voo.duracao_min}min</span>
                            </div>
                            <div class="gantt-info-rota">
                                <strong>${voo.origem_nome}</strong> (${voo.origem})<br>
                                ↓ <strong>${voo.destino_nome}</strong> (${voo.destino})
                            </div>
                        </div>
                        <div class="gantt-timeline">
                            <div class="gantt-grid-lines">
                                ${Array(18).fill('<div class="gantt-grid-line"></div>').join('')}
                            </div>
                            <div class="gantt-bar voo" style="left: ${leftPercent}%; width: ${vooWidth}%;"></div>
                            ${retornoBar}
                        </div>
                    </div>`;
                });
                
                body.innerHTML = html;
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
                    text.textContent = `Atualizado em ${data.atualizado_em}`;
                }
                spinner.classList.remove('active');
            } catch(e) {
                document.getElementById('refresh-spinner').classList.remove('active');
            }
        }
        
        // Refresh a cada 2 min
        setInterval(autoRefresh, 120000);
        
        document.addEventListener('DOMContentLoaded', () => {
            renderCalendario();
            renderProximosVoos();
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
                'retorno_info': None
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


def _get_cached_data():
    """Busca dados com cache de 2 minutos"""
    now = time.time()
    with _cache_lock:
        if _cache['data'] and (now - _cache['timestamp']) < CACHE_TTL:
            return _cache['data'], _cache['stats'], _cache['raw_json']
    
    sf = conectar_salesforce()
    if not sf:
        return None, None, None
    
    voos = buscar_voos(sf)
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
        sf_user = os.environ.get('SF_USERNAME', '')
        sf_domain = os.environ.get('SF_DOMAIN', 'login')
        has_creds = bool(sf_user and os.environ.get('SF_PASSWORD') and os.environ.get('SF_SECURITY_TOKEN'))
        return render_template_string('''
        <!DOCTYPE html>
        <html><head><title>Erro de Conexao - REVO</title></head>
        <body style="background:#0f172a;color:#e2e8f0;display:flex;justify-content:center;align-items:center;height:100vh;font-family:'Segoe UI',Tahoma,sans-serif;">
            <div style="text-align:center;max-width:600px;padding:40px;">
                <h1 style="color:#ef4444;margin-bottom:20px;">Erro de Conexao</h1>
                <p style="margin-bottom:20px;">Nao foi possivel conectar ao Salesforce.</p>
                {% if not has_creds %}
                <div style="background:#1e293b;border:1px solid #334155;border-radius:12px;padding:20px;text-align:left;margin-bottom:20px;">
                    <p style="color:#f59e0b;font-weight:600;margin-bottom:10px;">Variaveis de ambiente necessarias:</p>
                    <code style="color:#94a3b8;display:block;line-height:2;">
                        SF_USERNAME=seu_usuario@salesforce.com<br>
                        SF_PASSWORD=sua_senha<br>
                        SF_SECURITY_TOKEN=seu_token<br>
                        SF_DOMAIN=login
                    </code>
                </div>
                <p style="color:#64748b;font-size:0.85rem;">Configure as variaveis de ambiente no Cloud Run ou no arquivo .env</p>
                {% else %}
                <p style="color:#f59e0b;">Credenciais encontradas para <strong>{{ sf_user }}</strong> (domain: {{ sf_domain }}), mas a conexao falhou. Verifique se estao corretas.</p>
                {% endif %}
            </div>
        </body></html>
        ''', has_creds=has_creds, sf_user=sf_user, sf_domain=sf_domain), 503
    
    return render_template_string(
        HTML_TEMPLATE,
        voos_json=json.dumps(voos_json),
        helicopteros=HELICOPTEROS,
        helicopteros_json=json.dumps(HELICOPTEROS),
        icons=ICONS_BASE64,
        icons_json=json.dumps(ICONS_BASE64),
        stats=stats,
        data_atualizacao=datetime.now().strftime('%d/%m/%Y %H:%M')
    )


@app.route('/api/voos')
def api_voos():
    """API para auto-refresh sem recarregar a pagina"""
    voos_por_dia, stats, voos_json = _get_cached_data()
    if voos_json is None:
        return jsonify({'error': 'Erro ao conectar ao Salesforce'}), 500
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
