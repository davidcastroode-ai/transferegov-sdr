"""
Robô Transferegov · SDR/MAPA — páginas prontas do painel (Obras e Prestação de contas)
Lê os CSV que o processar.py gravou na pasta de saída e grava pagina_obras.html e pagina_prestacao.html
(dados embutidos; o Painel SDR abre essas páginas dentro da aba Parceria SDR).

Uso:  python scripts/paginas.py PASTA_DE_SAIDA
"""
import csv, json, os, re, sys, datetime, unicodedata, collections

csv.field_size_limit(10**9)
AQUI = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'paginas')


def na(t):
    return unicodedata.normalize('NFKD', t or '').encode('ascii', 'ignore').decode().upper()


def f(x):
    try:
        return round(float(x or 0), 2)
    except ValueError:
        return 0.0


def d(s):
    try:
        return datetime.datetime.strptime((s or '')[:10], '%d/%m/%Y').date()
    except ValueError:
        return None


def ler(pasta, nome):
    caminho = os.path.join(pasta, nome)
    if not os.path.exists(caminho):
        return []
    with open(caminho, encoding='utf-8') as fh:
        return list(csv.DictReader(fh))


# objeto resumido: tipo de obra pelas palavras do objeto
REGRAS = [('Pontes e passagens molhadas', r'PONTE|PASSAGE[MN]S? MOLHAD|BUEIRO'),
          ('Pavimentação', r'PAVIMENT|CALCAMENT|ASFALT'),
          ('Estradas vicinais', r'ESTRADA|VICINA|HORA MAQUINA|RODOVI|MATA.?BURRO|EROSAO'),
          ('Mercados e feiras', r'MERCADO|FEIRA|COMERCIALIZ|CENTRO DE ABAST'),
          ('Abatedouros e agroindústria', r'ABATEDOURO|MATADOURO|AGROINDUSTRIA|FRIGORIF|LATICINIO'),
          ('Suporte hídrico e irrigação', r'HIDRIC|AGUA|ACUDE|POCO|IRRIGA|BARRAGEM|BARRAGINHA|CISTERNA'),
          ('Energia', r'ENERGIA|ELETRIF'),
          ('Parques de exposição', r'EXPOSIC|PARQUE'),
          ('Máquinas e equipamentos', r'MAQUINA|EQUIPAMENTO|PATRULHA|TRATOR|VEICULO|MECANIZ'),
          ('Galpões, armazéns e currais', r'GALP|ARMAZEN|ENTREPOSTO|CURRAL|PAVILH|SILO|BALANCA'),
          ('Fomento agropecuário (genérico)', r'FOMENTO AOS? SETOR|AGROPECUARI')]


def objeto_resumido(o):
    t = na(o)
    for nome, rx in REGRAS:
        if re.search(rx, t):
            return nome
    return 'Outros'


def montar(tpl, dados, data_carga):
    h = open(os.path.join(AQUI, tpl), encoding='utf-8').read()
    h = h.replace('__CSS__', open(os.path.join(AQUI, 'estilo.css'), encoding='utf-8').read())
    h = h.replace('__MAPA__', open(os.path.join(AQUI, 'mapa.js'), encoding='utf-8').read())
    h = h.replace('__DATA__', data_carga)
    return h.replace('__DADOS__', json.dumps(dados, ensure_ascii=False, separators=(',', ':')).replace('</', '<\\/'))


