"""Sondagem 3: baixa só a lista de empenhos da API do Obrasgov das UGs da SDR (só leitura)."""
import json, os, sys, time, urllib.request, urllib.parse, urllib.error
BASE = 'https://api-publica.obrasgov.gestao.gov.br/obras'
OUT = sys.argv[1] if len(sys.argv) > 1 else 'saida'; os.makedirs(OUT, exist_ok=True)
def get(c, **q):
    url = BASE + c + '?' + urllib.parse.urlencode(q)
    for t in range(5):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers={'Accept': 'application/json'}), timeout=90) as r:
                return json.loads(r.read())
        except Exception as e:
            print('tentativa', t, url, e, flush=True); time.sleep(3 * (t + 1))
    raise RuntimeError(url)
todos = []
for ug in ['130010', '130141', '130255', '135098', '420013']:
    p, n = 1, 0
    while True:
        j = get('/empenho', ug_emitente=ug, pagina=p, tamanho_da_pagina=100)
        d = j.get('data') or []; todos += d; n += len(d)
        if p >= (j.get('total_pages') or 1) or not d: break
        p += 1
    print(ug, n, 'empenhos', flush=True)
json.dump(todos, open(os.path.join(OUT, 'empenhos_sdr.json'), 'w', encoding='utf-8'), ensure_ascii=False)
print('total', len(todos))
