# transferegov-sdr

Robô que atualiza, **todo dia às 6h**, os dados de propostas e instrumentos (convênios, contratos de repasse,
termos de fomento e de colaboração) da **Secretaria de Desenvolvimento Rural (SDR/MAPA)**, a partir dos
dados abertos do Transferegov (Discricionárias e Legais).

- Fonte: https://api-publica.transferegov.gestao.gov.br/downloads (arquivos `siconv_*.zip`, de 2008 até hoje)
- UGs da SDR: 130010, 130141, 135098, 420013, 130255
- Resultado: branch **`dados`** deste repositório, com os arquivos abaixo (CSV, UTF-8, separador vírgula, decimal com ponto)

| Arquivo | Uma linha por | Conteúdo |
|---|---|---|
| `painel_instrumentos.csv` | instrumento | versão leve de instrumentos.csv, usada pelo Painel SDR |
| `instrumentos.csv` | instrumento | situação, vigência, prestação de contas, valores, a desembolsar, último desembolso, dias sem desembolso, notas de empenho, aditivos, prorrogações + dados da proposta, programa e emenda |
| `propostas.csv` | proposta | propostas dos últimos anos (desde o ano atual − 3) dos programas da SDR, celebradas ou não, com proponente, objeto, valores, emenda e o instrumento gerado |
| `propostas_por_ano/propostas_AAAA.csv` | proposta | todas as propostas, um arquivo por ano (2008 em diante) |
| `empenhos.csv` | nota de empenho | notas de empenho dos instrumentos (nº da NE, tipo, UG, PI, PTRES, valor) |
| `desembolsos.csv` | desembolso | cada liberação de recurso |
| `aditivos.csv` | termo aditivo | aditivos dos instrumentos |
| `prorrogacoes.csv` | prorrogação de ofício | prorrogações |
| `obras.csv` | obra | dados do Obrasgov das obras dos instrumentos (situação da obra, execução física) |
| `emendas.csv` | emenda × proposta | parlamentar, nº da emenda, valores |
| `atualizacao.json` | — | data da carga do Transferegov, hora da geração, contagens e registro da execução |

Endereço para leitura direta (painel/planilha):
`https://raw.githubusercontent.com/davidcastroode-ai/transferegov-sdr/dados/<arquivo>`

Rodar na hora: aba **Actions › Atualizar dados Transferegov › Run workflow**.
