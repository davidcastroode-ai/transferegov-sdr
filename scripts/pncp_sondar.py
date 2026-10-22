"""Sondagem (só leitura) da API de consulta do PNCP para achar o link PNCP dos contratos da CEPLAC/SDR."""
import csv, io, json, os, sys, time, urllib.request, urllib.parse, urllib.error
OUT = sys.argv[1] if len(sys.argv) > 1 else 'saida'; os.makedirs(OUT, exist_ok=True)
log = []
def get(url):
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers={'Accept': 'application/json', 'User-Agent': 'painel-sdr-mapa/1.0'}), timeout=90) as r:
            return r.status, r.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read(2000)
    except Exception as e:
        return 0, str(e).encode()
CNPJ = '00396895000125'   # MAPA
for i, (ini, fim) in enumerate([('20260101', '20260331'), ('20260401', '20260630'), ('20260701', '20261021')]):
    for base in ['https://pncp.gov.br/api/consulta/v1/contratos']:
        q = urllib.parse.urlencode({'dataInicial': ini, 'dataFinal': fim, 'cnpjOrgao': CNPJ, 'pagina': 1, 'tamanhoPagina': 500})
        st, b = get(base + '?' + q)
        open(os.path.join(OUT, f'pncp_{i}.json'), 'wb').write(b[:5_000_000])
        log.append({'url': base + '?' + q, 'status': st, 'bytes': len(b), 'inicio': b[:300].decode('utf-8', 'ignore')})
        print(st, len(b), ini, fim, flush=True)
        time.sleep(1)
json.dump(log, open(os.path.join(OUT, 'pncp_log.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
