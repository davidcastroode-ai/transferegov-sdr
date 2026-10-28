"""Sonda as abas de alterações do instrumento no Acesso Livre do Transferegov (Ajustes do PT, Prorroga de Ofício, TAs, Apostilamentos),
com navegador (o Acesso Livre passa por login SAML automático e páginas com JavaScript).
Uso: python scripts/sondar_abas.py ID_PROPOSTA PASTA"""
import os, sys, re
from playwright.sync_api import sync_playwright

idp, out = sys.argv[1], sys.argv[2]
os.makedirs(out, exist_ok=True)
URL = f'https://discricionarias.transferegov.sistema.gov.br/voluntarias/ConsultarProposta/ResultadoDaConsultaDePropostaDetalharProposta.do?idProposta={idp}&Usr=guest&Pwd=guest'


def salvar(p, nome):
    open(os.path.join(out, nome + '.html'), 'w', encoding='utf-8').write(p.content())
    t = p.inner_text('body')
    open(os.path.join(out, nome + '.txt'), 'w', encoding='utf-8').write(t)
    print('==', nome, p.url[:160], len(t), flush=True)


with sync_playwright() as pw:
    b = pw.chromium.launch()
    p = b.new_page()
    p.goto(URL, timeout=90000)
    p.wait_for_load_state('networkidle', timeout=90000)
    salvar(p, '0_proposta')
    for aba in ['Execução Convenente', 'Execução Concedente']:
        try:
            p.get_by_text(aba, exact=True).first.click(timeout=15000)
            p.wait_for_load_state('networkidle', timeout=60000)
            salvar(p, '1_' + re.sub(r'\W+', '_', aba))
            break
        except Exception as e:
            print('aba', aba, 'erro', e, flush=True)
    BASEV = 'https://discricionarias.transferegov.sistema.gov.br/voluntarias'
    DEST = [('Ajustes_do_PT', '/ForwardAction.do?modulo=proposta&path=/SelecionarObjeto/SelecionarObjeto.do?destino=ListarAjustePlanoTrabalho'),
            ('Prorroga_de_Oficio', '/ForwardAction.do?modulo=proposta&path=/SelecionarConvenio/SelecionarConvenio.do?destino=ListarProrrogas'),
            ('TAs', '/ForwardAction.do?modulo=proposta&path=/SelecionarConvenio/SelecionarConvenio.do?destino=ListarTermosAditivos'),
            ('Apostilamentos', '/ForwardAction.do?modulo=proposta&path=/SelecionarConvenio/SelecionarConvenio.do?destino=Apostilamento')]
    for i, (nome, cam) in enumerate(DEST):
        try:
            p.goto(BASEV + cam, timeout=90000)
            p.wait_for_load_state('networkidle', timeout=60000)
            salvar(p, f'{i+2}_{nome}')
            for bt in p.locator('input[type=button]:visible, input[type=submit]:visible').all():
                print('   botão:', bt.get_attribute('value'), flush=True)
            loc = p.locator('input[value*="Solicita"]:visible, input[value^="Listar"]:visible')
            if loc.count():
                loc.first.click(timeout=15000)
                p.wait_for_load_state('networkidle', timeout=60000)
                salvar(p, f'{i+2}b_{nome}')
        except Exception as e:
            print(nome, 'erro', str(e)[:200], flush=True)
    b.close()
