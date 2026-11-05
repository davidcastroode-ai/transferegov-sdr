"""Histórico dos alertas (Parcerias e TED): o que entrou, o que saiu e como saiu, comparando com a última foto do dia anterior.
Entrada: saida/alertas.json (de alertas.py) e a foto anterior (variável HIST_ALERTAS = alertas_hist.json da rodada passada).
Saída:  saida/alertas_hist.json (fotos e contagens diárias, para a próxima rodada)
        saida/alertas.json ganha: item['novo']=1 · alerta['hist']={serie, novos, saiu, resolvidos, pioraram} · 'mud'={ref, itens:[…]}
Tipos de saída: resolvido (✓) · mudou (mudou de fase ou de alerta) · piorou (foi para um alerta mais grave) · conferir (saiu sem mudança que explique)
Uso: python scripts/alertas_hist.py saida
"""
import csv, datetime, gzip, json, os, re, sys

HOJE = datetime.date.today()
DIAS_SERIE = 60
f = lambda v: float(str(v or '0').replace(',', '.') or 0) if re.match(r'^-?[\d.,]+$', str(v or '0').strip() or '0') else 0.0
brl = lambda v: ('R$ ' + f'{v:,.2f}'.replace(',', 'X').replace('.', ',').replace('X', '.'))
# guardado na foto de cada item (o mínimo para explicar a saída no dia seguinte)
CAMPOS = ('num', 'nome', 'proponente', 'unid', 'uf', 'dep', 'ctrl', 'vprior', 'fim', 'prazo_pc', 'info', 'situacao', 'desembolsado', 'saldo', 'acomprovar', 'empenhado', 'nc', 'ult_des')
# um alerta "mais grave" para onde o item pode ter ido (não é resolução)
ESCALA = {'vig90': ('vig30', 'vigvenc'), 'vig30': ('vigvenc',), 'pc30': ('pcvenc',), 'pcvenc': ('inad', 'tce'), 'susp': ('vigvenc',), 'complem': (), 'analise': ()}


def ler(caminho):
    if not os.path.exists(caminho):
        return []
    abre = gzip.open if caminho.endswith('.gz') else open
    with abre(caminho, 'rt', encoding='utf-8-sig', newline='') as fh:
        return list(csv.DictReader(fh))


def chave_item(it):
    return str(it.get('num') or it.get('plano') or '').strip()


def foto_de(J):
    out = {}
    for grupo in ('parc', 'ted'):
        for a in J.get(grupo, []):
            k = a['menu'] + '|' + a['id']
            out[k] = {'sev': a['sev'], 'titulo': a['titulo'], 'itens': {chave_item(it): {c: it[c] for c in CAMPOS if it.get(c) not in (None, '')} for it in a['itens'] if chave_item(it)}}
    return out


