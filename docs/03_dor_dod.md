# Definition of Ready e Definition of Done

Pactos do time, combinados antes da Sprint 1 e usados em toda história. A DoD vale igualmente para o
código escrito pela IA.

## Definition of Ready (a história pode entrar na Sprint quando…)

1. Está no formato **Como <usuário>, quero <ação>, para <benefício>**.
2. Tem **critérios de aceite** testáveis (de preferência no formato Dado / Quando / Então).
3. Foi **estimada** pelo time em pontos e tem **até 8 pontos**; maior que isso, é fatiada.
4. Passou na **conferência INVEST**.
5. Está **fatiada na vertical**: entrega algo usável de ponta a ponta (tela + regra + dado).
6. **Dependências** resolvidas ou conhecidas (nada bloqueia o início).
7. Os **dados de teste fictícios** necessários estão definidos.
8. O PO definiu o **valor** e a posição no backlog.

## Definition of Done (a história está pronta quando…)

1. Todos os **critérios de aceite** foram conferidos pelo PO no link publicado.
2. Tem **teste automatizado** novo cobrindo o comportamento e toda a suíte passa no **CI**.
3. O código entrou na `main` por **pull request revisado pelo outro integrante**, inclusive o que a IA
   escreveu; quem revisa consegue explicar o trecho.
4. O **deploy automático** publicou a versão e a função foi verificada no link do Render.
5. **Nenhuma senha, chave ou dado pessoal real** foi para o repositório ou para os pedidos à IA.
6. Erros são **tratados** com mensagem clara para o usuário (sem página de erro do servidor).
7. O **registro de uso da IA** da história foi preenchido no Relatório (o que pediu, o que aceitou, o que
   corrigiu e por quê).
8. **README e docs** atualizados quando a história muda o uso do sistema.
9. O cartão foi movido para **Feito** no board com as datas preenchidas.
