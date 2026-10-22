"""Sondagem (só leitura): postos de trabalho e itens dos contratos (Contratos.gov.br) + campos da página de transparência."""
import json, os, re, sys, time, urllib.request, urllib.error
OUT = sys.argv[1] if len(sys.argv) > 1 else 'saida'; os.makedirs(OUT, exist_ok=True)
IDS = [int(x) for x in sys.argv[2].split(',')]
def get(url, js=True):
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers={'Accept': 'application/json' if js else 'text/html', 'User-Agent': 'Mozilla/5.0 painel-sdr-mapa'}), timeout=90) as r:
            b = r.read(); return r.status, b
    except urllib.error.HTTPError as e:
        return e.code, e.read(3000)
    except Exception as e:
        return 0, str(e).encode()
log = []
for i in IDS:
    for k in ['terceirizados', 'itens', 'cronograma']:
        st, b = get(f'https://contratos.comprasnet.gov.br/api/contrato/{i}/{k}')
        open(os.path.join(OUT, f'ct_{i}_{k}.json'), 'wb').write(b[:2_000_000]); log.append([i, k, st, len(b)])
    st, b = get(f'https://contratos.comprasnet.gov.br/transparencia/contratos/{i}', js=False)
    open(os.path.join(OUT, f'ct_{i}_pagina.html'), 'wb').write(b[:3_000_000]); log.append([i, 'pagina', st, len(b)])
    print(i, log[-4:], flush=True); time.sleep(1)
json.dump(log, open(os.path.join(OUT, 'postos_log.json'), 'w'), indent=0)
