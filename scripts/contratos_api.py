"""Contratos.gov.br (API pública https://contratos.comprasnet.gov.br/api) das UGs da SDR — complemento da Base Contratos do painel.
Grava em PASTA (branch dados): contratos_api_ctr.csv, contratos_api_emp.csv, contratos_api_fat.csv, contratos_api_his.csv, contratos_api_res.csv
(mesmas colunas da planilha "Base API Contratos"). Consulta a API uma vez por dia; nas outras rodadas reaproveita os arquivos do dia.
Os valores financeiros da API NÃO são usados (não batem com o SIAFI): o painel usa o EXE/RAP do Tesouro.
Uso: python scripts/contratos_api.py PASTA_SAIDA"""
import csv, json, os, re, shutil, sys, time, urllib.request, urllib.error
from concurrent.futures import ThreadPoolExecutor

BASE = 'https://contratos.comprasnet.gov.br'
UGS = ['130010', '130141', '130255', '135098', '420013']
OUT = sys.argv[1] if len(sys.argv) > 1 else 'saida'
ANT = os.environ.get('CONTRATOS_ANTERIOR', '')   # pasta com os arquivos da rodada anterior
HOJE = time.strftime('%d/%m/%Y')
ARQ = {
    'ctr': ['ID contrato (API)', 'UG atual', 'UG de origem', 'Nome UG origem', 'Nº contrato', 'Tipo', 'Categoria', 'Modalidade', 'Situação', 'Fornecedor', 'CNPJ/CPF',
            'Processo', 'Objeto', 'Início vigência', 'Fim vigência', 'Valor inicial', 'Valor global', 'Valor acumulado', 'Nº parcelas', 'Valor parcela', 'Link transparência', 'Consultado em'],
    'emp': ['ID contrato (API)', 'UG contrato', 'Nº contrato', 'UG da NE', 'Nota de empenho', 'Plano interno', 'Data emissão'],
    'fat': ['ID contrato (API)', 'UG contrato', 'Nº contrato', 'Nº fatura', 'Emissão', 'Vencimento', 'Valor (− glosa)', 'Situação', 'Data liquidação', 'NP / documento SIAFI'],
    'his': ['ID contrato (API)', 'UG contrato', 'Nº contrato', 'Tipo do termo', 'Nº do termo', 'Data assinatura', 'Fim vigência', 'Valor global (novo)', 'Observação'],
    'res': ['ID contrato (API)', 'UG contrato', 'Nº contrato', 'Função', 'Nome', 'Portaria', 'Situação'],
    'arq': ['ID contrato (API)', 'UG contrato', 'Nº contrato', 'Tipo', 'Descrição', 'Link PDF', 'Link SEI', 'Origem'],
}
nome = lambda k: os.path.join(OUT, f'contratos_api_{k}.csv')


def get(caminho):
    url = BASE + caminho
    for t in range(4):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers={'Accept': 'application/json', 'User-Agent': 'painel-sdr-mapa/1.0'}), timeout=90) as r:
                return json.loads(r.read())
        except urllib.error.HTTPError as e:
            if e.code in (400, 401, 403, 404):
                return None
            time.sleep(3 * (t + 1))
        except Exception:
            time.sleep(3 * (t + 1))
    raise RuntimeError('falhou: ' + url)


def num(s):
    s = str(s or '').strip()
    if not s:
        return 0.0
    return float(s.replace('.', '').replace(',', '.')) if ',' in s else float(s)


def br(v):
    return f'{v:.2f}'.replace('.', ',')


def gravar(k, linhas):
    with open(nome(k), 'w', encoding='utf-8', newline='') as fh:
        w = csv.writer(fh); w.writerow(ARQ[k]); w.writerows(linhas)


def reaproveitar():
    if not ANT:
        return False
    p = os.path.join(ANT, 'contratos_api_ctr.csv')
    if not os.path.exists(p):
        return False
    l = list(csv.DictReader(open(p, encoding='utf-8')))
    if not l or l[0].get('Consultado em') != HOJE:
        return False
    if any(not os.path.exists(os.path.join(ANT, f'contratos_api_{k}.csv')) or os.path.getsize(os.path.join(ANT, f'contratos_api_{k}.csv')) < 10 for k in ARQ):
        return False   # arquivo novo (ex.: arquivos do contrato) ainda não existe: consulta a API de novo
    for k in ARQ:
        q = os.path.join(ANT, f'contratos_api_{k}.csv')
        if os.path.exists(q):
            shutil.copy(q, nome(k))
    print(f'Contratos.gov.br: reaproveitados os arquivos de hoje ({len(l)} contratos)', flush=True)
    return True


