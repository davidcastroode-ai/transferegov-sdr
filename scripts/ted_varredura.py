"""Varredura de consistência do TED (03/11/2026).

Procura, TED por TED, dados que não fecham entre as fontes e dados de um TED que aparecem em outro:
situação × vigência, RP × emenda, ação, fim da vigência, valor firmado, processo, documentos (NC, PF, NE)
que citam outro TED ou aparecem em mais de uma ficha, e totais incoerentes (NC > firmado, PF > NC...).
Saída: ted/ted_varredura.csv (um problema por linha) e ted/ted_varredura.json (resumo).
"""
import csv, json, os, re, sys
from collections import defaultdict, Counter
from datetime import date, datetime

SAIDA = sys.argv[1] if len(sys.argv) > 1 else 'saida'
P = os.path.join(SAIDA, 'ted')
HOJE = date.today()


def ler(n):
    p = os.path.join(P, n)
    return list(csv.DictReader(open(p, encoding='utf-8'))) if os.path.exists(p) else []


def num(v):
    try:
        return float(str(v).replace(',', '.')) if str(v).strip() not in ('', '-', 'None') else 0.0
    except ValueError:
        return 0.0


def dt(v):
    v = str(v or '').strip()
    m = re.match(r'(\d{2})/(\d{2})/(\d{4})', v)
    if m:
        return date(int(m[3]), int(m[2]), int(m[1]))
    if re.fullmatch(r'\d{5}(\.0)?', v):
        return date.fromordinal(date(1899, 12, 30).toordinal() + int(float(v)))
    return None


def br(d):
    return d.strftime('%d/%m/%Y') if d else ''


def proc(v):
    m = re.search(r'(\d{5})\.?(\d{6})/?(\d{4})-?(\d{2})', str(v or ''))
    return f'{m[1]}.{m[2]}/{m[3]}-{m[4]}' if m else ''


def rp(v):
    m = re.search(r'(\d)', str(v or ''))
    return 'RP ' + m[1] if m else ''


ID = re.compile(r'\b(9\d{5}|[1-9]AA[A-Z0-9]{3}|6\d{5})\b')
SDR = ('420013', '130141', '130010', '130255', '135098')
GRAV = {'alta': 0, 'média': 1, 'baixa': 2}


