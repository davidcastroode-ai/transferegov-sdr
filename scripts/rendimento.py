"""Rendimento de aplicação financeira de cada convênio / termo (estimativa de uso).
Fonte: Transferegov (dados abertos) · instrumentos (rendimento, desembolsado, contrapartida, saldos devolvidos), pagamentos do convenente e termos aditivos.
Não existe, nos dados abertos, um campo de "rendimento utilizado". A estimativa é:
    usado (estimado) = pago aos fornecedores − (desembolsado pelo concedente + contrapartida depositada), limitado a 0 … rendimento gerado
    saldo de rendimento (estimado) = rendimento gerado − usado (estimado)
Conferência: entradas (desembolsado + contrapartida + rendimento) − saídas (pago + saldo em conta + devolvido) = dif_conta.
    Se a diferença passa de R$ 1.000 e de 1% das entradas, a estimativa é marcada como "conferir" (os dados abertos não fecham).
Também lista os termos aditivos cuja justificativa cita "rendimento" (indício de pedido / autorização de uso).
Saída (arquivo novo, não mexe nos demais): saida/painel_rendimento.csv
Uso: python scripts/rendimento.py saida
"""
import csv, gzip, os, re, sys
from collections import defaultdict

csv.field_size_limit(10 ** 9)


def ler(saida, nome):
    for c in (os.path.join(saida, nome), os.path.join(saida, nome + '.gz')):
        if os.path.exists(c):
            abre = gzip.open if c.endswith('.gz') else open
            with abre(c, 'rt', encoding='utf-8-sig', newline='') as fh:
                yield from csv.DictReader(fh)
            return


def num(v):
    s = str(v or '').strip()
    if not s:
        return 0.0
    if ',' in s:
        s = s.replace('.', '').replace(',', '.')
    try:
        return float(s)
    except ValueError:
        return 0.0


def main(saida):
    pago = defaultdict(float)
    for r in ler(saida, 'pagamentos.csv'):
        pago[r.get('NR_CONVENIO', '')] += num(r.get('VL_PAGO'))
    ta = defaultdict(list)
    for r in ler(saida, 'aditivos.csv'):
        if re.search(r'RENDIMENT', r.get('JUSTIFICATIVA_TA') or '', re.I):
            ta[r.get('NR_CONVENIO', '')].append(f"TA {r.get('NUMERO_TA') or '?'}" + (f" ({r['DT_ASSINATURA_TA'][:10]})" if r.get('DT_ASSINATURA_TA') else ''))
    out = []
    for r in ler(saida, 'instrumentos.csv'):
        n = (r.get('nr_instrumento') or '').strip()
        rend = num(r.get('rendimento_aplicacao'))
        if not n or (rend <= 0 and n not in ta):
            continue
        des, cp, pg = num(r.get('valor_desembolsado')), num(r.get('ingresso_contrapartida')), pago.get(n, 0.0)
        usado = min(max(pg - des - cp, 0.0), rend) if rend > 0 else 0.0
        dev = num(r.get('saldo_devolvido_tesouro'))
        ent, sai = des + cp + rend, pg + num(r.get('saldo_em_conta')) + dev
        dif = ent - sai
        out.append({'dif_conta': f'{dif:.2f}', 'confere': 'sim' if abs(dif) <= max(1000.0, 0.01 * ent) else 'não', 'nr_instrumento': n, 'rendimento': f'{rend:.2f}', 'desembolsado': f'{des:.2f}', 'contrapartida': f'{cp:.2f}', 'pago': f'{pg:.2f}',
                    'usado_est': f'{usado:.2f}', 'saldo_rend_est': f'{max(rend - usado, 0):.2f}', 'saldo_em_conta': f"{num(r.get('saldo_em_conta')):.2f}",
                    'devolvido_tesouro': f'{dev:.2f}', 'ta_rendimento': ' | '.join(ta.get(n, []))})
    campos = ['nr_instrumento', 'rendimento', 'desembolsado', 'contrapartida', 'pago', 'usado_est', 'saldo_rend_est', 'saldo_em_conta', 'devolvido_tesouro', 'dif_conta', 'confere', 'ta_rendimento']
    with open(os.path.join(saida, 'painel_rendimento.csv'), 'w', encoding='utf-8', newline='') as fh:
        w = csv.DictWriter(fh, fieldnames=campos)
        w.writeheader()
        w.writerows(out)
    print(f"painel_rendimento.csv: {len(out)} instrumentos · rendimento R$ {sum(num(x['rendimento']) for x in out):,.2f} · usado (est.) R$ {sum(num(x['usado_est']) for x in out):,.2f} · "
          f"{sum(1 for x in out if x['ta_rendimento'])} com aditivo citando rendimento · {sum(1 for x in out if x['confere'] == 'sim')} com as contas fechando", flush=True)


if __name__ == '__main__':
    main(sys.argv[1] if len(sys.argv) > 1 else 'saida')
