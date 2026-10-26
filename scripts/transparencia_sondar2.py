"""Sondagem 2 (só leitura): acesso direto ao servidor de arquivos do Portal (dadosabertos-download.cgu.gov.br).
Procura o primeiro ano das despesas (empenho/liquidação/pagamento) e testa nomes de arquivo das demais bases."""
import json, os, sys, time, urllib.request
SAIDA = sys.argv[1] if len(sys.argv) > 1 else 'saida'; os.makedirs(SAIDA, exist_ok=True)
CDN = 'https://dadosabertos-download.cgu.gov.br/PortalDaTransparencia/saida/'
UA = {'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/124 Safari/537.36', 'Range': 'bytes=0-1023'}
LOG = []
def log(m):
    m = time.strftime('%H:%M:%S') + '  ' + m; print(m, flush=True); LOG.append(m)
def tem(url):
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60) as r:
            d = r.read(4); return d[:2] == b'PK', r.status, r.headers.get('Content-Range') or r.headers.get('Content-Length')
    except Exception as e:
        return False, str(e)[:60], None
res = {'despesas': {}, 'outras': {}}
# 1) despesas: um dia útil de meados de janeiro de cada ano
for ano in range(2008, 2026):
    achou = None
    for dia in ('15', '16', '17', '14', '18', '20', '21'):
        ok, st, tam = tem(f'{CDN}despesas/{ano}01{dia}_Despesas.zip')
        if ok: achou = (f'{ano}01{dia}', tam); break
    res['despesas'][ano] = achou
    log(f'despesas {ano}: {achou}')
# 2) demais bases: nomes prováveis do arquivo
CAND = {
  'convenios': ['20250115_Convenios.zip', '20251020_Convenios.zip', '20251024_Convenios.zip'],
  'despesas-execucao': ['202501_Despesas.zip', '202501_ExecucaoDespesa.zip', '202501_DespesasExecucao.zip', '202501_Despesas_Execucao.zip'],
  'execucao-despesa': ['202501_Despesas.zip', '202501_ExecucaoDespesa.zip'],
  'orcamento-despesa': ['2025_OrcamentoDespesa.zip', '2025_Orcamento.zip', '2025_OrcamentoDespesa.zip'],
  'compras': ['202501_Compras.zip', '202501_Licitacoes.zip', '202501_Contratos.zip'],
  'licitacoes': ['202501_Licitacoes.zip'],
  'contratos': ['202501_Contratos.zip', '202501_Compras.zip'],
  'transferencias': ['202501_Transferencias.zip'],
  'despesas-favorecidos': ['202501_RecebimentosRecursosPorFavorecido.zip', '202501_DespesasFavorecidos.zip', '202501_Favorecidos.zip'],
}
for base, nomes in CAND.items():
    for n in nomes:
        ok, st, tam = tem(CDN + base + '/' + n)
        log(f'{base}/{n}: {"OK" if ok else "não"} {st} {tam}')
        res['outras'][base + '/' + n] = [ok, str(st), tam]
json.dump(res, open(os.path.join(SAIDA, 'transparencia_sondagem2.json'), 'w'), ensure_ascii=False, indent=1)
open(os.path.join(SAIDA, 'log2.txt'), 'w').write('\n'.join(LOG))