def main(pasta):
    hoje = datetime.date.today()
    meta = {}
    try:
        meta = json.load(open(os.path.join(pasta, 'atualizacao.json'), encoding='utf-8'))
    except Exception:
        pass
    data_carga = str(meta.get('data_carga') or meta.get('gerado_em') or hoje.strftime('%d/%m/%Y'))[:16]
    inst = {r['nr_instrumento']: r for r in ler(pasta, 'instrumentos.csv')}

    # ------------------------------------------------------------ Obras
    med = collections.defaultdict(list)
    for r in ler(pasta, 'obras_medicoes.csv'):
        med[r.get('ID_PROPOSTA', '')].append([r.get('NUMERO_MEDICAO_ACOMPANHAMENTO_OBRA', ''), r.get('SITUACAO_MEDICAO_ACOMPANHAMENTO_OBRA', ''),
                                              r.get('DATA_INICIO_MEDICAO_OBJETO_ACOMPANHAMENTO_OBRA', ''), r.get('DATA_FIM_MEDICAO_OBJETO_ACOMPANHAMENTO_OBRA', '')])
    obras = []
    for o in ler(pasta, 'painel_obras.csv'):
        i = inst.get(o['nr_instrumento'], {})
        m = sorted(med.get(i.get('id_proposta', ''), []), key=lambda x: (x[3] or '', x[0]))[-6:]
        obras.append(dict(n=o['nr_instrumento'], so=o['situacao_obra'], cr=o['criterio'], pf=f(o['pct_fisico']), vo=f(o['valor_obra']), vr=f(o['valor_realizado']),
                          dsm=o['dias_sem_medicao'], um=o['fim_ultima_medicao'], nm=o['nr_medicao'], sm=o['situacao_medicao'], io=o['inicio_obra'], emp=o['cnpj_empresa'],
                          si=o['situacao_instrumento'], ug=o['ug_emitente'], mod=o['modalidade'], fv=o['fim_vigencia'], rep=f(o['valor_repasse']), des=f(o['valor_desembolsado']),
                          pd=f(o['pct_desembolsado']), prop=o['proponente'], uf=o['uf'], mun=na(o['municipio']).strip(), munN=o['municipio'],
                          parl=o['parlamentar'] or '(sem parlamentar)', tp=i.get('tipo_parlamentar', '') or '(sem emenda)', obj=o['objeto'], objr=objeto_resumido(o['objeto']),
                          ano=i.get('ano_proposta', ''), np=i.get('nr_proposta', ''), nj=i.get('natureza_juridica', ''), emd=i.get('nr_emenda', ''),
                          ne=i.get('notas_empenho', ''), prog=i.get('programa', ''), link=o['link_transparencia'], med=m))
    with open(os.path.join(pasta, 'pagina_obras.html'), 'w', encoding='utf-8') as fh:
        fh.write(montar('obras.html', obras, data_carga))
    print(f'pagina_obras.html · {len(obras)} obras', flush=True)

    # ------------------------------------------------------------ Prestação de contas
    hist = collections.defaultdict(list)
    rej = {}
    for h in ler(pasta, 'historico_situacao.csv'):
        n, s = h.get('NR_CONVENIO', ''), h.get('HISTORICO_SIT', '')
        dt = d(h.get('DIA_HISTORICO_SIT'))
        hist[n].append((dt or datetime.date.min, (h.get('DIA_HISTORICO_SIT') or '')[:10], s.replace('_', ' ').capitalize()))
        if s == 'PRESTACAO_CONTAS_REJEITADA' and dt and (n not in rej or dt > rej[n][0]):
            rej[n] = (dt, (h.get('DIA_HISTORICO_SIT') or '')[:10])
    FASE = {'Aguardando Prestação de Contas': 'Aguardando PC', 'Prestação de Contas enviada para Análise': 'Enviada para análise',
            'Prestação de Contas em Análise': 'Em análise', 'Prestação de Contas Comprovada em Análise': 'Em análise',
            'Prestação de Contas em Complementação': 'Em complementação', 'Prestação de Contas Iniciada Por Antecipação': 'Iniciada por antecipação',
            'Prestação de Contas Rejeitada': 'Rejeitada', 'Inadimplente': 'Inadimplente'}
    pcs = []
    for n, r in inst.items():
        fa = FASE.get(r['situacao'])
        ja_ruim = bool(r.get('inadimplente_desde')) or n in rej
        if not fa and not ja_ruim:
            continue
        lim, fv = d(r['limite_prestacao_contas']), d(r['fim_vigencia'])
        if fa == 'Aguardando PC':
            fa = 'Aguardando PC · prazo vencido' if lim and lim < hoje else 'Aguardando PC · no prazo'
        if not fa:
            fa = 'Encerrada (já foi rejeitada/inadimplente)'
        tl = []
        for x in sorted(hist.get(n, [])):
            if not tl or tl[-1][1] != x[2]:
                tl.append((x[1], x[2]))
        pcs.append(dict(n=n, ug=r['ug_emitente'], fase=fa, sit=r['situacao'], sub=r['subsituacao'], ano=r['ano_proposta'], fv=r['fim_vigencia'], lim=r['limite_prestacao_contas'],
                        dfv=(hoje - fv).days if fv else None, dlim=(hoje - lim).days if lim else None, rep=f(r['valor_repasse']), des=f(r['valor_desembolsado']), emp=f(r['valor_empenhado']),
                        sc=f(r['saldo_em_conta']), rend=f(r['rendimento_aplicacao']), cp=f(r['ingresso_contrapartida']),
                        dt=f(r.get('saldo_devolvido_tesouro')), dc=f(r.get('saldo_devolvido_convenente')),
                        tce=r.get('em_processo_tce') == 'SIM', inad=r.get('inadimplente_desde', ''), rej=rej[n][1] if n in rej else '',
                        mod=r['modalidade'], prop=r['proponente'], uf=r['uf'], mun=na(r['municipio']).strip(), munN=r['municipio'],
                        parl=r['parlamentar'] or '(sem parlamentar)', tp=r['tipo_parlamentar'] or '(sem emenda)', nj=r['natureza_juridica'], obj=r['objeto'],
                        np=r['nr_proposta'], ne=r['notas_empenho'], prog=r['programa'], emd=r['nr_emenda'], link=r['link_proposta'], ultd=r['ultimo_desembolso'], tl=tl[-10:]))
    with open(os.path.join(pasta, 'pagina_prestacao.html'), 'w', encoding='utf-8') as fh:
        fh.write(montar('prestacao.html', pcs, data_carga))
    print(f'pagina_prestacao.html · {len(pcs)} instrumentos', flush=True)
    propostas(pasta, data_carga)


