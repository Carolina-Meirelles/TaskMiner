# Publicar: GitHub + Render (Entrega 1 e Sprint 1)

Faça com as contas de vocês; nada aqui precisa de cartão nem de senha no repositório.

## 1. Repositório no GitHub (Entrega 1, até 10/11)

1. Um integrante cria o repositório `taskminer` no GitHub (público, ou privado com acesso ao professor).
2. Adiciona o outro integrante em **Settings → Collaborators**.
3. Na pasta do projeto, no terminal do VS Code:
   ```
   git init
   git add .
   git commit -m "Protótipo inicial e plano do projeto (Entrega 1)"
   git branch -M main
   git remote add origin https://github.com/USUARIO/taskminer.git
   git push -u origin main
   ```
4. Cada um trabalha em uma branch por história e abre pull request; o outro revisa (DoD). Assim o
   histórico mostra o trabalho de cada integrante ao longo das Sprints.

## 2. Board (Entrega 1)

**Projects → New project → Board**. Crie as colunas de `docs/04_kanban.md` e os campos de data
*Data de início* e *Data de conclusão*. Cadastre as histórias de `docs/02_product_backlog.md`.

## 3. Render (Sprint 1, história 3)

1. Em render.com, entre com a conta do GitHub (plano gratuito) e escolha **New → Blueprint**, apontando
   para o repositório: o `render.yaml` cria o serviço sozinho.
2. Em **Settings → Deploy Hook**, copie a URL.
3. No GitHub: **Settings → Secrets and variables → Actions → New secret**, nome `RENDER_DEPLOY_HOOK`,
   valor = a URL copiada.
4. A partir daí, cada push na `main` roda os testes e, se passarem, publica (Deploy Contínuo).

O plano gratuito do Render "dorme" sem uso: o primeiro acesso depois de um tempo leva cerca de 1 minuto.
Abram o link antes da apresentação.

## 4. Métricas no fim de cada Sprint

Exporte o board em CSV no formato de `ferramentas/board_modelo.csv` e rode:
```
python ferramentas/metricas.py board.csv --saida docs/metricas
```
O script gera `docs/metricas/metricas.md` e os gráficos de Burndown, Velocity e CFD para o Relatório.

## 5. Endereço gratuito e uso real

- O Render já dá um endereço gratuito: `https://taskminer.onrender.com` (ou `taskminer-xxxx.onrender.com`
  se o nome estiver ocupado). Não precisa comprar domínio.
- Para o executor funcionar, preencha `ANTHROPIC_API_KEY` em **Environment** no Render.
- **Atenção:** o disco do plano gratuito é apagado a cada deploy/reinício e o banco é SQLite em arquivo.
  Para guardar dados reais de colaboradores é preciso trocar por um banco externo (ex.: PostgreSQL
  gratuito do Neon ou Supabase). Para demonstração, `DEMO=1` recria os dados sozinho.
