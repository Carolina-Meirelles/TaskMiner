# TaskMiner — IA que documenta os processos de cada função

O TaskMiner observa, por duas semanas, o que cada colaborador faz no computador, descobre sozinho
quais tarefas ele repete e gera um **manual de processos** com o passo a passo de cada uma,
a rotina diária e uma descrição da função, escritos pela IA (Claude). A empresa cadastra a equipe
por área, e o administrador acessa a documentação de todos.

Na literatura e no mercado, essa técnica se chama **task mining** (mineração de tarefas).

```
 PC de cada colaborador (Windows)                 Servidor da empresa (qualquer PC)
 ┌──────────────────────────┐   envia eventos   ┌────────────────────────────────────────┐
 │ agente.py  (14 dias)     │ ────────────────▶ │ painel.py  (login, empresa, equipes)   │
 │ janelas, cliques,        │  com o código     │ analise.py  → acha tarefas repetidas   │
 │ atalhos, ociosidade      │  pessoal (token)  │ documentador.py → Claude escreve POPs  │
 └──────────────────────────┘                   └────────────────────────────────────────┘
```

## Contas e acessos

| Quem | O que faz |
|---|---|
| **Administrador(a)** | Cadastra a empresa, os colaboradores (com **função** e **área**) e outros administradores. Vê a documentação e os processos de **todos**, filtra por área, roda as análises e exporta o manual da empresa inteira. |
| **Colaborador(a)** | Entra com o próprio e-mail e senha. Vê **só os próprios** processos, a página "Minha coleta" (como instalar o agente, com o código pessoal) e troca a própria senha. |

Senhas são guardadas com hash, os formulários têm proteção contra CSRF e cada empresa só enxerga a
própria equipe. Desativar um colaborador bloqueia o login e o envio de dados pelo agente.

---

## Projeto M2 — Métodos Ágeis

| O que | Onde |
|---|---|
| Visão do produto e ligação com times ágeis | `docs/00_visao_do_produto.md` |
| Papéis, cerimônias e datas das Sprints | `docs/01_papeis_e_cerimonias.md` |
| Product Backlog com critérios de aceite e INVEST | `docs/02_product_backlog.md` |
| DoR e DoD | `docs/03_dor_dod.md` |
| Board Kanban (colunas, WIP, políticas) | `docs/04_kanban.md` |
| XP e DevOps (Deploy Contínuo) | `docs/05_xp_devops.md`, `.github/workflows/ci.yml`, `render.yaml` |
| Cascata × Ágil | `docs/06_cascata_vs_agil.md` |
| BPMN da função principal | `docs/bpmn/` (`.bpmn` abre no bpmn.io) |
| Calculadora de métricas do board | `ferramentas/metricas.py` |
| Testes automatizados | `tests/` — rodar com `pytest` |
| Como publicar | `docs/07_publicar_no_github_e_render.md` |

---

## Executor (o Claude opera o computador)

Além de observar, o TaskMiner pode **executar** tarefas: o gestor ou o colaborador escreve um comando na
aba **Executor** e o Claude opera o computador (clica, digita, copia entre sistemas) por meio de um
agente local, com aprovação do dono do computador, cancelamento pelo painel e travas de segurança.
Detalhes e limites em `docs/08_executor.md`.

---

## Identificação de sites e sistemas

O TaskMiner registra o **sistema** usado, e não só o programa. Em vez de "Chrome", aparece "CRM Vendas",
"Gmail", "Google Planilhas", "Salesforce", "Portal da NF-e", "Banco do Brasil" e assim por diante.

- **Sites:** o agente lê o endereço na barra do Chrome, Edge, Firefox ou Brave (UI Automation do Windows)
  e guarda só o domínio e o primeiro trecho do caminho (`docs.google.com/spreadsheets`). Parâmetros,
  números e códigos do endereço são descartados.
- **Sites conhecidos:** `sistemas.py` tem um catálogo com e-mail, Google Workspace, Microsoft 365, CRMs,
  ERPs, ferramentas de projeto, portais do governo (NF-e, e-CAC, eSocial, SEFAZ) e bancos.
