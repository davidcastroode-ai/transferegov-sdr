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
| `painel_obras.csv` | instrumento com obra | situação da obra calculada (não iniciada, em andamento, paralisada, inacabada, finalizada), % físico, medições, vigência e valores |
| `historico_obras.csv` | dia × obra | fotografia diária do % físico (até 400 dias), usada no critério de obra paralisada da Lei 14.719/2023 |
| `historico_situacao.csv` | mudança de situação | histórico de situações de cada instrumento (mostra quando ficou inadimplente, por exemplo) |
| `planilha_parcerias.csv` | instrumento assinado | mesmas colunas (A:AH) e mesma ordem da planilha Parcerias; é o que o Apps Script da planilha usa para atualizar e acrescentar instrumentos novos |
| `planilha_propostas.csv` | proposta | colunas A:Y da planilha BASE PROPOSTAS SDR (+ sugestão de acompanhamento), propostas de 3 anos atrás em diante |
| `painel_empenhos.csv` | nota de empenho | versão leve das notas (instrumento, NE, UG, data, tipo, valor) usada na ficha do painel |
| `pagina_*.html` (obras, prestacao, propostas, empenho, programas, movimentacao) | página | telas prontas (dados embutidos) que o Painel SDR abre nas abas Obras, Prestação de contas e Propostas da Parceria SDR |
| `propostas_pag/AAAA.json` | ano | propostas dos anos anteriores (formato compacto), carregadas pela página Propostas depois de abrir |
| `ted/ted_planilha.csv` | TED | um TED por linha (enviados e recebidos pelas UGs da SDR), nas colunas da aba TED da BASE TED; demais arquivos `ted/*.csv`: notas de crédito, eventos, programações financeiras, cronograma, pareceres, metas, programas |
| `pagamentos.csv` | pagamento | pagamentos dos convenentes a fornecedores (OBTV e outros) |
| `cronograma_desembolso.csv` | parcela | cronograma de desembolso previsto (concedente e convenente) |
| `instrumentos_outros_orgaos.csv` | instrumento | instrumentos com UG da SDR mas concedente de outro ministério (o script da planilha apaga essas linhas) |
| `resumo_fisico_financeiro.csv` | instrumento | resumo físico-financeiro das obras |
| `emendas.csv` | emenda × proposta | parlamentar, nº da emenda, valores |
| `atualizacao.json` | — | data da carga do Transferegov, hora da geração, contagens e registro da execução |

Endereço para leitura direta (painel/planilha):
`https://raw.githubusercontent.com/davidcastroode-ai/transferegov-sdr/dados/<arquivo>`

Rodar na hora: aba **Actions › Atualizar dados Transferegov › Run workflow**.
