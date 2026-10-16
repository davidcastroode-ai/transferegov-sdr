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
    execucao(pasta, data_carga)


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
                               r.get('ug_emitente', ''), r.get('inicio_vigencia_proposta', ''), r.get('fim_vigencia_proposta', ''), r.get('cnpj_proponente', ''),
                               ix(dic, 'a', ' | '.join(sorted({x.strip()[-4:] for x in (r.get('acao_orcamentaria') or '').split('|') if x.strip()})))])
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


def execucao(pasta, data_carga):
    """Páginas Empenho/Desembolso, Programas/Emendas e Movimentação financeira (instrumentos vigentes + os com movimento no ano)."""
    hoje = datetime.date.today()
    ano = hoje.year
    inst = {r['nr_instrumento']: r for r in ler(pasta, 'instrumentos.csv')}
    agrupa = lambda lista: collections.defaultdict(list, {})
    emp, des, pag, cro, eme = (collections.defaultdict(list) for _ in range(5))
    for e in ler(pasta, 'empenhos.csv'):
        emp[e['NR_CONVENIO']].append(e)
    for d_ in ler(pasta, 'desembolsos.csv'):
        des[d_['NR_CONVENIO']].append(d_)
    for p_ in ler(pasta, 'pagamentos.csv'):
        pag[p_['NR_CONVENIO']].append(p_)
    for c in ler(pasta, 'cronograma_desembolso.csv'):
        cro[c['NR_CONVENIO']].append(c)
    for e in ler(pasta, 'emendas.csv'):
        eme[e['ID_PROPOSTA']].append(e)
    pag_ano = collections.Counter()
    linhas = []
    for n, r in inst.items():
        ds = [(d(x.get('DATA_DESEMBOLSO')), f(x.get('VL_DESEMBOLSADO')), x.get('NR_SIAFI', '')) for x in des.get(n, [])]
        ps = [(d(x.get('DATA_PAG')), f(x.get('VL_PAGO')), x.get('IDENTIF_FORNECEDOR', ''), x.get('NOME_FORNECEDOR', ''), x.get('TP_MOV_FINANCEIRA', ''), x.get('DESC_DL', ''), x.get('NR_DL', '')) for x in pag.get(n, [])]
        for x in ps:
            if x[0]:
                pag_ano[x[0].year] += 1
        mov_ano = any(x[0] and x[0].year == ano for x in ds) or any(x[0] and x[0].year == ano for x in ps)
        if r['situacao'] != 'Em execução' and not mov_ano:
            continue
        rpc = collections.Counter((e.get('RESULTADO_PRIMARIO') or '').strip() for e in emp.get(n, []) if (e.get('RESULTADO_PRIMARIO') or '').strip())
        nes = [[e.get('NR_EMPENHO', ''), e.get('UG_EMITENTE', ''), e.get('DATA_EMISSAO', ''), f(e.get('VALOR_EMPENHO')), e.get('DESC_TIPO_NOTA', '')] for e in emp.get(n, [])]
        ult_p = max((x[0] for x in ps if x[0]), default=None)
        forn = collections.defaultdict(lambda: [0.0, 0, ''])
        for x in ps:
            k = x[2] or x[3]
            forn[k][0] += x[1]
            forn[k][1] += 1
            forn[k][2] = x[3]
        fv = d(r['fim_vigencia'])
        crono = collections.Counter()
        for c in cro.get(n, []):
            if (c.get('TIPO_RESP_CRONO_DESEMBOLSO') or '').lower().startswith('concedente') and (c.get('ANO_CRONO_DESEMBOLSO') or '').isdigit():
                crono[f"{c['ANO_CRONO_DESEMBOLSO']}-{int(c.get('MES_CRONO_DESEMBOLSO') or 0):02d}"] += f(c.get('VALOR_PARCELA_CRONO_DESEMBOLSO'))
        ems = eme.get(r.get('id_proposta', ''), [])
        linhas.append(dict(
            n=n, ug=r['ug_emitente'], sit=r['situacao'], mod=r['modalidade'], prop=r['proponente'], cnpj=r['cnpj_proponente'], uf=r['uf'], mun=na(r['municipio']).strip(), munN=r['municipio'],
            parl=r['parlamentar'] or '(sem parlamentar)', tp=r['tipo_parlamentar'] or '(sem emenda)', nj=r['natureza_juridica'], ano=r['ano_proposta'], anoAss=(r['data_assinatura'] or '')[-4:],
            fv=r['fim_vigencia'], dv=(fv - hoje).days if fv else None, rep=f(r['valor_repasse']), des=f(r['valor_desembolsado']), aDes=f(r['valor_a_desembolsar']), emp=f(r['valor_empenhado']),
            sc=f(r['saldo_em_conta']), rend=f(r['rendimento_aplicacao']), cp=f(r['ingresso_contrapartida']), glob=f(r['valor_global']),
            dt=f(r.get('saldo_devolvido_tesouro')), dc=f(r.get('saldo_devolvido_convenente')),
            prog=(r['programa'] or '(sem programa)')[:120], acao=' | '.join(sorted({x.strip()[-4:] for x in (r.get('acao_orcamentaria') or '').split('|') if x.strip()})) or '(sem ação)',
            emd=r['nr_emenda'], vEm=round(sum(f(e.get('VALOR_REPASSE_EMENDA')) for e in ems), 2), nEm=len({e.get('NR_EMENDA') for e in ems if e.get('NR_EMENDA')}),
            ems=[[e.get('NR_EMENDA', ''), e.get('NOME_PARLAMENTAR', ''), e.get('TIPO_PARLAMENTAR', ''), f(e.get('VALOR_REPASSE_EMENDA')), e.get('IND_IMPOSITIVO', '')] for e in ems][:8],
            rp=(rpc.most_common(1)[0][0] if rpc else ''), objr=objeto_resumido(r['objeto']), obj=(r['objeto'] or '')[:300], link=r['link_proposta'],
            dsd=int(r['dias_sem_desembolso']) if (r['dias_sem_desembolso'] or '').isdigit() else None, ultd=r['ultimo_desembolso'], nes=nes[:20],
            desAno=[[x[0].strftime('%d/%m/%Y'), x[1], x[2]] for x in sorted(ds, key=lambda x: x[0] or datetime.date.min) if x[0] and x[0].year == ano],
            crono=sorted(crono.items()),
            pg=round(sum(x[1] for x in ps), 2), nPg=len(ps), pgAno=round(sum(x[1] for x in ps if x[0] and x[0].year == ano), 2),
            pgObtv=round(sum(x[1] for x in ps if 'OBTV' in (x[4] or '')), 2),
            ultP=ult_p.strftime('%d/%m/%Y') if ult_p else '', dsp=(hoje - ult_p).days if ult_p else None,
            forn=[[k, v[2], round(v[0], 2), v[1]] for k, v in sorted(forn.items(), key=lambda kv: -kv[1][0])[:6]],
            pags=[[x[0].strftime('%d/%m/%Y') if x[0] else '', x[3], x[1], x[5], x[6]] for x in sorted(ps, key=lambda x: x[0] or datetime.date.min, reverse=True)[:8]]))
    meta = {'ano': ano, 'pagAno': sorted([a, c] for a, c in pag_ano.items() if a >= 2008)}
    for aba, nome in (('emp', 'pagina_empenho.html'), ('prog', 'pagina_programas.html'), ('mov', 'pagina_movimentacao.html')):
        h = montar('execucao.html', {'linhas': linhas, 'meta': meta}, data_carga).replace('__ABA__', aba)
        with open(os.path.join(pasta, nome), 'w', encoding='utf-8') as fh:
            fh.write(h)
    print(f'páginas de execução · {len(linhas)} instrumentos', flush=True)


if __name__ == '__main__':
    main(sys.argv[1] if len(sys.argv) > 1 else 'saida')
