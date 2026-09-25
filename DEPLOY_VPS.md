# Guia de Deploy no Docker - VPS (Projeto Replanejamentos)

Este guia orienta a implantação completa do sistema **Replanejamento Físico-Financeiro** via **Docker / Docker Compose** na sua VPS, dentro da pasta criada: `Replanejamentos`.

---

## 1. Estrutura de Arquivos Necessária na VPS

Na sua VPS, dentro de `~/Replanejamentos` (ou `/var/www/Replanejamentos`), você precisará dos seguintes arquivos do repositório:

```text
Replanejamentos/
├── Dockerfile
├── docker-compose.yml
├── .dockerignore
├── requirements.txt
├── backend/
│   ├── app/
│   │   ├── main.py
│   │   ├── config.py
│   │   ├── database.py
│   │   ├── routers/
│   │   └── services/
│   ├── static/
│   │   └── index.html      # Frontend compilado pronto
│   └── data/               # Mapeado no volume persistente
│       ├── templates/      # Modelo padrão .xlsx
│       └── projects/       # Obras e planilhas importadas
```

---

## 2. Como Subir os Arquivos para a VPS

### Opção A: Via Git (Recomendado)
Se o projeto estiver num repositório Git (GitHub/GitLab):
```bash
# Acesse sua VPS via SSH
ssh usuario@ip_da_sua_vps

# Entre no diretório do projeto
cd ~/Replanejamentos

# Clone ou puxe as atualizações
git pull origin main
```

### Opção B: Via SCP / Rsync do seu PC
No terminal do seu computador:
```bash
# Exemplo usando rsync:
rsync -avz --exclude='.git' --exclude='.venv' --exclude='__pycache__' ./ usuario@ip_da_sua_vps:~/Replanejamentos/
```

---

## 3. Subindo o Container com Docker Compose

Dentro da pasta `Replanejamentos` na VPS:

```bash
cd ~/Replanejamentos

# 1. Construir a imagem e iniciar em segundo plano (daemon)
docker compose up -d --build

# 2. Verificar se o container está rodando com status saudável (healthy)
docker compose ps

# 3. Ver logs em tempo real
docker compose logs -f
```

O sistema estará disponível imediatamente em:
```text
http://IP_DA_SUA_VPS:8000
```

---

## 4. Persistência de Dados e Backups

Todos os arquivos enviados pelo usuário (novas obras, planilhas orçamentárias, cronogramas XML/MPP, vínculos de Nível 6 e versões) são gravados automaticamente na pasta local `./data` da VPS através do volume montado:

```yaml
volumes:
  - ./data:/app/backend/data
```

Isso garante que:
- Você pode atualizar o container (`docker compose down && docker compose up -d --build`) a qualquer momento sem perder nenhuma obra cadastrada.
- Para fazer backup de todas as obras, basta compactar a pasta `data`:
  ```bash
  tar -czvf backup_replanejamentos_$(date +%Y%m%d).tar.gz data/
  ```

---

## 5. Configuração com Domínio Próprio e SSL (Nginx + Let's Encrypt - Opcional)

Se desejar acessar por um domínio (ex: `replanejamento.seudominio.com.br`) com certificado HTTPS gratuito:

### 1. Instalar Nginx e Certbot na VPS
```bash
sudo apt update
sudo apt install -y nginx certbot python3-certbot-nginx
```

### 2. Configurar o bloco Nginx
Crie `/etc/nginx/sites-available/replanejamentos`:
```nginx
server {
    server_name replanejamento.seudominio.com.br;

    client_max_body_size 100M; # Permite upload de planilhas e cronogramas grandes

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

### 3. Ativar e Gerar Certificado SSL
```bash
sudo ln -s /etc/nginx/sites-available/replanejamentos /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx

# Gerar certificado SSL automático
sudo certbot --nginx -d replanejamento.seudominio.com.br
```

---

## 6. Padrão de Planilha para Importação na Web

No próprio painel do sistema (botão **"Nova Obra"** ou **"Obras"**):
1. Clique em **"Baixar Modelo Padrão (.xlsx)"**.
2. Preencha ou cole os dados do seu empreendimento:
   - **Níveis 1 a 5**: EAP do Orçamento (`Nível`, `Código`, `Descrição`, `Unidade`, `Quantidade`, `Preço Unitário`, `Preço Total`, `Medição Acumulada %`).
   - **Nível 6**: Inserido diretamente abaixo do item de Nível 5 pai, com a coluna `Descrição` preenchida com o nome exato da atividade do cronograma a que se vincula.
   - **Cronograma**: Tarefas com `ID`, `Nome da Atividade`, `Duração`, `Início`, `Término`, `Predecessoras`.
3. Clique em **"Importar & Abrir Obra"** e selecione a planilha salva.
4. O motor calculará todo o replanejamento físico-financeiro instantaneamente.
