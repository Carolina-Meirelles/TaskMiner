# XP e DevOps

## Práticas de XP usadas

| Prática | Como é feita | Evidência |
|---|---|---|
| **TDD** | Em cada história, o teste é escrito primeiro (falhando) e depois o código que o faz passar | Commits `test: ...` antes de `feat: ...` no histórico; pasta `tests/` |
| **Integração Contínua** | Todo push e todo pull request rodam a suíte de testes no GitHub Actions | Aba Actions do GitHub; selo verde nos PRs; `.github/workflows/ci.yml` |
| **Pequenos Releases** | Cada história concluída vai ao ar sozinha, sem esperar o fim da Sprint | Histórico de deploys no Render, um por história |

## DevOps — nível de entrega: Deploy Contínuo

Cada push na `main` dispara o CI; se todos os testes passarem, o GitHub Actions chama o *deploy hook*
do Render e a nova versão vai ao ar sem ação manual.

**Por que Deploy Contínuo:** o time é pequeno, o projeto é um painel web sem dados reais (demonstração
fictícia), a suíte automática cobre a função principal e as permissões, e o Render permite voltar ao
deploy anterior em um clique. O risco de publicar direto é baixo e o ganho é ver cada história no ar no
mesmo dia, como pede o "incremento no ar ao fim de cada Sprint".

**Segredos:** a URL do deploy hook fica em `Settings → Secrets → RENDER_DEPLOY_HOOK` no GitHub; a chave
de sessão é gerada pelo Render; a chave da API do Claude, se usada, fica só nas variáveis de ambiente.
Nada disso vai para o repositório.