def propostas(pasta, data_carga):
    """Página Propostas: anos recentes embutidos; anos anteriores em propostas_pag/AAAA.json, que a página carrega em seguida."""
    import glob
    hoje = datetime.date.today()
    anomin = hoje.year - 3
    anos = collections.defaultdict(lambda: [0, 0])
    pacotes = collections.defaultdict(lambda: {'dic': {}, 'rows': []})

    def ix(dic, k, v):
        d = dic.setdefault(k, {})
        if v not in d:
            d[v] = len(d)
        return d[v]
    for arq in sorted(glob.glob(os.path.join(pasta, 'propostas_por_ano', '*.csv'))):
        for r in ler(os.path.dirname(arq), os.path.basename(arq)):
            a = r.get('ano_proposta', '')
            if not a.isdigit():
                continue
            cel = r.get('celebrada') == 'SIM'
            anos[a][0] += 1
            anos[a][1] += 1 if cel else 0
            pk = pacotes['recentes' if int(a) >= anomin else a]
            dic = pk['dic']
            pk['rows'].append([int(a), ix(dic, 's', r['situacao_proposta']), ix(dic, 'm', r['modalidade']), ix(dic, 'u', r['uf']), ix(dic, 'g', (r['programa'] or '')[:120]),
                               ix(dic, 'p', r['parlamentar']), ix(dic, 't', r['tipo_parlamentar']), ix(dic, 'j', r['natureza_juridica']), 1 if cel else 0,
                               round(f(r['valor_repasse_proposta'])), round(f(r['valor_global_proposta'])), r['nr_proposta'], r['nr_instrumento'],
                               ix(dic, 'r', r['proponente']), ix(dic, 'c', r['municipio']), int(r['id_proposta'] or 0), r['nr_emenda'],
                               (r['objeto'] or '')[:220 if int(a) >= anomin else 120],
                               r.get('ug_emitente', ''), r.get('inicio_vigencia_proposta', ''), r.get('fim_vigencia_proposta', ''), r.get('cnpj_proponente', '')])
    emp = lambda pk: {'d': {k: list(v) for k, v in pk['dic'].items()}, 'r': pk['rows']}
    os.makedirs(os.path.join(pasta, 'propostas_pag'), exist_ok=True)
    antigos = sorted(a for a in pacotes if a != 'recentes')
    for a in antigos:
        with open(os.path.join(pasta, 'propostas_pag', a + '.json'), 'w', encoding='utf-8') as fh:
            json.dump(emp(pacotes[a]), fh, ensure_ascii=False, separators=(',', ':'))
    dados = emp(pacotes['recentes'])
    dados.update({'anos': [[a, n, c] for a, (n, c) in sorted(anos.items())], 'anomin': anomin, 'antigos': antigos})
    h = montar('propostas.html', dados, data_carga).replace('__ANOMIN__', str(anomin))
    with open(os.path.join(pasta, 'pagina_propostas.html'), 'w', encoding='utf-8') as fh:
        fh.write(h)
    print(f'pagina_propostas.html · {len(dados["r"])} propostas desde {anomin} + {len(antigos)} anos em propostas_pag/ · {sum(n for n, c in anos.values())} no total', flush=True)


if __name__ == '__main__':
    main(sys.argv[1] if len(sys.argv) > 1 else 'saida')
