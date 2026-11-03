"""Data de atualização de cada base do painel (03/11/2026).

A cada rodada o robô confere o conteúdo de cada base (arquivos do robô e abas publicadas das planilhas da equipe).
A data só muda quando o conteúdo muda: se nada foi alterado, fica a data da última atualização real.
Saída: datas_bases.json · o painel mostra a data no cabeçalho de cada menu.
"""
import csv, glob, gzip, hashlib, io, json, os, re, sys, urllib.request
from datetime import datetime, timedelta, timezone

SAIDA = sys.argv[1] if len(sys.argv) > 1 else 'saida'
REPO = os.environ.get('GITHUB_REPOSITORY', 'davidcastroode-ai/transferegov-sdr')
AGORA = datetime.now(timezone.utc) - timedelta(hours=3)
AGORA_T = AGORA.strftime('%d/%m/%Y %H:%M')
PUB = 'https://docs.google.com/spreadsheets/d/e/2PACX-1vRyLjeoCobYSRx7o3tiZ7fvj4-FhvKnGiSVxoA8l6yD2CqfJsUidxWN00jLuFpBMrFL6MesSdYuWnrb/pub?gid={}&single=true&output=csv'
# colunas que mudam todo dia sem o dado mudar (data da consulta, dias para vencer...)
VOLATIL = re.compile(r'consultad|gerad|^dias|dias a vencer|dias para|dias sem|ultima atualiza|última atualiza|atualizado em|hoje|lido em', re.I)

BASES = {
    # robô
    'transferegov': ('Transferegov · dados abertos', 'robô', ['instrumentos.csv', 'propostas.csv', 'desembolsos.csv', 'empenhos.csv', 'historico_situacao.csv']),
    'obras':        ('Obrasgov · obras e medições', 'robô', ['painel_obras.csv']),
    'contratos':    ('Contratos.gov.br · API', 'robô', ['contratos_api_ctr.csv', 'contratos_api_emp.csv', 'contratos_api_fat.csv', 'contratos_api_cro.csv', 'contratos_api_pag.csv']),
    'ted_api':      ('TED · API do Transferegov', 'robô', ['ted/ted_controle.csv', 'ted/ted_ajustes.csv']),
    'ted_tesouro':  ('TED · Tesouro Gerencial (NC, PF, NE)', 'robô', ['ted/ted_tesouro_nc.csv', 'ted/ted_tesouro_pf.csv', 'ted/ted_tesouro_ne.csv']),
    'orcamento':    ('Orçamento · BASE ORÇAMENTO SDR (Tesouro Gerencial)', 'robô', ['orcamento/orcamento.csv']),
    'emendas':      ('Emendas · SIOP', 'robô', ['emendas_siop.json']),
    # planilhas da equipe (abas publicadas)
    'pl_base':      ('Base Contratos (CEPLAC)', 'planilha', [PUB.format('668450794')]),
    'pl_despesas':  ('Novas despesas previstas', 'planilha', [PUB.format('1766013716'), PUB.format('1817651910')]),
    'pl_siop':      ('SIOP SDR (departamentos e PLOA)', 'planilha', [PUB.format('719441659')]),
    'pl_parc':      ('BASE GERAL Convênio e Termo', 'planilha', ['https://docs.google.com/spreadsheets/d/e/2PACX-1vR8PRRQUHy70JJBiexPLl9_A15v9ypqZWcVCr5LV4yxQwGJWnCEvuAP9QORGGRJTNWqCAJx_oHkSW4q/pub?gid=273934927&single=true&output=csv']),
    'pl_prop':      ('BASE PROPOSTAS', 'planilha', ['https://docs.google.com/spreadsheets/d/1f6_clsjTNDAkfTYGLLR3IcluPas1wAVfBXQh2qrxqhY/gviz/tq?tqx=out:csv&gid=1661663693', PUB.format('1382020454')]),
    'pl_conv':      ('BASE CONV. E TERMO (420013)', 'planilha', ['https://docs.google.com/spreadsheets/d/1f6_clsjTNDAkfTYGLLR3IcluPas1wAVfBXQh2qrxqhY/gviz/tq?tqx=out:csv&gid=668349515', PUB.format('1956761686')]),
    'pl_ted':       ('TED equipe (vigentes, dispensa, prestação de contas, aprovados)', 'planilha', [PUB.format(g) for g in ('195685963', '2018973768', '1576888866', '1791002980')]),
}


