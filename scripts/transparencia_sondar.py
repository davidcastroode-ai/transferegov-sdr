"""Sondagem (só leitura) das bases de download do Portal da Transparência.
Para cada base: descobre desde quando há arquivo, baixa uma amostra, lista os arquivos do zip,
as colunas e quantas linhas são das UGs da SDR (ou do órgão MAPA).
Uso: python scripts/transparencia_sondar.py PASTA_SAIDA
"""
import csv, io, json, os, sys, time, urllib.request, zipfile

SAIDA = sys.argv[1] if len(sys.argv) > 1 else 'saida'
os.makedirs(SAIDA, exist_ok=True)
UGS = {'130010', '130141', '130255', '135098', '420013'}
BASE = 'https://portaldatransparencia.gov.br/download-de-dados/'
UA = {'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36', 'Accept': '*/*'}
LOG = []
csv.field_size_limit(10**9)


def log(m):
    m = time.strftime('%H:%M:%S') + '  ' + m
    print(m, flush=True)
    LOG.append(m)


def pedir(url, metodo='GET', limite=None, tentativas=8):
    # o Portal responde 202 ("preparando o arquivo") e só depois redireciona para o zip: espera e tenta de novo
    for t in range(tentativas):
        req = urllib.request.Request(url, headers=UA, method=metodo)
        with urllib.request.urlopen(req, timeout=300) as r:
            final = r.geturl()
            tam = r.headers.get('Content-Length')
            if r.status == 202 and t < tentativas - 1:
                log(f'    202 (preparando) · nova tentativa em 20 s · {url}')
                time.sleep(20)
                continue
            if metodo == 'HEAD':
                return r.status, final, tam, None
            dados = r.read() if limite is None else r.read(limite)
            return r.status, final, tam, dados


def existe(url):
    try:
        st, final, tam, _ = pedir(url, 'HEAD', tentativas=1)
        return st == 200, final, tam
    except Exception as e:
        try:  # alguns servidores não aceitam HEAD
            st, final, tam, d = pedir(url, 'GET', 2048, tentativas=1)
            ok = st == 200 and d[:2] == b'PK'
            return ok, final, tam
        except Exception as e2:
            return False, str(e2)[:120], None


# período de cada base: diário (AAAAMMDD), mensal (AAAAMM) ou anual (AAAA)
BASES = {
    'despesas': 'd',               # documentos: empenho, liquidação, pagamento
    'despesas-execucao': 'm',
    'orcamento-despesa': 'a',
    'compras': 'm',
    'transferencias': 'm',
    'despesas-favorecidos': 'm',
    'convenios': 'd',
}


def chave(tipo, ano, mes=1, dia=2):
    return f'{ano}' if tipo == 'a' else f'{ano}{mes:02d}' if tipo == 'm' else f'{ano}{mes:02d}{dia:02d}'


def amostra_url(base, tipo):
    # período recente que certamente existe
    if tipo == 'a':
        return BASE + base + '/2025'
    if tipo == 'm':
        return BASE + base + '/202501'
    return BASE + base + '/20250115'


def ler_zip(dados, base):
    z = zipfile.ZipFile(io.BytesIO(dados))
    info = []
    for nome in z.namelist():
        with z.open(nome) as f:
            txt = io.TextIOWrapper(f, encoding='latin-1', newline='')
            rd = csv.reader(txt, delimiter=';')
            cab = next(rd, [])
            cabN = [c.strip().upper() for c in cab]
            iug = next((i for i, c in enumerate(cabN) if 'UNIDADE GESTORA' in c and 'CÓDIGO' in c.replace('CODIGO', 'CÓDIGO')), None)
            iorg = next((i for i, c in enumerate(cabN) if ('ÓRGÃO SUPERIOR' in c or 'ORGAO SUPERIOR' in c) and 'CÓDIGO' in c.replace('CODIGO', 'CÓDIGO')), None)
            n = nSdr = nMapa = 0
            ex = []
            for row in rd:
                n += 1
                ug = row[iug].strip() if iug is not None and iug < len(row) else ''
                org = row[iorg].strip() if iorg is not None and iorg < len(row) else ''
                if ug in UGS:
                    nSdr += 1
                    if len(ex) < 3:
                        ex.append(dict(zip(cab, row)))
                if org == '22000':
                    nMapa += 1
            info.append({'arquivo': nome, 'colunas': cab, 'linhas': n, 'linhas_ugs_sdr': nSdr, 'linhas_orgao_mapa_22000': nMapa,
                         'coluna_ug': cab[iug] if iug is not None else None, 'exemplos_sdr': ex})
            log(f'  {nome}: {n} linhas · SDR {nSdr} · MAPA {nMapa} · {len(cab)} colunas')
    return info


res = {}
for base, tipo in BASES.items():
    log(f'== {base}')
    r = {'tipo': {'d': 'diário', 'm': 'mensal', 'a': 'anual'}[tipo]}
    # 1) amostra recente
    url = amostra_url(base, tipo)
    try:
        st, final, tam, dados = pedir(url)
        r['amostra'] = {'url': url, 'final': final, 'status': st, 'bytes': len(dados or b'')}
        log(f'  amostra {url} -> {st} {final} {len(dados or b"")} bytes')
        if dados and dados[:2] == b'PK':
            r['arquivos'] = ler_zip(dados, base)
        else:
            r['amostra']['inicio'] = (dados or b'')[:300].decode('latin-1', 'replace')
    except Exception as e:
        r['amostra'] = {'url': url, 'erro': str(e)[:300]}
        log(f'  amostra ERRO {e}')
    # 2) primeiro ano disponível (procura de 1995 até 2025)
    primeiro = None
    tent = []
    modelo = (r.get('amostra') or {}).get('final', '')
    per_am = amostra_url(base, tipo).rsplit('/', 1)[1]
    usa_cdn = modelo.endswith('.zip') and per_am in modelo
    for ano in range(1995, 2026):
        if not usa_cdn and ano < 2026 and len(tent) > 40: break
        cand = [chave(tipo, ano)] if tipo != 'd' else [chave(tipo, ano, 1, d) for d in (2, 3, 4, 5, 6, 7, 8)]
        if tipo == 'm':
            cand = [chave(tipo, ano, m) for m in (1, 6, 12)]
        ok = False
        for c in cand:
            o, final, tam = existe(modelo.replace(per_am, c) if usa_cdn else BASE + base + '/' + c)
            if o:
                ok = True
                tent.append([c, 'ok', tam])
                break
        if not ok:
            tent.append([str(ano), 'não'])
        if ok:
            primeiro = ano
            break
    r['primeiro_ano'] = primeiro
    r['tentativas'] = tent[-5:]
    r['modelo_arquivo'] = modelo if usa_cdn else None
    log(f'  primeiro ano com arquivo: {primeiro}')
    res[base] = r
    json.dump(res, open(os.path.join(SAIDA, 'transparencia_sondagem.json'), 'w'), ensure_ascii=False, indent=1)

open(os.path.join(SAIDA, 'log.txt'), 'w').write('\n'.join(LOG))
log('fim')
