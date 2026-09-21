# PROJECT_STATE — SignalTranscript / checkpoint

**Observado em:** 2026-09-20 (Bahia). **Escopo:** MVP v0.1; contratos de provedores, análise por seções e fatia local HTTP/SQLite, sem pipeline completo YouTube → biblioteca. **Fontes:** [TASKLIST](TASKLIST.md), [PRD](PRD.md), [DESIGN](DESIGN.md), [AGENTS](AGENTS.md), [relatório de adoção](docs/ADOPTION_REPORT.md).

## Git e decisões

- Repositório: https://github.com/LuigiAPCPereira/SignalTranscript. `main` anteriormente observada no commit `e4fe22d6fee4120af33d9436f4b0e27864eb5df1`; revalidar antes de integração.
- PRs em Draft empilhados #1 → #2 → #3 → #4 → #5 → #6; **[PR #7](https://github.com/LuigiAPCPereira/SignalTranscript/pull/7)** aberto Draft, base `feat/t007-section-checkpoints` (#6), branch `feat/t005-local-job-api` derivada do HEAD #6 `30061e1d7cf38f299f45cfa52c618aa377e6e678`. HEAD final/CI devem ser consultados no GitHub, não presumidos deste checkpoint. Nenhum merge/deploy neste bloco.
- Decisões do usuário: ferramenta generalista; Python + FastAPI; Groq primeiro STT; provedores de transcrição e análise independentes. GPT-OSS 120B é adaptador offline, NVIDIA NIM/local ausentes. React/SQLite como arquitetura proposta; SQLite já usado tecnicamente em seções/jobs, sem estabelecer biblioteca final completa.

## Protocolo

Cópia `DOCUMENTATION_AND_CONTINUITY.md` 2.2 está disponível no ChatGPT Project e foi lida, mas equivalência integral com a fonte editorial aprovada e publicação/APPROVED do Notion não certificadas (última consulta Notion: STAGING). `AGENTS.md` da ref #6 foi consultado; [ADOPTION_REPORT](docs/ADOPTION_REPORT.md) continua **ADOÇÃO PARCIAL**. Nove funções mapeadas; não inferir acesso em agendamentos ou permissão de merge. Sem checkout autenticado local do repositório: GitHub consultado por conector; cópia de desenvolvimento isolada verificada com hashes Git blob.

## Tarefas e validação

- **T-004 (bloqueio documental):** origem canônica aprovada/equivalência e integração documental pendentes; não declarar adoção completa.
- **T-003/T-010 (parciais):** adaptadores Groq STT/análise e portas testados offline, sem SDK/conta/chave/áudio/modelo remoto/NIM/local.
- **T-007 (parcial):** seções e checkpoint em #5/#6, exposição HTTP apenas de seções em #7; sem síntese global, conteúdo real ou teste semântico de início/meio/fim.
- **T-005 (fatia atual, parcial):** [nota](docs/T005_LOCAL_JOB_API.md). `SQLiteJobs` persiste transcrição importada e estado de job; API FastAPI fornece `POST /api/jobs`, consulta de estado/seções e retomada manual. Worker único em lifespan FastAPI, lock de processo Linux; RUNNING interrompido no reinício não é reexecutado automaticamente, e prefixos de seções verificados são reutilizados após comando explícito. O sistema só entrega `SECTIONS_ONLY`. **Evidência de código**: commit `5bf6cf8f5e81ce29019a99ec5e4cb0d81e5b1b5a`, [GitHub Actions run 35552555937](https://github.com/LuigiAPCPereira/SignalTranscript/actions/runs/35552555937) `success` em Python 3.12/3.13; log Python 3.13: **87 testes PASS** (8 novos). Quatro blobs novos foram conferidos por hash contra a cópia local. Atualizações documentais subsequentes exigem revalidar CI no HEAD final. Não há entrypoint de produção configurado com provedor real, autenticação pública, cancelamento HTTP, lease multiworker, backup/migrações ou E2E.
- **T-006/T-008/T-009:** aquisição de vídeo/áudio, frontend, biblioteca e E2E não validados. CI offline não completa esses aceites.

**Próxima ação por ID:** T-005 — confirmar HEAD e CI da revisão final do PR #7; depois escolher fatia de configuração local segura e fluxo com provedor real autorizado, sem merge ou cobrança implícita. T-004 depende de fonte editorial aprovada. T-007 requer síntese global verificável. Preservar branches/PRs, não fazer merge ou deploy automático.
