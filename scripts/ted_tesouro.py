"""
Robô TED · leitura do relatório do Tesouro Gerencial (SIAFI) colado na planilha BASE TED.

De onde lê: os links de CSV publicados que estiverem em config/ted_tesouro.txt (um por linha; linhas com # são ignoradas).
Cada link é uma aba publicada (Arquivo › Compartilhar › Publicar na Web › aba › CSV).

O relatório pode vir em dois formatos, o robô reconhece sozinho:
  • LARGO   : uma linha por TED e uma coluna por valor (ex.: "A comprovar", "Comprovado", "A repassar"...)
  • COMPRIDO: uma linha por TED × conta contábil, com uma coluna "Conta contábil" e uma coluna de saldo
As linhas de título e filtro que o Tesouro Gerencial põe no topo são puladas, as células mescladas
(TED só na primeira linha do grupo) são repetidas para baixo e as linhas de "Total" são ignoradas.

Uso:  python scripts/ted_tesouro.py PASTA_DE_SAIDA     (grava PASTA/ted/ted_tesouro.csv e ted_tesouro.json)
"""
import csv, io, json, os, re, sys, time, unicodedata, urllib.request
from collections import OrderedDict

AQUI = os.path.dirname(os.path.abspath(__file__))
CONFIG = os.path.join(AQUI, '..', 'config', 'ted_tesouro.txt')


def na(t):
    return re.sub(r'\s+', ' ', unicodedata.normalize('NFKD', str(t or '')).encode('ascii', 'ignore').decode().upper()).strip()


def num(v):
    """'1.234,56' · 'R$ 1.234,56' · '(1.234,56)' · '1234.56' · '1.234,56-' → float; None se não for número"""
    t = str(v or '').strip().replace('R$', '').replace('\xa0', '').replace(' ', '')
    if not t or t in ('-', '—'):
        return None
    neg = t.startswith('(') and t.endswith(')') or t.endswith('-') or t.startswith('-')
    t = t.strip('()-')
    if not re.fullmatch(r'[\d.,]+', t):
        return None
    if ',' in t:
        t = t.replace('.', '').replace(',', '.')
    elif t.count('.') > 1:
        t = t.replace('.', '')
    try:
        x = float(t)
    except ValueError:
        return None
    return -x if neg else x


def chave_ted(v):
    """nº do TED como na API: '0984760' → '984760'; '7aaaqn' → '7AAAQN'; '984760 - IFMT…' → '984760'"""
    t = na(v)
    if not t or t in ('-', 'TOTAL', 'NAO SE APLICA', 'SEM INFORMACAO'):
        return ''
    t = re.split(r'\s+-\s+|\s+', t)[0]
    t = re.sub(r'[^0-9A-Z]', '', t)
    return t.lstrip('0') if t.isdigit() else t


# o que cada coluna (ou conta contábil) significa, pelas palavras do título
# o que cada coluna (ou conta contábil) significa, pelas palavras do título (contas de controle de TED do Tesouro Gerencial)
METRICAS = [(None, r'TRANSFERENCIAS FINANCEIRAS|ADIANTAMENTO|CONTROLE DE PROGRAMACAO|RP AUTORIZADO|RESTOS A PAGAR|RECEBIMENTO DE REPASSE|LIBERACAO DE REPASSE|REPASSE LIBERADO'),
            ('fir', r'FIRMAD|PACTUAD|VALOR (DO|TOTAL DO) TED|VALOR GLOBAL|CELEBRAD|TRANSFERENCIA - VALOR'),
            ('aComp', r'A COMPROVAR|PENDENTE DE COMPROVA'),
            ('aApr', r'A APROVAR'),
            ('comp', r'COMPROVAD'),
            ('apr', r'APROVAD|CONCLUID'),
            ('aRep', r'A REPASSAR|A LIBERAR|A TRANSFERIR|A DESCENTRALIZAR'),
            ('aRec', r'A RECEBER'),
            ('rep', r'REPASSAD[OA]S?$|VALOR REPASSADO|TRANSFERID'),
            ('dev', r'DEVOLV|DEVOLUC|NAO REPASSADO|ANULAD')]


def metrica(titulo):
    t = na(titulo)
    for k, rx in METRICAS:
        if re.search(rx, t):
            return k
    return ''


def baixar(url):
    for t in range(4):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers={'User-Agent': 'robo-sdr-mapa'}), timeout=120) as r:
                txt = r.read().decode('utf-8-sig', 'replace')
            if txt.lstrip().startswith('<'):
                raise ValueError('o link não devolveu CSV (a aba está publicada como CSV?)')
            return txt
        except Exception as e:
            err = e
            time.sleep(3 * (t + 1))
    raise err


