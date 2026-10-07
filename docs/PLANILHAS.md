# Planilhas de entrada (uma por tela)

Cada obra é uma pasta em `backend/data/projects/<id>/` com planilhas pequenas, uma por tela de entrada.
Só `orcamento.xlsx` é obrigatório. O cabeçalho fica **na linha 1**, a ordem das colunas é livre e acentos e maiúsculas
não importam.

Modelos vazios com exemplo: `backend/data/templates/modelo_separado/` (download: `GET /api/projects/template-split`).
Envio: `POST /api/projects/upload-split` (campos `project_name`, `orcamento`, `cronograma`, `distribuicao`, `medicao`).
Leitor: `backend/app/services/split_io.py`. Ele devolve o mesmo dicionário que `parse_excel_project()`.

Percentuais podem vir como fração (0,85) ou como número (85). Valores acima de 1 são divididos por 100.

## 1. `orcamento.xlsx`: tela Orçamento / EAP
Aba única.

| Coluna | Obrigatória | Conteúdo |
|---|---|---|
| Nível | sim | 1 a 5. O nível 1 é a obra: dá o nome e o orçamento total. |
| Código | sim | Código EAP (ex.: `01.02.01.01.001`). É a chave usada nas outras planilhas. |
| Código Pai | não | Se vazio, é deduzido pela linha de nível imediatamente acima. |
| Descrição | sim | |
| Unidade, Quantidade, Preço Unitário | não | Só nível 5. |
| Preço Total | sim | R$ |
| Medição Acumulada (%) | não | Acumulado até a data de corte. É ignorado quando `medicao.xlsx` tem a aba Acumulado. |

## 2. `cronograma.xlsx`: tela Cronograma / Gantt
Aba 1 **Cronograma**:

| Coluna | Conteúdo |
|---|---|
| ID | Único. Usado pelas predecessoras e pela aba Diario. |
| Nome da Atividade | Precisa ser idêntico ao usado em `distribuicao.xlsx`. |
| Duração (dias) | Dias úteis. |
| Data Início / Data Término | Data ou `AAAA-MM-DD`. Sem nenhuma das duas (e sem Diario), a atividade fica fora da distribuição. |
| Predecessoras | `4FS`, `4FS+2d`, `2SS+3d`, `5FF`, várias separadas por `;` |
| Lote Mãe / Lote / Pavimento | Opcionais. Se vazios, são deduzidos do nome (`X - T1 - Fachada A`). |

Aba 2 **Diario** (opcional): `ID`, `Nome da Atividade`, `Data`, `Valor`.
Serve quando a distribuição não é uniforme em dias úteis, como nas planilhas legadas. Sem ela, cada dia útil entre início
e término vale 1.

## 3. `distribuicao.xlsx`: tela Distribuição (vínculos nível 5 ↔ atividades)
Aba única, uma linha por vínculo (substitui as antigas linhas "nível 6").

| Coluna | Conteúdo |
|---|---|
| Código Item (Nível 5) | Código do orçamento. |
| Nome da Atividade | Nome exato no cronograma. |
| Duração Manual (dias) | Opcional. Se vazio, usa a duração do cronograma. |
| Valor Alocado (R$) | Opcional. Se vazio, o valor é rateado pela duração. |

## 4. `medicao.xlsx`: tela Medição
| Aba | Colunas | Conteúdo |
|---|---|---|
| Corte | Medição de Corte (Nº), Data de Corte | Uma linha: medição atual. |
| Historico | Nº Medição, Data, Realizado Obra (%) | Realizado mensal da obra inteira (curva S). Só entram medições até o corte. |
| Itens | Código Item, Nº Medição, Previsto (%), Realizado (%) | Percentual **do mês** (não acumulado) de cada item. |
| Acumulado | Código Item, Acumulado (%) | Acumulado de cada item na data de corte. |

## Nova Obra: uma planilha só
`GET /api/projects/template` baixa `Modelo_Obra_Completa.xlsx`. Ele traz as abas Orçamento, Cronograma,
(Cronograma Diario), Distribuição, Medição Corte, Medição Historico, Medição Itens e Medição Acumulado, com as mesmas
colunas acima. No upload, o sistema divide a planilha nos 4 arquivos. Planilhas antigas (modelo padrão antigo ou
Físico-Financeiro legado) também são aceitas: são extraídas uma vez e o original fica em `<obra>/_original/`.

## Versões por tela
Orçamento, Distribuição e Medição funcionam como o Cronograma: têm versão ativa, botão **Importar** (planilha do
modelo daquela tela, `GET /api/projects/template-split/<tela>`) e botão **Modelo**.
- Os dados ficam em `backend/data/versions/<obra>/index.json`, e as planilhas importadas em `<tela>_<versão>.xlsx`.
- As edições feitas na tela (medições mensais, vínculos, ajustes do Gantt) são salvas automaticamente **na versão
  ativa**. **Restaurar** descarta as edições e volta ao que veio na importação.
- "Revisão Atual (Arquivo)" é a planilha da própria obra (`backend/data/projects/<obra>/`).
- As versões do cronograma continuam em `schedule_versions.pkl`, porque aceitam MPP/XML.
- API: `GET /api/versions/<obra>`; `POST /api/versions/<obra>/<tela>/import|activate`; `PUT|DELETE /api/versions/<obra>/<tela>/edits`.

## Telas calculadas (não têm planilha direta de entrada)
Físico-Financeiro, FF Replanejado, Replanejado pelo Saldo, Curva de Competência, Curva Financeira,
Curva S e Resumo são geradas automaticamente pelo motor de cálculo (`replan_engine.py` e `competence_finance_engine.py`).
- **Curva de Competência (Contábil / Emissão de NF)**: Mão de obra no mês da medição (ciclo 21 a 20) e Material com faturamento na entrega em obra (dias de antecedência ou parcelado em lotes).
- **Curva Financeira (Desembolso / Fluxo de Caixa)**: Mão de obra no dia 05 do mês subsequente (+1 ciclo) e Material deslocado pelas condições de pagamento (padrão 28 dias ou parcelado em até 6x).
- **Parametrização por Etapa**: configurável via modal na tela ou via planilha Excel (`GET /api/replan/<obra>/curvas-config/template` e `POST /api/replan/<obra>/curvas-config/upload`), persistida no arquivo `curvas_config.json` da obra.


## Migrar uma planilha gigante (fazer uma única vez)
```
python backend/tools/extrair_planilha.py "C:\...\Planilha FF.xlsx" "Nome da Obra"
```
Depois da extração, a obra passa a ser lida só das planilhas pequenas. O scanner não volta para o arquivo do OneDrive.
