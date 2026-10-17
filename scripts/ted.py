"""
Robô TED · SDR/MAPA
Baixa as tabelas da API pública de TED do Transferegov (https://api-publica.transferegov.gestao.gov.br/ted/docs)
e guarda só os TEDs das UGs da SDR, como descentralizadora (TED enviado) ou descentralizada/executora (TED recebido).

Uso:  python scripts/ted.py PASTA_DE_SAIDA
Saída (em PASTA/ted/):
  ted_planilha.csv          um TED por linha, nas colunas da planilha BASE TED API (aba TED)
  ted_notas_credito.csv     notas de crédito dos TEDs (com o valor somado dos eventos)
  ted_eventos.csv           eventos das notas (PTRES, PI, fonte, natureza, valor)
  ted_programacoes.csv      programações financeiras (com o valor somado dos itens TRF)
  ted_cronograma.csv        cronograma de desembolso do plano de trabalho
  ted_analises_pareceres.csv análises e pareceres dos planos de ação
  ted_metas.csv             metas dos planos de ação
  ted_programas.csv         programas de TED das UGs da SDR
  ted_atualizacao.json      data da carga da API e contagens
"""
import csv, json, os, sys, time, datetime, urllib.request, urllib.parse
from collections import defaultdict

B = 'https://api-publica.transferegov.gestao.gov.br/ted'
UGS = {'130010', '130141', '130255', '135098', '420013'}
LOG = []


def log(m):
    print(time.strftime('%H:%M:%S') + '  ' + m, flush=True)
    LOG.append(m)
    if os.environ.get('GITHUB_ACTIONS'):
        print('::notice::TED · ' + m, flush=True)


def get(path, params):
    url = B + path + '?' + urllib.parse.urlencode(params)
    for t in range(5):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers={'User-Agent': 'robo-sdr-mapa', 'Accept': 'application/json'}), timeout=180) as r:
                return json.loads(r.read())
        except Exception as e:
            err = e
            time.sleep(4 * (t + 1))
    raise err


def tudo(path):
    """baixa a tabela inteira, de 1000 em 1000"""
    out, pag = [], 1
    while True:
        js = get(path, {'pagina': pag, 'tamanho_da_pagina': 1000})
        dados = js.get('data', js) if isinstance(js, dict) else js
        out.extend(dados or [])
        tot = js.get('total_pages', 1) if isinstance(js, dict) else 1
        if pag >= (tot or 1) or not dados:
            break
        pag += 1
    log(f'{path}: {len(out)} registros')
    return out


def s(v):
    return '' if v is None else str(v).strip()


def n(v):
    try:
        return float(v or 0)
    except (TypeError, ValueError):
        return 0.0


def br(d):
    d = s(d)[:10]
    try:
        return datetime.date.fromisoformat(d).strftime('%d/%m/%Y')
    except ValueError:
        return d


def gravar(pasta, nome, linhas, campos=None):
    campos = campos or (list(dict.fromkeys(k for l in linhas for k in l.keys())) if linhas else ['vazio'])
    with open(os.path.join(pasta, nome), 'w', encoding='utf-8', newline='') as f:
        w = csv.DictWriter(f, fieldnames=campos, extrasaction='ignore')
        w.writeheader()
        for l in linhas:
            w.writerow({k: (json.dumps(v, ensure_ascii=False) if isinstance(v, (dict, list)) else v) for k, v in l.items()})
    log(f'gravou {nome} · {len(linhas)} linhas')


