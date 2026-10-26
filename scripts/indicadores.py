"""Indicadores do IDTRU-DL (visão do repassador) calculados com os dados do Transferegov das 5 UGs da SDR.
Manual Metodológico do Cálculo do IDTRU-DL (SEGES/MGI). Janela de 5 anos (AP-01: 12 meses), contada da data da rodada.
Saída: indicadores.json com numerador/denominador por grupo (UG · modalidade) e a lista dos itens de cada conta.
Uso: python scripts/indicadores.py SAIDA
"""
import collections, csv, datetime as dt, json, os, sys

csv.field_size_limit(10**9)
P = sys.argv[1] if len(sys.argv) > 1 else 'saida'
HOJE = dt.date.today()
C5 = HOJE.replace(year=HOJE.year - 5)
C1 = HOJE.replace(year=HOJE.year - 1)


def ler(nome):
    caminho = os.path.join(P, nome + '.csv')
    if not os.path.exists(caminho):
        return []
    with open(caminho, encoding='utf-8') as f:
        return list(csv.DictReader(f))


def data(s):
    s = (s or '').strip()[:10]
    for fm in ('%d/%m/%Y', '%Y-%m-%d'):
        try:
            return dt.datetime.strptime(s, fm).date()
        except ValueError:
            pass
    return None


def num(s):
    try:
        return float(str(s or 0).replace(',', '.'))
    except ValueError:
        return 0.0


inst = ler('instrumentos')
prop = ler('propostas')
hist = ler('historico_situacao')
desemb = ler('desembolsos')

# grupos: UG · modalidade (a proposta só ganha UG quando vira instrumento)
G = collections.defaultdict(lambda: collections.defaultdict(lambda: [0, 0]))
ITENS = collections.defaultdict(list)
por_prop = {p['id_proposta']: p for p in prop}
por_inst = {i['nr_instrumento']: i for i in inst}
inst_por_idprop = {i['id_proposta']: i for i in inst if i.get('id_proposta')}  # propostas antigas não estão na tabela de propostas


# ---------- UG da proposta ----------
# No Transferegov a proposta só ganha UG quando vira instrumento. Para as demais, a UG é deduzida, nesta ordem:
# 1) UG do instrumento; 2) contrato de repasse → 135098 (mandatária); 3) UG dos instrumentos já assinados do mesmo programa e modalidade
# (quando ≥ 90% saíram pela mesma UG); 4) idem pela ação orçamentária. O que não se encaixa fica sem UG (só entra no consolidado).
_pm = collections.defaultdict(collections.Counter)
_am = collections.defaultdict(collections.Counter)
for _p in prop:
    if _p.get('ug_emitente'):
        _pm[(_p.get('cod_programa'), _p.get('modalidade'))][_p['ug_emitente']] += 1
        _am[((_p.get('acao_orcamentaria') or '')[:4], _p.get('modalidade'))][_p['ug_emitente']] += 1
REGRA_UG = collections.Counter()


def ug_prop(p):
    if p.get('_ug') is not None:
        return p['_ug']
    ug, regra = '', 'sem UG identificada'
    if p.get('ug_emitente'):
        ug, regra = p['ug_emitente'], 'UG do instrumento'
    elif p.get('modalidade') == 'CONTRATO DE REPASSE':
        ug, regra = '135098', 'contrato de repasse (mandatária)'
    else:
        for mapa, chave, rot in ((_pm, (p.get('cod_programa'), p.get('modalidade')), 'pelo programa'),
                                 (_am, ((p.get('acao_orcamentaria') or '')[:4], p.get('modalidade')), 'pela ação')):
            m = mapa.get(chave)
            if m:
                u, n = m.most_common(1)[0]
                if n / sum(m.values()) >= 0.9:
                    ug, regra = u, rot
                    break
    p['_ug'] = ug
    p['_regra'] = regra
    REGRA_UG[regra] += 1
    return ug


def grupo(ug, mod):
    return (ug or '') + '|' + (mod or '')


GA = collections.defaultdict(lambda: collections.defaultdict(lambda: [0, 0]))   # por ano: "ug|mod|ano"
ITENS_ANO = collections.defaultdict(list)                                          # ano de cada item da lista (mesma ordem de ITENS)


def conta(ind, ug, mod, numerador, item=None, ano=None):
    v = (numerador if isinstance(numerador, (int, float)) and not isinstance(numerador, bool) else 1) if numerador else 0
    g = G[grupo(ug, mod)][ind]
    g[1] += 1
    g[0] += v
    if ano:
        ga = GA[grupo(ug, mod) + '|' + str(ano)][ind]
        ga[1] += 1
        ga[0] += v
    if item is not None:
        ITENS[ind].append(item)
        ITENS_ANO[ind].append(ano or '')


# ---------- histórico por proposta ----------
hp = collections.defaultdict(list)
for h in hist:
    t = data(h.get('DIA_HISTORICO_SIT'))
    if t:
        hp[h['ID_PROPOSTA']].append((t, h['HISTORICO_SIT']))
