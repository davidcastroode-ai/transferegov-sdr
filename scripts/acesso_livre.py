"""Lê no Acesso Livre do Transferegov as abas de alterações de cada instrumento (Ajustes do PT, Prorroga de Ofício, TAs com as
Solicitações de Alteração, Apostilamentos): a situação do momento, sem esperar a carga dos dados abertos (que pode atrasar dias).
Uso: python scripts/acesso_livre.py PAINEL_INSTRUMENTOS.csv PARC_LINKS.json.gz ANTERIOR.json SAIDA.json [nº,nº,...]
Sem lista: instrumentos da UG 420013 em execução ou aguardando prestação de contas."""
import csv, datetime, gzip, json, os, re, sys, time
from playwright.sync_api import sync_playwright

PAINEL, LINKS, ANT, SAIDA = sys.argv[1:5]
LISTA = [x.strip() for x in (sys.argv[5] if len(sys.argv) > 5 else '').split(',') if x.strip()]
UGS = {'420013'}
SITS = ('Em execução', 'Aguardando Prestação de Contas')
V = 'https://discricionarias.transferegov.sistema.gov.br/voluntarias'
ABAS = [('ajustes', '/ForwardAction.do?modulo=proposta&path=/SelecionarObjeto/SelecionarObjeto.do?destino=ListarAjustePlanoTrabalho'),
        ('prorrogas', '/ForwardAction.do?modulo=proposta&path=/SelecionarConvenio/SelecionarConvenio.do?destino=ListarProrrogas'),
        ('tas', '/ForwardAction.do?modulo=proposta&path=/SelecionarConvenio/SelecionarConvenio.do?destino=ListarTermosAditivos'),
        ('apostilamentos', '/ForwardAction.do?modulo=proposta&path=/SelecionarConvenio/SelecionarConvenio.do?destino=Apostilamento')]
# tabelas da página, cada uma com o título da seção que vem antes dela (ex.: "Termos Aditivos" e "Solicitações de Alteração")
JS = r"""() => {
  const marcas = [...document.querySelectorAll('h1,h2,h3,h4,legend,span,div,td,b,strong,p')].filter(e => e.children.length === 0 &&
    /^(Termos Aditivos|Solicitações de Alteração|Ajustes do Plano de Trabalho|Apostilamentos|Prorroga(s)? de Of[ií]cio)/i.test((e.textContent || '').trim()));
  return [...document.querySelectorAll('table')].map(t => {
    const ths = [...t.querySelectorAll('th')].map(x => x.innerText.trim().replace(/\s+/g, ' '));
    const rows = [...t.querySelectorAll('tr')].map(tr => [...tr.querySelectorAll('td')].map(td => td.innerText.trim().replace(/\s+/g, ' '))).filter(r => r.length >= 2 && r.some(c => c));
    let rot = ''; marcas.forEach(m => { if(m.compareDocumentPosition(t) & Node.DOCUMENT_POSITION_FOLLOWING) rot = m.textContent.trim(); });
    return {rot, ths, rows};
  }).filter(t => t.ths.length >= 2 && t.rows.length && t.ths.some(h => /N[uú]mero|Situa/i.test(h)));
}"""


def agora():
    return (datetime.datetime.utcnow() - datetime.timedelta(hours=3)).strftime('%d/%m/%Y %H:%M')


def main():
    ids = json.load(gzip.open(LINKS, 'rt', encoding='utf-8'))['prop']
    alvo = LISTA or [r['nr_instrumento'] for r in csv.DictReader(open(PAINEL, encoding='utf-8'))
                     if r.get('ug_emitente') in UGS and r.get('situacao') in SITS]
    try:
        res = json.load(open(ANT, encoding='utf-8'))
    except Exception:
        res = {}
    ok = falhas = 0
    t0 = time.time()
    with sync_playwright() as pw:
        b = pw.chromium.launch()
        ctx = b.new_context()
        p = ctx.new_page()
        p.set_default_timeout(60000)
        for n in alvo:
            idp = ids.get(n)
            if not idp:
                continue
            reg = {'lido': agora(), 'abas': {}}
            try:
                p.goto(f'{V}/ConsultarProposta/ResultadoDaConsultaDePropostaDetalharProposta.do?idProposta={idp}&Usr=guest&Pwd=guest')
                p.wait_for_load_state('networkidle')
                if f'Instrumento {n}' not in p.inner_text('body'):
                    raise RuntimeError('a página não abriu o instrumento')
                for aba, cam in ABAS:
                    p.goto(V + cam)
                    p.wait_for_load_state('networkidle')
                    corpo = p.inner_text('body')
                    if f'Instrumento {n}' not in corpo:
                        raise RuntimeError(f'aba {aba} abriu outro instrumento')
                    reg['abas'][aba] = p.evaluate(JS)
                res[n] = reg
                ok += 1
            except Exception as e:
                falhas += 1
                ant = res.get(n) or {}
                res[n] = {**ant, 'erro': str(e)[:200], 'tentativa': agora()}
                ctx.close(); ctx = b.new_context(); p = ctx.new_page(); p.set_default_timeout(60000)
            time.sleep(0.5)
        b.close()
    json.dump(res, open(SAIDA, 'w', encoding='utf-8'), ensure_ascii=False, separators=(',', ':'))
    print(f'Acesso Livre: {ok} instrumento(s) lidos · {falhas} falha(s) · {len(alvo)} na lista · {time.time() - t0:.0f}s', flush=True)


if __name__ == '__main__':
    main()
