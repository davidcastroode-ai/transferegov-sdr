"""Sonda as abas de alterações do instrumento no Acesso Livre do Transferegov (Ajustes do PT, Prorroga de Ofício, TAs, Apostilamentos).
Uso: python scripts/sondar_abas.py ID_PROPOSTA PASTA"""
import http.cookiejar, os, re, sys, urllib.request, urllib.parse, html

B = 'https://discricionarias.transferegov.sistema.gov.br'
idp, out = sys.argv[1], sys.argv[2]
os.makedirs(out, exist_ok=True)
cj = http.cookiejar.CookieJar()
op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
op.addheaders = [('User-Agent', 'Mozilla/5.0 (X11; Linux x86_64) Chrome/124 Safari/537.36')]


def get(url, nome):
    try:
        with op.open(url, timeout=60) as r:
            t = r.read().decode('iso-8859-1', 'replace')
        open(os.path.join(out, nome), 'w', encoding='utf-8').write(t)
        print(nome, len(t), r.geturl()[:150], flush=True)
        return t
    except Exception as e:
        print(nome, 'ERRO', e, flush=True)
        return ''


t = get(f'{B}/voluntarias/ConsultarProposta/ResultadoDaConsultaDePropostaDetalharProposta.do?idProposta={idp}&Usr=guest&Pwd=guest', '0_proposta.html')
links = sorted(set(html.unescape(x) for x in re.findall(r'(?:href|action)="([^"]+)"', t)))
open(os.path.join(out, 'links.txt'), 'w').write('\n'.join(links))
alvo = [l for l in links if re.search(r'Aditiv|Apostil|Prorrog|Ajuste|TermoAditivo|Execucao|Convenente', l, re.I)]
print('links de interesse:', len(alvo))
for i, l in enumerate(alvo[:30]):
    u = urllib.parse.urljoin(B + '/voluntarias/', l)
    get(u, f'{i+1:02d}_' + re.sub(r'[^\w]+', '_', l.split('?')[0])[-60:] + '.html')