def main():
    if reaproveitar():
        return
    t0 = time.time()
    cs = []
    for ug in UGS:
        for ativo, cam in [(1, f'/api/contrato/ug/{ug}'), (0, f'/api/contrato/inativo/ug/{ug}')]:
            l = get(cam) or []
            for c in l if isinstance(l, list) else []:
                c['_ug'] = ug; cs.append(c)
    print(f'Contratos.gov.br: {len(cs)} contratos', flush=True)

    def det(c):
        i = c['id']
        return c, {k: (get(f'/api/contrato/{i}/{k}') or []) for k in ['empenhos', 'faturas', 'historico', 'responsaveis', 'arquivos']}
    with ThreadPoolExecutor(4) as ex:
        D = list(ex.map(det, cs))
    L = {k: [] for k in ARQ}
    for c, d in D:
        o = c['contratante']['orgao_origem']['unidade_gestora_origem']
        ch = [c['id'], c['_ug'], c.get('numero')]
        L['ctr'].append([c['id'], c['_ug'], o.get('codigo'), o.get('nome_resumido'), c.get('numero'), c.get('tipo'), c.get('categoria'), c.get('modalidade'), c.get('situacao'),
                         c['fornecedor'].get('nome'), c['fornecedor'].get('cnpj_cpf_idgener'), c.get('processo'), (c.get('objeto') or '').strip(), c.get('vigencia_inicio'), c.get('vigencia_fim'),
                         br(num(c.get('valor_inicial'))), br(num(c.get('valor_global'))), br(num(c.get('valor_acumulado'))), c.get('num_parcelas'), br(num(c.get('valor_parcela'))),
                         f"https://contratos.comprasnet.gov.br/transparencia/contratos/{c['id']}", HOJE])
        for e in d['empenhos'] if isinstance(d['empenhos'], list) else []:
            L['emp'].append(ch + [e.get('unidade_gestora'), e.get('numero'), (e.get('planointerno') or '')[:60], e.get('data_emissao')])
        for f in d['faturas'] if isinstance(d['faturas'], list) else []:
            L['fat'].append(ch + [f.get('numero'), f.get('emissao'), f.get('vencimento'), br(num(f.get('valor')) - num(f.get('glosa'))), f.get('situacao'), f.get('data_liquidacao'), f.get('sfadrao_id')])
        for h in sorted(d['historico'] if isinstance(d['historico'], list) else [], key=lambda h: h.get('data_assinatura') or ''):
            L['his'].append(ch + [h.get('tipo'), h.get('numero'), h.get('data_assinatura'), h.get('vigencia_fim'), br(num(h.get('novo_valor_global') or h.get('valor_global'))), (h.get('observacao') or '')[:200]])
        for r in d['responsaveis'] if isinstance(d['responsaveis'], list) else []:
            L['res'].append(ch + [r.get('funcao_id'), re.sub(r'^[\d\*\.\-]+\s*-\s*', '', r.get('usuario') or ''), r.get('portaria') or '', r.get('situacao')])
        for a in d['arquivos'] if isinstance(d['arquivos'], list) else []:
            sei = a.get('link_sei') or ''
            L['arq'].append(ch + [a.get('tipo'), (a.get('descricao') or '')[:200], a.get('path_arquivo') or '', '' if sei in ('null', 'None') else sei, a.get('origem') or ''])
    for k in ARQ:
        gravar(k, L[k])
    print('Contratos.gov.br: ' + ' · '.join(f'{k} {len(v)}' for k, v in L.items()) + f' · {time.time()-t0:.0f}s', flush=True)


if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        print(f'Contratos.gov.br: falhou ({e}); mantendo os arquivos anteriores', flush=True)
        if ANT:
            for k in ARQ:
                q = os.path.join(ANT, f'contratos_api_{k}.csv')
                if os.path.exists(q):
                    shutil.copy(q, nome(k))
