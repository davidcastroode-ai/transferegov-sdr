"""Monta a base do assistente virtual (assistente/base.json) a partir de:
- fontes/conceitos_1.py e conceitos_2.py (210 perguntas conceituais com resposta)
- fontes/operacionais.json (210 perguntas de situação, ligadas a consultas aos dados do painel)
Gera variações, palavras-chave, sinônimos e a lista de normas.
Uso: python assistente/montar_base.py
"""
import json, os, re, sys, unicodedata, datetime

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(AQUI, 'fontes'))
from conceitos_1 import CONVENIO, FOMENTO, REPASSE
from conceitos_2 import TED, CONTRATOS, ORCAMENTO, FINANCEIRO

PL = 'https://www.planalto.gov.br/ccivil_03/'
NORMAS = {
    'D11531': ['Decreto nº 11.531/2023', PL + '_ato2023-2026/2023/decreto/d11531.htm'],
    'PC33': ['Portaria Conjunta MGI/MF/CGU nº 33/2023', 'https://www.gov.br/transferegov/pt-br/legislacao/portarias/portaria-conjunta-mgi-mf-cgu-no-33-de-30-de-agosto-de-2023'],
    'PC28': ['Portaria Conjunta MGI/MF/CGU nº 28/2024 (regime simplificado)', 'https://www.gov.br/transferegov/pt-br/legislacao/portarias'],
    'L14133': ['Lei nº 14.133/2021', PL + '_ato2019-2022/2021/lei/l14133.htm'],
    'L13019': ['Lei nº 13.019/2014 (MROSC)', PL + '_ato2011-2014/2014/lei/l13019.htm'],
    'D8726': ['Decreto nº 8.726/2016', PL + '_ato2015-2018/2016/decreto/d8726.htm'],
    'D11948': ['Decreto nº 11.948/2024', PL + '_ato2023-2026/2024/decreto/d11948.htm'],
    'D10426': ['Decreto nº 10.426/2020 (TED)', PL + '_ato2019-2022/2020/decreto/d10426.htm'],
    'D12841': ['Decreto nº 12.841/2026 (altera o TED)', PL + '_ato2023-2026/2026/decreto/d12841.htm'],
    'P892': ['Portaria SEGES/MGI nº 892/2025', 'https://www.gov.br/transferegov/pt-br/legislacao/portarias'],
    'D11246': ['Decreto nº 11.246/2022', PL + '_ato2019-2022/2022/decreto/d11246.htm'],
    'D11462': ['Decreto nº 11.462/2023', PL + '_ato2023-2026/2023/decreto/d11462.htm'],
    'IN5': ['IN SEGES/MP nº 5/2017', 'https://www.gov.br/compras/pt-br/acesso-a-informacao/legislacao'],
    'L4320': ['Lei nº 4.320/1964', PL + 'leis/l4320.htm'],
    'LC101': ['Lei Complementar nº 101/2000', PL + 'leis/lcp/lcp101.htm'],
    'D93872': ['Decreto nº 93.872/1986', PL + 'decreto/d93872.htm'],
    'LDO': ['Lei nº 15.321/2025 (LDO 2026)', PL + '_ato2023-2026/2025/lei/l15321.htm'],
    'LOA': ['Lei nº 15.346/2026 (LOA 2026)', PL + '_ato2023-2026/2026/lei/l15346.htm'],
}

