# Board Kanban

Ferramenta: **GitHub Projects** (gratuito, ligado ao repositório). Cada história é um cartão; cada
cartão guarda a data em que entrou em cada coluna (campos de data), que alimenta as métricas.

| Coluna | Limite de WIP | Política para entrar | Política para sair |
|---|---|---|---|
| Backlog | — | História escrita no formato Como/quero/para | Atende à DoR e foi escolhida na Planning |
| Pronto para fazer | — | Atende à **DoR** | Um desenvolvedor puxa quando tem espaço em "Fazendo" |
| Fazendo | **2** (1 por pessoa) | Alguém assumiu o cartão; preencher **Data de início** | Código e teste prontos, PR aberto |
| Revisão e teste | **2** | PR aberto, CI rodando | PR aprovado pelo outro integrante e CI verde |
| Feito | — | Atende à **DoD**; preencher **Data de conclusão** | — |

Regras do time:
- **Puxar, não empurrar:** só puxa cartão novo quando a coluna seguinte tem espaço.
- Coluna cheia = o time ajuda a esvaziar antes de começar outra coisa.
- Cartão parado há mais de 2 dias em "Fazendo" é assunto da daily.
- No fim de cada Sprint, tirar uma **imagem do board** e colocar no Relatório.

## Campos de cada cartão (para exportar e calcular as métricas)

`id, titulo, pontos, sprint, criado_em, iniciado_em, concluido_em` (datas no formato AAAA-MM-DD).
A exportação em CSV do GitHub Projects vai direto para a calculadora `ferramentas/metricas.py`.