for k in hp:
    hp[k].sort()

# ---------- AP-01 · propagação dos programas (12 meses) ----------
ENVIO = ('PROPOSTA_ENVIADA_ANALISE', 'PROPOSTA_COMPLEMENTADA_ENVIADA_ANALISE')
ap1 = collections.defaultdict(lambda: [0, set()])
for k, l in hp.items():
    if k in por_prop and any(s in ENVIO and t >= C1 for t, s in l):
        p = por_prop[k]
        g = ap1[grupo(ug_prop(p), p.get('modalidade'))]
        g[0] += 1
        g[1].add(p.get('cod_programa'))
        ITENS['AP-01'].append([p['nr_proposta'], ug_prop(p), p.get('modalidade', ''), p.get('programa', '')[:80], p.get('proponente', '')[:60]])
        ITENS_ANO['AP-01'].append(min(t for t, s in l if s in ENVIO and t >= C1).year)
AP1 = {g: [v[0], sorted(x for x in v[1] if x)] for g, v in ap1.items()}
# AP-01 por ano civil: propostas enviadas pela primeira vez no ano ÷ programas distintos dessas propostas
ap1a = collections.defaultdict(lambda: [0, set()])
for k, l in hp.items():
    if k in por_prop:
        env = [t for t, s in l if s in ENVIO]
        if env and min(env).year >= C5.year + 1:
            p = por_prop[k]
            g = ap1a[grupo(ug_prop(p), p.get('modalidade')) + '|' + str(min(env).year)]
            g[0] += 1
            g[1].add(p.get('cod_programa'))
AP1A = {g: [v[0], sorted(x for x in v[1] if x)] for g, v in ap1a.items()}

# ---------- AP-02 e AP-03 · propostas (5 anos, pelo ano da proposta) ----------
ano5 = C5.year + (1 if C5.month > 6 else 0)
for p in prop:
    try:
        ano = int(p.get('ano_proposta') or 0)
    except ValueError:
        ano = 0
    sit = p.get('situacao_proposta') or ''
    if ano < ano5 or not sit or 'Cadastrad' in sit:
        continue
    analisada = any(x in sit for x in ('Aprovad', 'Rejeitad', 'Eliminada'))
    conta('AP-02', ug_prop(p), p.get('modalidade'), analisada,
          [p['nr_proposta'], ug_prop(p), p.get('modalidade', ''), sit, p.get('proponente', '')[:60]] if not analisada else None, ano)
    aprovada = 'Aprovad' in sit or p.get('celebrada') == 'SIM'
    if aprovada:
        cel = p.get('celebrada') == 'SIM' or bool(p.get('nr_instrumento'))
        conta('AP-03', ug_prop(p), p.get('modalidade'), cel,
              [p['nr_proposta'], ug_prop(p), p.get('modalidade', ''), sit, p.get('proponente', '')[:60]] if not cel else None, ano)

# ---------- EX-02 · cláusula suspensiva (assinados nos 5 anos, convênio e contrato de repasse) ----------
for i in inst:
    a = data(i.get('data_assinatura'))
    if not a or a < C5 or i.get('modalidade') not in ('CONVENIO', 'CONTRATO DE REPASSE'):
        continue
    sus = 'Suspensiva' in (i.get('situacao_contratacao') or '') or bool((i.get('clausula_suspensiva_ate') or '').strip())
    conta('EX-02', i.get('ug_emitente'), i.get('modalidade'), sus,
          [i['nr_instrumento'], i.get('ug_emitente', ''), i.get('modalidade', ''), i.get('situacao_contratacao', ''), i.get('proponente', '')[:60], i.get('clausula_suspensiva_ate', '')] if sus else None, a.year)

# ---------- EX-03 · sem desembolso 60+ dias (aproximado: conta da assinatura, sem a data do aceite da licitação) ----------
dd = collections.defaultdict(list)
for x in desemb:
    t = data(x.get('DATA_DESEMBOLSO'))
    if t:
        dd[x['NR_CONVENIO']].append(t)
for i in inst:
    ini = data(i.get('inicio_vigencia'))
    if i.get('situacao') != 'Em execução' or not ini or ini < C5 or i.get('modalidade') not in ('CONVENIO', 'CONTRATO DE REPASSE'):
        continue
    a = data(i.get('data_assinatura')) or ini
    sem = not dd.get(i['nr_instrumento']) and (HOJE - a).days > 60
    conta('EX-03', i.get('ug_emitente'), i.get('modalidade'), sem,
          [i['nr_instrumento'], i.get('ug_emitente', ''), i.get('modalidade', ''), (HOJE - a).days, i.get('proponente', '')[:60], num(i.get('valor_repasse'))] if sem else None)

