# Executor: o Claude opera o computador

O executor deixa o Claude fazer uma tarefa no computador de um colaborador (abrir programas, clicar,
digitar, copiar dados entre sistemas), a partir de um comando escrito no painel.

```
 Painel (servidor)                                   Computador do colaborador
 ┌───────────────────────────────┐   captura de tela  ┌──────────────────────────┐
 │ fila de comandos + aprovação  │ ◀───────────────── │ executor.py              │
 │ executor_ia.py ⇄ API do Claude│ ──── ação ───────▶ │ clica, digita, rola      │
 │ (a chave da API fica aqui)    │                    │ (pyautogui)              │
 └───────────────────────────────┘                    └──────────────────────────┘
```

## Como usar
1. No servidor, defina `ANTHROPIC_API_KEY` (no Render: Environment).
2. No computador: `pip install -r requirements-executor.txt` e
   `python executor.py --servidor https://SEU-SITE --token SEU_CODIGO` (o comando pronto aparece na aba **Executor**).
3. Na aba **Executor**, o colaborador clica em **Liberar o executor** e escreve o comando.
   Se o gestor escrever o comando para outra pessoa, ele só roda depois que ela **aprovar**.

## Travas de segurança
| Trava | Onde |
|---|---|
| O colaborador precisa liberar o executor (desligado por padrão) | painel |
| Comando de outra pessoa exige aprovação do dono do computador; admin não aprova por ele | painel |
| Cancelar no painel interrompe no próximo passo | painel + API |
| Mouse num canto da tela ou Ctrl+C para na hora | executor.py |
| Janela de senha, banco, gerenciador de senhas ou navegação anônima em foco: nenhuma captura é enviada e o comando termina como "bloqueado" | executor.py |
| Limite de passos por comando (`EXECUTOR_MAX_PASSOS`, padrão 40) | servidor |
| Instruções do sistema proíbem digitar senhas/2FA, ações irreversíveis não pedidas, e mandam tratar o conteúdo das telas como dados (defesa contra prompt injection) | `executor_ia.SISTEMA` |
| Texto digitado e capturas não ficam no banco; só o tipo de cada ação | `executor_ia.py` |

## Privacidade (importante para a LGPD)
Enquanto um comando roda, capturas da tela do colaborador são enviadas ao servidor e à API da Anthropic.
Isso é diferente da coleta de task mining, que nunca captura a tela. O texto de consentimento deve
mencionar o executor antes de ele ser usado com pessoas reais.

## Limites conhecidos
- A versão da ferramenta de computador da API está em `config.EXECUTOR_TOOL_TYPE` / `EXECUTOR_BETA`.
  Se a API rejeitar, consulte a documentação atual e troque os dois valores.
- O bloqueio por janela sensível só funciona no Windows; no macOS/Linux o executor roda sem essa checagem.
- Um comando por vez por computador; sem retomada se o computador for desligado no meio.