- **Sites da própria empresa:** quando o domínio não está no catálogo, o nome vem do título da aba
  (ex.: `crm.empresa.com.br` + "CRM Vendas - Oportunidades" → **CRM Vendas**, tela "Oportunidades").
  Para fixar um nome, acrescente uma linha em `SITES` no `sistemas.py`.
- **Programas instalados:** nome conhecido do executável ou o nome do produto gravado no próprio `.exe`.
- Para nunca registrar um site, coloque o domínio em `DOMINIOS_IGNORADOS` no `config.py`.

---

## Documentação dos processos

Cada processo identificado vira um **POP (Procedimento Operacional Padrão)** com: objetivo, quando fazer,
responsável, frequência, horário típico, duração, sistemas, entradas e resultado, e o **passo a passo
numerado** (etapas com sub-passos 1.1, 1.2…, o sistema usado e o tempo típico de cada etapa), além de
pontos de atenção e oportunidades de melhoria.

- **Tela principal**: ao entrar, o administrador vê **Processos da empresa** (todas as atividades por
  área e colaborador, cada uma com o passo a passo, com filtro e busca) e o colaborador vê **Minhas
  atividades** (rotina da semana e o passo a passo de cada atividade). Resumo, gráficos e gargalos
  ficam no menu.
- **Página do processo**: o POP completo aparece no topo, seguido dos gargalos e dos gráficos.
- **Manual de processos do colaborador** (“Meu manual”): descrição da função, rotina da semana
  (o que é feito em cada dia e em que horário) e todos os POPs em sequência.
- **Manual da empresa** (administrador): os manuais de todos os colaboradores, organizados por área.
- **Exportação**: o manual de cada colaborador e o da empresa inteira podem ser baixados em Markdown.

Com a chave da API, quem escreve o POP é o Claude. Sem a chave, um gerador por regras monta o POP a
partir do que foi observado (nome do processo por palavras-chave, instruções no imperativo, entradas e
saídas inferidas). Na Empresa Demo, sem chave, o sistema usa textos de exemplo já escritos pelo Claude
para os dados simulados (`docs_demo.json`).

---

## Processos novos (fora do padrão)

Quando o TaskMiner encontra uma sequência de telas que **se repete** e tem as etapas bem ligadas, mas
ainda **não aparece o suficiente para ser um processo** (ex.: uma atividade que começou nos últimos
dias), ele mostra o aviso **"Novo processo identificado"** com o nome sugerido, o que foi observado e a
pergunta: **ela deve virar um processo fixo?**

- **Sim, tornar processo fixo:** o processo é documentado com o passo a passo (POP) e entra no manual,
  nos gráficos e nas sugestões de melhoria, com a etiqueta "fixado pelo gestor". A documentação já
  escrita dos outros processos é mantida.
- **Não, foi algo pontual:** a sequência deixa de aparecer como processo novo nas próximas análises.
- **Decidir depois:** o aviso some da tela até a próxima visita.

Só o administrador decide; o colaborador vê o aviso de que o gestor vai decidir. As decisões ficam
salvas no banco e valem também quando a análise é refeita. Limites em `config.py` (`NOVO_*`).

---

## Melhorias e gargalos

A aba **Melhorias e gargalos** (para o administrador, a empresa inteira; para o colaborador, só as dele)
reúne as sugestões de melhoria e os gargalos, das mais prioritárias para as menos.

| Fonte | Exemplos |
|---|---|
| Padrões de desperdício vistos na coleta | informação copiada de um sistema e colada em outro; exportação e importação manual; arquivo movido à mão entre pastas; e-mail escrito do zero a cada execução; dados digitados em mais de um sistema |
| Gargalos | etapa lenta, tempo instável, interrupções, digitação manual repetitiva |
| Documentação | oportunidades de melhoria e recomendações escritas no POP e na descrição da função |

