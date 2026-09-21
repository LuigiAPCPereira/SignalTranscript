# PROJECT_STATE — SignalTranscript / checkpoint

**Ref observada:** `feat/t005-smoke-test`, PR #9, em 2026-09-20/21 (horário da Bahia, commits GitHub datados em UTC). **Tarefa ativa: T-005**; pendências relacionadas T-004, T-007 e T-010. Escopo é análise de **transcrição importada por seções**, não pipeline completo YouTube → biblioteca. [TASKLIST](TASKLIST.md) · [PRD](PRD.md) · [DESIGN](DESIGN.md) · [AGENTS](AGENTS.md) · [adoção](docs/ADOPTION_REPORT.md).

## Git e decisões

- Repositório: https://github.com/LuigiAPCPereira/SignalTranscript. PRs #1–#9 empilhados em Draft, #9 sobre [#8](https://github.com/LuigiAPCPereira/SignalTranscript/pull/8), não sobre `main`. `main` foi observada anteriormente em `e4fe22d6fee4120af33d9436f4b0e27864eb5df1`; revalidar antes de qualquer integração. Nenhum merge ou deploy nesta fatia.
- HEAD do PR #9 ao criar: `69fabfeaf4822932875823c8b33df336ae4f8468`; [CI 35555229747](https://github.com/LuigiAPCPereira/SignalTranscript/actions/runs/35555229747) `success` em Python 3.12 e 3.13, 104 testes PASS no log Python 3.13. O log mostrou quatro avisos `ResourceWarning` provenientes de conexões SQLite não fechadas em `tests/test_section_checkpoint.py`; o teste foi corrigido no commit `33b6cdc049ee7dc8c4daa4a17b7776a77ec301ff`. Conferir CI do HEAD atual/final; não usar run antigo como prova de ausência dos avisos.
- Decisões aceitas: ferramenta generalista, Python + FastAPI, Groq como primeira opção e **não dependência de domínio**; transcrição e análise selecionadas independentemente. SQLite implementado para jobs/checkpoints. React, biblioteca e aquisição permanecem por concluir; NVIDIA NIM/local não estão operacionais.

## Protocolo e fontes

`AGENTS.md` da branch mãe #8 foi consultado; cópia v2.2 de `DOCUMENTATION_AND_CONTINUITY.md` do Project disponível, mas equivalência integral Project↔fonte editorial não comprovada. Índice Notion reaberto e permanece **STAGING**, `verification=unverified`; publicação APPROVED não certificada. Nove funções mapeadas no [relatório](docs/ADOPTION_REPORT.md), **ADOÇÃO PARCIAL**. Não presumir acesso por Codex/tarefas agendadas, nem permissão de merge. Trabalho remoto feito pelo conector GitHub; cópia isolada local não é checkout Git completo.

## Estado por tarefa

- **T-005 — parcial, bloco atual:** API FastAPI, worker único Linux, jobs/transcrições persistidos e checkpoints com retomada explícita nos PRs #6–#8. PR #9 acrescenta [smoke test](docs/T005_SMOKE_TEST.md) sem rede por padrão e texto sintético, rota `/api/config` com nome do provedor/modelo, exigência de consentimento para um único POST, consulta job/seções, cobertura de IDs e referências válidas. CI inicial #9 aprovou o percurso HTTP/SQLite com provider fake. **Groq real não foi chamada**. Faltam cancelamento HTTP, migrações/backup, vídeo e E2E.
- **T-010 — parcial:** portas neutras, registro explícito de análise e checagem da identidade antes do POST. Nenhum fallback automático, Groq opcional, NIM/modelos locais não implementados/testados. Operação real ainda pendente.
- **T-007 — parcial:** seções e checkpoints; `SECTIONS_ONLY` não é síntese global nem verificação factual. Prova semântica com conteúdo real pendente.
- **T-004 — bloqueio documental:** publicação aprovada/equivalência fonte canônica pendentes. **T-003/T-006/T-008/T-009:** teste de STT com áudio autorizado, aquisição, frontend/biblioteca e E2E pendentes.

**Próxima ação por ID:** T-005 — confirmar CI do HEAD final do PR #9; testar `python -m signaltranscript.backend.smoke --transcript examples/synthetic_transcript.json` sem rede e, somente após escolha explícita do usuário e credenciais no ambiente dele, um teste Groq real, registrando resultado sem conteúdo sensível. Não reenviar automaticamente job de resultado incerto. Depois priorizar T-006 ou síntese global T-007 conforme gates verificados. Sem merge/deploy automático.
