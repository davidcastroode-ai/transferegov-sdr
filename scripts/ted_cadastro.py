"""Cadastro único de TEDs (etapa 1 · 03/11/2026).

Junta todas as fontes e responde "quais TEDs existem":
  T = relatório do Tesouro (TED × contas contábeis)      ted/ted_tesouro.csv
  N = notas de crédito do Tesouro (desde 2017)           ted/ted_tesouro_nc.csv
  P = programações financeiras do Tesouro                 ted/ted_tesouro_pf.csv
  A = API de TED do Transferegov (termos com nº)          ted/ted_planilha.csv
  C = controle interno da equipe (4 abas)                 ted/ted_equipe.csv

Regra: um TED existe quando tem nº no SIAFI e aparece em pelo menos uma fonte oficial (T, N, P ou A).
Só no controle interno → "a confirmar". Dispensa de TED e plano de ação sem nº não são TED: vão em listas à parte.
Saídas: ted/ted_cadastro.csv · ted/ted_cadastro_extras.json
"""
import csv, json, os, re, sys
from collections import defaultdict
from datetime import date, datetime

SAIDA = sys.argv[1] if len(sys.argv) > 1 else 'saida'
P = os.path.join(SAIDA, 'ted')
HOJE = date.today()


def ler(nome):
    p = os.path.join(P, nome)
    if not os.path.exists(p):
        print('sem', nome); return []
    return list(csv.DictReader(open(p, encoding='utf-8')))


def num(v):
    try:
        return float(str(v).replace(',', '.')) if str(v).strip() not in ('', '-') else 0.0
    except ValueError:
        return 0.0


def dt(v):
    v = str(v or '').strip()
    m = re.match(r'(\d{2})/(\d{2})/(\d{4})', v)
    if m:
        return date(int(m[3]), int(m[2]), int(m[1]))
    if re.fullmatch(r'\d{5}(\.0)?', v):           # data do Excel (nº de série)
        return date(1899, 12, 30).fromordinal(date(1899, 12, 30).toordinal() + int(float(v)))
    m = re.match(r'(\d{4})-(\d{2})-(\d{2})', v)
    return date(int(m[1]), int(m[2]), int(m[3])) if m else None


def br(d):
    return d.strftime('%d/%m/%Y') if d else ''


def proc(v):
    m = re.search(r'(\d{5})\.?(\d{6})/?(\d{4})-?(\d{2})', str(v or ''))
    return f'{m[1]}.{m[2]}/{m[3]}-{m[4]}' if m else ''


ID_TED = re.compile(r'^(\d{6}|1[A-Z]{2}[A-Z0-9]{3})$')
SIT_API = {'EM_EXECUCAO': 'Em execução', 'CUMPRIMENTO_OBJETO_INICIADO': 'Prestação de contas (iniciada)',
           'CUMPRIMENTO_OBJETO_ENVIADO_ANALISE': 'Prestação de contas (em análise)', 'CUMPRIMENTO_OBJETO_APROVADO': 'Concluído (aprovado)',
           'CUMPRIMENTO_OBJETO_APROVADO_COM_RESSALVAS': 'Concluído (aprovado com ressalvas)', 'PENDENTE_REGISTRO_NO_SIAFI': 'Pendente de registro no SIAFI'}
SIT_CTRL = {'TED vigente': 'Em execução', 'Prestação de contas': 'Prestação de contas', 'Aprovado / concluído': 'Concluído (aprovado)'}


