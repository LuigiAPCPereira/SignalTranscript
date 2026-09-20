# SESSION_LOG — Histórico recuperável

## 2026-09-20 — Planejamento e primeira revisão documental

- O usuário definiu o produto generalista, escolheu Python + FastAPI e aceitou Whisper Large V3 Turbo pela Groq. GPT-OSS 120B, React/TS, SQLite, yt-dlp e worker foram discutidos como propostas, sem testes.
- Cinco rascunhos locais foram produzidos na conversa. Depois o usuário informou `https://github.com/LuigiAPCPereira/SignalTranscript`. Verificação remota inicial: `main` em `e4fe22d6fee4120af33d9436f4b0e27864eb5df1` com apenas README original; worktree local não inspecionada.
- Branch documental `docs/mvp-architecture-v0.1`; HEAD observado `11f893e5d2cb1cf1ef663b4d838f34cbc9152a2f`; PR #1 aberto como draft e não mesclado na consulta.
- A central do protocolo v2.2 no Notion foi reaberta e continuava STAGING, sem prova de equivalência à cópia do Project nem de acesso independente em Codex/agendamentos. ADOÇÃO PARCIAL.

## 2026-09-20 — Fatia offline do contrato de transcrição

- T-003: referência oficial da Groq confirma `whisper-large-v3-turbo`, `response_format=verbose_json` e timestamps de `segment`. Um comentário de exemplo apresenta inconsistência textual e não substitui a referência de parâmetros.
- Normalizador isolado em Python, sem SDK, rede ou segredos, valida segmento, ID determinístico por chunk/posição, timestamps em milissegundos e offset explícito. Oito testes `unittest` passaram no ambiente da sessão anterior, e `compileall` terminou sem erros; execução no CI GitHub não verificada.
- Publicada a branch `feat/t003-groq-contract-offline` e aberto [PR #2](https://github.com/LuigiAPCPereira/SignalTranscript/pull/2) em draft, empilhado no PR #1. T-003 não verifica contas, chamada real, limite de upload, sobreposição ou aplicativo completo.

## 2026-09-20 — Independência de provedores (T-010)

- O usuário determinou que a Groq não seja dependência permanente e que transcrição e análise possam escolher provedores diferentes, inclusive locais no futuro. [ADR-002](docs/adr/ADR-002-provider-independence.md) registra a decisão; REQ-013 e T-010 registram aceites e dependências.
- Na branch do PR #2, acrescentados os protocolos Python `TranscriptionProvider`/`AnalysisProvider`, dados canônicos, seleção independente sem fallback e validação estrutural de referências. Nove testes novos passaram no diretório isolado desta sessão após corrigir um erro no teste inicial; `compileall` passou. Testes usam implementações simuladas, não NIM/local/Groq de verdade.
- Tentativa de `git clone` para executar a suíte inteira sobre a revisão remota falhou por resolução de DNS do GitHub no ambiente. Arquivos são verificáveis pelo conector; CI, integração remota, E2E e faturamento seguem sem teste.
- A decisão arquitetural adicionou uma fatia pequena ao PR #2 existente; não foi criado outro PR, e a `main` não foi alterada por essas operações.

**Checkpoint vinculado:** T-004 documental e T-010 técnico, com T-003 parcial. Conferir [TASKLIST](TASKLIST.md), [PROJECT_STATE](PROJECT_STATE.md) e PRs/HEAD atuais antes de continuar.