def interpretar(linhas, origem=''):
    """devolve {ted: {...}} a partir das linhas de um CSV do Tesouro Gerencial"""
    linhas = [[c.strip() for c in l] for l in linhas]
    # 1. linha de títulos: a primeira (até a 40ª) que tem uma coluna de TED e é seguida de linhas com números
    rx_ted = r'\bTED\b|TRANSFERENCIA|TERMO DE EXECUCAO|INSTRUMENTO|N[OUº]?\s*DO?\s*TED'
    ih = None
    for i, l in enumerate(linhas[:40]):
        if sum(1 for c in l if c) >= 2 and any(re.search(rx_ted, na(c)) for c in l):
            ih = i
            break
    if ih is None:
        raise ValueError('não achei a coluna do nº do TED nos títulos')
    H = linhas[ih]
    # o Tesouro Gerencial às vezes põe o título da métrica numa linha e "Saldo - R$" na de baixo: junta as duas
    if ih + 1 < len(linhas) and any(re.search(r'SALDO|R\$|VALOR', na(c)) for c in linhas[ih + 1]) and not any(num(c) is not None for c in linhas[ih + 1]):
        H = [(a + ' ' + b).strip() for a, b in zip(H + [''] * len(linhas[ih + 1]), linhas[ih + 1] + [''] * len(H))]
        ih += 1
    Hn = [na(h) for h in H]
    corpo = [l + [''] * (len(H) - len(l)) for l in linhas[ih + 1:]]
    # 2. papéis das colunas
    cT = next(i for i, h in enumerate(Hn) if re.search(rx_ted, h))
    def acha(rx, evita=None):
        return next((i for i, h in enumerate(Hn) if re.search(rx, h) and i != cT and not (evita and re.search(evita, h))), None)
    # no Tesouro Gerencial a "UG Executora" é a UG da SDR que registra o TED (lado que descentraliza)
    cUe = acha(r'UG EXECUTORA COD|UG EXECUTORA$|UG.*(EMIT|RESP|CONCED|DESCENTRALIZADORA|ORIGEM)|EMITENTE|CONCEDENTE|DESCENTRALIZADORA')
    cUf = acha(r'UG.*(FAVOR|BENEF|RECEB|DESCENTRALIZADA|DESTINO)|FAVORECID|BENEFICIARI|DESCENTRALIZADA|CONVENENTE', r'UG EXECUTORA')
    cNomeF = acha(r'CONVENENTE NOM|FAVORECID.*NOM|BENEFICIARI.*NOM|DESCENTRALIZADA.*NOM')
    if cNomeF == cUf:
        cNomeF = None
    cSit = acha(r'SITUACAO')
    cIni = acha(r'INICIO VIG')
    cFim = acha(r'FINAL VIG|FIM VIG')
    cObj = acha(r'JUSTIFICATIVA|OBJETO')
    cAno = acha(r'^ANO|EXERCICIO|ANO ')
    cProc = acha(r'PROCESSO')
    # colunas de valor: as que têm número na maioria das linhas preenchidas
    def numerica(i):
        vs = [l[i] for l in corpo if l[i] and l[i].strip() not in ('-', '—') and not na(l[i]).startswith('TOTAL')]
        return len(vs) > 0 and sum(1 for v in vs if num(v) is not None) >= 0.8 * len(vs)
    # conta contábil (formato comprido): coluna de texto cujo título fala de conta
    cConta = next((i for i, h in enumerate(Hn) if re.search(r'CONTA', h) and i not in (cT, cUe, cUf, cAno, cProc) and not numerica(i)), None)
    papeis = {cT, cUe, cUf, cConta, cAno, cProc, cNomeF, cSit, cIni, cFim, cObj} - {None}
    cVal = [i for i in range(len(H)) if i not in papeis and numerica(i)]
    cTxt = [i for i in range(len(H)) if i not in papeis and i not in cVal]
    if not cVal:
        raise ValueError('não achei colunas de valor')
    comprido = cConta is not None
    # 3. linhas (repetindo para baixo as células mescladas das dimensões)
    out, ant = OrderedDict(), {}
    dims = [c for c in (cT, cUe, cUf, cConta, cAno, cProc, cNomeF, cSit, cIni, cFim, cObj) if c is not None] + cTxt
    for l in corpo:
        if not any(l):
            continue
        if any(na(c).startswith('TOTAL') for c in l[:max(dims) + 1]):
            continue
        for c in dims:
            if l[c]:
                ant[c] = l[c]
            else:
                l[c] = ant.get(c, '')
        k = chave_ted(l[cT])
        if not k:
            continue
        o = out.setdefault(k, {'ted': k, 'ted_txt': l[cT], 'ug_emit': '', 'ug_fav': '', 'ano': '', 'processo': '', 'nome_fav': '',
                               'fir': None, 'nc': None, 'rep': None, 'aRep': None, 'aComp': None, 'comp': None, 'dev': None, 'aApr': None, 'apr': None, 'aRec': None,
                               'situacao': '', 'ini': '', 'fim': '', 'objeto': '',
                               'contas': OrderedDict(), 'origem': origem})
        ug = lambda c: re.match(r'\s*(\d{6})', l[c]).group(1) if c is not None and re.match(r'\s*(\d{6})', l[c]) else ''
        o['ug_emit'] = o['ug_emit'] or ug(cUe)
        o['ug_fav'] = o['ug_fav'] or ug(cUf)
        if not o['nome_fav']:
            if cNomeF is not None:
                o['nome_fav'] = l[cNomeF][:120]
            elif cUf is not None:
                o['nome_fav'] = re.sub(r'^\s*\d{6}\s*-?\s*', '', l[cUf])[:120]
        for campo, c in (('situacao', cSit), ('ini', cIni), ('fim', cFim), ('objeto', cObj)):
            if c is not None and not o.get(campo):
                o[campo] = l[c][:600]
        if cAno is not None and not o['ano']:
            m = re.search(r'20\d\d', l[cAno])
            if m:
                o['ano'] = m.group(0)
        if cProc is not None:
            o['processo'] = o['processo'] or l[cProc]
        if not o['ano']:
            m = re.match(r'(20\d\d)', o['ted'])
            if m:
                o['ano'] = m.group(1)
        itens = [(l[cConta] + (' · ' + H[c] if len(cVal) > 1 else ''), c) for c in cVal] if comprido else [(H[c], c) for c in cVal]
        for rot, c in itens:
            v = num(l[c])
            if v is None:
                continue
            o['contas'][rot] = round(o['contas'].get(rot, 0) + v, 2)
            m = metrica(rot)
            if m == 'fir':      # "Valor da transferência" e "Valores firmados" são o mesmo número: fica o maior
                o['fir'] = max(o['fir'] or 0, v)
            elif m:
                o[m] = round((o.get(m) or 0) + v, 2)
    for o in out.values():
        # repassado = firmado − a repassar (o Tesouro não tem uma conta só de "repassado")
        if o.get('rep') is None and o['fir'] is not None and o['aRep'] is not None:
            o['rep'] = round(o['fir'] - o['aRep'], 2)
    return out


