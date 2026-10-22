"""Sondagem da API do Contratos.gov.br (https://contratos.comprasnet.gov.br/api) das UGs da SDR. Só leitura.
Grava em PASTA: docs (especificação), contratos_<ug>.json (ativos e inativos) e detalhes (empenhos, faturas, histórico) por contrato."""
import json, os, sys, time, urllib.request, urllib.error
from concurrent.futures import ThreadPoolExecutor
BASE = 'https://contratos.comprasnet.gov.br'
OUT = sys.argv[1] if len(sys.argv) > 1 else 'saida'; os.makedirs(OUT, exist_ok=True)
UGS = ['130010', '130141', '130255', '135098', '420013']
log = []
def get(caminho, bruto=False):
    url = BASE + caminho
    for t in range(4):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers={'Accept': 'application/json', 'User-Agent': 'painel-sdr-mapa/1.0'}), timeout=90) as r:
                b = r.read(); log.append([r.status, url, len(b)])
                return b if bruto else json.loads(b)
        except urllib.error.HTTPError as e:
            log.append([e.code, url, 0])
            if e.code in (404, 400, 401, 403): return None
            time.sleep(3 * (t + 1))
        except Exception as e:
            log.append([0, url, str(e)[:100]]); time.sleep(3 * (t + 1))
    return None
# documentação
for c in ['/api/docs', '/docs/api-docs.json', '/api/docs.json', '/api-docs.json', '/docs/api-docs.yaml']:
    b = get(c, bruto=True)
    if b: open(os.path.join(OUT, 'doc' + c.replace('/', '_')), 'wb').write(b[:3_000_000])
contratos = {}
for ug in UGS:
    at = get(f'/api/contrato/ug/{ug}') or []
    ina = get(f'/api/contrato/inativo/ug/{ug}') or []
    for x in at: x['_ativo'] = 1
    for x in ina: x['_ativo'] = 0
    contratos[ug] = (at if isinstance(at, list) else []) + (ina if isinstance(ina, list) else [])
    print(ug, 'ativos', len(at) if isinstance(at, list) else at, 'inativos', len(ina) if isinstance(ina, list) else ina, flush=True)
json.dump(contratos, open(os.path.join(OUT, 'contratos.json'), 'w', encoding='utf-8'), ensure_ascii=False)
def det(c):
    i = c.get('id')
    return {'id': i, 'ug': c.get('_ug'), **{k: get(f'/api/contrato/{i}/{k}') for k in ['empenhos', 'faturas', 'historico', 'responsaveis']}}
todos = []
for ug, l in contratos.items():
    for c in l: c['_ug'] = ug; todos.append(c)
with ThreadPoolExecutor(4) as ex:
    D = list(ex.map(det, todos))
json.dump(D, open(os.path.join(OUT, 'detalhes.json'), 'w', encoding='utf-8'), ensure_ascii=False)
json.dump(log, open(os.path.join(OUT, 'log.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=0)
print('contratos', len(todos), 'com empenhos', sum(1 for d in D if d.get('empenhos')), flush=True)
