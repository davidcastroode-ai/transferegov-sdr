"""
Robô · Orçamento por ação (Tesouro Gerencial) — lê a aba ORCAMENTO da planilha BASE ORÇAMENTO SDR.

O relatório do Tesouro Gerencial ("Orçamento SDR por ação 2026") tem uma linha por UG × ação × PO × PTRES × GND × RP
e uma coluna por item de informação (dotação inicial, suplementar, atualizada, cancelada/remanejada, provisão recebida
e concedida, destaque, crédito disponível e indisponível, empenhado, liquidado, pago).

Lê os links de config/orcamento.txt e grava PASTA/orcamento/orcamento.csv (uma linha por combinação, colunas com nome fixo).
Uso:  python scripts/orcamento.py PASTA_DE_SAIDA
"""
import csv, io, json, os, re, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ted_tesouro import na, num, baixar

AQUI = os.path.dirname(os.path.abspath(__file__))
CONFIG = os.path.join(AQUI, '..', 'config', 'orcamento.txt')

# item de informação → campo (pelo nome do item)
ITENS = [('ini', r'DOTACAO INICIAL'), ('sup', r'DOTACAO SUPLEMENTAR'), ('esp', r'DOTACAO ESPECIAL'), ('ext', r'DOTACAO EXTRAORDINARIA'),
         ('atu', r'DOTACAO ATUALIZADA'), ('canc', r'DOTACAO CANCELADA|REMANEJAD'), ('provRec', r'PROVISAO RECEBIDA'), ('provConc', r'PROVISAO CONCEDIDA'),
         ('destRec', r'DESTAQUE RECEBIDO'), ('destConc', r'DESTAQUE CONCEDIDO'), ('disp', r'CREDITO DISPONIVEL'), ('indisp', r'CREDITO INDISPONIVEL'),
         ('emp', r'EMPENHAD'), ('liq', r'LIQUIDAD'), ('pago', r'PAGAS|PAGO')]
CAMPOS_V = [k for k, _ in ITENS]
CAMPOS = ['ug', 'ug_nome', 'acao', 'acao_nome', 'po', 'po_nome', 'ptres', 'gnd', 'gnd_nome', 'rp', 'rp_nome'] + CAMPOS_V


def interpretar(linhas):
    linhas = [[c.strip() for c in l] for l in linhas]
    ih = next((i for i, l in enumerate(linhas[:40]) if any(na(c) == 'UG EXECUTORA' for c in l) and any(na(c) == 'ACAO GOVERNO' for c in l)), None)
    if ih is None:
        raise ValueError('não achei os títulos "UG Executora" e "Ação Governo"')
    H = [na(h) for h in linhas[ih]]
    # nomes dos itens: na linha de baixo (o Tesouro Gerencial põe o código numa linha e o nome na seguinte)
    N = [na(h) for h in linhas[ih + 1]] if ih + 1 < len(linhas) else []
    col = lambda rx: next((i for i, h in enumerate(H) if re.search(rx, h)), None)
    cUG, cAc, cPO, cPT, cGND, cRP = col(r'^UG EXECUTORA'), col(r'^ACAO GOVERNO'), col(r'^PLANO ORCAMENTARIO'), col(r'^PTRES'), col(r'^GRUPO DESPESA'), col(r'^RESULTADO PRIMARIO')
    itens = {}
    for i in range(len(H)):
        rot = (N[i] if i < len(N) else '') or H[i]
        for k, rx in ITENS:
            if re.search(rx, rot) and k not in itens.values() and i not in itens:
                itens[i] = k
                break
    if not itens:
        raise ValueError('não achei as colunas dos itens de informação')
    g = lambda l, i: l[i].strip() if i is not None and i < len(l) else ''
    out = []
    for l in linhas[ih + 2:]:
        ug = g(l, cUG)
        if not re.fullmatch(r'\d{6}', ug):
            continue
        # o PO vem em várias colunas (UO, função, subfunção, programa, ação, PO, nome): o código do PO é a penúltima
        po_cols = [i for i in range(cPO, cPT)] if cPO is not None and cPT is not None else []
        po, po_nome = (g(l, po_cols[-2]), g(l, po_cols[-1])) if len(po_cols) >= 2 else ('', '')
        o = {'ug': ug, 'ug_nome': g(l, cUG + 1), 'acao': g(l, cAc), 'acao_nome': g(l, cAc + 1), 'po': po, 'po_nome': po_nome,
             'ptres': g(l, cPT), 'gnd': g(l, cGND), 'gnd_nome': g(l, cGND + 1), 'rp': g(l, cRP), 'rp_nome': g(l, cRP + 1)}
        # a planilha do Google tira os zeros à esquerda (PO 0003 vira 3; ação 0181 vira 181)
        for k_ in ('acao', 'po'):
            if re.fullmatch(r'\d{1,3}', o[k_]):
                o[k_] = o[k_].zfill(4)
        for i, k in itens.items():
            v = num(g(l, i))
            o[k] = v if v is not None else 0.0
        for k in CAMPOS_V:
            o.setdefault(k, 0.0)
        out.append(o)
    return out


def ler(pasta_saida):
    if not os.path.exists(CONFIG):
        print('Orçamento: sem config/orcamento.txt', flush=True)
        return []
    urls = [l.strip() for l in open(CONFIG, encoding='utf-8') if l.strip() and not l.strip().startswith('#')]
    todas, info = [], []
    for u in urls:
        try:
            out = interpretar(list(csv.reader(io.StringIO(baixar(u)))))
            todas += out
            info.append({'link': u, 'linhas': len(out), 'ok': True})
            print(f'Orçamento: {len(out)} linhas em {u[-60:]}', flush=True)
        except Exception as e:
            info.append({'link': u, 'erro': str(e)[:200], 'ok': False})
            print(f'Orçamento: erro em {u[-60:]}: {e}', flush=True)
    os.makedirs(os.path.join(pasta_saida, 'orcamento'), exist_ok=True)
    with open(os.path.join(pasta_saida, 'orcamento', 'orcamento.csv'), 'w', encoding='utf-8', newline='') as fh:
        w = csv.DictWriter(fh, fieldnames=CAMPOS)
        w.writeheader()
        w.writerows(todas)
    json.dump({'gerado_em': time.strftime('%d/%m/%Y %H:%M'), 'fontes': info, 'linhas': len(todas)},
              open(os.path.join(pasta_saida, 'orcamento', 'orcamento.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    return todas


if __name__ == '__main__':
    ler(sys.argv[1] if len(sys.argv) > 1 else 'saida')
