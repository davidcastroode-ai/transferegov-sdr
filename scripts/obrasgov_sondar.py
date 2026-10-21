"""Sondagem da API pública do Obrasgov (https://api-publica.obrasgov.gestao.gov.br).
Só leitura: descobre a documentação (OpenAPI), lista os recursos e baixa uma amostra pequena de cada um.
Uso: python scripts/obrasgov_sondar.py PASTA_SAIDA"""
import json, os, sys, time, urllib.request, urllib.parse, urllib.error

BASE = 'https://api-publica.obrasgov.gestao.gov.br'
OUT = sys.argv[1] if len(sys.argv) > 1 else 'obrasgov_teste'
os.makedirs(OUT, exist_ok=True)
log = []


def get(url, limite=400_000):
    req = urllib.request.Request(url, headers={'Accept': 'application/json, text/html;q=0.9, */*;q=0.5', 'User-Agent': 'painel-sdr-mapa/1.0'})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            corpo = r.read(limite)
            return r.status, r.headers.get('Content-Type', ''), corpo
    except urllib.error.HTTPError as e:
        return e.code, e.headers.get('Content-Type', ''), e.read(20_000)
    except Exception as e:
        return 0, '', str(e).encode()


def salvar(nome, corpo):
    with open(os.path.join(OUT, nome), 'wb') as f:
        f.write(corpo)


def registrar(url, st, ct, corpo, nome):
    log.append({'url': url, 'status': st, 'tipo': ct, 'bytes': len(corpo), 'arquivo': nome})
    print(st, len(corpo), url, flush=True)


# 1) páginas e documentação
CANDIDATOS = ['/', '/obras/docs', '/obras/docs/', '/obras/openapi.json', '/obras/docs/openapi.json', '/obras/v3/api-docs',
              '/openapi.json', '/docs', '/docs/openapi.json', '/v3/api-docs', '/obras/api-docs', '/obras/swagger.json',
              '/obrasgov/api/v3/api-docs', '/obrasgov/api/swagger-ui/index.html', '/obras/redoc', '/api', '/obras']
spec = None
for i, c in enumerate(CANDIDATOS):
    url = BASE + c
    st, ct, corpo = get(url)
    nome = f'doc_{i:02d}' + ('.json' if 'json' in ct else '.html' if 'html' in ct else '.txt')
    salvar(nome, corpo)
    registrar(url, st, ct, corpo, nome)
    if st == 200 and 'json' in ct and spec is None:
        try:
            j = json.loads(corpo)
            if 'paths' in j:
                spec = j
        except Exception:
            pass
    time.sleep(0.5)

# procura links de openapi dentro do HTML da documentação
if spec is None:
    import re
    for f in sorted(os.listdir(OUT)):
        if f.endswith('.html'):
            for m in re.findall(rb'["\'](/[^"\']*(?:openapi|api-docs|swagger)[^"\']*\.json)["\']', open(os.path.join(OUT, f), 'rb').read()):
                url = BASE + m.decode()
                st, ct, corpo = get(url)
                registrar(url, st, ct, corpo, 'doc_achado.json')
                salvar('doc_achado.json', corpo)
                try:
                    j = json.loads(corpo)
                    if 'paths' in j:
                        spec = j
                        break
                except Exception:
                    pass
        if spec:
            break

# 2) amostra de cada recurso
if spec:
    salvar('openapi.json', json.dumps(spec, ensure_ascii=False, indent=1).encode())
    servidor = (spec.get('servers') or [{'url': ''}])[0].get('url', '')
    raiz = servidor if servidor.startswith('http') else BASE + servidor
    resumo = []
    for caminho, ops in spec['paths'].items():
        op = ops.get('get')
        if not op:
            continue
        params = op.get('parameters', [])
        nomes = [p.get('name') for p in params]
        resumo.append({'caminho': caminho, 'resumo': op.get('summary', ''), 'parametros': [(p.get('name'), p.get('in'), p.get('required', False)) for p in params]})
        if '{' in caminho:
            continue
        q = {}
        for p in params:
            n = (p.get('name') or '')
            nl = n.lower()
            if 'pagina' in nl or nl in ('page', 'pag'):
                q[n] = 1 if 'tamanho' not in nl else 5
            if 'tamanho' in nl or nl in ('size', 'limit', 'limite', 'per_page'):
                q[n] = 5
            if nl in ('uf', 'sg_uf', 'uf_principal', 'siglauf', 'sigla_uf'):
                q[n] = 'BA'
        obrig = [p.get('name') for p in params if p.get('required') and p.get('name') not in q]
        if obrig:
            resumo[-1]['pulado'] = 'parâmetros obrigatórios: ' + ', '.join(obrig)
            continue
        url = raiz.rstrip('/') + caminho + ('?' + urllib.parse.urlencode(q) if q else '')
        st, ct, corpo = get(url, 300_000)
        nome = 'amostra_' + caminho.strip('/').replace('/', '_')[:60] + '.json'
        salvar(nome, corpo)
        registrar(url, st, ct, corpo, nome)
        time.sleep(1)
    salvar('recursos.json', json.dumps(resumo, ensure_ascii=False, indent=1).encode())
else:
    print('não achei a especificação OpenAPI; ver doc_*.html', flush=True)

salvar('log.json', json.dumps(log, ensure_ascii=False, indent=1).encode())
