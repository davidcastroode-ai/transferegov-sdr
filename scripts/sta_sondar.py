"""Sondagem (só leitura) da API de ordens bancárias do Tesouro (sta.api.gov.br) a partir dos empenhos dos contratos (Contratos.gov.br).
Pega uma amostra de NEs de 2023 a 2026 das UGs da SDR e grava a resposta de cada uma em PASTA/sta_*.json."""
import csv, io, json, os, sys, time, urllib.request, urllib.error
OUT = sys.argv[1] if len(sys.argv) > 1 else 'saida'; os.makedirs(OUT, exist_ok=True)
raw = urllib.request.urlopen('https://raw.githubusercontent.com/davidcastroode-ai/transferegov-sdr/dados/contratos_api_emp.csv', timeout=60).read().decode('utf-8')
E = list(csv.DictReader(io.StringIO(raw)))
amostra, vistos = [], set()
for ano in ['2026', '2025', '2024', '2023']:
    for ug in ['130010', '130141', '130005']:
        l = [e for e in E if e['Nota de empenho'].startswith(ano) and e['UG da NE'] == ug and (ug, e['Nota de empenho']) not in vistos][:6]
        for e in l:
            vistos.add((ug, e['Nota de empenho'])); amostra.append(e)
log = []
for e in amostra:
    ne = e['UG da NE'] + '00001' + e['Nota de empenho']
    for url in [f'https://sta.api.gov.br/api/ordembancaria/empenho/{ne}']:
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers={'Accept': 'application/json', 'User-Agent': 'painel-sdr-mapa/1.0'}), timeout=60) as r:
                b = r.read(); st = r.status
        except urllib.error.HTTPError as x:
            b = x.read(3000); st = x.code
        except Exception as x:
            b = str(x).encode(); st = 0
        open(os.path.join(OUT, f'sta_{ne}.json'), 'wb').write(b[:400000])
        log.append({'ne': ne, 'contrato': e['Nº contrato'], 'id': e['ID contrato (API)'], 'status': st, 'bytes': len(b), 'inicio': b[:300].decode('utf-8', 'ignore')})
        print(st, len(b), ne, flush=True)
        time.sleep(0.5)
json.dump(log, open(os.path.join(OUT, 'sta_log.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