# sinônimos: termo canônico -> formas como as pessoas escrevem (sem acento, minúsculas)
SINONIMOS = {
    'convenio': ['convenio', 'convenios', 'conv', 'convenente', 'concedente'],
    'fomento': ['termo de fomento', 'termos de fomento', 'fomento', 'tf', 'mrosc', 'osc', 'oscs', 'organizacao da sociedade civil', 'entidade sem fins lucrativos'],
    'repasse': ['contrato de repasse', 'contratos de repasse', 'repasse', 'cr', 'mandataria', 'caixa', 'agente financeiro', 'operacao de repasse'],
    'ted': ['ted', 'teds', 'termo de execucao descentralizada', 'termos de execucao descentralizada', 'descentralizacao', 'destaque', 'unidade descentralizada'],
    'contrato': ['contrato administrativo', 'contratos administrativos', 'contrato', 'contratos', 'contratos.gov', 'contratos.gov.br', 'comprasnet', 'fornecedor', 'contratado', 'empresa contratada'],
    'ata': ['ata de registro de precos', 'ata', 'arp', 'registro de precos', 'srp'],
    'instrumento': ['instrumento', 'instrumentos', 'parceria', 'parcerias', 'transferencia', 'transferencias'],
    'proposta': ['proposta', 'propostas', 'pleito'],
    'emenda': ['emenda', 'emendas', 'emenda parlamentar', 'parlamentar', 'deputado', 'senador', 'bancada'],
    'pc': ['prestacao de contas', 'prestacoes de contas', 'prestar contas', 'pc', 'pcs', 'relatorio de cumprimento do objeto', 'rco', 'relatorio de execucao'],
    'vigencia': ['vigencia', 'vigente', 'vigentes', 'vencimento', 'vence', 'vencer', 'vencido', 'vencida', 'termino', 'fim da vigencia', 'data final', 'expira'],
    'prorrogacao': ['prorrogacao', 'prorrogar', 'prorroga', 'aditivo de prazo', 'estender', 'extensao de prazo', 'prorrogado'],
    'aditivo': ['aditivo', 'termo aditivo', 'ta', 'apostilamento', 'aditamento'],
    'desembolso': ['desembolso', 'desembolsado', 'desembolsar', 'liberacao', 'liberado', 'liberada', 'liberar', 'parcela', 'parcelas', 'repassado', 'recurso liberado', 'dinheiro'],
    'empenho': ['empenho', 'empenhos', 'empenhado', 'empenhar', 'nota de empenho', 'ne', 'nes'],
    'liquidacao': ['liquidacao', 'liquidado', 'liquidar', 'ateste', 'atesto', 'atestada', 'atestado'],
    'pagamento': ['pagamento', 'pagamentos', 'pago', 'paga', 'pagar', 'ordem bancaria', 'ob', 'quitado', 'quitacao'],
    'saldo': ['saldo', 'disponivel', 'resta', 'restante', 'sobrou', 'falta liberar', 'a desembolsar', 'a pagar'],
    'situacao': ['situacao', 'status', 'andamento', 'como esta', 'como anda', 'etapa', 'fase', 'pe', 'posicao'],
    'pt': ['plano de trabalho', 'pt', 'ajuste de pt', 'ajuste do plano', 'reprogramacao', 'remanejamento'],
    'suspensiva': ['clausula suspensiva', 'suspensiva', 'condicao suspensiva', 'pendencia de projeto'],
    'rap': ['restos a pagar', 'rap', 'raps', 'inscrito', 'inscritos', 'reinscrito', 'processados', 'nao processados'],
    'orcamento': ['orcamento', 'orcamentaria', 'orcamentario', 'dotacao', 'credito', 'creditos', 'loa', 'ldo', 'ppa', 'limite'],
    'pendencia': ['pendencia', 'pendencias', 'pendente', 'diligencia', 'diligencias', 'irregularidade', 'irregular', 'restricao', 'problema', 'impedimento', 'inadimplente', 'inadimplencia', 'cauc'],
    'tce': ['tce', 'tomada de contas especial', 'tomada de contas'],
    'obra': ['obra', 'obras', 'medicao', 'medicoes', 'vistoria', 'execucao fisica', 'percentual fisico', 'engenharia', 'projeto basico', 'lae'],
    'encerramento': ['encerramento', 'encerrado', 'encerrar', 'concluido', 'concluida', 'finalizado', 'finalizar', 'baixa'],
    'devolucao': ['devolucao', 'devolver', 'gru', 'restituir', 'saldo remanescente', 'recolher'],
    'documento': ['documento', 'documentos', 'documentacao', 'papel', 'papeis', 'certidao', 'certidoes'],
    'legislacao': ['legislacao', 'lei', 'decreto', 'portaria', 'norma', 'normas', 'regra', 'regras', 'base legal', 'fundamento'],
    'municipio': ['municipio', 'municipios', 'prefeitura', 'prefeituras', 'cidade', 'cidades'],
    'quanto': ['quanto', 'quantos', 'quantas', 'valor', 'valores', 'total', 'soma', 'montante'],
    'nf': ['nota fiscal', 'notas fiscais', 'nf', 'nfe', 'fatura', 'faturas', 'conta'],
}

# abreviações usadas para gerar variações das perguntas
ABREV = [('prestação de contas', 'PC'), ('termo de fomento', 'TF'), ('plano de trabalho', 'PT'), ('nota de empenho', 'NE'), ('restos a pagar', 'RAP'),
         ('termo de execução descentralizada', 'TED'), ('Termo de Execução Descentralizada (TED)', 'TED'), ('contrato de repasse', 'CR'), ('convênio', 'conv'),
         ('organização da sociedade civil', 'OSC'), ('cláusula suspensiva', 'suspensiva')]


def sem_acento(s):
    return ''.join(c for c in unicodedata.normalize('NFD', s) if unicodedata.category(c) != 'Mn').lower()


