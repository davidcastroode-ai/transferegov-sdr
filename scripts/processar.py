"""
Robô Transferegov · SDR/MAPA
Baixa os arquivos de dados abertos do Transferegov (Discricionárias e Legais), filtra o que é da SDR
e gera arquivos CSV pequenos e organizados, prontos para o Painel SDR e para as planilhas.

Escopo SDR:
  • instrumentos (convênios, contratos de repasse, termos de fomento/colaboração) emitidos pelas UGs da SDR;
  • propostas desses instrumentos + todas as propostas dos mesmos programas (inclusive as não celebradas).

Uso:  python scripts/processar.py PASTA_DE_SAIDA
      (variável FONTE_LOCAL=pasta com os .zip já baixados, para testar sem internet)
"""
import csv, io, json, os, sys, time, urllib.request, zipfile, datetime, re

BASE = 'https://api-publica.transferegov.gestao.gov.br/downloads/dadosgov/'
UGS_SDR = ['130010', '130141', '135098', '420013', '130255']
ARQUIVOS = ['siconv_convenio', 'siconv_programa_proposta', 'siconv_programa', 'siconv_proposta', 'siconv_emenda',
            'siconv_empenho', 'siconv_desembolso', 'siconv_termo_aditivo', 'siconv_prorroga_oficio', 'data_carga_siconv',
            'siconv_dados_obrasgov_geral', 'siconv_acomp_obras_contratos_medicoes_modulo_empresas', 'siconv_acomp_obras_valores_itens_medicao_modulo_empresas']
TMP = os.environ.get('FONTE_LOCAL') or '/tmp/transferegov'
csv.field_size_limit(10**9)
LOG = []


def log(msg):
    linha = time.strftime('%H:%M:%S') + '  ' + msg
    print(linha, flush=True)
    LOG.append(linha)
    if os.environ.get('GITHUB_ACTIONS'):
        print('::notice::' + msg, flush=True)


# ---------------------------------------------------------------- download
def baixar(nome):
    destino = os.path.join(TMP, nome + '.zip')
    if os.environ.get('FONTE_LOCAL'):
        return destino if os.path.exists(destino) else None
    os.makedirs(TMP, exist_ok=True)
    for tentativa in range(1, 4):
        try:
            t = time.time()
            req = urllib.request.Request(BASE + nome + '.zip', headers={'User-Agent': 'robo-sdr-mapa'})
            with urllib.request.urlopen(req, timeout=600) as r, open(destino, 'wb') as f:
                while True:
                    bloco = r.read(1 << 20)
                    if not bloco:
                        break
                    f.write(bloco)
            log(f'baixou {nome}.zip · {os.path.getsize(destino)/1048576:.1f} MB · {time.time()-t:.1f} s')
            return destino
        except Exception as e:
            log(f'falha ao baixar {nome} (tentativa {tentativa}): {e}')
            time.sleep(10 * tentativa)
    return None


def linhas(nome):
    """Lê o CSV de dentro do .zip linha a linha (sem carregar tudo na memória). Devolve (cabeçalho, iterador de dicts)."""
    caminho = os.path.join(TMP, nome + '.zip')
    if not os.path.exists(caminho):
        return None, iter(())
    z = zipfile.ZipFile(caminho)
    membro = next((n for n in z.namelist() if n.lower().endswith('.csv')), z.namelist()[0])
    bruto = io.TextIOWrapper(z.open(membro), encoding='utf-8-sig', newline='')
    leitor = csv.reader(bruto, delimiter=';')
    cab = [c.strip().upper() for c in next(leitor)]

    def gerar():
        for r in leitor:
            if len(r) < len(cab):
                r = r + [''] * (len(cab) - len(r))
            yield dict(zip(cab, r))
    return cab, gerar()


# ---------------------------------------------------------------- formatos
def num(s):
    """'1869731,8' · '242754.81' · '1.234,56' · '' → float"""
    s = (s or '').strip()
    if not s:
        return 0.0
    if ',' in s:
        s = s.replace('.', '').replace(',', '.')
    try:
        return float(s)
    except ValueError:
        return 0.0


def data(s):
    s = (s or '').strip()
    for fmt in ('%d/%m/%Y', '%Y-%m-%d', '%d/%m/%Y %H:%M:%S', '%Y-%m-%d %H:%M:%S'):
        try:
            return datetime.datetime.strptime(s[:19], fmt).date()
        except ValueError:
            pass
    return None


