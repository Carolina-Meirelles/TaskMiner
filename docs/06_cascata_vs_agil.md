# O que daria errado se este projeto fosse feito em Cascata

Em Cascata, todos os requisitos seriam fechados antes de construir, e o sistema só seria testado com
dados no fim. Neste projeto isso teria dado errado em três pontos concretos:

1. **O algoritmo só funciona depois de testado com dados.** Na primeira versão, a análise apontou 19
   "processos", quase todos ruído; só rodando com dados simulados o problema apareceu e foi criado o filtro
   de coesão. Mais tarde, quando os dados mudaram, apareceu um processo duplicado (o mesmo ciclo
   começando pelo meio). Em Cascata, isso apareceria só na fase de testes, com o prazo no fim.
2. **O escopo mudou depois de ler o enunciado.** O protótipo documentava processos de qualquer função; a
   ligação com times ágeis (gargalos virando backlog e Kaizen) surgiu depois. Em Cascata, mudar o
   requisito exigiria refazer a especificação e o projeto.
3. **O usuário externo testa antes do fim.** O enunciado pede o teste antes da Sprint 3 e que o retorno
   entre no backlog. Em Cascata, a opinião do usuário chegaria só na entrega, sem tempo para mudar.
