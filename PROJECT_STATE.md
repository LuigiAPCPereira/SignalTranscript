# PROJECT_STATE — SignalTranscript / checkpoint

**Observado em:** 2026-09-20. **Escopo:** MVP v0.1, documentação e contratos parciais. **Fontes:** [TASKLIST](TASKLIST.md), [PRD](PRD.md), [DESIGN](DESIGN.md), [AGENTS](AGENTS.md), [relatório documental](docs/ADOPTION_REPORT.md).

## Git e decisões

- Repositório: https://github.com/LuigiAPCPereira/SignalTranscript. Base `main` previamente observada `e4fe22d6fee4120af33d9436f4b0e27864eb5df1`; revalidar antes de integrar.
- PR #1: `docs/mvp-architecture-v0.1` em draft, base do PR #2; último HEAD observado `11f893e5d2cb1cf1ef663b4d838f34cbc9152a2f`.
- PR #2: `feat/t003-groq-contract-offline`, empilhado sobre PR #1, recebeu fatia de T-010 além de T-003. HEAD final deste arquivo deve ser confrontado com GitHub depois do commit; não presumir CI, merge ou estado da `main` por este texto.
- Decidido pelo usuário: produto generalista, Python + FastAPI, Groq Whisper Large V3 Turbo como integração inicial e independência futura de provedores. GPT-OSS 120B, NIM/local como implementações, React/TS, SQLite, yt-dlp e worker têm graus diferentes de proposta/pendência conforme [PRD](PRD.md) e [ADR-002](docs/adr/ADR-002-provider-independence.md).

## Protocolo e cobertura

Índice Notion v2.2 consultado em 2026-09-20: **STAGING**. Fonte canônica editorial aprovada da v2.2, equivalência com a cópia do Project e acesso em Codex/agendamentos não demonstrados. [Relatório](docs/ADOPTION_REPORT.md) mantém **ADOÇÃO PARCIAL**. GitHub remoto foi inspecionado via conector; checkout do repositório nesta sessão não foi obtido (falha de DNS no clone).

## Tarefas e evidências

- **T-004 (checkpoint documental):** nove funções cobertas parcialmente, origem aprovada ainda pendente; não promover STAGING a adotado.
- **T-003 (parcial):** normalizador Groq offline, oito testes locais aprovados em sessão anterior; sem chamada real, cota, limites, chunk overlap, CI ou E2E.
- **T-010 (fatia atual):** portas neutras `TranscriptionProvider`/`AnalysisProvider`, modelo de dados, seleção independente sem fallback e referências validadas. Nove testes novos passaram no diretório local isolado; arquivos enviados à branch e precisam de teste sobre checkout/CI. Não há adaptador Groq operacional, NIM/local reais nem configuração persistente.
- T-005–T-009: sem implementação do produto validada. O PR #2 não demonstra aplicativo funcional.

**Próximo bloco por ID:** T-010 — revisar arquivos publicados e integrar os futuros adaptadores somente pelas portas; T-003 — validar Groq com áudio autorizado e acesso legítimo, sem versionar chaves; T-004 — reconciliar a fonte canônica aprovada quando disponível. Não efetuar merge nem deploy automaticamente.
