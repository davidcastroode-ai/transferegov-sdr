"""Diagnóstico: API pública de TED do Transferegov + planilha BASE TED API."""
import json, re, urllib.request, csv, io
def nota(t):
    for i in range(0, len(t), 3500): print('::notice::' + t[i:i+3500].replace('\n', ' ‖ '), flush=True)
def get(u, h=None):
    r = urllib.request.urlopen(urllib.request.Request(u, headers=h or {'User-Agent':'robo-sdr-mapa','Accept':'*/*'}), timeout=120); return r.read()
B = 'https://api-publica.transferegov.gestao.gov.br/ted/'
doc = get(B + 'docs').decode('utf-8', 'ignore')
nota('DOCS html: ' + re.sub(r'\s+', ' ', doc)[:1500])
spec = None
for u in re.findall(r'''["']([^"']*(?:openapi|swagger)[^"']*\.json)["']''', doc) + ['openapi.json', 'docs/openapi.json', 'swagger.json', 'v3/api-docs', 'openapi']:
    full = u if u.startswith('http') else (B + u.lstrip('/') if not u.startswith('/') else 'https://api-publica.transferegov.gestao.gov.br' + u)
    try:
        spec = json.loads(get(full)); nota('SPEC em ' + full); break
    except Exception as e: nota('sem spec em ' + full + ': ' + str(e)[:80])
if spec:
    for p, ops in spec.get('paths', {}).items():
        for m, op in ops.items():
            ps = [x.get('name') for x in op.get('parameters', [])]
            nota(f'{m.upper()} {p} · {op.get("summary","")} · params: {ps}')
    nota('SCHEMAS: ' + ' ; '.join(f'{k}: ' + ', '.join((v.get('properties') or {}).keys()) for k, v in (spec.get('components', {}).get('schemas', {}) or spec.get('definitions', {})).items())[:12000])
    json.dump(spec, open('spec_ted.json', 'w'))
try:
    t = get('https://docs.google.com/spreadsheets/d/e/2PACX-1vQ8khlUawIDFMPUSOMjki7m2RN3mIuL7E-n5h7-bneKZ2aitrRrxyr56LArOeSWQx2A261o2pOZ531z/pub?output=csv').decode('utf-8', 'ignore')
    L = list(csv.reader(io.StringIO(t)))
    nota(f'PLANILHA: {len(L)} linhas · ' + ' ‖ '.join(' | '.join(l) for l in L[:8]))
except Exception as e: nota('PLANILHA erro ' + str(e))
