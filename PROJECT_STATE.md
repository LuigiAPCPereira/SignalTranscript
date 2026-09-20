# PROJECT_STATE — SignalTranscript / checkpoint

**Data da observação:** 2026-09-20. **Escopo:** MVP v0.1, planejamento. **Fonte:** [TASKLIST](TASKLIST.md) é o inventário, [PRD](PRD.md) é a especificação, [DESIGN](DESIGN.md) é arquitetura proposta.

## Repositório e revisão observados

- Repo: https://github.com/LuigiAPCPereira/SignalTranscript (público; acesso de escrita confirmado pelo conector).
- Base `main`: `e4fe22d6fee4120af33d9436f4b0e27864eb5df1` (commit inicial; só README no inventário observado).
- Branch de documentação: `docs/mvp-architecture-v0.1` (criada a partir da base acima). HEAD final da branch e PR devem ser revalidados após a publicação; não presumir merge.
- Worktree local do repositório: **não inspecionada**; o conector GitHub fornece estado remoto.

## Decisões, fonte do protocolo e situação

- Decidido pelo usuário: propósito generalista; Python + FastAPI; Groq Whisper Large V3 Turbo. Proposto: React/TS, SQLite, yt-dlp condicionado, GPT-OSS 120B, worker.
- `DOCUMENTATION_AND_CONTINUITY.md` v2.2 e `AGENTS_TEMPLATE.md` são snapshots anexos do Project, lidos em contexto separado do checkout. Índice Notion v2.2 consultado em 20/09/2026: STAGING, sem equivalência editorial integral certificada; fonte canônica APPROVED/PUBLISHED da v2.2 **não comprovada**. Não supor acesso de Codex ou automações aos anexos/Notion.
- Este pacote não significa adoção concluída do protocolo; conferir [relatório](docs/ADOPTION_REPORT.md) e atualizar somente com evidência da ref publicada.

## Tarefa ativa e próximo bloco

**T-004** — completar entrada documental, cobertura de nove funções e revisão remota do conteúdo desta branch ([TASKLIST](TASKLIST.md)); antes de código, reconciliar status editorial do protocolo e avaliar impedimentos reais. T-002 possui contrato proposto, sem validação com vídeos reais. T-003 aguarda teste de contrato Groq autorizado.

Implementação do produto, testes de API/E2E, CI, merge e deploy: **não realizados / não verificados**. Limites efetivos da conta Groq, autorização concreta de vídeos e política de retenção ainda desconhecidos.

**Próxima ação verificável:** reabrir README, AGENTS, PRD, DESIGN, TASKLIST, ROADMAP, ADR, SESSION_LOG e relatório na branch; atualizar estados/PR/HEAD conforme evidências, sem declarar adoção concluída enquanto o protocolo necessário não estiver comprovado.