def como_saiu(menu, id_, p, atual):
    """(tipo, texto) · p = item na foto de ontem · atual = registro de hoje (instrumento, TED, proposta) ou None."""
    if menu in ('parc', 'conv', 'repasse'):
        r = atual.get('inst', {}).get(p.get('num'))
        if not r:
            return 'conferir', 'não aparece mais na base do Transferegov · conferir'
        sit = r.get('situacao') or ''
        if re.search(r'TCE|Tomada de Contas', sit, re.I) or (r.get('em_processo_tce') or '').upper().startswith('SIM'):
            if id_ != 'tce':
                return 'piorou', 'foi para Tomada de Contas Especial'
        if id_ in ('vigvenc', 'vig30', 'vig90'):
            if r.get('fim_vigencia') and p.get('fim') and r['fim_vigencia'] != p['fim']:
                return 'resolvido', f"aditivo de prazo · nova vigência {r['fim_vigencia']}"
            if not re.search(r'Em execu', sit, re.I):
                return 'mudou', f'saiu de execução · situação: {sit}'
        if id_ in ('pcvenc', 'pc30'):
            if re.search(r'Presta.*(enviada|em An|Comprovada|Aprovad)|Aprovad|Conclu', sit, re.I):
                return 'resolvido', f'prestação de contas enviada · situação: {sit}'
            if r.get('limite_prestacao_contas') and p.get('prazo_pc') and r['limite_prestacao_contas'] != p['prazo_pc']:
                return 'resolvido', f"prazo da prestação de contas prorrogado para {r['limite_prestacao_contas']}"
            if (r.get('inadimplente_desde') or '').strip():
                return 'piorou', f"convenente registrado como inadimplente desde {r['inadimplente_desde']}"
        if id_ == 'susp':
            if not (r.get('clausula_suspensiva_ate') or '').strip():
                return 'resolvido', 'cláusula suspensiva retirada'
            if p.get('info') and r['clausula_suspensiva_ate'] not in p['info']:
                return 'resolvido', f"prazo da suspensiva prorrogado para {r['clausula_suspensiva_ate']}"
        if id_ == 'semdes':
            d = f(r.get('valor_desembolsado')) - (p.get('desembolsado') or 0)
            if d > 0.5:
                return 'resolvido', f"desembolso de {brl(d)}" + (f" em {r['ultimo_desembolso']}" if r.get('ultimo_desembolso') else '')
            if f(r.get('valor_a_desembolsar')) <= 0:
                return 'resolvido', 'não há mais valor a desembolsar'
        if id_ == 'saldo':
            d = (p.get('saldo') or 0) - f(r.get('saldo_em_conta'))
            if d > 0.5:
                return 'resolvido', f"saldo em conta caiu {brl(d)} (aplicado no objeto ou devolvido)"
        if id_ == 'ajuste' and not (r.get('ajuste_pt_aberto') or '').strip():
            return 'resolvido', 'ajuste do plano de trabalho analisado'
        if id_ == 'inad' and not (r.get('inadimplente_desde') or '').strip():
            return 'resolvido', 'inadimplência baixada'
        if id_ == 'obra':
            o = atual.get('obras', {}).get(p.get('num'))
            if o and str(o.get('dias_sem_medicao') or '').isdigit() and int(o['dias_sem_medicao']) <= 90:
                return 'resolvido', 'nova medição registrada no Obrasgov'
            if o and re.search(r'conclu|finaliz', o.get('situacao_obra') or '', re.I):
                return 'resolvido', f"obra {o.get('situacao_obra')}"
        if id_ == 'pcanal':
            if re.search(r'Aprovad|Conclu', sit, re.I):
                return 'resolvido', f'prestação de contas analisada · situação: {sit}'
            if re.search(r'Rejeitad|Reprovad|Impugn', sit, re.I):
                return 'mudou', f'prestação de contas analisada · situação: {sit}'
        if sit and p.get('situacao') and sit != p['situacao']:
            return 'mudou', f'situação mudou para: {sit}'
        return 'conferir', 'saiu da lista sem mudança identificada · conferir'
    if menu in ('ted', 'tedapi'):
        r = atual.get('ted', {}).get(p.get('num'))
        if not r:
            return 'conferir', 'não aparece mais na base do TED · conferir'
        if id_ in ('vigvenc', 'vig30', 'vig90'):
            fim = r.get('Fim da vigência (painel)') or ''
            if fim and p.get('fim') and fim != p['fim']:
                return 'resolvido', f'prorrogado · nova vigência {fim}'
            if r.get('Fase (painel)') and r['Fase (painel)'] != 'Em execução':
                return 'mudou', f"fase: {r['Fase (painel)']}"
        if id_ == 'ncsemne' and f(r.get('Empenhado pela unidade (NE)')) > 0:
            return 'resolvido', f"a unidade empenhou {brl(f(r.get('Empenhado pela unidade (NE)')))}"
        if id_ == 'semnc' and (f(r.get('NC no Tesouro')) > 0 or f(r.get('Descentralizado NC (API)')) > 0):
            return 'resolvido', 'nota de crédito emitida'
        if id_ == 'comprovar':
            ac = f(r.get('A comprovar (Tesouro)'))
            if ac <= 0.5:
                return 'resolvido', 'tudo comprovado no SIAFI'
            d = (p.get('acomprovar') or 0) - ac
            if d > 0.5:
                return 'resolvido', f'comprovado {brl(d)} no SIAFI'
        return 'conferir', 'saiu da lista sem mudança identificada · conferir'
    if menu == 'prop':
        r = atual.get('prop', {}).get(p.get('num'))
        sit = (r or {}).get('situacao_proposta') or ''
        if not r:
            return 'conferir', 'proposta não aparece mais na base · conferir'
        if re.search(r'Aprovad|Celebrad|Assinad|Em execu', sit, re.I):
            return 'resolvido', f'proposta analisada · situação: {sit}'
        if sit and sit != p.get('situacao'):
            return 'mudou', f'situação mudou para: {sit}'
        return 'conferir', 'saiu da lista sem mudança identificada · conferir'
    if menu == 'captacao':
        return 'resolvido', 'proposta cadastrada no Transferegov (ou emenda remanejada)'
    return 'conferir', 'saiu da lista sem mudança identificada · conferir'


