# Product Backlog (ordenado por valor)

Pontos em Fibonacci (1, 2, 3, 5, 8). Valor: 1 a 5, definido pelo PO. Todas as histórias são fatiadas na
vertical: cada uma entrega tela + regra + dado, funcionando de ponta a ponta no link publicado.

| # | História | Pontos | Valor | Sprint |
|---|---|---|---|---|
| H1 | Como **Scrum Master**, quero **transformar uma sugestão de melhoria em história de usuário** (Como/quero/para, com critérios de aceite) **para** levar o gargalo direto ao backlog do time | 5 | 5 | 1 |
| H2 | Como **Product Owner**, quero **ver as histórias de melhoria ordenadas por horas por semana e com a conferência INVEST** **para** priorizar o backlog com dados | 3 | 5 | 1 |
| H3 | Como **membro do time**, quero **acessar o TaskMiner por um link público** **para** usar sem instalar nada | 3 | 4 | 1 |
| H4 | Como **desenvolvedor**, quero **que os testes rodem a cada push e bloqueiem o deploy se falharem** **para** não publicar erro | 2 | 4 | 1 |
| H5 | Como **Scrum Master**, quero **registrar uma ação de melhoria com responsável e prazo** **para** cobrar na próxima retrospectiva | 3 | 4 | 2 |
| H6 | Como **time**, quero **comparar o tempo do processo antes e depois da ação** **para** saber se a melhoria funcionou | 8 | 4 | 2 |
| H7 | Como **Scrum Master**, quero **aplicar os 5 Porquês a um gargalo e guardar a causa raiz** **para** atacar a causa e não o sintoma | 3 | 3 | 2 |
| H8 | Como **Product Owner**, quero **exportar as histórias de melhoria em CSV para o board** **para** não redigitar no GitHub Projects ou Trello | 2 | 3 | 2 |
| H9 | Como **Scrum Master**, quero **ver as melhorias por Sprint (abertas, concluídas, funcionou)** **para** mostrar a evolução do time | 5 | 3 | 3 |
| H10 | Como **colaborador observado**, quero **pedir a exclusão dos meus dados coletados** **para** exercer meu direito na LGPD | 3 | 3 | 3 |
| H11 | Como **pessoa nova que assume uma função**, quero **seguir o manual da função como roteiro de treinamento, marcando cada atividade aprendida**, **para** começar a trabalhar sem depender de quem saiu | 5 | 3 | 3 |
| H12 | Como **avaliador externo**, quero **um roteiro guiado na demonstração** **para** testar o sistema sem explicação | 2 | 2 | 3 |
| H13 | Ajustes vindos do **teste com usuário externo** (as histórias entram aqui quando o teste acontecer) | — | — | 3 |

Capacidade planejada: Sprint 1 = 13 pontos, Sprint 2 = 16, Sprint 3 = 15 + ajustes do teste externo.
Se a velocity da Sprint 1 mostrar que 15 é demais, H12 é a primeira a voltar para o backlog.
A velocity real da Sprint 1 ajusta o plano das seguintes.

---

## Critérios de aceite e INVEST

### H1 — Transformar sugestão em história de usuário (5 pts)
- **Dado** que o Scrum Master está na aba Melhorias, **quando** clicar em "Levar ao backlog" numa
  sugestão, **então** o sistema cria a história no formato Como/quero/para com o processo, a etapa e a
  evidência preenchidos, e ela aparece na lista "Backlog de melhoria".
- **Dado** que a história foi criada, **então** ela tem pelo menos 2 critérios de aceite sugeridos,
  que podem ser editados antes de salvar.
- **Dado** que a mesma sugestão já virou história, **então** o botão mostra "Já no backlog" e não
  duplica.

### H2 — Ordenar por valor e conferir INVEST (3 pts)
- A lista do backlog de melhoria fica ordenada por horas por semana (maior primeiro) e pode ser
  reordenada à mão pelo PO.
- Cada história mostra os 6 itens do INVEST com marcação feita pelo PO; história com item não marcado
  aparece com o aviso "não atende ao INVEST".

### H3 — Link público (3 pts)
- O painel abre no link do Render com a Empresa Demo e os logins fictícios.
- Nenhuma senha real, chave ou dado pessoal real no repositório (chaves só em variáveis de ambiente).

### H4 — Testes bloqueiam o deploy (2 pts)
- A cada push, o GitHub Actions roda `pytest`; com teste falhando, o deploy não acontece.
- Com todos os testes passando na `main`, o Render publica a nova versão sem ação manual.

### H5 — Ação de melhoria com responsável e prazo (3 pts)
- Na aba Melhorias, a ação tem responsável (uma conta da empresa), prazo e situação.
- Ações com prazo vencido e não concluídas aparecem destacadas.

### H6 — Antes e depois (8 pts)
- Para uma ação concluída, o sistema compara a duração mediana do processo nas duas coletas e mostra
  a diferença em minutos e em %.
- Com menos de 3 execuções na coleta nova, mostra "dados insuficientes" em vez de um número.

### H7 — 5 Porquês (3 pts)
- Para um gargalo, o time registra até 5 "por quê" encadeados e marca a causa raiz.
- A causa raiz aparece junto do gargalo e na história gerada a partir dele.

### H8 — Exportar CSV (2 pts)
- O CSV tem título, descrição Como/quero/para, critérios, pontos e valor, e importa no GitHub Projects.

### H9 — Melhorias por Sprint (5 pts)
- Gráfico com abertas, concluídas e "funcionou" por Sprint.

### H10 — Exclusão dos dados (3 pts)
- O colaborador pede a exclusão em "Minha coleta"; o administrador confirma; os eventos e a análise
  daquela pessoa são apagados e a ação fica registrada.

### H11 — Manual como roteiro de treinamento (5 pts)
- **Dado** o manual de uma função, **quando** a pessoa nova abre o modo treinamento, **então** vê as
  atividades em ordem de frequência, cada uma com o passo a passo.
- Cada atividade pode ser marcada como "acompanhada", "feita com ajuda" e "feita sozinha".
- O Scrum Master vê o progresso do treinamento em %.

### H12 — Roteiro guiado (2 pts)
- Na tela de login da demonstração, um roteiro de 5 passos leva o avaliador pela função principal.

### Conferência INVEST (feita na Planning, antes de a história entrar na Sprint)

| História | I | N | V | E | S | T | Observação |
|---|---|---|---|---|---|---|---|
| H1 | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | depende só da aba Melhorias, que já existe |
| H2 | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | usa as histórias criadas em H1 (pode ser feita com dados de teste) |
| H3 | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | |
| H4 | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | |
| H5 | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | |
| H6 | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | maior história; se não couber, fatiar em "comparar duração" e "mostrar no painel" |
| H7 | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | |
| H8 | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | |
| H9 | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | |
| H10 | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | |
| H11 | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | usa o manual que já existe; não depende das outras histórias |
| H12 | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | |

I = Independente · N = Negociável · V = Valiosa · E = Estimável · S = Pequena (Small) · T = Testável
