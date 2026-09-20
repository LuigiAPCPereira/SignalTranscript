# PROJECT_STATE — SignalTranscript / checkpoint

**Observado em:** 2026-09-20. **Escopo:** MVP v0.1, desenvolvimento incremental com contratos e adaptadores offline; aplicação E2E ausente. **Fontes:** [TASKLIST](TASKLIST.md), [PRD](PRD.md), [DESIGN](DESIGN.md), [AGENTS](AGENTS.md), [relatório documental](docs/ADOPTION_REPORT.md).

## Git e decisões

- Repositório: https://github.com/LuigiAPCPereira/SignalTranscript. `main` observada anteriormente em `e4fe22d6fee4120af33d9436f4b0e27864eb5df1`, revalidar antes de qualquer integração.
- Cadeia de revisão: PR #1 `docs/mvp-architecture-v0.1` (documentação); PR #2 `feat/t003-groq-contract-offline` (portas/normalização); PR #3 `feat/t003-groq-stt-adapter` (STT). Todos observados como Drafts, não mesclados, na recuperação desta fatia.
- **Fatia atual:** branch `feat/t010-groq-analysis-adapter`, derivada do PR #3 HEAD `8bec26d46ad2c27ba8319b53f6fb3402c9dab3a8`. Revalidar HEAD/PR na conclusão da publicação; sem merge ou deploy nesta sessão.
- Decisões do usuário: produto generalista, backend Python + FastAPI, Groq Whisper Turbo como integração inicial e independência entre provedores STT/LLM. GPT-OSS 120B permanece modelo proposto de análise com adaptador técnico offline; NIM/local não integrados.

## Protocolo e cobertura

Notion v2.2 reaberto em 2026-09-20: **STAGING**. Versão canônica APPROVED/PUBLISHED, igualdade integral à cópia do Project e disponibilidade em Codex/agendamentos não certificadas. [ADOPTION_REPORT](docs/ADOPTION_REPORT.md): **ADOÇÃO PARCIAL**. A branch remota foi consultada por GitHub; nenhum checkout Git do repositório foi obtido neste ambiente (DNS indisponível). Não inferir worktree.

## Tarefas e evidência

- **T-004 (checkpoint documental):** cobertura das nove funções na branch, mas fonte editorial aprovada e integração na `main` pendentes. Não anunciar adoção concluída.
- **T-003 (parcial):** normalizador/adapter Groq STT offline existentes. Classificador de erros extraído para módulo Groq compartilhado sem alterar interface neutra. Sem chamada real, áudio, limite de conta, chunk overlap ou validação CI.
- **T-010 (fatia atual parcial):** portas/seleção independentes, Groq STT e `GroqAnalysisAdapter` offline; JSON Schema estrito, entrada limitada sem truncamento, rejeição de referências inexistentes, respostas incompletas e recusas, falhas tipadas. **47 testes locais passaram** na cópia de arquivos Git blob correspondentes (31 anteriores, 16 de análise); `compileall` passou. Sem SDK instalado, chave, modelo remoto, NIM/local, configuração persistida, CI ou E2E. [Nota técnica](docs/T010_GROQ_ANALYSIS.md).
- **T-007:** pipeline de análise completa pendente: segmentação de vídeos longos, consolidação, versões/persistência, qualidade e evidência de início/meio/fim. A existência do adaptador não conclui esta tarefa.
- T-005, T-006, T-008, T-009: pendentes conforme [TASKLIST](TASKLIST.md).

**Próxima ação executável:** revalidar HEAD/PR desta branch e arquivos publicados; para T-010/T-003, exercitar contratos reais Groq somente em ambiente seguro com conteúdo autorizado e chave local. Em T-007, implementar chunking e consolidar sem perder referências; T-004 continua com bloqueio editorial declarado. Não efetuar merge ou deploy automaticamente.