def br(d):
    return d.strftime('%d/%m/%Y') if d else ''


def v2(x):
    return f'{x:.2f}'


def gravar(pasta, nome, campos, registros):
    caminho = os.path.join(pasta, nome)
    with open(caminho, 'w', encoding='utf-8', newline='') as f:
        w = csv.DictWriter(f, fieldnames=campos, extrasaction='ignore')
        w.writeheader()
        for r in registros:
            w.writerow(r)
    log(f'gravou {nome} · {len(registros)} linhas · {os.path.getsize(caminho)/1048576:.1f} MB')


# ---------------------------------------------------------------- principal
def main(saida):
    os.makedirs(saida, exist_ok=True)
    hoje = datetime.date.today()
    meta = {'gerado_em': datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=-3))).strftime('%d/%m/%Y %H:%M'),
            'ugs': UGS_SDR, 'cabecalhos': {}, 'contagens': {}}

    for a in ARQUIVOS:
        baixar(a)

    # data da carga do Transferegov
    cab, it = linhas('data_carga_siconv')
    for r in it:
        meta['data_carga'] = ' '.join(v for v in r.values() if v)
        break

    # 1. instrumentos das UGs da SDR
    cab, it = linhas('siconv_convenio')
    meta['cabecalhos']['convenio'] = cab
    conv = {}
    for r in it:
        if r.get('UG_EMITENTE') in UGS_SDR:
            conv[r['NR_CONVENIO']] = r
    prop_do_conv = {r['ID_PROPOSTA']: n for n, r in conv.items()}
    log(f'instrumentos da SDR: {len(conv)}')

    # 2. programas usados pela SDR → escopo de propostas
    cab, it = linhas('siconv_programa_proposta')
    meta['cabecalhos']['programa_proposta'] = cab
    progs_da_prop, pares = {}, []
    for r in it:
        pares.append((r.get('ID_PROPOSTA'), r.get('ID_PROGRAMA')))
    for p, g in pares:
        if p in prop_do_conv:
            progs_da_prop.setdefault(p, set()).add(g)
    progs_sdr = set(g for gs in progs_da_prop.values() for g in gs)
    escopo = set(prop_do_conv)
    for p, g in pares:
        if g in progs_sdr:
            escopo.add(p)
            progs_da_prop.setdefault(p, set()).add(g)
    pares = None
    log(f'programas da SDR: {len(progs_sdr)} · propostas no escopo: {len(escopo)}')

    cab, it = linhas('siconv_programa')
    meta['cabecalhos']['programa'] = cab
    programa = {r['ID_PROGRAMA']: r for r in it if r.get('ID_PROGRAMA') in progs_sdr}

    # 3. propostas (arquivo grande, lido em fluxo)
    cab, it = linhas('siconv_proposta')
    meta['cabecalhos']['proposta'] = cab
    proposta = {}
    for r in it:
        if r.get('ID_PROPOSTA') in escopo:
            proposta[r['ID_PROPOSTA']] = r
    log(f'propostas lidas: {len(proposta)}')

    # 4. emendas
    cab, it = linhas('siconv_emenda')
    meta['cabecalhos']['emenda'] = cab
    emendas = [r for r in it if r.get('ID_PROPOSTA') in escopo]
    emendas_da_prop = {}
    for r in emendas:
        emendas_da_prop.setdefault(r['ID_PROPOSTA'], []).append(r)

    # 5. empenhos, desembolsos, aditivos e prorrogações dos instrumentos
    def do_conv(nome):
        cab, it = linhas(nome)
        meta['cabecalhos'][nome.replace('siconv_', '')] = cab
        out = [r for r in it if r.get('NR_CONVENIO') in conv]
        log(f'{nome}: {len(out)} linhas da SDR')
        return cab, out
    cab_emp, empenhos = do_conv('siconv_empenho')
    cab_des, desembolsos = do_conv('siconv_desembolso')
    cab_ta, aditivos = do_conv('siconv_termo_aditivo')
    cab_pr, prorrogas = do_conv('siconv_prorroga_oficio')

    def por_conv(lista):
        g = {}
        for r in lista:
            g.setdefault(r['NR_CONVENIO'], []).append(r)
        return g
    emp_c, des_c, ta_c, pr_c = por_conv(empenhos), por_conv(desembolsos), por_conv(aditivos), por_conv(prorrogas)

    def info_prop(p):
        pr = proposta.get(p, {})
        gs = sorted(progs_da_prop.get(p, []))
        pg = [programa[g] for g in gs if g in programa]
        em = emendas_da_prop.get(p, [])
        return {
            'id_proposta': p,
            'nr_proposta': pr.get('NR_PROPOSTA', ''),
            'ano_proposta': pr.get('ANO_PROP', ''),
            'situacao_proposta': pr.get('SIT_PROPOSTA', ''),
            'modalidade': pr.get('MODALIDADE', ''),
            'orgao_concedente': (pr.get('COD_ORGAO', '') + ' - ' + pr.get('DESC_ORGAO', '')).strip(' -'),
            'cnpj_proponente': pr.get('IDENTIF_PROPONENTE', ''),
            'proponente': pr.get('NM_PROPONENTE', ''),
            'natureza_juridica': pr.get('NATUREZA_JURIDICA', ''),
            'uf': pr.get('UF_PROPONENTE', ''),
            'municipio': pr.get('MUNIC_PROPONENTE', ''),
            'cod_ibge': pr.get('COD_MUNIC_IBGE', ''),
            'objeto': (pr.get('OBJETO_PROPOSTA', '') or '').replace('\r', ' ').replace('\n', ' ').strip(),
            'valor_global_proposta': v2(num(pr.get('VL_GLOBAL_PROP'))),
            'valor_repasse_proposta': v2(num(pr.get('VL_REPASSE_PROP'))),
            'valor_contrapartida_proposta': v2(num(pr.get('VL_CONTRAPARTIDA_PROP'))),
            'inicio_vigencia_proposta': pr.get('DIA_INIC_VIGENCIA_PROPOSTA', ''),
            'fim_vigencia_proposta': pr.get('DIA_FIM_VIGENCIA_PROPOSTA', ''),
            'cod_programa': ' | '.join(x.get('COD_PROGRAMA', '') for x in pg),
            'programa': ' | '.join(x.get('NOME_PROGRAMA', '') for x in pg),
            'acao_orcamentaria': ' | '.join(sorted(set(x.get('ACAO_ORCAMENTARIA', '') for x in pg if x.get('ACAO_ORCAMENTARIA')))),
            'id_programa': ' | '.join(gs),
            'nr_emenda': ' | '.join(sorted(set(e.get('NR_EMENDA', '') for e in em if e.get('NR_EMENDA')))),
            'parlamentar': ' | '.join(sorted(set(e.get('NOME_PARLAMENTAR', '') for e in em if e.get('NOME_PARLAMENTAR')))),
            'tipo_parlamentar': ' | '.join(sorted(set(e.get('TIPO_PARLAMENTAR', '') for e in em if e.get('TIPO_PARLAMENTAR')))),
            'valor_emenda': v2(sum(num(e.get('VALOR_REPASSE_EMENDA')) for e in em)),
            'link_proposta': 'https://discricionarias.transferegov.sistema.gov.br/voluntarias/ConsultarProposta/ResultadoDaConsultaDePropostaDetalharProposta.do?idProposta=' + p + '&Usr=guest&Pwd=guest',
        }

    # 6. instrumentos (1 linha por instrumento)
    inst = []
    for n, c in conv.items():
        rep, desemb = num(c.get('VL_REPASSE_CONV')), num(c.get('VL_DESEMBOLSADO_CONV'))
        ds = sorted((data(d.get('DATA_DESEMBOLSO')) for d in des_c.get(n, [])), key=lambda x: x or datetime.date.min)
        ult = ds[-1] if ds and ds[-1] else None
        emps = emp_c.get(n, [])
        nes = sorted(set(e.get('NR_EMPENHO', '') for e in emps if e.get('NR_EMPENHO')))
        reg = {
            'nr_instrumento': n,
            'ug_emitente': c.get('UG_EMITENTE', ''),
            'situacao': c.get('SIT_CONVENIO', ''),
            'subsituacao': c.get('SUBSITUACAO_CONV', ''),
            'instrumento_ativo': c.get('INSTRUMENTO_ATIVO', ''),
            'assinado': c.get('IND_ASSINADO', ''),
            'ano': c.get('ANO', ''),
            'nr_processo': c.get('NR_PROCESSO', ''),
            'data_assinatura': c.get('DIA_ASSIN_CONV', ''),
            'data_publicacao': c.get('DIA_PUBL_CONV', ''),
            'inicio_vigencia': c.get('DIA_INIC_VIGENC_CONV', ''),
            'fim_vigencia': c.get('DIA_FIM_VIGENC_CONV', ''),
            'fim_vigencia_original': c.get('DIA_FIM_VIGENC_ORIGINAL_CONV', ''),
            'limite_prestacao_contas': c.get('DIA_LIMITE_PREST_CONTAS', ''),
            'clausula_suspensiva_ate': c.get('DATA_SUSPENSIVA', ''),
            'situacao_contratacao': c.get('SITUACAO_CONTRATACAO', ''),
            'valor_global': v2(num(c.get('VL_GLOBAL_CONV'))),
            'valor_repasse': v2(rep),
            'valor_contrapartida': v2(num(c.get('VL_CONTRAPARTIDA_CONV'))),
            'valor_empenhado': v2(num(c.get('VL_EMPENHADO_CONV'))),
            'valor_desembolsado': v2(desemb),
            'valor_a_desembolsar': v2(max(0.0, rep - desemb)),
            'pct_desembolsado': f'{(desemb / rep * 100) if rep else 0:.2f}',
            'ingresso_contrapartida': v2(num(c.get('VL_INGRESSO_CONTRAPARTIDA'))),
            'rendimento_aplicacao': v2(num(c.get('VL_RENDIMENTO_APLICACAO'))),
            'saldo_em_conta': v2(num(c.get('VL_SALDO_CONTA'))),
            'qtd_desembolsos': str(len(ds)),
            'ultimo_desembolso': br(ult),
            'dias_sem_desembolso': str((hoje - ult).days) if ult else '',
            'qtd_aditivos': str(len(ta_c.get(n, []))),
            'qtd_prorrogacoes': str(len(pr_c.get(n, []))),
            'notas_empenho': ' | '.join(nes),
            'qtd_notas_empenho': str(len(nes)),
        }
        reg.update(info_prop(c.get('ID_PROPOSTA', '')))
        inst.append(reg)
    inst.sort(key=lambda r: (r['ano'] or '0000', r['nr_instrumento']), reverse=True)
    campos_inst = list(inst[0].keys()) if inst else []
    gravar(saida, 'instrumentos.csv', campos_inst, inst)
    # versão leve para o painel (abre rápido no navegador)
    leve = ['nr_instrumento', 'ug_emitente', 'ano', 'situacao', 'situacao_contratacao', 'clausula_suspensiva_ate', 'fim_vigencia',
            'limite_prestacao_contas', 'nr_processo', 'modalidade', 'proponente', 'uf', 'municipio', 'natureza_juridica', 'tipo_parlamentar',
            'valor_repasse', 'valor_desembolsado', 'valor_a_desembolsar', 'ultimo_desembolso', 'dias_sem_desembolso', 'qtd_aditivos',
            'qtd_prorrogacoes', 'notas_empenho', 'saldo_em_conta', 'objeto']
    gravar(saida, 'painel_instrumentos.csv', leve, [{**r, 'objeto': r['objeto'][:160]} for r in inst])

    # 7. propostas (todas do escopo, celebradas ou não)
    props = []
    for p in escopo:
        if p not in proposta:
            continue
        reg = info_prop(p)
        n = prop_do_conv.get(p, '')
        c = conv.get(n, {})
        reg.update({'nr_instrumento': n, 'ug_emitente': c.get('UG_EMITENTE', ''), 'situacao_instrumento': c.get('SIT_CONVENIO', ''),
                    'celebrada': 'SIM' if c.get('IND_ASSINADO') == 'SIM' else 'NÃO'})
        props.append(reg)
    props.sort(key=lambda r: (r['ano_proposta'] or '0000', r['nr_proposta']), reverse=True)
    campos_prop = list(props[0].keys()) if props else []
    # o arquivo completo passa de 100 MB (limite do GitHub): um arquivo por ano + "propostas.csv" com os anos recentes
    ano_min = hoje.year - 3
    gravar(saida, 'propostas.csv', campos_prop, [r for r in props if (r['ano_proposta'] or '0') >= str(ano_min)])
    por_ano = {}
    for r in props:
        por_ano.setdefault(r['ano_proposta'] or 'sem_ano', []).append(r)
    os.makedirs(os.path.join(saida, 'propostas_por_ano'), exist_ok=True)
    for ano, lista in sorted(por_ano.items()):
        gravar(saida, os.path.join('propostas_por_ano', f'propostas_{ano}.csv'), campos_prop, lista)
    meta['propostas_por_ano'] = {ano: {'total': len(l), 'celebradas': sum(1 for r in l if r['celebrada'] == 'SIM')} for ano, l in sorted(por_ano.items())}
    meta['propostas_csv_desde'] = ano_min

    # 8. tabelas de detalhe (colunas originais do Transferegov)
    gravar(saida, 'empenhos.csv', cab_emp or ['NR_CONVENIO'], empenhos)
    gravar(saida, 'desembolsos.csv', cab_des or ['NR_CONVENIO'], desembolsos)
    gravar(saida, 'aditivos.csv', cab_ta or ['NR_CONVENIO'], aditivos)
    gravar(saida, 'prorrogacoes.csv', cab_pr or ['NR_CONVENIO'], prorrogas)
    gravar(saida, 'emendas.csv', meta['cabecalhos'].get('emenda') or ['ID_PROPOSTA'], emendas)

    # obras (Obrasgov / módulo de empresas): filtra pelos instrumentos ou propostas da SDR, qualquer que seja a coluna de ligação
    for nome, arq in [('siconv_dados_obrasgov_geral', 'obras.csv'), ('siconv_acomp_obras_contratos_medicoes_modulo_empresas', 'obras_medicoes.csv'),
                      ('siconv_resumo_fisico_financeiro', 'resumo_fisico_financeiro.csv')]:
        cab, it = linhas(nome)
        meta['cabecalhos'][nome.replace('siconv_', '')] = cab
        if not cab:
            continue
        cc = [c for c in cab if c in ('NR_CONVENIO', 'NR_INSTRUMENTO', 'NUMERO_INSTRUMENTO', 'NUM_INSTRUMENTO', 'NR_CONVENIO_SICONV')]
        cp = [c for c in cab if c in ('ID_PROPOSTA', 'NR_PROPOSTA_SICONV')]
        out = [r for r in it if any(r.get(c) in conv for c in cc) or any(r.get(c) in prop_do_conv for c in cp)]
        log(f'{nome}: {len(out)} linhas da SDR (ligação por {", ".join(cc + cp) or "nenhuma coluna conhecida"})')
        gravar(saida, arq, cab, out)

    # obras (Obrasgov / acompanhamento de obras): filtra pelo nº do instrumento ou pelo ID da proposta, o que o arquivo tiver
    def obras_de(nome, saida_nome):
        cab, it = linhas(nome)
        meta['cabecalhos'][nome.replace('siconv_', '')] = cab
        if not cab:
            return 0
        ci = next((c for c in cab if c in ('NR_CONVENIO', 'NR_INSTRUMENTO', 'NUMERO_INSTRUMENTO', 'NR_TRANSFERENCIA')), None) \
            or next((c for c in cab if 'CONVENIO' in c or 'INSTRUMENTO' in c), None)
        cp = 'ID_PROPOSTA' if 'ID_PROPOSTA' in cab else None
        out = [r for r in it if (ci and r.get(ci) in conv) or (cp and r.get(cp) in prop_do_conv)]
        log(f'{nome}: {len(out)} linhas da SDR (chave: {ci or cp})')
        gravar(saida, saida_nome, cab, out)
        return len(out)
    n_obras = obras_de('siconv_dados_obrasgov_geral', 'obras.csv')
    n_med = obras_de('siconv_acomp_obras_contratos_medicoes_modulo_empresas', 'obras_medicoes.csv')
    n_itm = obras_de('siconv_acomp_obras_valores_itens_medicao_modulo_empresas', 'obras_itens_medicao.csv')

    meta['contagens'] = {'obras': n_obras, 'obras_medicoes': n_med, 'obras_itens_medicao': n_itm, 'instrumentos': len(inst), 'propostas': len(props), 'empenhos': len(empenhos),
                         'desembolsos': len(desembolsos), 'aditivos': len(aditivos), 'prorrogacoes': len(prorrogas),
                         'emendas': len(emendas), 'programas': len(progs_sdr)}
    meta['log'] = LOG
    with open(os.path.join(saida, 'atualizacao.json'), 'w', encoding='utf-8') as f:
        json.dump(meta, f, ensure_ascii=False, indent=1)
    log('fim')


if __name__ == '__main__':
    main(sys.argv[1] if len(sys.argv) > 1 else 'saida')