def main(saida):
    caminho = os.path.join(saida, 'alertas.json')
    J = json.load(open(caminho, encoding='utf-8'))
    H = {}
    ant_arq = os.environ.get('HIST_ALERTAS') or os.path.join(saida, 'alertas_hist.json')
    try:
        H = json.load(open(ant_arq, encoding='utf-8'))
    except Exception:
        print('sem histórico anterior: começa hoje', flush=True)
    hoje = HOJE.isoformat()
    atual = foto_de(J)
    # a referência é a última foto de um dia anterior (as rodadas do mesmo dia comparam sempre com ontem)
    if H.get('foto', {}).get('data') and H['foto']['data'] < hoje:
        ref = H['foto']
    else:
        ref = H.get('foto_ant') or {}
    ant = ref.get('itens') or {}
    dias = H.get('dias', {})
    dias[hoje] = {k: len(v['itens']) for k, v in atual.items()}
    dias = {d: dias[d] for d in sorted(dias)[-DIAS_SERIE:]}
    datas8 = sorted(dias)[-8:]
    # registros de hoje, para explicar como cada item saiu
    reg = {'inst': {r['nr_instrumento']: r for r in ler(os.path.join(saida, 'painel_instrumentos.csv'))},
           'obras': {r['nr_instrumento']: r for r in ler(os.path.join(saida, 'painel_obras.csv'))},
           'ted': {}, 'prop': {}}
    for r in ler(os.path.join(saida, 'ted', 'ted_base_atualizada.csv')):
        for c in (r.get('Nº TED'), r.get('Plano de ação')):
            if c:
                reg['ted'][c] = r
    for p in (ler(os.path.join(saida, 'propostas.csv.gz')) or ler(os.path.join(saida, 'propostas.csv'))):
        if p.get('ano_proposta') == str(HOJE.year):
            reg['prop'][p.get('nr_proposta', '')] = p
    mud = []
    for grupo in ('parc', 'ted'):
        for a in J.get(grupo, []):
            k = a['menu'] + '|' + a['id']
            cur = atual.get(k, {'itens': {}})['itens']
            serie = [dias[d].get(k, 0) for d in datas8]
            if not ant:
                a['hist'] = {'serie': serie, 'datas': datas8, 'ref': None}
                continue
            antk = (ant.get(k) or {}).get('itens', {})
            novos = set(cur) - set(antk)
            for it in a['itens']:
                if chave_item(it) in novos:
                    it['novo'] = 1
            cont = {'resolvido': 0, 'mudou': 0, 'piorou': 0, 'conferir': 0}
            for num in set(antk) - set(cur):
                p = antk[num]
                destino = [e for e in ESCALA.get(a['id'], ()) if num in (atual.get(a['menu'] + '|' + e) or {}).get('itens', {})]
                if destino:
                    tipo, como = 'piorou', 'foi para: ' + atual[a['menu'] + '|' + destino[0]]['titulo'].lower()
                else:
                    tipo, como = como_saiu(a['menu'], a['id'], p, reg)
                cont[tipo] += 1
                mud.append({'menu': a['menu'], 'id': a['id'], 'titulo': a['titulo'], 'sev': a['sev'], 'num': num,
                            'nome': p.get('proponente') or p.get('unid') or p.get('nome') or '', 'uf': p.get('uf', ''), 'dep': p.get('dep', ''), 'ctrl': p.get('ctrl', ''),
                            'valor': p.get('vprior', 0), 'tipo': tipo, 'como': como})
            a['hist'] = {'serie': serie, 'datas': datas8, 'ref': ref.get('data'), 'novos': len(novos), 'saiu': len(set(antk) - set(cur)),
                         'resolvidos': cont['resolvido'], 'mudou': cont['mudou'], 'pioraram': cont['piorou'], 'conferir': cont['conferir']}
    ordem = {'resolvido': 0, 'mudou': 1, 'piorou': 2, 'conferir': 3}
    mud.sort(key=lambda x: (ordem[x['tipo']], -(x['valor'] or 0)))
    J['mud'] = {'ref': ref.get('data'), 'itens': mud}
    json.dump(J, open(caminho, 'w', encoding='utf-8'), ensure_ascii=False, separators=(',', ':'))
    H2 = {'dias': dias, 'foto': {'data': hoje, 'itens': atual}, 'foto_ant': ref if ref else (H.get('foto_ant') or {})}
    json.dump(H2, open(os.path.join(saida, 'alertas_hist.json'), 'w', encoding='utf-8'), ensure_ascii=False, separators=(',', ':'))
    from collections import Counter
    print('referência:', ref.get('data') or '(primeira foto)', '·', dict(Counter(m['tipo'] for m in mud)), '· novos:',
          sum(1 for g in ('parc', 'ted') for a in J.get(g, []) for it in a['itens'] if it.get('novo')), flush=True)


if __name__ == '__main__':
    main(sys.argv[1] if len(sys.argv) > 1 else 'saida')