def main(saida):
    pasta = os.path.join(saida, 'ted')
    os.makedirs(pasta, exist_ok=True)
    hoje = datetime.date.today()
    atual = get('/data-atualizacao', {})

    programas = tudo('/programas')
    acoes = tudo('/programas-acoes-orcamentarias')
    planos = tudo('/planos-acao')
    termos = tudo('/termos-execucao')
    notas = tudo('/notas-credito')
    eventos = tudo('/eventos')
    pfs = tudo('/programacoes-financeiras')
    trfs = tudo('/programacoes-financeiras-trf')
    crono = tudo('/planos-trabalho-cronogramas')
    analises = tudo('/planos-acao-analises')
    pareceres = tudo('/planos-acao-pareceres')
    metas = tudo('/planos-acao-metas')

    prog = {p['id_programa']: p for p in programas}
    # escopo: TED enviado (programa de UG da SDR) ou recebido/executado por UG da SDR; ou com nota de crédito de/para UG da SDR
    ids = set()
    for p in planos:
        pr = prog.get(p.get('id_programa'), {})
        if s(pr.get('unidade_gestora_descentralizadora')) in UGS or s(p.get('unidade_descentralizada_gestora')) in UGS or s(p.get('unidade_responsavel_execucao_gestora')) in UGS:
            ids.add(p['id_plano_acao'])
    for nc in notas:
        if s(nc.get('cd_ug_emitente_nota')) in UGS or s(nc.get('cd_ug_favorecida_nota')) in UGS:
            ids.add(nc.get('id_plano_acao'))
    pl = [p for p in planos if p['id_plano_acao'] in ids]
    log(f'TEDs no escopo das UGs da SDR: {len(pl)}')

    por = _agrupa
    termo_p = por(termos, 'id_plano_acao')
    nc_p = por([x for x in notas if x.get('id_plano_acao') in ids], 'id_plano_acao')
    ev_n = por(eventos, 'id_nota')
    pf_p = por([x for x in pfs if x.get('id_plano_acao') in ids], 'id_plano_acao')
    trf_pf = por(trfs, 'id_programacao')
    cr_p = por([x for x in crono if x.get('id_plano_acao') in ids], 'id_plano_acao')
    an_p = por([x for x in analises if x.get('id_plano_acao') in ids], 'id_plano_acao')
    pa_p = por([x for x in pareceres if x.get('id_plano_acao') in ids], 'id_plano_acao')
    ac_g = por(acoes, 'id_programa')

    # notas de crédito com o valor dos eventos
    ncs = []
    for p_id, lst in nc_p.items():
        for nc in lst:
            evs = ev_n.get(nc['id_nota'], [])
            ncs.append({**{k: v for k, v in nc.items()}, 'valor_eventos': round(sum(n(e.get('vl_evento')) for e in evs), 2),
                        'ptres': ' | '.join(sorted({s(e.get('cd_ptres_evento')) for e in evs if e.get('cd_ptres_evento')})),
                        'plano_interno': ' | '.join(sorted({s(e.get('cd_plano_interno_evento')) for e in evs if e.get('cd_plano_interno_evento')})),
                        'natureza': ' | '.join(sorted({s((e.get('natureza_despesa_evento') or {}).get('codigo_natureza')) for e in evs if e.get('natureza_despesa_evento')})),
                        'resultado_primario': ' | '.join(sorted({s(e.get('ptres_resultado_primario')) for e in evs if e.get('ptres_resultado_primario')})),
                        'autor_emenda': ' | '.join(sorted({s(e.get('ptres_codigo_autor_emenda')) for e in evs if s(e.get('ptres_codigo_autor_emenda')) not in ('', '0', 'None')}))})
    ev_sdr = [e for p_id in ids for nc in nc_p.get(p_id, []) for e in ev_n.get(nc['id_nota'], [])]
    # programações financeiras com o valor dos itens TRF
    pfl = []
    for p_id, lst in pf_p.items():
        for pf in lst:
            its = trf_pf.get(pf['id_programacao'], [])
            pfl.append({**pf, 'valor_trf': round(sum(n(i.get('vl_valor_trf')) for i in its), 2), 'qtd_itens_trf': len(its)})

    linhas = []
    for p in pl:
        pid = p['id_plano_acao']
        pr = prog.get(p.get('id_programa'), {})
        tm = (termo_p.get(pid) or [{}])[-1]
        nn = [x for x in ncs if x['id_plano_acao'] == pid]
        nn_ok = [x for x in nn if 'CANCEL' not in s(x.get('tx_situacao_nota')).upper() and 'ESTORN' not in s(x.get('tx_situacao_nota')).upper()]
        pp = [x for x in pfl if x['id_plano_acao'] == pid]
        pp_ok = [x for x in pp if 'CANCEL' not in s(x.get('tx_situacao_programacao')).upper()]
        total = n(p.get('vl_total_plano_acao'))
        v_nc = round(sum(x['valor_eventos'] for x in nn_ok), 2)
        v_pf = round(sum(x['valor_trf'] for x in pp_ok), 2)
        ug_desc = s(pr.get('unidade_gestora_descentralizadora'))
        ug_rec = s(p.get('unidade_descentralizada_gestora'))
        ug_exe = s(p.get('unidade_responsavel_execucao_gestora'))
        papel = 'Enviado' if ug_desc in UGS else 'Recebido' if (ug_rec in UGS or ug_exe in UGS) else ('Enviado' if any(s(x.get('cd_ug_emitente_nota')) in UGS for x in nn) else 'Recebido')
        fim = s(p.get('dt_fim_vigencia'))[:10]
        try:
            dias = (datetime.date.fromisoformat(fim) - hoje).days
        except ValueError:
            dias = ''
        hist = sorted(an_p.get(pid, []) + pa_p.get(pid, []), key=lambda x: s(x.get('dt_data_parecer')) or '')
        ult = hist[-1] if hist else {}
        cr = sorted(cr_p.get(pid, []), key=lambda x: (n(x.get('ano_cronograma_plano_trabalho')), n(x.get('mes_cronograma_plano_trabalho'))))
        prox = [x for x in cr if (int(n(x.get('ano_cronograma_plano_trabalho'))), int(n(x.get('mes_cronograma_plano_trabalho')))) >= (hoje.year, hoje.month)]
        linhas.append({
            'Nº TED (SIAFI)': s(p.get('sq_instrumento')),
            'Ano do TED': s(p.get('aa_instrumento')) or s(p.get('aa_ano_plano_acao')),
            'Código do plano de ação': s(p.get('codigo_plano_acao')),
            'Enviado / recebido': papel,
            'UG descentralizadora': ug_desc,
            'Unidade descentralizadora': s(pr.get('unidade_descentralizadora')),
            'Órgão descentralizador': s(pr.get('descentralizadora_sup')),
            'UG descentralizada': ug_rec,
            'Unidade descentralizada': s(p.get('unidade_descentralizada')),
            'Órgão descentralizado': s(p.get('descentralizada_sup')),
            'UG executora': ug_exe,
            'Programa': (s(pr.get('tx_codigo_programa')) + ' · ' + s(pr.get('tx_nome_programa'))).strip(' ·'),
            'Ação orçamentária': ' | '.join(sorted({s(a.get('tx_codigo_acao_orcamentaria')) for a in ac_g.get(p.get('id_programa'), []) if a.get('tx_codigo_acao_orcamentaria')})),
            'Objeto': s(p.get('tx_objeto_plano_acao')).replace('\n', ' '),
            'Situação do plano de ação': s(p.get('tx_situacao_plano_acao')),
            'Situação do termo': s(tm.get('tx_situacao_termo')),
            'Processo SEI': s(tm.get('tx_num_processo_sei')),
            'Data de assinatura': br(tm.get('dt_assinatura_termo')),
            'Início da vigência': br(p.get('dt_inicio_vigencia')),
            'Fim da vigência': br(p.get('dt_fim_vigencia')),
            'Dias para o fim': dias,
            'Valor firmado': round(total, 2),
            'Descentralizado (notas de crédito)': v_nc,
            'Orçamento pendente': round(max(0.0, total - v_nc), 2),
            'Repassado (programação financeira)': v_pf,
            'A repassar': round(max(0.0, total - v_pf), 2),
            'Notas de crédito': ' | '.join(s(x.get('tx_numero_nota')) for x in nn_ok if x.get('tx_numero_nota')),
            'Programações financeiras': ' | '.join(s(x.get('tx_numero_programacao')) for x in pp_ok if x.get('tx_numero_programacao')),
            'PTRES': ' | '.join(sorted({x['ptres'] for x in nn if x['ptres']})),
            'Resultado primário': ' | '.join(sorted({x['resultado_primario'] for x in nn if x['resultado_primario']})),
            'Emenda (autor)': ' | '.join(sorted({x['autor_emenda'] for x in nn if x['autor_emenda']})),
            'Próxima parcela do cronograma': (f"{int(n(prox[0].get('mes_cronograma_plano_trabalho'))):02d}/{int(n(prox[0].get('ano_cronograma_plano_trabalho')))} · {n(prox[0].get('valor_cronograma_plano_trabalho')):.2f}" if prox else ''),
            'Último parecer / análise': (br(ult.get('dt_data_parecer')) + ' · ' + s(ult.get('resultado_parecer') or ult.get('resultado_analise')) + ' · ' + s(ult.get('tp_analise_parecer') or ult.get('tx_situacao_analise'))).strip(' ·') if ult else '',
            'Link do termo': s((tm.get('link_termo_execucao') or {}).get('tx_link') if isinstance(tm.get('link_termo_execucao'), dict) else tm.get('link_termo_execucao')),
            'Nº da NS do termo': s((tm.get('formalizacao_termo_execucao') or {}).get('tx_numero_ns_termo')),
            'id_plano_acao': pid,
        })
    linhas.sort(key=lambda r: (r['Ano do TED'], r['Nº TED (SIAFI)']), reverse=True)
    gravar(pasta, 'ted_planilha.csv', linhas)
    gravar(pasta, 'ted_notas_credito.csv', ncs)
    gravar(pasta, 'ted_eventos.csv', ev_sdr)
    gravar(pasta, 'ted_programacoes.csv', pfl)
    gravar(pasta, 'ted_cronograma.csv', [x for l in cr_p.values() for x in l])
    gravar(pasta, 'ted_analises_pareceres.csv', [dict(x, tipo='parecer' if 'id_parecer' in x else 'análise') for l in list(an_p.values()) + list(pa_p.values()) for x in l])
    gravar(pasta, 'ted_metas.csv', [x for x in metas if x.get('id_plano_acao') in ids])
    gravar(pasta, 'ted_programas.csv', [p for p in programas if s(p.get('unidade_gestora_descentralizadora')) in UGS or s(p.get('unidade_gestora_acompanhamento')) in UGS])
    cont = defaultdict(int)
    for l in linhas:
        cont[l['Enviado / recebido'] + ' · ' + l['Situação do plano de ação']] += 1
    json.dump({'data_api': atual, 'gerado_em': datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=-3))).strftime('%d/%m/%Y %H:%M'),
               'teds': len(linhas), 'por_situacao': dict(cont), 'log': LOG}, open(os.path.join(pasta, 'ted_atualizacao.json'), 'w'), ensure_ascii=False, indent=1)


def _agrupa(lista, k):
    g = defaultdict(list)
    for x in lista:
        g[x.get(k)].append(x)
    return g


if __name__ == '__main__':
    main(sys.argv[1] if len(sys.argv) > 1 else 'saida')
