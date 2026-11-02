"""LGPD (Lei 13.709/2018): mascara o CPF de pessoas físicas em todos os arquivos publicados pelo robô.

Padrão do Portal da Transparência: ***.452.881-** (só os 6 dígitos do meio ficam visíveis).
CNPJ (14 dígitos), números de processo, NE/NC e valores não são alterados.
Uso: python scripts/lgpd.py saida
"""
import csv, gzip, io, json, os, re, sys

CPF = re.compile(r'(?<![\d./-])(\d{3})\.?(\d{3})\.?(\d{3})-?(\d{2})(?!\d|[.,]\d)')
mascara = lambda s: CPF.sub(lambda m: f'***.{m.group(2)}.{m.group(3)}-**', s) if isinstance(s, str) and len(s) >= 11 else s


def anda(o):
    if isinstance(o, str):
        return mascara(o)
    if isinstance(o, list):
        return [anda(x) for x in o]
    if isinstance(o, dict):
        return {k: anda(v) for k, v in o.items()}
    return o


def texto_csv(t):
    out = io.StringIO()
    w = csv.writer(out, lineterminator='\n')
    for row in csv.reader(io.StringIO(t)):
        w.writerow([mascara(c) for c in row])
    return out.getvalue()


def tratar(caminho):
    gz = caminho.endswith('.gz')
    base = caminho[:-3] if gz else caminho
    if not base.endswith(('.csv', '.json')):
        return False
    bruto = gzip.open(caminho, 'rb').read() if gz else open(caminho, 'rb').read()
    try:
        t = bruto.decode('utf-8-sig')
    except UnicodeDecodeError:
        return False
    if not CPF.search(t):
        return False
    if base.endswith('.json'):
        try:
            novo = json.dumps(anda(json.loads(t)), ensure_ascii=False, separators=(',', ':') if gz else None, indent=None if gz else 1)
        except ValueError:
            return False
    else:
        novo = texto_csv(t)
    if novo == t:
        return False
    dado = novo.encode('utf-8')
    if gz:
        with gzip.open(caminho, 'wb') as fh:
            fh.write(dado)
    else:
        open(caminho, 'wb').write(dado)
    return True


def main(pasta):
    n = 0
    for raiz, _, arqs in os.walk(pasta):
        for a in arqs:
            try:
                n += tratar(os.path.join(raiz, a))
            except Exception as e:
                print(f'LGPD: não tratei {a}: {e}', flush=True)
    print(f'LGPD: CPF mascarado em {n} arquivo(s)', flush=True)


if __name__ == '__main__':
    main(sys.argv[1] if len(sys.argv) > 1 else 'saida')
