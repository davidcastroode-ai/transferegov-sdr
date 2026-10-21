"""Base Obrasgov (API pública https://api-publica.obrasgov.gestao.gov.br) das UGs da SDR.
1) empenhos com ug_emitente nas UGs da SDR -> ids dos projetos de investimento
2) para cada projeto: projeto, execução física, geometria, histórico de paralisação/cancelamento, contratos
Grava PASTA/obrasgov_obras.csv (uma linha por obra), obrasgov_empenhos.csv e obrasgov_paralisacoes.csv.
Uso: python scripts/obrasgov.py PASTA_SAIDA"""
import csv, json, os, sys, time, urllib.request, urllib.parse, urllib.error
from concurrent.futures import ThreadPoolExecutor

BASE = 'https://api-publica.obrasgov.gestao.gov.br/obrasgov/api'
UGS = ['130010', '130141', '130255', '135098', '420013']
OUT = sys.argv[1] if len(sys.argv) > 1 else 'saida'
os.makedirs(OUT, exist_ok=True)
TAM = 100


def get(caminho, **q):
    url = BASE + caminho + '?' + urllib.parse.urlencode(q)
    for tentativa in range(5):
        try:
            req = urllib.request.Request(url, headers={'Accept': 'application/json', 'User-Agent': 'painel-sdr-mapa/1.0'})
            with urllib.request.urlopen(req, timeout=90) as r:
                return json.loads(r.read())
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return {'data': []}
            if e.code in (429, 500, 502, 503, 504):
                time.sleep(3 * (tentativa + 1)); continue
            raise
        except Exception:
            time.sleep(3 * (tentativa + 1))
    raise RuntimeError('falhou: ' + url)


def todas(caminho, **q):
    out, p = [], 1
    while True:
        j = get(caminho, pagina=p, tamanho_da_pagina=TAM, **q)
        d = j.get('data') or []
        out += d
        tp = j.get('total_pages') or 1
        if p >= tp or not d:
            return out
        p += 1


def descobrir_base():
    global BASE
    for b in ['https://api-publica.obrasgov.gestao.gov.br/obrasgov/api', 'https://api-publica.obrasgov.gestao.gov.br']:
        try:
            BASE = b
            j = get('/empenho', pagina=1, tamanho_da_pagina=1)
            if 'data' in j:
                return
        except Exception:
            pass
    raise RuntimeError('não achei o caminho da API')