Cada sugestão mostra o **impacto** (horas por semana gastas hoje nas etapas envolvidas), o **esforço**
estimado (baixo, médio, alto) e a **prioridade** (alto impacto, ganho rápido, avaliar). Uma matriz
impacto × esforço mostra por onde começar. O administrador acompanha a **situação** de cada sugestão
(nova, em análise, em andamento, concluída, descartada), que fica salva no banco e vai para o manual
exportado da empresa. As regras ficam em `melhorias.py`.

---

## Gráficos e gargalos

- **Gráficos da empresa** (administrador): horas por semana em tarefas repetitivas por área, gargalos
  por área e severidade, ranking dos processos que mais consomem tempo e a divisão do tempo por etapa
  de cada processo.
- **Gráficos do colaborador**: horas por semana em cada processo, mapa de calor de quando os processos
  começam (dia × hora), execuções por dia e onde o tempo vai em cada processo.
- **Em cada processo**: a duração de cada execução ao longo do período (com o tempo normal marcado) e
  a faixa de tempo de cada etapa, que mostra quais etapas variam muito.
- **Gargalos**: uma página com todos os gargalos da empresa (filtro por área e severidade), os
  principais na visão geral e na página do colaborador, e a lista completa dentro de cada processo.
  Também entram no manual exportado e na análise do Claude.

| Gargalo | Quando é apontado |
|---|---|
| Etapa concentra o tempo | uma etapa ocupa 35%+ do tempo do processo |
| Tempo instável | 1 em cada 10 execuções da etapa leva 2× ou mais o tempo normal (mediana) |
| Interrupções frequentes | o colaborador sai do processo no meio em 10%+ das vezes |
| Digitação manual repetitiva | 3+ campos preenchidos à mão na mesma etapa, em toda execução |

Cada gargalo mostra a severidade (alta ou média), a evidência medida, o impacto em horas por semana e
uma sugestão do que fazer. Os limites ficam em `config.py`.

---

## Testar agora, em 2 minutos (qualquer computador)

**Windows:** dê dois cliques em `iniciar.bat`. **Mac:** dois cliques em `iniciar.command`.
Ele instala o que falta, cria a demonstração e abre o Chrome no painel. Pelo terminal, o equivalente é:

```bash
pip install -r requirements.txt
python main.py demo
```

Isso cria a **Empresa Demo Ltda.** com 4 pessoas e simula duas semanas de coleta de duas delas.
Abra **http://localhost:5000** e entre com (senha de todos: `demo12345`):

| Login | Pessoa | Perfil |
|---|---|---|
| marina@demo.com.br | Marina Costa, Gerente de Operações | **Administradora**: vê toda a empresa |
| ana.souza@demo.com.br | Ana Souza, Analista de Contas a Pagar (Financeiro) | colaboradora com processos documentados |
| bruno.lima@demo.com.br | Bruno Lima, Executivo de Vendas (Comercial) | colaborador com processos documentados |
| carla.mendes@demo.com.br | Carla Mendes, Analista de RH | colaboradora ainda sem coleta |

O sistema precisa descobrir sozinho os processos escondidos no meio de muito "ruído" (Teams, e-mails,
navegação, reuniões). Resultado esperado:

| Colaborador | Processo descoberto | Frequência |
|---|---|---|
| Ana | Notas fiscais (Outlook → Acrobat → SAP → Excel) | ~8x por dia |
| Ana | Conciliação bancária (Chrome → Explorador → Excel → Outlook) | 1x por dia, ~08:40 |
| Ana | Relatório semanal (SAP → Excel → PowerPoint → Outlook) | sextas, ~15:00 |
| Bruno | Pedido de venda (Outlook → CRM → SAP → Outlook) | ~7x por dia |
| Bruno | Previsão de vendas (CRM → Excel → Teams) | 1x por dia |
| Bruno | Resultado de metas (CRM → Excel → PowerPoint → Outlook) | segundas |

Para a documentação ser escrita pelo Claude (nomes, objetivos, descrição da função), configure a chave
**antes** do `demo`:

```bash
copy .env.example .env      # Windows   (Linux/Mac: cp .env.example .env)
# edite o .env e cole sua chave em ANTHROPIC_API_KEY
```

