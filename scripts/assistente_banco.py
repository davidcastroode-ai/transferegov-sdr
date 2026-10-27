"""Banco de perguntas para testar o assistente virtual do Painel SDR (roda todo dia no robô).

Junta três fontes num arquivo só (assistente_banco.json):
  1. perguntas de DADOS geradas a partir das bases (UG × UF × situação × RP × modalidade × natureza jurídica × programa),
     escritas de vários jeitos; cada uma leva a especificação do filtro ("spec"), e o painel calcula o gabarito
     com a mesma regra da tela da Parceria SDR;
  2. perguntas de CONCEITO da base de 420 perguntas (assistente/base.json), com variações de escrita; o gabarito é o id do item;
  3. perguntas REAIS feitas no painel (aba de registro, quando configurada em config/assistente_registro.txt).
Uso: python scripts/assistente_banco.py SAIDA
"""
import csv, json, os, random, re, sys, unicodedata, urllib.request, io, datetime

csv.field_size_limit(10**9)
P = sys.argv[1] if len(sys.argv) > 1 else 'saida'
AQUI = os.path.dirname(os.path.abspath(__file__))
random.seed(int(datetime.date.today().strftime('%Y%m%d')))   # muda todo dia: a cada rodada entram combinações novas

UF_NOME = {'AC': 'Acre', 'AL': 'Alagoas', 'AP': 'Amapá', 'AM': 'Amazonas', 'BA': 'Bahia', 'CE': 'Ceará', 'DF': 'Distrito Federal', 'ES': 'Espírito Santo',
           'GO': 'Goiás', 'MA': 'Maranhão', 'MT': 'Mato Grosso', 'MS': 'Mato Grosso do Sul', 'MG': 'Minas Gerais', 'PA': 'Pará', 'PB': 'Paraíba', 'PR': 'Paraná',
           'PE': 'Pernambuco', 'PI': 'Piauí', 'RJ': 'Rio de Janeiro', 'RN': 'Rio Grande do Norte', 'RS': 'Rio Grande do Sul', 'RO': 'Rondônia', 'RR': 'Roraima',
           'SC': 'Santa Catarina', 'SP': 'São Paulo', 'SE': 'Sergipe', 'TO': 'Tocantins'}
DO_UF = {'BA': 'na', 'PB': 'na', 'AL': 'em', 'GO': 'em', 'MG': 'em', 'PE': 'em', 'RO': 'em', 'RR': 'em', 'SC': 'em', 'SP': 'em', 'SE': 'em', 'MT': 'no', 'MS': 'no'}


def ler(nome):
    c = os.path.join(P, nome)
    return list(csv.DictReader(open(c, encoding='utf-8'))) if os.path.exists(c) else []


inst = ler('painel_instrumentos.csv')
plan = {r['Nº Instrumento']: r for r in ler('planilha_parcerias.csv')}
ativos = [r for r in inst if r.get('situacao') == 'Em execução']
print(f'banco: {len(inst)} instrumentos, {len(ativos)} em execução')

# ---------------------------------------------------------------- 1. perguntas de dados
UGS = ['130141', '135098', '420013', '130255', '130010']
TEMAS = [  # (código do tema no gabarito, jeitos de dizer)
    ('vigentes', ['vigentes', 'em execução', 'ativos', 'em andamento']),
    ('pc', ['em prestação de contas', 'com prestação de contas em andamento']),
    ('vencem30', ['que vencem nos próximos 30 dias', 'com vigência vencendo em 30 dias']),
    ('vencidos', ['com vigência vencida', 'que já venceram e continuam em execução']),
    ('semdes', ['sem desembolso há mais de 180 dias', 'parados sem desembolso']),
    ('suspensiva', ['em cláusula suspensiva']),
]
NOMES = {'': ['instrumentos', 'parcerias', 'instrumentos (convênios, termos e contratos de repasse)'], 'CONVENIO': ['convênios'], 'FOMENTO': ['termos de fomento'], 'REPASSE': ['contratos de repasse']}
ABERT = ['quantos {n} {t} {f}?', 'quantidade de {n} {t} {f}', 'total de {n} {t} {f}', 'me mostra {n} {t} {f}', 'quais {n} estão {t} {f}?',
         'preciso saber quantos {n} {t} existem {f}', 'qual o número de {n} {t} {f}?']


def f_ug(u):
    return random.choice([f'da UG {u}', f'pela {u}', f'na ug {u}', f'da {u}', f'na unidade gestora {u}'])


def f_uf(uf):
    nome = UF_NOME[uf]
    return random.choice([f'no estado {"do" if uf in ("MT","MS","PA","PR","PI","RJ","RN","RS","ES","AM","AP","AC","CE","DF","MA","TO") else "de" if uf in ("GO","MG","PE","RO","RR","SC","SP","SE","AL") else "da"} {nome}',
                          f'{DO_UF.get(uf, "no")} {nome}', f'em {uf}', f'na UF {uf}'])


def f_rp(rp):
    extra = {'2': ['discricionários (RP2)', 'RP 2'], '6': ['de emenda individual (RP6)', 'RP6'], '7': ['de emenda de bancada (RP7)', 'RP 7'],
             '8': ['de emenda de comissão (RP8)', 'RP8'], '9': ['RP 9']}.get(rp, [])
    return random.choice([f'de resultado primário {rp}', f'RP{rp}', f'com resultado primário (RP{rp})'] + extra)


