"""Complemento Obrasgov (API pública https://api-publica.obrasgov.gestao.gov.br/obras), igual ao Tesouro nos TEDs:
os dados principais continuam do Transferegov e do Tesouro; a API só acrescenta, por instrumento, o que não temos:
justificativa da paralisação/cancelamento e tratativas, contrato da obra (empresa, valor, vigência, link),
% físico e data da última atualização no Obrasgov, local cadastrado.
Só para as obras ativas (não finalizadas). Roda a API uma vez por dia; nas outras rodadas reaproveita o arquivo do dia.
Grava PASTA/obrasgov_complemento.csv (uma linha por instrumento).
Uso: python scripts/obrasgov.py PASTA_SAIDA"""
import csv, io, json, os, sys, time, urllib.request, urllib.parse, urllib.error
from concurrent.futures import ThreadPoolExecutor

BASE = 'https://api-publica.obrasgov.gestao.gov.br/obras'
UGS = ['130010', '130141', '130255', '135098', '420013']
OUT = sys.argv[1] if len(sys.argv) > 1 else 'saida'
ARQ = os.path.join(OUT, 'obrasgov_complemento.csv')
ANTERIOR = os.environ.get('OBRASGOV_ANTERIOR', '')   # arquivo da rodada anterior (baixado da branch dados)
CAMPOS = ['nr_instrumento', 'id_projeto', 'situacao_api', 'pct_fisico_api', 'atualizacao_fisica', 'municipio_api', 'uf_api', 'cod_ibge',
          'paralisacao_situacao', 'paralisacao_data', 'paralisacao_justificativa', 'tratativas', 'fase_tratativas',
          'contrato_numero', 'contrato_fornecedor', 'contrato_cnpj', 'contrato_valor', 'contrato_fim_vigencia', 'contrato_link', 'consultado_em']


def get(caminho, **q):
    url = BASE + caminho + '?' + urllib.parse.urlencode(q)
    for t in range(5):
        try:
            req = urllib.request.Request(url, headers={'Accept': 'application/json', 'User-Agent': 'painel-sdr-mapa/1.0'})
            with urllib.request.urlopen(req, timeout=90) as r:
                return json.loads(r.read())
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return {'data': []}
            time.sleep(3 * (t + 1))
        except Exception:
            time.sleep(3 * (t + 1))
    raise RuntimeError('falhou: ' + url)


def todas(caminho, **q):
    out, p = [], 1
    while True:
        j = get(caminho, pagina=p, tamanho_da_pagina=100, **q)
        d = j.get('data') or []
        out += d
        if p >= (j.get('total_pages') or 1) or not d:
            return out
        p += 1


def reaproveitar():
    """Se o arquivo da rodada anterior é de hoje, copia e não chama a API."""
    if not ANTERIOR or not os.path.exists(ANTERIOR):
        return False
    linhas = list(csv.DictReader(open(ANTERIOR, encoding='utf-8')))
    if not linhas or linhas[0].get('consultado_em') != time.strftime('%d/%m/%Y'):
        return False
    with open(ARQ, 'w', encoding='utf-8', newline='') as fh:
        w = csv.DictWriter(fh, fieldnames=CAMPOS); w.writeheader(); w.writerows({k: l.get(k, '') for k in CAMPOS} for l in linhas)
    print(f'Obrasgov: reaproveitado o arquivo de hoje ({len(linhas)} instrumentos)', flush=True)
    return True


