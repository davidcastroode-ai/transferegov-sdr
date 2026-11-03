"""Proteção: se o download do Transferegov falhou (0 instrumentos), mantém os dados da rodada anterior.

Em 03/11/2026 o servidor de dados abertos respondeu HTTP 403 e o robô publicou as bases vazias:
Parcerias, Propostas, Contrato de Repasse, Indicadores e Relatório do instrumento ficaram sem dados.
Agora, quando isso acontece, os arquivos da rodada anterior (branch "dados") voltam para a pasta de saída
antes dos passos seguintes (páginas, alertas, relatório, indicadores), e a data de carga continua a antiga.
"""
import gzip, json, os, shutil, subprocess, sys

SAIDA = sys.argv[1] if len(sys.argv) > 1 else 'saida'
ANT = '/tmp/dados_anteriores'
# gerados por passos que rodam depois (são refeitos a partir dos dados restaurados) ou que têm proteção própria
FORA = ('ted/', 'contratos_api_', 'orcamento/', 'relatorio/', 'pagina_')
FORA_ARQ = {'alertas.json', 'indicadores.json', 'assistente_banco.json', 'emendas_siop.json', 'versao.txt', 'log_contratos.txt', 'atualizacao.json'}


def tam(p):
    return os.path.getsize(p) if os.path.exists(p) else 0


def main():
    try:
        at = json.load(open(os.path.join(SAIDA, 'atualizacao.json'), encoding='utf-8'))
    except Exception:
        at = {}
    n = (at.get('contagens') or {}).get('instrumentos', 0)
    if n:
        print(f'download ok · {n} instrumentos · nada a restaurar')
        return
    repo = os.environ.get('GITHUB_REPOSITORY', 'davidcastroode-ai/transferegov-sdr')
    print('::warning title=Transferegov sem dados::o download falhou (0 instrumentos) · mantendo os dados da rodada anterior')
    shutil.rmtree(ANT, ignore_errors=True)
    subprocess.run(['git', 'clone', '-q', '--depth', '1', '--single-branch', '-b', 'dados',
                    f'https://github.com/{repo}.git', ANT], check=True)
    restaurados = 0
    for raiz, _, arqs in os.walk(ANT):
        if '/.git' in raiz:
            continue
        for a in arqs:
            orig = os.path.join(raiz, a)
            rel = os.path.relpath(orig, ANT)
            if rel.startswith(FORA) or rel in FORA_ARQ:
                continue
            alvo_rel = rel[:-3] if rel.endswith('.gz') and rel[:-3].endswith('.csv') else rel   # os passos seguintes leem o .csv
            alvo = os.path.join(SAIDA, alvo_rel)
            atual = max(tam(alvo), tam(alvo + '.gz'))
            if atual * 20 >= tam(orig):   # a rodada de hoje produziu algo do mesmo porte: fica o de hoje
                continue
            os.makedirs(os.path.dirname(alvo) or SAIDA, exist_ok=True)
            for x in (alvo, alvo + '.gz'):
                if os.path.exists(x):
                    os.remove(x)
            if alvo_rel != rel:
                with gzip.open(orig, 'rb') as fi, open(alvo, 'wb') as fo:
                    shutil.copyfileobj(fi, fo)
            else:
                shutil.copy2(orig, alvo)
            restaurados += 1
    # data de carga: continua a da última leitura boa; registra a falha de hoje
    try:
        ant = json.load(open(os.path.join(ANT, 'atualizacao.json'), encoding='utf-8'))
        ant['falha_download'] = {'em': at.get('gerado_em'), 'log': (at.get('log') or [])[-6:]}
        json.dump(ant, open(os.path.join(SAIDA, 'atualizacao.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    except Exception as e:
        print('não foi possível manter o atualizacao.json anterior:', e)
    print(f'::notice title=Dados anteriores mantidos::{restaurados} arquivos restaurados da rodada anterior')


if __name__ == '__main__':
    main()
