"""Sondagem 2: testa filtros da API do Obrasgov e grava total_items de cada consulta (só leitura)."""
import json, os, sys, urllib.request, urllib.parse, urllib.error
BASE = 'https://api-publica.obrasgov.gestao.gov.br/obras'
OUT = sys.argv[1] if len(sys.argv) > 1 else 'saida'; os.makedirs(OUT, exist_ok=True)
res = []
def get(c, **q):
    url = BASE + c + '?' + urllib.parse.urlencode(q)
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers={'Accept': 'application/json'}), timeout=60) as r:
            j = json.loads(r.read()); return url, 200, j
    except urllib.error.HTTPError as e:
        return url, e.code, {'erro': e.read(500).decode('utf-8', 'ignore')}
    except Exception as e:
        return url, 0, {'erro': str(e)}
T = [('/empenho', dict(ug_emitente='135098')), ('/empenho', dict(ug_emitente=135098)), ('/empenho', dict(ug_emitente='130141')),
     ('/empenho', dict(ug_emitente='420013')), ('/empenho', dict(ug_emitente='130010')), ('/empenho', dict(ug_emitente='130255')),
     ('/empenho', dict(unidade_orcamentaria='22101')), ('/empenho', dict(acao_orcamentaria='20ZV')), ('/empenho', dict(nr_empenho='2024NE000199')),
     ('/empenho', dict(organizacao_empenho='MINISTERIO DA AGRICULTURA E PECUARIA')), ('/empenho', dict()),
     ('/projeto-investimento', dict(organizacao_resp='MINISTERIO DA AGRICULTURA E PECUARIA')),
     ('/projeto-investimento', dict(organizacao_resp='Ministério da Agricultura e Pecuária')),
     ('/projeto-investimento', dict(cnpj_organizacao_resp='00396895000125')), ('/projeto-investimento', dict()),
     ('/projeto-investimento', dict(sistema_resp='TRANSFEREGOV')), ('/execucao-fisica', dict(tipo_instrumento='Contrato de Repasse'))]
for c, q in T:
    url, st, j = get(c, pagina=1, tamanho_da_pagina=3, **q)
    d = j.get('data') if isinstance(j, dict) else None
    res.append({'url': url, 'status': st, 'total_items': j.get('total_items') if isinstance(j, dict) else None, 'amostra': d[:3] if d else j.get('erro') if isinstance(j, dict) else None})
    print(st, j.get('total_items') if isinstance(j, dict) else '', url, flush=True)
# distribuição de ug_emitente numa página grande de empenhos
url, st, j = get('/empenho', pagina=1, tamanho_da_pagina=100)
res.append({'ugs_pag1': sorted({str(x.get('ug_emitente')) for x in (j.get('data') or [])})})
json.dump(res, open(os.path.join(OUT, 'sondagem2.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