def f_nat(n):
    return {'Administração Pública Municipal': random.choice(['com municípios', 'com prefeituras']),
            'Organização da Sociedade Civil': random.choice(['com OSC', 'com entidades privadas', 'com organizações da sociedade civil']),
            'Administração Pública Estadual ou do Distrito Federal': random.choice(['com os estados', 'com governos estaduais'])}.get(n)


def ug_de(r):   # a mesma UG da planilha (coluna UG), como na tela
    p = plan.get(r['nr_instrumento'])
    return (p and p.get('UG')) or r.get('ug_emitente', '')


def rp_de(r):
    p = plan.get(r['nr_instrumento'])
    return re.sub(r'\D', '', (p and p.get('Resultado Primário')) or '')[:1]


def mod_de(r):
    m = (r.get('modalidade') or '').upper()
    return 'FOMENTO' if 'FOMENTO' in m else 'REPASSE' if 'REPASSE' in m else 'CONVENIO' if 'CONVENIO' in m else ''


dados = []
vistos = set()
for _ in range(6000):
    if len(dados) >= 1500:
        break
    r = random.choice(ativos if random.random() < 0.8 else inst)   # parte de um instrumento real: a combinação sempre existe na base
    spec = {}
    tema, jeitos = random.choice(TEMAS[:1] * 4 + TEMAS)
    spec['tema'] = tema
    partes = []
    escolhas = random.sample(['ug', 'uf', 'rp', 'mod', 'nat'], k=random.choice([1, 1, 2, 2, 3]))
    if 'ug' in escolhas and ug_de(r) in UGS:
        spec['ug'] = ug_de(r); partes.append(f_ug(spec['ug']))
    if 'uf' in escolhas and r.get('uf') in UF_NOME:
        spec['uf'] = r['uf']; partes.append(f_uf(r['uf']))
    if 'rp' in escolhas and rp_de(r):
        spec['rp'] = rp_de(r); partes.append(f_rp(spec['rp']))
    if 'nat' in escolhas and f_nat(r.get('natureza_juridica', '')):
        spec['nat'] = r['natureza_juridica']; partes.append(f_nat(r['natureza_juridica']))
    mod = mod_de(r) if 'mod' in escolhas else ''
    if mod:
        spec['mod'] = mod
    if len(spec) < 2:
        continue
    random.shuffle(partes)
    q = random.choice(ABERT).format(n=random.choice(NOMES[mod]), t=random.choice(jeitos), f=' '.join(partes)).replace('  ', ' ').replace(' ?', '?').strip()
    q = q[0].upper() + q[1:] if random.random() < 0.5 else q
    chave = json.dumps(spec, sort_keys=True) + q
    if chave in vistos:
        continue
    vistos.add(chave)
    dados.append({'id': f'D{len(dados)+1:04d}', 'tipo': 'dado', 'q': q, 'spec': spec})

# ---------------------------------------------------------------- 2. perguntas de conceito (base de 420)
base = json.load(open(os.path.join(AQUI, '..', 'assistente', 'base.json'), encoding='utf-8'))
PREF = ['', 'me explica: ', 'gostaria de saber: ', 'por favor, ', 'uma dúvida: ', 'você sabe me dizer ', 'pode me informar ']
conc = []
for it in base['itens']:
    frases = [it['p']] + list(it.get('v') or [])[:2]
    for f in frases:
        q = random.choice(PREF) + (f[0].lower() + f[1:] if f else f)
        conc.append({'id': f"C-{it['id']}-{len(conc)}", 'tipo': it['tipo'], 'q': q.strip(), 'esperado': it['id'], 'campo': it.get('campo', '')})

# ---------------------------------------------------------------- 3. perguntas reais (registro do painel)
reais = []
cfg = os.path.join(AQUI, '..', 'config', 'assistente_registro.txt')
if os.path.exists(cfg):
    for u in [l.strip() for l in open(cfg, encoding='utf-8') if l.strip() and not l.startswith('#')]:
        try:
            txt = urllib.request.urlopen(urllib.request.Request(u, headers={'User-Agent': 'robo-sdr'}), timeout=60).read().decode('utf-8')
            for r in csv.DictReader(io.StringIO(txt)):
                q = (r.get('Pergunta') or '').strip()
                if q and (r.get('Origem') or 'uso') == 'uso':
                    reais.append({'id': f'R{len(reais)+1:04d}', 'tipo': 'real', 'q': q, 'quando': r.get('Data', ''), 'avaliacao': r.get('Avaliação', ''),
                                  'resposta': (r.get('Resposta') or '')[:160]})
        except Exception as e:
            print('registro: não leu', u[-50:], e)
    # cada pergunta real uma vez só (a mais recente)
    un = {}
    for r in reais:
        un[re.sub(r'\s+', ' ', r['q'].lower())] = r
    reais = list(un.values())

out = {'gerado_em': datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=-3))).strftime('%d/%m/%Y %H:%M'),
       'dados': dados, 'conceitos': conc, 'reais': reais}
os.makedirs(P, exist_ok=True)
json.dump(out, open(os.path.join(P, 'assistente_banco.json'), 'w', encoding='utf-8'), ensure_ascii=False, separators=(',', ':'))
print(f'banco do assistente: {len(dados)} perguntas de dados · {len(conc)} de conceito · {len(reais)} reais')
