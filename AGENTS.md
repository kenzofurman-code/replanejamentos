# AGENTS.md: Replanejamento Físico-Financeiro (Piemonte)

Instruções para qualquer agente de IA (Claude Code, Codex, Cursor, Gemini, etc.) que trabalhe neste repositório.

## Regra nº 1: nunca abrir a planilha gigante
- **Não** leia, abra nem inspecione com Python as planilhas Físico-Financeiras originais (~60 MB) do OneDrive
  (`C:\Users\HomePC\OneDrive - Piemonte Construtora\...`, `C:\Users\HomePC\Piemonte Construtora\...`).
- A estrutura de dados está documentada em **`docs/PLANILHAS.md`**. Consulte esse documento, não a planilha.
- Para testar ou depurar, use as planilhas pequenas:
  - modelo com exemplo: `backend/data/templates/modelo_separado/` (4 arquivos, poucos KB);
  - obra real já extraída: `backend/data/projects/platea/` (≈350 KB no total);
  - o dicionário já processado pode ser carregado com `parse_excel_project("<pasta da obra>")`.
- Se for realmente necessário migrar uma planilha nova, rode **uma única vez**
  `python backend/tools/extrair_planilha.py "<arquivo>" "<Nome da Obra>"` e peça autorização ao usuário antes.
- Não imprima dicionários ou tabelas inteiras no terminal. Mostre só contagens, chaves ou poucas linhas.

## Arquitetura (FastAPI + Alpine.js, sem build)
```
backend/app/main.py                 app, rota "/" monta index.html + partials
backend/app/routers/projects.py     listar/carregar/enviar obras (PROJECT_CACHE em memória)
backend/app/routers/replan.py       simulate / export / import-schedule / links
backend/app/routers/versions.py     /api/versions: importar, ativar, salvar e restaurar edições por tela
backend/app/services/
  split_io.py          leitura e escrita das planilhas separadas (formato atual) e da planilha única da Nova Obra
  versions.py          versões por tela + edições salvas na versão ativa (data/versions/<obra>/index.json)
  excel_reader.py      parse_excel_project(): pasta → split_io; .xlsx → leitor legado + cache em data/cache
  replan_engine.py     run_replan_calculation(): todos os cálculos das telas (arquivo grande, leia por trechos)
  exporter.py          geração dos .xlsx de exportação
  schedule_importer.py importação MPP/XML/XLSX de cronograma
  piemonte_scanner.py  descobre obras em data/projects e nas pastas do OneDrive
backend/static/
  index.html           só o esqueleto (cabeçalho, barra de abas)
  partials/tabN_*.html uma aba por arquivo; drawer_*/modal_* para painéis
  js/app.js            componente Alpine replanApp() (estado e métodos)
  css/app.css
docs/PLANILHAS.md      contrato das planilhas de entrada
tests/                 pytest
```
Contrato central: `parse_excel_project()` e `parse_split_project()` devolvem o **mesmo dicionário**
(`budget_items`, `tasks`, `links_by_l5`, `all_links`, `item_measurements`, `item_monthly_measurements`,
`history_monthly`, `cutoff_med_num`, `cutoff_date`, `start_date`, `end_date`, `project_name`, `total_budget`).
Se mudar esse formato, incremente `PARSER_VERSION` em `excel_reader.py`, atualize `docs/PLANILHAS.md` e rode os testes.

## Como economizar contexto
- Para mexer em uma tela, abra só `backend/static/partials/<aba>.html` e busque (grep) em `js/app.js` o método
  correspondente. Não leia `app.js` nem `replan_engine.py` inteiros; use busca e leitura por intervalo de linhas.
- `scratch/` é lixo local (ignorado pelo git): não leia nem use como referência. Os scripts `scratch/gen_*.py`
  geravam o antigo `index.html` monolítico e estão **obsoletos**. Rodá-los sobrescreveria o front atual.
- Ignore `backend/data/cache/`, `*.pkl`, `*.bak`, `backend/tools/jre17/` e `backend/tools/mpxj/`.

## Rodar e testar
```
python -m uvicorn backend.app.main:app --reload --port 8000     # na raiz do repositório
python -m pytest tests -q
```
`tests/test_split_roundtrip.py` garante que as planilhas separadas geram o mesmo resultado do motor que a
planilha original (usa o cache já extraído, sem abrir o arquivo de 60 MB).

## Convenções
- Textos de interface e documentação em português; código e identificadores seguem o estilo existente (inglês).
- Mudanças cirúrgicas: não reformatar nem refatorar código que não faz parte da tarefa.
- Regras de negócio (ciclo de medição 21→20, níveis 1–6 da EAP, rateio por duração) ficam no `replan_engine.py`.
  Não invente regras novas sem confirmar com o usuário.
