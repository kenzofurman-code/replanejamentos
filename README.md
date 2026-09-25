# Sistema Web de Replanejamento Físico-Financeiro de Obras
### Piemonte Engenharia & Construtora

Aplicação de alta performance para **replanejamento de obras pelo saldo remanescente**, substituindo planilhas pesadas de 40–60 MB por cálculos instantâneos (< 100 ms) integrados a banco de dados PostgreSQL.

---

## Principais Funcionalidades

1. **Replanejamento Real pelo Saldo**:
   - $\text{Saldo a Medir} = \text{Orçado Total} - \text{Realizado Acumulado}$.
   - O saldo de cada item de serviço (Nível 5) é distribuído estritamente sobre as **tarefas futuras/não finalizadas** do cronograma atualizado.
   - O histórico de medições anteriores à data de corte fica 100% blindado com os valores medidos reais.
2. **Ciclos de Medição Flexíveis e Configuráveis**:
   - Defina qualquer janela de medição: **Dia 21 ao 20** (padrão Platea), **Dia 26 ao 25**, **Dia 1 ao 30**, ou intervalos personalizados.
   - O fatiamento soma os percentuais diários das colunas do cronograma que caem dentro de cada intervalo.
3. **Catálogo Integrado de Obras Piemonte**:
   - Varredura e carregamento direto das pastas das obras (`PLATEA`, `POTY`, `ALBERI`, `AMIZ`, `GLB`, `LIOR`, `NIZZA`, `PACE`, `QOYA RESIDENCE`, etc.).
4. **Visualização Executiva e Operacional**:
   - **Curva S Dinâmica**: Previsto Inicial vs Realizado Medido vs Replanejado Futuro.
   - **Tabela EAP com Drill-Down**: Navegação em cascata pelos Níveis 1 a 5 com filtros por código ou descrição.
5. **Exportação Formatada para Excel**:
   - Gera arquivo `.xlsx` limpo com tabela resumo da Curva S e a EAP completa com todas as colunas de ciclos.

---

## Como Executar Localmente

### Pré-requisitos
- Python 3.10+ instalado.

### Passo a Passo
1. No diretório do projeto:
```bash
cd "c:\Users\HomePC\Documents\GITHUBS\REPLANEJAMENTO DE OBRA"
```

2. Instale as dependências:
```bash
pip install -r backend/requirements.txt
```

3. Inicie o servidor FastAPI:
```bash
python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000 --reload
```

4. Abra no navegador:
```
http://localhost:8000
```

---

## Como Fazer Deploy na VPS (com PostgreSQL e Docker)

1. Clone o repositório na sua VPS:
```bash
git clone <URL_DO_REPOSITORIO> replanejamento-obra
cd replanejamento-obra
```

2. Configure o arquivo `.env`:
```bash
cp .env.example .env
nano .env
```

3. Suba o banco PostgreSQL e a aplicação com um único comando:
```bash
docker compose up -d --build
```

4. A aplicação estará ativa em:
```
http://<IP_DA_SUA_VPS>:8000
```
Com banco de dados PostgreSQL 16 persistente no volume `pgdata`.