Com o demo já criado, basta clicar em **Atualizar análise** na página de cada colaborador.

---

## Usar de verdade numa empresa

### 1. Servidor (um computador da empresa)

```bash
pip install -r requirements.txt
python main.py painel --rede
```

`--rede` deixa o painel acessível pelos outros computadores, no endereço `http://IP-DESTE-PC:5000`
(veja o IP com `ipconfig`). Abra o endereço, clique em **Cadastre a empresa** e crie a conta de
administrador. Depois, em **Colaboradores**, cadastre cada pessoa com nome, e-mail, função, área e
senha inicial.

### 2. Computador de cada colaborador (Windows 10/11, Python 3.10+)

O colaborador entra no painel com o próprio login, abre **Minha coleta** e copia o comando pessoal:

```bash
pip install -r requirements.txt
python main.py coletar --servidor http://192.168.0.10:5000 --token CODIGO-PESSOAL
```

1. Aparece o **termo de consentimento**. Sem "Sim", nada é coletado.
2. Os eventos ficam primeiro no próprio PC e são enviados ao servidor a cada minuto. Sem rede, esperam
   e são enviados depois; nada se perde.
3. A coleta dura 14 dias corridos. Se o PC for desligado, basta rodar `python main.py coletar` de novo
   (servidor e código ficam salvos).
4. **Ctrl+Alt+P** pausa/retoma a coleta a qualquer momento.

Para não precisar abrir o terminal todo dia: `Win + R` → `shell:startup` → crie um atalho para
`pythonw.exe "C:\caminho\para\taskmining\main.py" coletar` (`pythonw` roda sem janela).

### 3. Depois da coleta

Na página do colaborador, o administrador clica em **Rodar análise**. O TaskMiner identifica os
processos e o Claude escreve a documentação, levando em conta a função e a área cadastradas.
A **Visão geral** mostra todos os processos da empresa por área, e **Exportar manual da empresa**
gera um único documento com tudo.

> Sem servidor (um único PC, para testes): `python main.py coletar` sem `--servidor` grava só
> localmente, com o usuário do Windows como identificador. Cadastre esse usuário em
> "Opções avançadas → Identificador de coleta" do colaborador para ligar os dados à conta.

---

## O que é coletado (e o que NÃO é)

| Coletado | Não coletado |
|---|---|
| Aplicativo, título da janela e **sistema** em uso (nos sites, só o **domínio**, ex.: `crm.empresa.com.br`) | Texto digitado (só a **quantidade** de caracteres) e o endereço completo das páginas |
| Nome do botão/campo clicado (UI Automation do Windows) | Senhas, campos de senha |
| Atalhos (Ctrl+C, Ctrl+S…) e teclas Enter/Tab/Esc | Capturas de tela |
| Períodos de ociosidade | Janelas anônimas e gerenciadores de senha |

E-mails, CPFs, CNPJs, cartões e telefones que aparecem em títulos são substituídos por `[email]`,
`[cpf]` etc. **antes** de serem gravados (`privacidade.py`). As listas de apps ignorados e termos
sensíveis ficam em `config.py`.

> **LGPD:** monitorar colaboradores exige base legal, transparência e finalidade definida. O projeto
> pede consentimento explícito, informa o que é coletado, permite pausar e guarda os dados
> localmente. Em uso real numa empresa, envolva o RH/jurídico e o DPO.

---

## Como a IA identifica as tarefas (para a apresentação)

O algoritmo está em `analise.py` e tem 4 etapas:

1. **Segmentação.** Os eventos viram *segmentos*: cada período contínuo numa mesma janela,
   com as ações feitas nela (cliques, campos preenchidos, atalhos).

2. **Generalização.** Títulos são normalizados (`NF_4521.pdf` → `NF_#.pdf`, datas → `<data>`) e as partes
   do título que mudam muito (nome do cliente, assunto do e-mail) viram `*`. Assim, "a planilha de
   controle" é reconhecida como a mesma tela todo dia. Cada segmento recebe um **contexto**
   (aplicativo + tipo de tela).