def main():
    if reaproveitar():
        return
    t0 = time.time()
    # NE -> instrumento (Transferegov) e situação da obra que já temos
    ne_inst = {}
    for x in csv.DictReader(open(os.path.join(OUT, 'empenhos.csv'), encoding='utf-8')):
        ne_inst[(x['UG_EMITENTE'], x['NR_EMPENHO'])] = x['NR_CONVENIO']
    sit_obra = {x['nr_instrumento']: x.get('situacao_obra', '') for x in csv.DictReader(open(os.path.join(OUT, 'painel_obras.csv'), encoding='utf-8'))}
    proj_inst = {}
    for ug in UGS:
        l = todas('/empenho', ug_emitente=ug)
        print(f'Obrasgov: {len(l)} empenhos da UG {ug}', flush=True)
        for e in l:
            n = ne_inst.get((str(e.get('ug_emitente')), e.get('nr_empenho')))
            if n and e.get('id_projeto_investimento'):
                proj_inst.setdefault(e['id_projeto_investimento'], n)
    ativos = {p: n for p, n in proj_inst.items() if sit_obra.get(n, '') not in ('Finalizada',)}
    print(f'Obrasgov: {len(proj_inst)} obras ligadas a instrumentos · {len(ativos)} ativas (não finalizadas)', flush=True)

    def um(item):
        p, n = item
        r = {'nr_instrumento': n, 'id_projeto': p, 'consultado_em': time.strftime('%d/%m/%Y')}
        try:
            pj = (todas('/projeto-investimento', id_projeto_investimento=p) or [{}])[0]
            r['situacao_api'] = pj.get('situacao') or ''
            fis = sorted(todas('/execucao-fisica', id_projeto_investimento=p), key=lambda x: str(x.get('dt_atualizacao_execucao') or x.get('dt_cadastro_execucao') or ''))
            if fis:
                r['pct_fisico_api'] = fis[-1].get('percentual_execucao_fisica')
                r['atualizacao_fisica'] = str(fis[-1].get('dt_atualizacao_execucao') or fis[-1].get('dt_cadastro_execucao') or '')[:10]
            geo = todas('/geometria', id_projeto_investimento=p)
            if geo:
                r['municipio_api'] = geo[0].get('no_municipio') or ''; r['uf_api'] = geo[0].get('sg_uf') or ''; r['cod_ibge'] = geo[0].get('cod_ibge') or ''
            if r['situacao_api'] in ('Paralisada', 'Cancelada', 'Inacabada') or sit_obra.get(n) in ('Paralisada', 'Inacabada'):
                h = sorted(todas('/historico-situacao-cancelada-paralisada', id_projeto_investimento=p), key=lambda x: str(x.get('data_historico_situacao_investimento') or ''))
                if h:
                    h = h[-1]
                    r.update(paralisacao_situacao=h.get('descricao_historico_situacao_investimento') or '', paralisacao_data=h.get('data_historico_situacao_investimento') or '',
                             paralisacao_justificativa=(h.get('justificativa_cancelada_paralisada') or '')[:600], tratativas=h.get('possui_tratativas_situacao_investimento') or '',
                             fase_tratativas=h.get('fase_tratativas_situacao_investimento') or '')
            ctr = todas('/contrato', id_projeto_investimento=p)
            if ctr:
                c = max(ctr, key=lambda x: float(x.get('valor_global_contrato') or 0))
                r.update(contrato_numero=c.get('numero_contrato') or '', contrato_fornecedor=c.get('fornecedor_contrato') or '', contrato_cnpj=c.get('cnpj_fornecedor_contrato') or '',
                         contrato_valor=c.get('valor_global_contrato') or '', contrato_fim_vigencia=c.get('vigencia_fim_contrato') or '', contrato_link=c.get('link_transparencia') or '')
        except Exception as e:
            print(f'Obrasgov: erro no projeto {p}: {e}', flush=True)
        return r
    with ThreadPoolExecutor(8) as ex:
        linhas = list(ex.map(um, sorted(ativos.items())))
    with open(ARQ, 'w', encoding='utf-8', newline='') as fh:
        w = csv.DictWriter(fh, fieldnames=CAMPOS); w.writeheader(); w.writerows({k: l.get(k, '') for k in CAMPOS} for l in linhas)
    print(f'Obrasgov: obrasgov_complemento.csv com {len(linhas)} instrumentos · '
          f'{sum(1 for l in linhas if l.get("paralisacao_justificativa"))} com justificativa de paralisação · '
          f'{sum(1 for l in linhas if l.get("contrato_numero"))} com contrato · {time.time()-t0:.0f}s', flush=True)


if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        # API fora do ar: mantém o arquivo anterior (mesmo de outro dia) para a página não perder o complemento
        print(f'Obrasgov: falhou ({e}); mantendo o arquivo anterior', flush=True)
        if ANTERIOR and os.path.exists(ANTERIOR):
            import shutil; shutil.copy(ANTERIOR, ARQ)
        sys.exit(0)