def variacoes(p):
    """Formas alternativas da mesma pergunta (sem acento, abreviações, modo falado)."""
    v = set()
    base = p.rstrip('?')
    v.add(sem_acento(base))
    for longo, curto in ABREV:
        if longo.lower() in base.lower():
            v.add(sem_acento(re.sub(re.escape(longo), curto, base, flags=re.I)))
    m = re.match(r'^(O que é|O que são)\s+(.*)$', base, re.I)
    if m:
        alvo = m.group(2)
        v.update(sem_acento(x) for x in [f'o que significa {alvo}', f'explique {alvo}', f'defina {alvo}', f'{alvo} o que é', f'me explica {alvo}'])
    m = re.match(r'^Como\s+(.*)$', base, re.I)
    if m:
        resto = m.group(1)
        v.update(sem_acento(x) for x in [f'como faço para {resto}', f'de que forma {resto}', f'qual o procedimento para {resto}', f'passo a passo para {resto}'])
    m = re.match(r'^Qual é (a|o)\s+(.*)$', base, re.I)
    if m:
        v.update(sem_acento(x) for x in [f'qual {m.group(1)} {m.group(2)}', f'me diga {m.group(1)} {m.group(2)}', f'{m.group(2)}'])
    m = re.match(r'^(Quais)\s+(.*)$', base, re.I)
    if m:
        v.update(sem_acento(x) for x in [f'lista de {m.group(2)}', f'quais sao {m.group(2)}'])
    v.discard(sem_acento(base))
    return sorted(v)[:8]


STOP = set('a o as os de da do das dos e em no na nos nas um uma uns umas para por com sem que qual quais como ao aos se ja ou ser esta este esse essa isso ha tem pode sao e foi'.split())


def palavras(*txt):
    t = sem_acento(' '.join(txt))
    return sorted({w for w in re.findall(r'[a-z0-9.]+', t) if len(w) > 2 and w not in STOP})


itens = []
CAT = [('CV', 'Convênio', CONVENIO, 'Área técnica do departamento responsável e COAPI/SDR'), ('TF', 'Termo de fomento', FOMENTO, 'Gestor da parceria e COAPI/SDR'),
       ('CR', 'Contrato de repasse', REPASSE, 'Mandatária (Caixa) e área técnica da SDR'), ('TD', 'TED', TED, 'Área técnica responsável pelo TED'),
       ('CT', 'Contratos', CONTRATOS, 'Gestor e fiscais do contrato'), ('OR', 'Orçamento', ORCAMENTO, 'Área de orçamento e finanças da SDR'),
       ('FN', 'Financeiro', FINANCEIRO, 'Área de execução orçamentária e financeira da UG')]
for sig, cat, lista, setor in CAT:
    for i, (p, sub, kw, r, normas, sis) in enumerate(lista, 1):
        itens.append({'id': f'{sig}-{i:02d}', 'tipo': 'conceito', 'cat': cat, 'sub': sub, 'p': p, 'v': variacoes(p), 'kw': palavras(kw, p, sub),
                      'r': r, 'normas': normas, 'sis': sis, 'setor': setor})

# ---------- perguntas de situação: consulta aos dados do painel ----------
OPS = json.load(open(os.path.join(AQUI, 'fontes', 'operacionais.json'), encoding='utf-8'))
NOME_OP = {'1': ('CV', 'Convênio', 'inst'), '2': ('TF', 'Termo de fomento', 'inst'), '3': ('CR', 'Contrato de repasse', 'inst'), '4': ('TD', 'TED', 'ted'),
           '5': ('CT', 'Contratos', 'contrato'), '6': ('OR', 'Orçamento', 'orc'), '7': ('FN', 'Financeiro', 'fin')}


def campo_inst(q):
    s = sem_acento(q)
    regras = [('proxima', r'proxima|prioritaria'), ('encerramento', r'encerr|concluid|finaliz|recebida formalmente'), ('pc', r'prestacao de contas|relatorio de (conclusao|execucao|cumprimento)|diligencia pendente na|respondeu|corre'),
              ('prorrogacao', r'prorroga'), ('ajuste', r'plano de trabalho|alteracao|reprograma'), ('suspensiva', r'suspensiva'),
              ('fisico', r'percentual|metas|executad|obra|medic|vistoria|cronograma|atividades|ordem de servico|licitat|projeto tecnico|iniciad|atrasad|atraso'),
              ('assinatura', r'assinad|formaliz|publicad'), ('vigencia', r'vigent|vigencia|vencid|vencimento|prazo|termino|ativo'),
              ('devolucao', r'devolver|remanescente|nao utilizad|devolucao'),
              ('valores', r'liberad|repassad|saldo|valor|pago|medido|descentraliz|empenhad|liquidad|credito|recursos financeiros|parcela'),
              ('pendencia', r'pendencia|restricao|irregularidade|documento|restricao|impeca|impedindo|apto|aptos')]
    for c, rx in regras:
        if re.search(rx, s):
            return c
    return 'situacao'


