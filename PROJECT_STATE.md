# PROJECT_STATE — SignalTranscript / checkpoint

**Observado em:** 2026-09-20 (horário da Bahia). **Escopo:** MVP v0.1, portas/adaptadores offline, análise por seções e checkpoint local de seções; aplicativo completo não existe. **Autoridades:** [TASKLIST](TASKLIST.md), [PRD](PRD.md), [DESIGN](DESIGN.md), [AGENTS](AGENTS.md), [adoção](docs/ADOPTION_REPORT.md).

## Git e decisões

- Repositório: https://github.com/LuigiAPCPereira/SignalTranscript. `main` vista anteriormente em `e4fe22d6fee4120af33d9436f4b0e27864eb5df1`; revalidar antes de merge. PRs #1–#5 observados abertos em Draft, empilhados. [PR #6](https://github.com/LuigiAPCPereira/SignalTranscript/pull/6) criado Draft sobre #5; verificar HEAD atual antes de integração.
- **Fatia atual T-007:** branch `feat/t007-section-checkpoints` criada do HEAD #5 `c0f35a6bd7e9a14c6ba330d2bc29b8bed7720d64`. Sem merge/deploy nesta fatia. Checkout Git local remoto indisponível neste ambiente por DNS; arquivos examinados via conector e hashes Git blobs dos três arquivos Python alterados/novos confrontados com cópia local testada.
- Decidido pelo usuário: produto generalista, Python + FastAPI, Groq Whisper Turbo inicial e independência por função. GPT-OSS 120B: adaptador offline, sem teste autenticado. NIM/local ausentes.

## Protocolo

Manifesto v2.2 disponível no Project está STAGING/NÃO PUBLICADO INTEGRALMENTE; versão editorial aprovada, equivalência integral ao Project e acesso em outras sessões/agendamentos não verificados. [ADOPTION_REPORT](docs/ADOPTION_REPORT.md): **ADOÇÃO PARCIAL**. Nove funções documentadas, autoridade aprovada pendente; não inventar permissões.

## Tarefas e evidência

- **T-004:** documentação e nove funções mapeadas na branch; fonte aprovada, equivalência e integração não confirmadas.
- **T-003/T-010 (parciais):** portas neutras e Groq STT/análise offline; [CI #4](https://github.com/LuigiAPCPereira/SignalTranscript/actions/runs/35548137252) aprovado Python 3.12/3.13. SDK real, áudio, API autenticada, cotas e NIM/local pendentes.
- **T-007 (parcial, checkpoint SQLite):** `ai/long_form.py` executa plano imutável com prefixo validado; `ai/section_checkpoint.py` persiste run e seções, vinculando run ID, hash de transcrição/plano, provedor/modelo e revisão explícita. Reabre prefixo íntegro; não transforma timeout desconhecido em sucesso. **Evidência:** [GitHub Actions run 35549703924](https://github.com/LuigiAPCPereira/SignalTranscript/actions/runs/35549703924) concluiu `success` sobre HEAD `0014d66bd9588687ce6db362e1fe64ec3bd430b1`, ambos Python 3.12/3.13 com `compileall` e suíte offline; log 3.13 confirma 79 testes PASS. Commits documentais posteriores requerem CI no HEAD mais recente. [Nota](docs/T007_LONG_FORM.md).
- **T-005:** nenhuma API FastAPI, scheduler, lease multiworker, persistência de vídeos/transcrições ou recuperação integral de job; checkpoint de seção não conclui tarefa.
- **T-006/T-008/T-009:** aquisição, interface e E2E não existem. T-007 ainda requer síntese global referenciada, versão/persistência de análise completa e teste de representatividade real.

**Próxima ação por ID:** verificar o CI no HEAD final do PR #6; avançar T-005 com backend/worker quando os gates documentais permitirem, sem confundir seção persistida com job durável. T-007 exige síntese global e validação real início/meio/fim. T-003/T-010 exigem testes remotos seguros autorizados. Não efetuar merge/deploy automático.
