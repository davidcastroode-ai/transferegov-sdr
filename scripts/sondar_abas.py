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
    for i, sub in enumerate(['Ajustes do PT', 'Prorroga de Ofício', 'TAs', 'Apostilamentos']):
        try:
            p.get_by_text(sub, exact=True).first.click(timeout=15000)
            p.wait_for_load_state('networkidle', timeout=60000)
            salvar(p, f'{i+2}_' + re.sub(r'\W+', '_', sub))
            # "Listar Termos Aditivos e Solicitações" e afins
            for bt in p.locator('input[type=button], input[type=submit], a').all():
                try:
                    v = (bt.get_attribute('value') or bt.inner_text() or '').strip()
                except Exception:
                    continue
                if re.search(r'^Listar|Solicita', v):
                    print('   botão:', v, flush=True)
            for alvo in ['Listar Termos Aditivos e Solicitações', 'Listar Apostilamentos e Solicitações', 'Listar']:
                loc = p.locator(f'input[value="{alvo}"]')
                if loc.count():
                    loc.first.click(timeout=15000)
                    p.wait_for_load_state('networkidle', timeout=60000)
                    salvar(p, f'{i+2}b_' + re.sub(r'\W+', '_', sub))
                    p.go_back()
                    p.wait_for_load_state('networkidle', timeout=60000)
                    break
        except Exception as e:
            print('sub', sub, 'erro', str(e)[:200], flush=True)
    b.close()