# ---------- PC-01 · em TCE (estoque em prestação de contas) ----------
for i in inst:
    s = i.get('situacao') or ''
    if 'Prestação de Contas' in s or s == 'Aguardando Prestação de Contas':
        tce = i.get('em_processo_tce') == 'SIM'
        conta('PC-01', i.get('ug_emitente'), i.get('modalidade'), tce,
              [i['nr_instrumento'], i.get('ug_emitente', ''), i.get('modalidade', ''), s, i.get('proponente', '')[:60]] if tce else None)

# ---------- PC-02 e PC-03 · análise da prestação de contas (5 anos, pelo histórico) ----------
FIM = {'PRESTACAO_CONTAS_APROVADA', 'PRESTACAO_CONTAS_APROVADA_COM_RESSALVAS', 'PRESTACAO_CONTAS_REJEITADA'}
for k, l in hp.items():
    fins = [(t, s) for t, s in l if s in FIM] or [(t, s) for t, s in l if s == 'PRESTACAO_CONTAS_CONCLUIDA']
    if not fins:
        continue
    tf, sf = fins[-1]
    if tf < C5:
        continue
    i = None
    p = por_prop.get(k)
    nr = (p or {}).get('nr_instrumento') or ''
    i = por_inst.get(nr) or inst_por_idprop.get(k)
    nr = nr or (i or {}).get('nr_instrumento', '')
    ug = (i or {}).get('ug_emitente', '') or (ug_prop(p) if p else '')
    mod = (i or p or {}).get('modalidade', '')
    prop_ = (i or p or {}).get('proponente', '')[:60]
    ok = sf == 'PRESTACAO_CONTAS_APROVADA'
    conta('PC-02', ug, mod, ok, [nr or k, ug, mod, sf.replace('_', ' ').title(), prop_, tf.strftime('%d/%m/%Y')] if not ok else None, tf.year)
    ini = next((t for t, s in l if s == 'PRESTACAO_CONTAS_ENVIADA_ANALISE'), None)
    if ini and ini <= tf:
        tot, comp, cur = (tf - ini).days, 0, None
        for t, s in l:
            if t < ini or t > tf:
                continue
            if s == 'PRESTACAO_CONTAS_EM_COMPLEMENTACAO' and cur is None:
                cur = t
            elif cur is not None and s != 'PRESTACAO_CONTAS_EM_COMPLEMENTACAO':
                comp += (t - cur).days
                cur = None
        dias = max(0, tot - comp)
        conta('PC-03', ug, mod, dias, [nr or k, ug, mod, dias, prop_, ini.strftime('%d/%m/%Y'), tf.strftime('%d/%m/%Y')], tf.year)

# ---------- PC-04 · encerrados com saldo em conta (estoque total) ----------
ENC = {'Cancelado', 'Prestação de Contas Aprovada', 'Prestação de Contas Aprovada com Ressalvas', 'Prestação de Contas Concluída',
       'Convênio Anulado', 'Prestação de Contas Rejeitada', 'Convênio Rescindido'}
for i in inst:
    if i.get('situacao') in ENC:
        sal = num(i.get('saldo_em_conta'))
        conta('PC-04', i.get('ug_emitente'), i.get('modalidade'), sal > 0.01,
              [i['nr_instrumento'], i.get('ug_emitente', ''), i.get('modalidade', ''), i.get('situacao', ''), i.get('proponente', '')[:60], sal] if sal > 0.01 else None)

saida = {
    'gerado_em': dt.datetime.now(dt.timezone(dt.timedelta(hours=-3))).strftime('%d/%m/%Y %H:%M'),
    'janela': {'inicio_5a': C5.strftime('%d/%m/%Y'), 'inicio_12m': C1.strftime('%d/%m/%Y')},
    'grupos': {g: {k: v for k, v in d.items()} for g, d in G.items()},
    'ap01': AP1,
    'grupos_ano': {g: {k: v for k, v in d.items()} for g, d in GA.items() if int(g.rsplit('|', 1)[1]) >= C5.year + 1},
    'ap01_ano': AP1A,
    'itens_ano': ITENS_ANO,
    'anos': sorted({int(g.rsplit('|', 1)[1]) for g in GA if int(g.rsplit('|', 1)[1]) >= C5.year + 1}),
    'ug_propostas': dict(REGRA_UG),
    'itens': ITENS,
}
with open(os.path.join(P, 'indicadores.json'), 'w', encoding='utf-8') as f:
    json.dump(saida, f, ensure_ascii=False, separators=(',', ':'))
tot = collections.defaultdict(lambda: [0, 0])
for d in G.values():
    for k, (a, b) in d.items():
        tot[k][0] += a
        tot[k][1] += b
print('UG das propostas:', dict(REGRA_UG))
for k in sorted(tot):
    a, b = tot[k]
    print(f'{k}: {a} / {b} = {a / b if b else 0:.4f}')
print('AP-01:', sum(v[0] for v in AP1.values()), 'propostas ·', len({x for v in AP1.values() for x in v[1]}), 'programas')
print('arquivo:', os.path.getsize(os.path.join(P, 'indicadores.json')) // 1024, 'KB')
