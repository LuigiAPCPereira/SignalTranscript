# PROJECT_STATE — SignalTranscript / checkpoint

**Observado em:** 2026-09-20. **Escopo:** MVP v0.1, documentação e contratos parciais. **Fontes:** [TASKLIST](TASKLIST.md), [PRD](PRD.md), [DESIGN](DESIGN.md), [AGENTS](AGENTS.md), [relatório documental](docs/ADOPTION_REPORT.md).

## Git e decisões

- Repositório: https://github.com/LuigiAPCPereira/SignalTranscript. Base `main` previamente observada `e4fe22d6fee4120af33d9436f4b0e27864eb5df1`; revalidar antes de integrar.
- PR #1: branch `docs/mvp-architecture-v0.1` em draft. PR #2: `feat/t003-groq-contract-offline`, empilhado sobre #1, último HEAD confirmado antes desta fatia `457112a31d92af68f36fb6bcd9c53b8c9cc0dfae`.
- Fatia atual: branch `feat/t003-groq-stt-adapter`, derivada do HEAD do PR #2 citado. PR e HEAD final devem ser verificados no GitHub após publicação; não presumir CI, merge ou trabalho em worktree local do repositório.
- Decidido pelo usuário: produto generalista, Python + FastAPI, Groq Whisper Large V3 Turbo como integração inicial e independência futura de provedores. GPT-OSS 120B, NIM/local como implementações, React/TS, SQLite, yt-dlp e worker têm graus diferentes de proposta/pendência conforme [PRD](PRD.md) e [ADR-002](docs/adr/ADR-002-provider-independence.md).

## Protocolo e cobertura

Índice Notion v2.2 consultado em 2026-09-20: **STAGING**. Fonte canônica editorial aprovada da v2.2, equivalência com a cópia do Project e acesso em Codex/agendamentos não demonstrados. [Relatório](docs/ADOPTION_REPORT.md) mantém **ADOÇÃO PARCIAL**. Conector GitHub inspecionado; testes foram executados em cópia isolada dos arquivos (hash Git dos arquivos base confrontado), não em checkout remoto autenticado nem CI.

## Tarefas e evidências

- **T-004 (checkpoint documental):** nove funções documentadas com lacunas de fonte aprovada; não promover STAGING a adotado.
- **T-003 (fatia atual parcial):** normalizador offline e adaptador `AsyncGroq` por injeção; arquivo checado antes de enviar, sem retry automático de SDK, falhas tipadas, resposta convertida para `Transcript`. Testes locais completos da cópia: 31 `unittest` aprovados (8 do normalizador, 9 das portas e 14 do adaptador); `compileall` passou. Nenhuma chamada Groq, SDK real, teste de áudio/codec, cota efetiva, chunk overlap, CI ou E2E. Detalhes em [nota T-003](docs/T003_GROQ_ADAPTER.md).
- **T-010 (parcial):** portas e seleção independentes existentes; adaptador de transcrição Groq integra a porta em testes com fake, mas `AnalysisProvider` real, configuração persistente, NIM e local não existem.
- T-005–T-009: sem implementação do aplicativo validada; PRs em draft não significam integração.

**Próximo bloco por ID:** T-003 — conferir HEAD/PR da fatia e realizar validação do SDK e API com áudio autorizado, chave somente no ambiente, limites reais e bordas de chunk; T-010 — implementar análise pela porta neutra depois; T-004 — verificar fonte aprovada quando disponível. Não efetuar merge ou deploy automaticamente.