def main():
    t0 = time.time()
    descobrir_base()
    print('API:', BASE, flush=True)
    emp = []
    for ug in UGS:
        l = todas('/empenho', ug_emitente=ug)
        print(f'empenhos UG {ug}: {len(l)}', flush=True)
        emp += l
    ids = sorted({e.get('id_projeto_investimento') for e in emp if e.get('id_projeto_investimento')})
    print(f'projetos: {len(ids)} · {time.time()-t0:.0f}s', flush=True)

    def um(i):
        r = {'id': i}
        for k, c in [('proj', '/projeto-investimento'), ('fis', '/execucao-fisica'), ('geo', '/geometria'),
                     ('hist', '/historico-situacao-cancelada-paralisada'), ('ctr', '/contrato')]:
            try:
                r[k] = todas(c, id_projeto_investimento=i)
            except Exception as e:
                r[k] = []; r.setdefault('erros', []).append(f'{c}: {e}')
        return r
    with ThreadPoolExecutor(6) as ex:
        det = list(ex.map(um, ids))
    print(f'detalhes: {len(det)} · {time.time()-t0:.0f}s', flush=True)

    j = lambda l, k: ' | '.join(sorted({str(x.get(k)) for x in l if x.get(k) not in (None, '')}))
    soma = lambda l, k: round(sum(float(x.get(k) or 0) for x in l), 2)
    por_proj = {}
    for e in emp:
        por_proj.setdefault(e.get('id_projeto_investimento'), []).append(e)
    linhas, paral = [], []
    for r in det:
        p = (r['proj'] or [{}])[0]
        fis = sorted(r['fis'], key=lambda x: str(x.get('dt_atualizacao_execucao') or x.get('dt_cadastro_execucao') or ''))
        f = fis[-1] if fis else {}
        geo = r['geo']; hist = sorted(r['hist'], key=lambda x: str(x.get('data_historico_situacao_investimento') or ''))
        h = hist[-1] if hist else {}
        ctr = r['ctr']; c = max(ctr, key=lambda x: float(x.get('valor_global_contrato') or 0)) if ctr else {}
        es = por_proj.get(r['id'], [])
        for x in hist:
            paral.append({'id_projeto': r['id'], 'situacao': x.get('descricao_historico_situacao_investimento'), 'data': x.get('data_historico_situacao_investimento'),
                          'justificativa': x.get('justificativa_cancelada_paralisada'), 'tratativas': x.get('possui_tratativas_situacao_investimento'),
                          'fase_tratativas': x.get('fase_tratativas_situacao_investimento')})
        linhas.append({
            'ID projeto (Obrasgov)': r['id'], 'Nome do projeto': p.get('desc_nome'), 'Descrição': (p.get('desc_projeto') or '')[:500],
            'Situação': p.get('situacao'), 'Natureza': p.get('natureza_intervencao'), 'Espécie': p.get('especie_intervencao'),
            'UF': p.get('uf_principal') or j(geo, 'sg_uf'), 'Município': j(geo, 'no_municipio'), 'Cód. IBGE': j(geo, 'cod_ibge'),
            'Órgão responsável': p.get('organizacao_resp'),
            'Executor': ' | '.join(x.get('organizacao_executor') or '' for x in p.get('executores') or []),
            'CNPJ executor': ' | '.join(x.get('cnpj_executor') or '' for x in p.get('executores') or []),
            'Tomador': ' | '.join(x.get('organizacao_tomador') or '' for x in p.get('tomadores') or []),
            'Repassador': ' | '.join(str(x.get('organizacao_repassador') or x) for x in p.get('repassadores') or []),
            'Tipo de instrumento': f.get('tipo_instrumento'), 'Forma de execução': f.get('tipo_forma_execucao'),
            'Início previsto': p.get('dt_inicial_prevista'), 'Fim previsto': p.get('dt_final_prevista'),
            'Início efetivo': p.get('dt_inicial_efetiva'), 'Fim efetivo': p.get('dt_final_efetiva'),
            '% execução física': f.get('percentual_execucao_fisica'), 'Atualização da execução': f.get('dt_atualizacao_execucao') or f.get('dt_cadastro_execucao'),
            'Investimento previsto': round(sum(float(x.get('vl_investimento_previsto') or 0) for x in p.get('investimentos_previstos') or []), 2),
            'UG emitente': j(es, 'ug_emitente'), 'Notas de empenho': j(es, 'nr_empenho'), 'Ação orçamentária': j(es, 'acao_orcamentaria'),
            'Plano interno': j(es, 'plano_interno'), 'Autor da emenda': j(es, 'codigo_autor_emenda'),
            'Empenhado': soma(es, 'valor_empenho'), 'A liquidar': soma(es, 'aliquidar'), 'Liquidado': soma(es, 'liquidado'), 'Pago': soma(es, 'pago'),
            'RP inscrito': soma(es, 'rpinscrito'), 'RP a liquidar': soma(es, 'rpaliquidar'), 'RP pago': soma(es, 'rppago'),
            'Data da paralisação/cancelamento': h.get('data_historico_situacao_investimento'), 'Justificativa da paralisação': h.get('justificativa_cancelada_paralisada'),
            'Possui tratativas': h.get('possui_tratativas_situacao_investimento'), 'Fase das tratativas': h.get('fase_tratativas_situacao_investimento'),
            'Nº contrato': c.get('numero_contrato'), 'Fornecedor': c.get('fornecedor_contrato'), 'CNPJ fornecedor': c.get('cnpj_fornecedor_contrato'),
            'Valor global contrato': c.get('valor_global_contrato'), 'Fim vigência contrato': c.get('vigencia_fim_contrato'), 'Link transparência': c.get('link_transparencia'),
            'Atualizado em (API)': time.strftime('%d/%m/%Y'),
        })

    def gravar(nome, rows):
        if not rows:
            return
        with open(os.path.join(OUT, nome), 'w', encoding='utf-8', newline='') as fh:
            w = csv.DictWriter(fh, fieldnames=list(rows[0].keys())); w.writeheader(); w.writerows(rows)
        print(f'{nome}: {len(rows)} linhas', flush=True)
    gravar('obrasgov_obras.csv', linhas)
    gravar('obrasgov_empenhos.csv', [{k: (json.dumps(v, ensure_ascii=False) if isinstance(v, (list, dict)) else v) for k, v in e.items()} for e in emp])
    gravar('obrasgov_paralisacoes.csv', paral)
    with open(os.path.join(OUT, 'obrasgov_bruto.json'), 'w', encoding='utf-8') as fh:
        json.dump(det, fh, ensure_ascii=False)
    print(f'fim · {time.time()-t0:.0f}s', flush=True)


if __name__ == '__main__':
    main()