def main():
    te, nc, pf, api, eq = ler('ted_tesouro.csv'), ler('ted_tesouro_nc.csv'), ler('ted_tesouro_pf.csv'), ler('ted_planilha.csv'), ler('ted_equipe.csv')
    R = defaultdict(lambda: {'fontes': set(), 'proc': set(), 'nc': 0.0, 'nc_dev': 0.0, 'pf': 0.0, 'n_nc': 0, 'n_pf': 0, 'datas': [],
                             'ug_desc': '', 'ug_rec': '', 'nome_rec': '', 'acao': set(), 'objeto': '', 'fir_t': 0.0, 'fir_a': 0.0, 'fir_c': 0.0,
                             'sit_t': '', 'sit_a': '', 'aba_c': '', 'fim': [], 'ini': None, 'dep': '', 'ug_resp': '', 'recebido': False})
    dispensas, sem_no = [], []
    for r in te:
        x = R[r['ted']]; x['fontes'].add('Tesouro'); x['proc'].add(proc(r['processo']))
        x['ug_desc'] = x['ug_desc'] or r['ug_emit']; x['ug_rec'] = x['ug_rec'] or r['ug_fav']; x['nome_rec'] = x['nome_rec'] or r['nome_fav']
        x['fir_t'] = num(r['fir']); x['sit_t'] = r['situacao']; x['objeto'] = x['objeto'] or r['objeto']
        x['ini'] = x['ini'] or dt(r['ini']); f = dt(r['fim']); f and x['fim'].append(('Tesouro', f))
    for r in nc:
        if not r['ted']:
            continue
        x = R[r['ted']]; x['fontes'].add('NC'); x['n_nc'] += 1; v = num(r['valor']); d = dt(r['data']); d and x['datas'].append(d)
        if r['ug_emit'] in ('420013', '130141', '130010', '130255', '135098'):
            x['nc'] += v; x['ug_desc'] = x['ug_desc'] or r['ug_emit']; x['ug_rec'] = x['ug_rec'] or r['ug_fav']; x['nome_rec'] = x['nome_rec'] or r['nome_fav']
        else:
            x['nc_dev'] += v          # nota de crédito devolvida pela unidade que recebeu
        r['acao'] and x['acao'].add(r['acao']); x['proc'].add(proc(r['obs']))
    for r in pf:
        x = R[r['ted']]; x['fontes'].add('PF'); x['n_pf'] += 1; x['pf'] += num(r['valor']); d = dt(r['data']); d and x['datas'].append(d)
        x['proc'].add(proc(r['obs']))
    for r in api:
        n = r['Nº TED (SIAFI)'].strip()
        if not n:
            sem_no.append({'plano': r['Código do plano de ação'], 'ug_desc': r['UG descentralizadora'], 'recebedora': r['Unidade descentralizada'],
                           'situacao_plano': r['Situação do plano de ação'], 'situacao_termo': r['Situação do termo'], 'processo': r['Processo SEI'],
                           'valor': num(r['Valor firmado']), 'objeto': r['Objeto'][:300]})
            continue
        x = R[n]; x['fontes'].add('API'); x['proc'].add(proc(r['Processo SEI'])); x['fir_a'] = num(r['Valor firmado'])
        x['sit_a'] = r['Situação do termo']; x['recebido'] = r['Enviado / recebido'] == 'Recebido'
        x['ug_desc'] = x['ug_desc'] or r['UG descentralizadora']; x['ug_rec'] = x['ug_rec'] or r['UG descentralizada']; x['nome_rec'] = x['nome_rec'] or r['Unidade descentralizada']
        r['Ação orçamentária'] and x['acao'].add(r['Ação orçamentária']); x['objeto'] = r['Objeto'] or x['objeto']
        x['ini'] = x['ini'] or dt(r['Início da vigência']); f = dt(r['Fim da vigência']); f and x['fim'].append(('API', f))
    for r in eq:
        t = r['ted'].strip()
        if r['Aba do controle'] == 'Dispensa de TED' or not ID_TED.match(t):
            dispensas.append({'processo': r['Processo'] or t, 'recebedora': r['Unidade'], 'departamento': r['Departamento'], 'valor': num(r['Firmado / total']),
                              'aba': r['Aba do controle'], 'situacao': r['Situação / tratamento'], 'objeto': (r['Objeto'] or '')[:300]})
            continue
        x = R[t]; x['fontes'].add('Controle'); x['proc'].add(proc(r['Processo'])); x['aba_c'] = r['Aba do controle']
        x['fir_c'] = num(r['Firmado / total']); x['dep'] = r['Departamento']; x['ug_resp'] = r['UG responsável']
        x['nome_rec'] = x['nome_rec'] or r['Unidade']; x['objeto'] = x['objeto'] or r['Objeto']
        r['Ação'] and x['acao'].add(r['Ação']); f = dt(r['Fim (controle)']); f and x['fim'].append(('Controle', f))

    # mesmo processo com mais de um nº de TED: possível duplicidade (ou aditivo registrado com outro nº)
    por_proc = defaultdict(set)
    for k, x in R.items():
        for p in x['proc']:
            p and por_proc[p].add(k)
    linhas = []
    for k, x in R.items():
        f = x['fontes']
        oficial = f & {'Tesouro', 'NC', 'PF', 'API'}
        irmaos = set().union(*[por_proc[p] for p in x['proc'] if p]) - {k} if x['proc'] else set()
        if 'API' in f and x['sit_a'] == 'PENDENTE_REGISTRO_NO_SIAFI' and not (f & {'Tesouro', 'NC', 'PF'}):
            reg = sorted(i for i in irmaos if R[i]['fontes'] & {'Tesouro', 'NC', 'PF'})
            cls = ('Provável nº duplicado · no SIAFI é o ' + ', '.join(reg)) if reg else 'Assinado · pendente de registro no SIAFI'
        elif oficial:
            cls = 'Confirmado'
        else:
            cls = 'A confirmar (só no controle interno)'
        fim = None
        for fonte in ('Controle', 'API', 'Tesouro'):          # vale a data do controle da equipe, depois API, depois Tesouro
            fs = [d for s, d in x['fim'] if s == fonte]
            if fs:
                fim = max(fs); break
        # situação: controle da equipe > API > Tesouro > pela data de fim
        if x['aba_c'] in SIT_CTRL:
            sit = SIT_CTRL[x['aba_c']]
        elif x['sit_a'] in SIT_API:
            sit = SIT_API[x['sit_a']]
        elif x['sit_t'] == 'CONCLUIDO':
            sit = 'Concluído (Tesouro)'
        elif x['sit_t'] in ('CANCELADO', 'EXCLUIDO'):
            sit = x['sit_t'].capitalize()
        elif fim:
            sit = 'Em execução (pela data de fim)' if fim >= HOJE else 'Vigência encerrada · sem registro de prestação de contas'
        elif f <= {'NC', 'PF'}:
            sit = 'Sem situação registrada · só NC/PF no SIAFI'
        else:
            sit = 'Sem informação de situação'
        ds = sorted(x['datas'])
        ano = (x['ini'] or (ds[0] if ds else None))
        outros = sorted(set().union(*[por_proc[p] for p in x['proc'] if p]) - {k}) if x['proc'] else []
        firmado = x['fir_t'] or x['fir_a'] or x['fir_c'] or x['nc']
        linhas.append({
            'Nº TED': k, 'Classificação': cls, 'Situação': sit, 'Enviado / recebido': 'Recebido' if x['recebido'] else 'Enviado',
            'UG descentralizadora': x['ug_desc'], 'UG que recebeu': x['ug_rec'], 'Unidade que recebeu': x['nome_rec'],
            'Processo': ' · '.join(sorted(p for p in x['proc'] if p)), 'Ação': ' · '.join(sorted(x['acao'])),
            'Ano': ano.year if ano else '', 'Início': br(x['ini']), 'Fim da vigência': br(fim),
            'Valor firmado': round(firmado, 2), 'NC enviada': round(x['nc'], 2), 'NC devolvida': round(x['nc_dev'], 2), 'PF repassada': round(x['pf'], 2),
            'Qtde NC': x['n_nc'], 'Qtde PF': x['n_pf'],
            'Tesouro': 'sim' if 'Tesouro' in f else '', 'NC': 'sim' if 'NC' in f else '', 'PF': 'sim' if 'PF' in f else '',
            'API Transferegov': 'sim' if 'API' in f else '', 'Controle da equipe': x['aba_c'] if 'Controle' in f else '',
            'Departamento': x['dep'], 'Mesmo processo de': ' · '.join(outros), 'Objeto': re.sub(r'\s+', ' ', x['objeto'] or '')[:400]})
    ordem = lambda c: 0 if c == 'Confirmado' else 1 if c.startswith('Assinado') else 2 if c.startswith('Provável') else 3
    linhas.sort(key=lambda r: (ordem(r['Classificação']), -(r['Ano'] or 0), r['Nº TED']))
    with open(os.path.join(P, 'ted_cadastro.csv'), 'w', encoding='utf-8', newline='') as fh:
        w = csv.DictWriter(fh, fieldnames=list(linhas[0].keys())); w.writeheader(); w.writerows(linhas)
    json.dump({'gerado_em': datetime.now().strftime('%d/%m/%Y %H:%M'), 'dispensas': dispensas, 'planos_sem_no': sem_no},
              open(os.path.join(P, 'ted_cadastro_extras.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    from collections import Counter
    print('ted_cadastro.csv ·', len(linhas), 'TEDs ·', dict(Counter(r['Classificação'] for r in linhas)), '· dispensas', len(dispensas), '· planos sem nº', len(sem_no))


if __name__ == '__main__':
    main()