3. **Mineração de sequências.** O dia vira uma lista de contextos. O sistema conta todas as
   subsequências de 3 a 8 etapas (*n-gramas*) e aceita como processo as que:
   - se repetem **4+ vezes em 3+ dias** (tarefas diárias), ou têm 4+ etapas e se repetem
     em 2+ dias (tarefas semanais);
   - têm **coesão** alta: cada etapa leva à próxima em pelo menos 50% das vezes. Esse filtro elimina
     coincidências (ex.: "abriu o Teams, depois o navegador, depois o e-mail" por acaso);
   - quando se repetem poucas vezes (tarefas semanais), a primeira e a última etapa precisam estar
     ligadas nos dois sentidos, para não "grudar" uma tela aberta por acaso antes ou depois;
   - não se sobrepõem a um processo já escolhido (seleção gulosa por tempo coberto).

4. **Consolidação.** Para cada processo, as ações que aparecem em **50%+ das execuções** formam
   o passo a passo, na ordem média em que acontecem. Ações cujo alvo muda sempre (abrir um
   e-mail diferente a cada vez) viram uma ação genérica ("clicar em item da lista — varia").
   Calcula também frequência, duração média e horário típico.

Por fim, `documentador.py` manda o resumo de cada processo para o **Claude**, que escreve um
**POP** (nome, objetivo, gatilho, passos claros, entradas, saídas, pontos de atenção e
oportunidades de automação) e uma **descrição da função**. Os dados enviados à IA já estão
anonimizados. Sem chave de API, um modelo automático gera a documentação.

Todos os limites (4 repetições, 50% de coesão etc.) podem ser ajustados em `config.py`.

---

## Estrutura do projeto

```
taskmining/
├── main.py            # linha de comando: demo | painel | coletar | enviar | analisar | exportar | simular
├── config.py          # todos os parâmetros ajustáveis
├── agente.py          # coleta no Windows (janela ativa, cliques, atalhos, ociosidade)
├── envio.py           # envio dos eventos do PC do colaborador para o servidor
├── privacidade.py     # mascaramento de dados pessoais
├── sistemas.py        # identifica o sistema/site usado (catálogo de domínios e programas)
├── melhorias.py       # sugestões de melhoria (padrões de desperdício, gargalos, recomendações)
├── analise.py         # algoritmo de task mining
├── documentador.py    # POPs: Claude (com chave) ou gerador por regras; exportação Markdown
├── docs_demo.json     # documentação de exemplo da Empresa Demo
├── painel.py          # painel web (Flask): login, empresa, colaboradores, API do agente
├── simulador.py       # dados fictícios (perfis financeiro e comercial) e a Empresa Demo
├── wsgi.py            # entrada do servidor em produção (Render)
├── render.yaml        # configuração do Render
├── .github/workflows/ # integração contínua e deploy contínuo
├── tests/             # testes automatizados (pytest)
├── ferramentas/       # calculadora de métricas do board
├── docs/              # documentos do Projeto M2 (backlog, DoR, DoD, board, BPMN...)
├── db.py              # banco SQLite
└── templates/         # páginas do painel
```

## Limitações e ideias de evolução

- Para uso fora da rede interna, publique o painel com HTTPS (ex.: atrás de um proxy) e troque o
  servidor de desenvolvimento do Flask por um de produção (waitress no Windows, gunicorn no Linux).
- Processos interrompidos no meio (ex.: atendeu o Teams entre duas etapas) não são contados naquela
  execução. Evolução: permitir "lacunas" na mineração (algoritmos como PrefixSpan com *gaps*).
- O nome dos elementos depende de o aplicativo expor UI Automation; sistemas antigos ou remotos
  (Citrix/RDP) só mostram a janela.
- Coleta só no Windows; macOS/Linux exigiriam outro agente.
- Evoluções: exportar BPMN, sugerir scripts de automação (RPA) para os processos mais frequentes,
  comparar a rotina de vários colaboradores da mesma função.
