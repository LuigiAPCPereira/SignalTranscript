# T-005 — API local e worker recuperável: fatias parciais

**Estado:** implementação parcial em [PR #7](https://github.com/LuigiAPCPereira/SignalTranscript/pull/7) (API/worker) e [PR #8](https://github.com/LuigiAPCPereira/SignalTranscript/pull/8) (composição local opt-in). São PRs empilhados ainda não integrados à `main`. [TASKLIST](../TASKLIST.md) · [Checkpoint](../PROJECT_STATE.md) · [Arquitetura](../DESIGN.md) · [Execução](T005_LOCAL_RUNTIME.md).

## API e execução de tarefas

`backend/jobs.py` persiste `Job` e transcrição importada em SQLite (WAL), pré-valida o plano de seções e usa transação `BEGIN IMMEDIATE` para reivindicar somente um job em `RUNNING`. `backend/api.py` fornece `create_app(db_path, analysis_provider=..., provider_name=..., model=..., revision=..., max_chars=...)`, exigindo um `AnalysisProvider` selecionado, sem provedor padrão, chamadas ocultas, retry ou fallback. O FastAPI inicia o worker com `lifespan`. No Linux, `flock` exclusivo no arquivo vizinho ao banco rejeita um segundo processo para esse banco; **não** é lease multiworker nem suporte a `uvicorn --workers N`.

Entrada atual: `POST /api/jobs` recebe **transcrição importada**, não URL/áudio. `GET /api/jobs/{id}` exibe progresso; `GET /api/jobs/{id}/sections` entrega seções, **não resumo global**; `POST /api/jobs/{id}/resume` exige ação explícita. Erros são códigos seguros, sem resposta bruta do SDK. Não há autenticação de serviço público: não expor à rede nem a túneis.

Ao iniciar, jobs `RUNNING` antigos viram `INTERRUPTED/REMOTE_OUTCOME_UNKNOWN`, sem retransmissão automática. Jobs `QUEUED` somente seguem quando sua configuração gravada coincide com provedor/modelo/revisão/orçamento da instância atual; se divergir, viram `INTERRUPTED/CONFIGURATION_CHANGED` **antes de enviar a transcrição**. Retomada manual exige identidade idêntica; `SQLiteSectionCheckpoint` verifica hash de transcrição/plano e reutiliza somente seções gravadas. Sem transação aberta durante IA; shutdown cooperativo não garante cancelamento remoto.

## Composição operacional proposta

O PR #8 acrescenta `backend/serve.py`: seleção obrigatória `--analysis-provider groq`, bind `127.0.0.1`, um processo, SDK opcional de Groq, revisão por hash de prompt/schema/modelo/limite de saída, diretório e banco privados, fechamento assíncrono do cliente. Veja [comandos, privacidade e exemplos](T005_LOCAL_RUNTIME.md). Groq é o primeiro registro; novas integrações devem implementar a porta neutra e adicionar registro explícito, jamais fallback silencioso. Isso torna o backend **iniciável**, mas não comprova sucesso de uma chamada autenticada.

## Verificação e exclusões

Executar `python -m pip install -e '.[test]'`, `python -m compileall -q src tests` e `PYTHONPATH=src python -m unittest discover -s tests -v`. [CI PR #7 final](https://github.com/LuigiAPCPereira/SignalTranscript/actions/runs/35552807725): `success` em Python 3.12/3.13. [CI PR #8 código](https://github.com/LuigiAPCPereira/SignalTranscript/actions/runs/35554172636): `success` Python 3.12/3.13; log 3.13 com **97 testes PASS**, incluindo nove de composição. Verificar CI novamente se HEAD mudar; nenhum teste usa Groq real/credenciais.

**Limites:** sem aquisição YouTube, upload binário, job STT real, migrações/backup, cancelamento por endpoint, espera automática de rate-limit, multiworker, síntese global, UI, autenticação para acesso externo ou E2E com vídeo. `revision` faz hash dos materiais conhecidos; mudanças semânticas fora do hash exigem alteração explícita de contrato. T-005 permanece parcial; T-007/T-010 também. T-004 mantém fonte editorial do protocolo pendente. Nenhum merge/deploy automático.
