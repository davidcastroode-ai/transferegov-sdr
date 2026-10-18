"""
Robô Transferegov · SDR/MAPA — arquivo da aba "Base Celebração" (Planilha Execução Parcerias SDR), só UG 420013.

Lê PASTA/instrumentos.csv e PASTA/pagamentos.csv (gravados pelo processar.py) e grava
PASTA/planilha_celebracao_420013.csv com as colunas A a AH da aba, na mesma ordem e com os mesmos títulos.
As colunas que a planilha calcula ou que a equipe preenche (N, O, S, T, Y, AD, AH) vão vazias: o Apps Script não mexe nelas.

Uso:  python scripts/celebracao.py PASTA_DE_SAIDA
"""
import csv, os, sys, datetime, collections

csv.field_size_limit(10**9)
UG = '420013'
TITULOS = ['Ano Proposta', 'Nº Instrumento', 'Nome Parlamentar', 'UF', 'Nº Emenda', 'Nº Proposta', 'Modalidade', 'Ação Orçamentária',
           'Nome Proponente', 'CNPJ', 'Nº Processo', 'Objeto', 'Situação Instrumento', 'Status Financeiro', 'Observação',
           'Data Início de Vigência Conv.', 'Data Fim de Vigência Conv.', 'Data Limite Prestação de Contas', 'Dias a Vencer',
           'Data Ultima atualização', 'Resultado Primário', 'Valor Global', 'Valor de Repasse', 'Valor Desembolsado Acumulado',
           'Valor a Desembolsar', 'Valor de Contrapartida', 'Ingresso de Contrapartida', 'Rendimento Aplicação', 'Saldo em conta',
           'Executor', 'Valor Total Execução PAD', 'Último Pagamento Convenente', 'Sem Desembolso Concedente',
           'Percentual Não Desembolsado a Executar']


def fl(v):
    try:
        return float(str(v or 0).replace(',', '.'))
    except ValueError:
        return 0.0


def faixa(dias):
    if dias is None:
        return ''
    if dias <= 90:
        return 'Até 90 dias'
    if dias <= 180:
        return 'Acima de 90 até 180 dias'
    if dias <= 365:
        return 'Acima de 180 até 365 dias'
    return 'Acima de 365 dias'


def main(pasta):
    hoje = datetime.date.today()
    pago, ult = collections.defaultdict(float), {}
    with open(os.path.join(pasta, 'pagamentos.csv'), encoding='utf-8') as fh:
        for x in csv.DictReader(fh):
            n = x['NR_CONVENIO']
            pago[n] += fl(x['VL_PAGO'])
            try:
                d = datetime.datetime.strptime(x['DATA_PAG'][:10], '%d/%m/%Y').date()
                if n not in ult or d > ult[n]:
                    ult[n] = d
            except ValueError:
                pass
    rpc = collections.defaultdict(collections.Counter)
    with open(os.path.join(pasta, 'empenhos.csv'), encoding='utf-8') as fh:
        for e in csv.DictReader(fh):
            v = (e.get('RESULTADO_PRIMARIO') or '').strip()
            if v:
                rpc[e['NR_CONVENIO']][v] += 1
    linhas = []
    with open(os.path.join(pasta, 'instrumentos.csv'), encoding='utf-8') as fh:
        for r in csv.DictReader(fh):
            if r['ug_emitente'] != UG or not r['nr_instrumento'] or r['situacao'] in ('', 'Convênio Anulado', 'Cancelado') or r['situacao'].startswith('Proposta/Plano'):
                continue
            n = r['nr_instrumento']
            des, ing, ren = fl(r['valor_desembolsado']), fl(r['ingresso_contrapartida']), fl(r['rendimento_aplicacao'])
            base = des + ing + ren
            # % executado pelo convenente: pago aos fornecedores ÷ (desembolsado + contrapartida + rendimento)
            pad = round(min(pago[n] / base, 1), 4) if base > 0 and n in pago else (0 if base > 0 else '')
            dsd = int(r['dias_sem_desembolso']) if (r['dias_sem_desembolso'] or '').isdigit() else None
            ug_pg = faixa((hoje - ult[n]).days) if n in ult else ('Sem Desembolso' if des <= 0 else '-')
            acao = ((r['acao_orcamentaria'] or '') or (r.get('acao_pela_ptres') or '')).split('|')[0].strip()   # sem ação: pega pela PTRES das notas de empenho
            rp = rpc[n].most_common(1)[0][0] if rpc[n] else ''
            linha = {
                'Ano Proposta': r['ano_proposta'], 'Nº Instrumento': n, 'Nome Parlamentar': r['parlamentar'], 'UF': r['uf'],
                'Nº Emenda': r['nr_emenda'], 'Nº Proposta': (lambda p: p.split('/')[0].zfill(6) + '/' + p.split('/')[1] if '/' in p else p)(r['nr_proposta'] or ''), 'Modalidade': r['modalidade'],
                'Ação Orçamentária': acao[-4:] if acao else '', 'Nome Proponente': r['proponente'], 'CNPJ': r['cnpj_proponente'],
                'Nº Processo': ''.join(c for c in r['nr_processo'] if c.isdigit()), 'Objeto': (r['objeto'] or '').upper(), 'Situação Instrumento': r['situacao'],
                'Data Início de Vigência Conv.': r['inicio_vigencia'], 'Data Fim de Vigência Conv.': r['fim_vigencia'],
                'Data Limite Prestação de Contas': r['limite_prestacao_contas'], 'Resultado Primário': rp,
                'Valor Global': r['valor_global'], 'Valor de Repasse': r['valor_repasse'], 'Valor Desembolsado Acumulado': r['valor_desembolsado'],
                'Valor de Contrapartida': r['valor_contrapartida'], 'Ingresso de Contrapartida': r['ingresso_contrapartida'],
                'Rendimento Aplicação': r['rendimento_aplicacao'], 'Saldo em conta': r['saldo_em_conta'],
                'Valor Total Execução PAD': pad, 'Último Pagamento Convenente': ug_pg,
                'Sem Desembolso Concedente': faixa(dsd) if dsd is not None else '-',
            }
            linhas.append([linha.get(t, '') for t in TITULOS])
    with open(os.path.join(pasta, 'planilha_celebracao_420013.csv'), 'w', encoding='utf-8', newline='') as fh:
        w = csv.writer(fh)
        w.writerow(TITULOS)
        w.writerows(linhas)
    print(f'planilha_celebracao_420013.csv · {len(linhas)} instrumentos da UG {UG}', flush=True)


if __name__ == '__main__':
    main(sys.argv[1] if len(sys.argv) > 1 else 'saida')