def main():
    ficha = json.load(open(os.path.join(P, 'ted_ficha.json'), encoding='utf-8')) if os.path.exists(os.path.join(P, 'ted_ficha.json')) else {}
    base = {r['Nº TED']: r for r in ler('ted_base_atualizada.csv')}
    api = {r['Nº TED (SIAFI)']: r for r in ler('ted_planilha.csv') if r['Nº TED (SIAFI)']}
    ctl = {r['ted']: r for r in ler('ted_equipe.csv')}
    tes = {r['ted']: r for r in ler('ted_tesouro.csv')}
    nc = ler('ted_tesouro_nc.csv')
    cad = {r['Nº TED']: r for r in ler('ted_cadastro.csv')}
    todos = set(ficha) | set(cad) | set(ctl)
    conhecidos = set(todos) | set(api) | set(tes)
    rpNC, acNC = defaultdict(set), defaultdict(set)
    for r in nc:
        if r['ted']:
            if re.fullmatch(r'RP \d', r['rp'] or ''):
                rpNC[r['ted']].add(r['rp'])
            if re.fullmatch(r'[0-9A-Z]{4}', r['acao'] or ''):
                acNC[r['ted']].add(r['acao'])
    P_ = []

    def prob(ted, cat, grav, achado, fontes, sugestao):
        b = base.get(ted, {})
        ugE = (b.get('UG descentralizadora') or (cad.get(ted) or {}).get('UG descentralizadora') or (ficha.get(ted) or {}).get('ugd') or (ctl.get(ted) or {}).get('UG responsável') or '').strip()
        P_.append({'Nº TED': ted, 'UG emitente': ugE, 'Departamento': (ctl.get(ted) or {}).get('Departamento', ''),
                   'Unidade': b.get('Unidade descentralizada') or (ctl.get(ted) or {}).get('Unidade', ''),
                   'Categoria': cat, 'Gravidade': grav, 'O que foi encontrado': achado, 'Fontes': fontes, 'O que fazer': sugestao})

    # ---------- documentos em mais de uma ficha ----------
    donos = {k: defaultdict(set) for k in ('NC', 'PF', 'NE')}
    for t, f in ficha.items():
        for x in f.get('ncs') or []:
            donos['NC'][(x[2], x[0])].add(t)
        for x in f.get('pfs') or []:
            donos['PF'][(x[2], x[0])].add(t)
        for x in f.get('nes') or []:
            donos['NE'][x[0]].add(t)

    for t in sorted(todos):
        f, b, a, c, ts, cd = ficha.get(t, {}), base.get(t, {}), api.get(t, {}), ctl.get(t, {}), tes.get(t, {}), cad.get(t, {})
        # 1. situação × vigência
        fins = {'API': dt(a.get('Fim da vigência')), 'Controle': dt(c.get('Fim (controle)')), 'Tesouro': dt(ts.get('fim')), 'Painel': dt(b.get('Fim da vigência (painel)'))}
        fim = fins['Controle'] or fins['API'] or fins['Tesouro'] or fins['Painel']
        vig = c.get('Aba do controle') == 'TED vigente' or a.get('Situação do termo') == 'EM_EXECUCAO' or (f.get('fase') or '').lower().startswith('em execu')
        if vig and fim and fim < HOJE:
            prob(t, 'Situação × vigência', 'alta', f'aparece como vigente/em execução, mas a vigência terminou em {br(fim)} ({(HOJE - fim).days} dia(s))',
                 f"controle: {c.get('Aba do controle') or '—'} · API: {a.get('Situação do termo') or '—'} · painel: {f.get('fase') or '—'}",
                 'mover para Prestação de contas no controle ou registrar a prorrogação (termo aditivo)')
        # 2. fim da vigência divergente
        # 04/11/2026: a API do Transferegov está desatualizada · as comparações ficam só entre Tesouro e controle da equipe
        fs = {k: v for k, v in fins.items() if v and k not in ('Painel', 'API')}
        if fs and (max(fs.values()) - min(fs.values())).days > 1:   # 1 dia de diferença é só a contagem (Tesouro conta o dia seguinte)
            prob(t, 'Fim da vigência divergente', 'média', ' · '.join(f'{k} {br(v)}' for k, v in fs.items()), 'controle, Tesouro',
                 'conferir o fim correto (último aditivo) e acertar a fonte errada')
        # 3. RP × emenda
        rps = {'Controle': rp(c.get('RP')), 'Tesouro (NC)': ' / '.join(sorted(rpNC.get(t, [])))}
        rps = {k: v for k, v in rps.items() if v}
        # TED pode ter mais de um RP (ex.: RP 2 + emenda RP 7): só acusa quando o RP da planilha não aparece em NENHUMA NC
        rpC, rpT = set(re.findall(r'RP \d', rps.get('Controle', ''))), set(rpNC.get(t, []))
        if rpC and rpT and not (rpC & rpT):
            prob(t, 'RP divergente', 'alta', ' · '.join(f'{k}: {v}' for k, v in rps.items()), 'controle, NC do Tesouro (pelo PTRES)',
                 'o RP da planilha não aparece em nenhuma NC: vale o da NC do Tesouro; corrigir no controle')
        # 4. ação divergente
        acs = {'Controle': (c.get('Ação') or '').strip(), 'NC': ' / '.join(sorted(acNC.get(t, [])))}
        acs = {k: v for k, v in acs.items() if v}
        norm_ = lambda v: frozenset(re.findall(r'[0-9A-Z]{4}', v.upper()))
        decl = frozenset().union(*[norm_(v) for k, v in acs.items() if k != 'NC']) if any(k != 'NC' for k in acs) else frozenset()
        # a NC pode sair de outra ação por remanejamento (ex.: 20ZV executada pela 420013): não é erro, é atenção
        if 'NC' in acs and decl and not (norm_(acs['NC']) <= decl):
            prob(t, 'Atenção · possível remanejamento', 'baixa',
                 ' · '.join(f'{k}: {v}' for k, v in acs.items()), 'controle, NC do Tesouro',
                 'confirmar se o crédito foi remanejado para esta ação e registrar no controle (se não foi, a NC pode ser de outro TED)')
        # 5. firmado divergente
        fr = {'Tesouro': num(ts.get('fir')), 'Controle': num(c.get('Firmado / total'))}
        fr = {k: v for k, v in fr.items() if v > 0}
        if fr and max(fr.values()) - min(fr.values()) > 1:
            prob(t, 'Valor firmado divergente', 'média', ' · '.join(f'{k} R$ {v:,.2f}' for k, v in fr.items()).replace(',', 'X').replace('.', ',').replace('X', '.'),
                 'Tesouro, controle', 'conferir aditivo de valor; vale o Tesouro')
        # 6. processo divergente
        pr = {'Controle': proc(c.get('Processo')), 'Tesouro': proc(ts.get('processo'))}
        pr = {k: v for k, v in pr.items() if v}
        if len(set(pr.values())) > 1:
            prob(t, 'Processo divergente', 'média', ' · '.join(f'{k} {v}' for k, v in pr.items()), 'controle, Tesouro', 'corrigir o processo no controle')
        # 7. documentos que citam outro TED / UG diferente
        ugr = (b.get('UG descentralizada') or '').strip()
        for tipo, lista, iu, iobs in (('NC', f.get('ncs') or [], 3, 12), ('PF', f.get('pfs') or [], 3, 6), ('NE', f.get('nes') or [], None, 10)):
            for x in lista:
                obs = str(x[iobs] if len(x) > iobs else '').upper()
                cit = {i for i in ID.findall(obs) if i in conhecidos and i != t.upper()}
                if cit and t.upper() not in obs:
                    prob(t, f'{tipo} cita outro TED', 'alta', f'{tipo} {x[0]} ({x[1]}) cita o TED {", ".join(sorted(cit))} e não este', f'{tipo} do Tesouro',
                         f'retirar a {tipo} desta ficha (pertence a {", ".join(sorted(cit))})')
                if iu is not None and tipo == 'PF' and str(x[iu]).strip() in SDR and str(x[2]).strip() in SDR:
                    prob(t, 'PF interna somada como repasse', 'alta', f'PF {x[0]} ({x[1]}) foi da UG {x[2]} para a UG {x[iu]} (da própria SDR): é financeiro recebido pela SDR, não repasse ao parceiro', 'PF do Tesouro',
                         'não somar esta PF no repassado do TED')
                elif iu is not None and ugr and str(x[iu]).strip() and str(x[iu]).strip() != ugr and tipo == 'PF' and not str(x[5] if len(x) > 5 else '').startswith('Devolução'):
                    prob(t, 'PF para outra UG', 'baixa', f'PF {x[0]} foi para a UG {x[iu]}, mas o TED é da UG {ugr}', 'PF × cadastro', 'conferir se a UG é do mesmo órgão (ex.: unidade x sede) ou se a PF é de outro TED')
        # 8. PF maior que o TED (PF de vários TEDs somada inteira)
        firm = max(fr.values()) if fr else num(f.get('fir'))
        for x in f.get('pfs') or []:
            if firm and num(x[4]) > firm * 1.01:
                prob(t, 'PF maior que o TED', 'alta', f'PF {x[0]} de R$ {num(x[4]):,.2f} para um TED de R$ {firm:,.2f}'.replace(',', 'X').replace('.', ',').replace('X', '.'),
                     'PF do Tesouro', 'a PF atende mais de um TED: ratear ou não somar inteira nesta ficha')
        # 9. totais incoerentes
        ncT, pfT, emp = num(f.get('nc')), num(f.get('pf')), num((f.get('neT') or [0])[0])
        if firm and ncT > firm * 1.01:
            prob(t, 'NC maior que o firmado', 'alta', f'NC R$ {ncT:,.2f} × firmado R$ {firm:,.2f}'.replace(',', 'X').replace('.', ',').replace('X', '.'), 'ficha', 'NC de outro TED ligada aqui ou aditivo não registrado')
        if ncT and pfT > ncT * 1.01:
            prob(t, 'PF maior que a NC', 'média', f'PF R$ {pfT:,.2f} × NC R$ {ncT:,.2f}'.replace(',', 'X').replace('.', ',').replace('X', '.'), 'ficha', 'PF de outro TED ligada aqui ou NC faltando')
        if ncT and emp > ncT * 1.01:
            prob(t, 'Empenho maior que a NC', 'média', f'empenhado R$ {emp:,.2f} × NC R$ {ncT:,.2f}'.replace(',', 'X').replace('.', ',').replace('X', '.'), 'ficha', 'empenho de outro TED (mesmo PTRES) ligado aqui')
        if not ncT and (pfT or emp) and dt(cd.get('Início')) and dt(cd.get('Início')).year >= 2026:
            prob(t, 'Sem NC no relatório', 'média', f'tem PF/empenho mas nenhuma NC ligada', 'NC do Tesouro', 'conferir se a NC 2026 entrou no relatório TED_NC26')
        # 10. empenhos compartilhados
        comp = [x for x in f.get('nes') or [] if len(x) > 11 and x[11]]
        if comp:
            prob(t, 'Empenho em mais de um TED', 'média', f'{len(comp)} empenho(s) ligado(s) também a: {", ".join(sorted({x[12] for x in comp if len(x) > 12 and x[12]}))[:120]}',
                 'NE do Tesouro (mesma UG + PTRES)', 'identificar o TED certo pelo processo/descrição da NE')
    # 11. o mesmo documento em mais de uma ficha
    for tipo, d in donos.items():
        for doc, ts_ in d.items():
            if len(ts_) > 1 and tipo != 'NE':
                for t in ts_:
                    prob(t, f'{tipo} em mais de uma ficha', 'alta', f'{tipo} {doc[1]} (UG {doc[0]}) aparece também em {", ".join(sorted(ts_ - {t}))}', 'fichas', 'manter só no TED citado no documento')
    # 12. mesmo processo com dois nº
    for t, r in cad.items():
        if r.get('Mesmo processo de'):
            prob(t, 'Mesmo processo com outro nº', 'média', f'processo {r.get("Processo")} também no TED {r["Mesmo processo de"]}', 'cadastro', 'confirmar se é o mesmo TED (nº duplicado) ou aditivo')

    vis = set(); P_ = [p for p in P_ if not ((p['Nº TED'], p['Categoria'], p['O que foi encontrado']) in vis or vis.add((p['Nº TED'], p['Categoria'], p['O que foi encontrado'])))]
    P_.sort(key=lambda r: (GRAV[r['Gravidade']], r['Categoria'], r['Nº TED']))
    if P_:
        with open(os.path.join(P, 'ted_varredura.csv'), 'w', encoding='utf-8', newline='') as fh:
            w = csv.DictWriter(fh, fieldnames=list(P_[0].keys())); w.writeheader(); w.writerows(P_)
    res = {'gerado_em': datetime.now().strftime('%d/%m/%Y %H:%M'), 'problemas': len(P_), 'teds_com_problema': len({p['Nº TED'] for p in P_}),
           'por_categoria': dict(Counter(p['Categoria'] for p in P_)), 'por_gravidade': dict(Counter(p['Gravidade'] for p in P_))}
    json.dump(res, open(os.path.join(P, 'ted_varredura.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print('ted_varredura ·', json.dumps(res, ensure_ascii=False))


if __name__ == '__main__':
    main()
