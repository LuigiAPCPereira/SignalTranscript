# PROJECT_STATE — SignalTranscript / checkpoint

**Observado:** 2026-09-20, horário da Bahia, na branch `feat/t005-provider-composition`. **Escopo:** MVP v0.1; análise de transcrições importadas por seções, não YouTube → biblioteca. Autoridades do projeto: [TASKLIST](TASKLIST.md), [PRD](PRD.md), [DESIGN](DESIGN.md), [AGENTS](AGENTS.md), [adoção](docs/ADOPTION_REPORT.md).

## Git, decisões e integração

- Repositório: https://github.com/LuigiAPCPereira/SignalTranscript. `main` anteriormente observada em `e4fe22d6fee4120af33d9436f4b0e27864eb5df1`; revalidar antes de integração.
- PRs em Draft empilhados #1 → #2 → #3 → #4 → #5 → #6 → #7 → [#8](https://github.com/LuigiAPCPereira/SignalTranscript/pull/8); base de #8 `feat/t005-local-job-api` no commit `2a354aa58c15b3d6f0ad2f559b73c6ab9a7b862c`. HEAD de código #8 `1791dc7a6d10564096785bea0a27482bb57b1deb` validado pelo [CI 35554172636](https://github.com/LuigiAPCPereira/SignalTranscript/actions/runs/35554172636), `success` Python 3.12/3.13 e 97 testes no log 3.13. Commits documentais posteriores exigem checar CI no HEAD final. Nenhum merge/deploy autorizado nesta fatia.
- Decisões aceitas: produto generalista, Python + FastAPI, Groq inicial e independência das funções STT/LLM. SQLite presente em jobs/checkpoints; React ainda proposto. Modelos locais/NVIDIA NIM não integrados.

## Protocolo e fonte

`AGENTS.md` no HEAD #7 lido; `DOCUMENTATION_AND_CONTINUITY.md` v2.2 disponível no Project foi consultado. Índice Notion reaberto nesta etapa com status **STAGING**, `verification=unverified`; release aprovada e igualdade completa Notion↔Project não comprovadas. [Relatório](docs/ADOPTION_REPORT.md): **ADOÇÃO PARCIAL**, nove funções mapeadas. Não inferir acesso por Codex ou tarefas agendadas, nem permissão de merge. GitHub examinado via conector; não houve checkout local do repositório por falha de DNS. Uma cópia parcial isolada foi testada em sintaxe e os blobs alterados comparados por SHA Git; não chamá-la de worktree Git.

## Tarefas e evidência

- **T-004 — bloqueio documental:** autoridade/editorial APPROVED, equivalência da cópia e integração do PR #1 ainda pendentes.
- **T-005 — fatia atual, parcial:** `backend/jobs.py` grava transcrições e jobs; `backend/api.py` possui worker único/lifespan, lock Linux, endpoints HTTP e checkpoints; `backend/serve.py` adiciona startup opt-in `--analysis-provider groq`, bind `127.0.0.1`, registro de provedores substituível, diretório/banco privados, revisão de contrato e fechamento do cliente. Uma tarefa `QUEUED` com identidade antiga vira `INTERRUPTED/CONFIGURATION_CHANGED` antes de qualquer chamada ao novo provedor. [Documentação](docs/T005_LOCAL_RUNTIME.md), [PR #8](https://github.com/LuigiAPCPereira/SignalTranscript/pull/8). O [CI de código #8](https://github.com/LuigiAPCPereira/SignalTranscript/actions/runs/35554172636) passou Python 3.12/3.13, log 3.13: **97 testes PASS**, incluindo nove testes de composição; revisar HEAD/CI após este checkpoint. Sem execução Groq autenticada, cancelamento HTTP, migrações/backup ou E2E.
- **T-010 — parcial:** STT e análise permanecem em portas distintas. Groq é opt-in e um registro, não importada no núcleo, sem troca silenciosa; SDK é dependência opcional. NIM/local não validados.
- **T-007 — parcial:** planos, seções, persistência e leitura HTTP com referências estruturalmente verificadas, **não** síntese global nem qualidade de fonte comprovada.
- **T-003/T-006/T-008/T-009:** áudio/Groq reais, aquisição, frontend e E2E pendentes; CI offline não satisfaz seus aceites.

**Próxima ação por ID:** T-005 — confirmar revisão final do PR #8 e CI; após isso, validar uma transcrição autorizada com Groq em ambiente seguro quando credenciais locais estiverem disponíveis, sem expor chave nem assumir cota. T-004 — reconciliar fonte quando houver publicação aprovada. T-007 — síntese global com referências e validação real. Nenhum merge/deploy automático.