def campo_ctr(q):
    s = sem_acento(q)
    if re.search(r'ocorrenc|notificac|fiscais|gestor|documentacao trabalhista|postos|profissionais|niveis de servico|nao conformidade|escalas|regular', s):
        return 'sem_dado'
    for c, rx in [('vigencia', r'vigen|vigencia|inicio e termino|ativo|suspenso|encerrad|concluido'), ('pagamentos', r'fatura|pagamento|pagas|pendentes de pag'),
                  ('aditivo', r'aditivo|prorrogac'), ('valores', r'saldo|valor|percentual|executad|orcamentario'), ('ata', r'\bata\b')]:
        if re.search(rx, s):
            return c
    return 'situacao'


def campo_orc(q):
    s = sem_acento(q)
    if re.search(r'solicitacao|pedido|status da|validad|compativel|restricao na fonte|remanejamento|adicional|registrad', s):
        return 'sem_dado'
    for c, rx in [('rap', r'restos a pagar'), ('ne', r'nota de empenho|saldo de empenho|reforco|anulacao|empenho ja'), ('disponivel', r'saldo|disponivel|dotacao disponivel|existe orcamento|existe dotacao|bloqueio|contingenciamento'),
                  ('percentual', r'percentual|situacao atual'), ('dotacao', r'autorizado|dotacao'), ('pago', r'pago'), ('liquidado', r'liquidado'), ('empenhado', r'empenhado|comprometendo'),
                  ('descentralizado', r'descentraliz')]:
        if re.search(rx, s):
            return c
    return 'percentual'


def campo_fin(q):
    s = sem_acento(q)
    if re.search(r'atestada|retenc|cadastral|bancari|divergencia|cronologica|duplicidade|devolucao de valores|limite financeiro|documental|recebida|bruto', s):
        return 'sem_dado'
    for c, rx in [('total', r'total de pagamentos|periodo'), ('fornecedor', r'fornecedor|por contrato'), ('rap', r'restos a pagar'), ('ne', r'.')]:
        if re.search(rx, s):
            return c
    return 'ne'


SEM_DADO = {
    'contrato': 'Essa informação é do acompanhamento do fiscal e do gestor e não vem nos dados do painel. Consulte o processo no SEI e o Contratos.gov.br (ocorrências, faturas e documentos), ou o gestor do contrato.',
    'orc': 'Esse andamento fica no processo (SEI) e no SIOP/SIAFI e não vem nos dados do painel. Consulte a área de orçamento e finanças da SDR.',
    'fin': 'Esse detalhe (ateste, retenções, dados bancários, documentos) fica no processo de pagamento (SEI/SIAFI) e não vem nos dados do painel. Consulte o setor de execução financeira.',
}
for cat_n, n, q in OPS:
    sig, cat, intent = NOME_OP[cat_n]
    campo = campo_inst(q) if intent in ('inst', 'ted') else campo_ctr(q) if intent == 'contrato' else campo_orc(q) if intent == 'orc' else campo_fin(q)
    it = {'id': f'{sig}-S{n:02d}', 'tipo': 'dado', 'cat': cat, 'sub': 'Situação', 'p': q, 'v': variacoes(q), 'kw': palavras(q), 'intent': intent, 'campo': campo,
          'precisa': {'inst': 'número do instrumento', 'ted': 'número do TED ou do processo', 'contrato': 'número do contrato ou o fornecedor',
                      'orc': 'UG ou ação (opcional)', 'fin': 'número da nota de empenho ou o fornecedor'}[intent]}
    if campo == 'sem_dado':
        it['r'] = SEM_DADO[intent]
    if cat in ('Convênio', 'Termo de fomento', 'Contrato de repasse'):
        it['mod'] = {'Convênio': 'CONVENIO', 'Termo de fomento': 'FOMENTO', 'Contrato de repasse': 'REPASSE'}[cat]
    itens.append(it)

base = {'versao': datetime.date.today().isoformat(), 'normas': NORMAS, 'sinonimos': SINONIMOS, 'itens': itens,
        'regras': ['Não afirmar que algo foi aprovado, pago, liberado ou concluído sem o dado do painel ou fonte oficial.',
                   'Sempre mostrar a fonte e a data dos dados.', 'Pedir o número do instrumento quando ele for indispensável.',
                   'Sem resposta segura: oferecer as categorias e registrar a pergunta como sem resposta.']}
caminho = os.path.join(AQUI, 'base.json')
json.dump(base, open(caminho, 'w', encoding='utf-8'), ensure_ascii=False, separators=(',', ':'))
from collections import Counter
print(len(itens), 'perguntas ·', Counter(i['tipo'] for i in itens), '·', os.path.getsize(caminho) // 1024, 'KB')
print(Counter((i.get('intent'), i.get('campo')) for i in itens if i['tipo'] == 'dado'))
