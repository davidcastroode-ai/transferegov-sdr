"""Diagnóstico: API pública de TED do Transferegov (spec + amostras por UG) + planilha BASE TED API → pasta diag/"""
import json, urllib.request, urllib.parse, os, time
os.makedirs('diag', exist_ok=True)
B = 'https://api-publica.transferegov.gestao.gov.br/ted'
def get(u):
    for t in range(3):
        try: return urllib.request.urlopen(urllib.request.Request(u, headers={'User-Agent':'robo-sdr-mapa','Accept':'application/json'}), timeout=120).read()
        except Exception as e: err = e; time.sleep(3)
    raise err
spec = json.loads(get(B + '/openapi.json')); json.dump(spec, open('diag/spec_ted.json','w'), ensure_ascii=False, indent=1)
open('diag/data_atualizacao.json','wb').write(get(B + '/data-atualizacao'))
UGS = ['130010','130141','130255','135098','420013']
res = {}
for path, ops in spec['paths'].items():
    if path == '/data-atualizacao': continue
    params = [p['name'] for p in ops['get'].get('parameters', [])]
    try:
        js = json.loads(get(B + path + '?' + urllib.parse.urlencode({'pagina':1,'tamanho_da_pagina':3})))
        res[path] = {'params': params, 'amostra': js}
    except Exception as e: res[path] = {'params': params, 'erro': str(e)}
    for p in params:
        if 'gestora' in p or 'unidade_gestora' in p:
            for ug in UGS:
                try:
                    js = json.loads(get(B + path + '?' + urllib.parse.urlencode({p: ug, 'pagina':1, 'tamanho_da_pagina':5})))
                    res.setdefault(path + '|' + p, {})[ug] = js
                except Exception as e: res.setdefault(path + '|' + p, {})[ug] = {'erro': str(e)}
json.dump(res, open('diag/amostras.json','w'), ensure_ascii=False, indent=1)
try:
    open('diag/base_ted_api.csv','wb').write(get('https://docs.google.com/spreadsheets/d/e/2PACX-1vQ8khlUawIDFMPUSOMjki7m2RN3mIuL7E-n5h7-bneKZ2aitrRrxyr56LArOeSWQx2A261o2pOZ531z/pub?output=csv'))
except Exception as e: open('diag/base_ted_api.err','w').write(str(e))
print('ok')