def ler(pasta_saida):
    """lê os links de config/ted_tesouro.txt e grava ted/ted_tesouro.csv + ted_tesouro.json; devolve o dicionário"""
    if not os.path.exists(CONFIG):
        print('Tesouro TED: sem config/ted_tesouro.txt', flush=True)
        return {}
    urls = [l.strip() for l in open(CONFIG, encoding='utf-8') if l.strip() and not l.strip().startswith('#')]
    tudo, info = OrderedDict(), []
    for u in urls:
        try:
            linhas = list(csv.reader(io.StringIO(baixar(u))))
            d = interpretar(linhas, origem=u[-40:])
            for k, o in d.items():
                if k in tudo:   # o mesmo TED em duas abas: soma as contas
                    for rot, v in o['contas'].items():
                        tudo[k]['contas'][rot] = round(tudo[k]['contas'].get(rot, 0) + v, 2)
                    for m in ('nc', 'rep', 'aRep', 'aComp', 'aApr', 'comp', 'apr', 'aRec', 'dev'):
                        if o[m] is not None:
                            tudo[k][m] = round((tudo[k][m] or 0) + o[m], 2)
                else:
                    tudo[k] = o
            info.append({'link': u, 'teds': len(d), 'ok': True})
            print(f'Tesouro TED: {len(d)} TEDs em {u[-60:]}', flush=True)
        except Exception as e:
            info.append({'link': u, 'erro': str(e)[:200], 'ok': False})
            print(f'Tesouro TED: erro em {u[-60:]}: {e}', flush=True)
    os.makedirs(os.path.join(pasta_saida, 'ted'), exist_ok=True)
    contas = list(OrderedDict.fromkeys(r for o in tudo.values() for r in o['contas']))
    campos = ['ted', 'ted_txt', 'ug_emit', 'ug_fav', 'nome_fav', 'ano', 'processo', 'situacao', 'ini', 'fim', 'objeto',
              'fir', 'nc', 'rep', 'aRep', 'aComp', 'aApr', 'comp', 'apr', 'aRec', 'dev']
    with open(os.path.join(pasta_saida, 'ted', 'ted_tesouro.csv'), 'w', encoding='utf-8', newline='') as fh:
        w = csv.writer(fh)
        w.writerow(campos + contas)
        for o in tudo.values():
            w.writerow([o[c] if o[c] is not None else '' for c in campos] + [o['contas'].get(c, '') for c in contas])
    json.dump({'gerado_em': time.strftime('%d/%m/%Y %H:%M'), 'fontes': info, 'teds': len(tudo), 'contas': contas},
              open(os.path.join(pasta_saida, 'ted', 'ted_tesouro.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    return tudo


if __name__ == '__main__':
    ler(sys.argv[1] if len(sys.argv) > 1 else 'saida')
