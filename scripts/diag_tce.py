"""Diagnóstico: onde aparece TCE nos dados abertos do Transferegov."""
import csv, io, re, urllib.request, zipfile, collections
csv.field_size_limit(10**9)
B = 'https://api-publica.transferegov.gestao.gov.br/downloads/'
UGS = {'130010','130141','135098','420013','130255'}
def nota(t):
    for i in range(0, len(t), 3500): print('::notice::' + t[i:i+3500].replace('\n', ' ‖ '), flush=True)
def get(u):
    r = urllib.request.urlopen(urllib.request.Request(u, headers={'User-Agent':'robo-sdr-mapa'}), timeout=600); return r.read()
for u in [B, B+'dadosgov/', 'https://repositorio.dados.gov.br/seges/detru/']:
    try:
        h = get(u).decode('utf-8','ignore'); z = sorted(set(re.findall(r'[\w\-]+\.(?:zip|csv)', h)))
        nota(f'INDICE {u}: {len(h)} bytes, {len(z)} arquivos: ' + ', '.join(z))
        if not z: nota('INDICE trecho: ' + re.sub(r'\s+',' ',h)[:1500])
    except Exception as e: nota(f'INDICE {u}: erro {e}')
def abrir(nome):
    d = get(B+'dadosgov/'+nome+'.zip'); zf = zipfile.ZipFile(io.BytesIO(d)); n = zf.namelist()[0]
    t = zf.read(n).decode('utf-8-sig', 'ignore'); return list(csv.reader(io.StringIO(t), delimiter=';'))
conv = abrir('siconv_convenio'); cab = conv[0]; nota('CONVENIO colunas: ' + ' | '.join(cab))
iS, iSub, iUG, iN = cab.index('SIT_CONVENIO'), cab.index('SUBSITUACAO_CONV'), cab.index('UG_EMITENTE'), cab.index('NR_CONVENIO')
tod = collections.Counter((l[iS], l[iSub]) for l in conv[1:] if len(l) > iSub)
nota('CONVENIO situações (todos os órgãos): ' + ' ; '.join(f'{a} / {b}: {v}' for (a,b),v in tod.most_common()))
sdr = {l[iN] for l in conv[1:] if len(l) > iUG and l[iUG] in UGS}
tcecols = [c for c in cab if re.search('TCE|TOMADA|INADIMP|REMAN|DEVOL', c)]
nota('CONVENIO colunas TCE/inadimp/devolução: ' + ', '.join(tcecols))
for nome in ['siconv_historico_situacao','siconv_hist_situacao','siconv_tce','siconv_convenio_tce','siconv_tomada_contas_especial','siconv_prestacao_contas','siconv_obtv_convenente','siconv_pagamento','siconv_devolucao','siconv_inadimplencia']:
    try:
        L = abrir(nome); c = L[0]
        nota(f'ARQ {nome}: {len(L)-1} linhas · colunas: ' + ' | '.join(c))
        ic = next((i for i,h in enumerate(c) if h in ('NR_CONVENIO','ID_CONVENIO')), None)
        txt = [i for i,h in enumerate(c) if re.search('SITUACAO|SIT_|HIST|STATUS|TCE', h)]
        cnt = collections.Counter(); amostra = []
        for l in L[1:]:
            for i in txt:
                if i < len(l) and re.search('TCE|TOMADA|INADIMPL', l[i], re.I):
                    cnt[l[i]] += 1
                    if ic is not None and ic < len(l) and l[ic] in sdr and len(amostra) < 15: amostra.append(l[ic] + ':' + l[i])
        nota(f'ARQ {nome}: valores com TCE/inadimplência: ' + ' ; '.join(f'{k}: {v}' for k,v in cnt.most_common(30)) + ' || SDR: ' + ', '.join(amostra))
    except Exception as e: nota(f'ARQ {nome}: {e}')