def baixar(url):
    req = urllib.request.Request(url + ('&' if '?' in url else '?') + 'cb=' + AGORA.strftime('%H%M%S'), headers={'User-Agent': 'robo-sdr-mapa'})
    with urllib.request.urlopen(req, timeout=120) as r:
        return r.read().decode('utf-8', 'replace')


def ler_arquivo(rel):
    p = os.path.join(SAIDA, rel)
    if os.path.exists(p):
        return open(p, encoding='utf-8', errors='replace').read()
    if os.path.exists(p + '.gz'):
        with gzip.open(p + '.gz', 'rt', encoding='utf-8', errors='replace') as f:
            return f.read()
    return None


def limpar_json(o):
    if isinstance(o, dict):
        return {k: limpar_json(v) for k, v in o.items() if not re.search(r'gerad|atualiz|consult|lido', k, re.I)}
    if isinstance(o, list):
        return [limpar_json(v) for v in o]
    return o


def impressao(txt, nome):
    """hash do conteúdo sem as colunas voláteis · devolve (hash, linhas)"""
    if nome.endswith('.json'):
        try:
            return hashlib.sha256(json.dumps(limpar_json(json.loads(txt)), sort_keys=True).encode()).hexdigest(), 0
        except Exception:
            return hashlib.sha256(txt.encode()).hexdigest(), 0
    rows = list(csv.reader(io.StringIO(txt)))
    if not rows:
        return hashlib.sha256(b'').hexdigest(), 0
    cab = rows[0]
    fica = [i for i, h in enumerate(cab) if not VOLATIL.search(h or '')]
    h = hashlib.sha256()
    for r in rows:
        h.update(('\x1f'.join(r[i] if i < len(r) else '' for i in fica) + '\n').encode())
    return h.hexdigest(), max(0, len(rows) - 1)


def anterior():
    try:
        url = f'https://raw.githubusercontent.com/{REPO}/dados/datas_bases.json?cb={AGORA.strftime("%H%M%S")}'
        return json.loads(urllib.request.urlopen(url, timeout=60).read().decode('utf-8')).get('bases', {})
    except Exception as e:
        print('sem datas anteriores:', e)
        return {}


def main():
    ant = anterior()
    out = {}
    for k, (nome, tipo, fontes) in BASES.items():
        h = hashlib.sha256(); linhas = 0; ok = True
        for f in fontes:
            txt = None
            try:
                txt = baixar(f) if f.startswith('http') else ler_arquivo(f)
            except Exception as e:
                print(f'{k}: não leu {f[:90]} · {e}')
            if txt is None or (f.startswith('http') and txt.lstrip().startswith('<')):
                if tipo == 'planilha' and k in ('pl_prop', 'pl_conv') and f is fontes[0]:
                    continue   # gviz da planilha nova falhou: vale o link publicado (próxima fonte)
                ok = False; continue
            hx, n = impressao(txt, f.split('?')[0])
            h.update(hx.encode()); linhas += n
            if k in ('pl_prop', 'pl_conv'):
                break       # a primeira fonte que respondeu basta
        hx = h.hexdigest()
        a = ant.get(k) or {}
        if not ok and a:
            out[k] = dict(a, conferido=AGORA_T, ok=False)        # não conseguiu ler hoje: fica a data anterior
        elif not ok:
            out[k] = {'nome': nome, 'tipo': tipo, 'atualizado': None, 'conferido': AGORA_T, 'ok': False}
        else:
            mudou = a.get('hash') != hx
            out[k] = {'nome': nome, 'tipo': tipo, 'hash': hx, 'linhas': linhas, 'ok': True, 'conferido': AGORA_T,
                      'atualizado': AGORA_T if (mudou or not a.get('atualizado')) else a['atualizado']}
        print(f"{k:13} {'mudou' if out[k].get('atualizado') == AGORA_T else 'igual'} · {out[k].get('atualizado')} · {linhas} linhas{'' if ok else ' · FALHOU'}")
    # Transferegov: data em que o governo carregou os dados (quando o robô tem)
    try:
        at = json.load(open(os.path.join(SAIDA, 'atualizacao.json'), encoding='utf-8'))
        if at.get('data_carga'):
            out['transferegov']['carga'] = at['data_carga']
        if at.get('falha_download'):
            out['transferegov']['falha'] = at['falha_download'].get('em')
    except Exception:
        pass
    json.dump({'gerado_em': AGORA_T, 'bases': out}, open(os.path.join(SAIDA, 'datas_bases.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)


if __name__ == '__main__':
    main()
