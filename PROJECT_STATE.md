# PROJECT_STATE — SignalTranscript / checkpoint

**Ref de trabalho:** `feat/t006-caption-import`, derivada do HEAD `b726344368b387f2e0e6cbd12a7e9d95bbdb8163` do PR #9 em 20/09/2026 (Bahia; commits GitHub podem constar como 21/09 UTC). **Tarefa ativa: [T-006](TASKLIST.md)** — fatia de importação de legendas locais, não aquisição/vídeo→biblioteca completo. [PRD](PRD.md) · [DESIGN](DESIGN.md) · [AGENTS](AGENTS.md) · [adoção](docs/ADOPTION_REPORT.md).

## Git e decisões

- Repositório: https://github.com/LuigiAPCPereira/SignalTranscript. PRs #1–#9 empilhados, abertos em Draft, não mesclados. Branch T-006 criada a partir de #9; PR desta fatia a abrir. `main` anteriormente verificada no commit inicial `e4fe22d6fee4120af33d9436f4b0e27864eb5df1`. Não houve merge/deploy nem chamada Groq autenticada.
- Decisões: produto generalista, Python + FastAPI, Groq inicial e fronteiras STT/análise independentes. SQLite implementado em jobs/checkpoints; React, biblioteca e aquisição ainda não concluídos. A conversão SRT/VTT é local e não seleciona provedor.

## Protocolo

`AGENTS.md` da ref exata #9 consultado. Snapshot `DOCUMENTATION_AND_CONTINUITY.md` v2.2 disponível no Project foi lido; Notion v2.2 estava STAGING e `verification=unverified` na última consulta, equivalência integral Project↔fonte canônica não certificada. Nove funções documentais mapeadas no relatório; **ADOÇÃO PARCIAL**, não completar o gate por uma nova branch. Não supor acesso em Codex/agendamentos nem autorização de merge. GitHub examinado por conector; arquivos locais isolados não são checkout Git integral.

## Estado por ID e evidências

- **T-006 — parcial, fatia atual:** `backend/caption_import.py` converte SRT e WebVTT fornecidos pelo usuário para JSON `manual_import` aceito pelo smoke do PR #9. Timestamps lidos, IDs sequenciais, limites de bytes/cues, rejeição de formatos/timebase não suportados, JSON privado e sem overwrite. [Contrato e comandos](docs/T006_CAPTION_IMPORT.md). Código e 13 testes foram validados **isoladamente** com stubs de API/domínio; os hashes Git blob do código e testes publicados conferem com arquivos locais. A suíte no repositório/CI do HEAD desta branch **ainda precisa ser confirmada**. Não houve vídeo/legenda real autorizado, verificação da origem ou chamada externa. Aquisição, áudio, STT, chunks, proveniência completa e E2E pendentes.
- **T-005 — parcial:** PR #9 adicionou smoke opt-in, checagem pré-envio, FastAPI/SQLite e worker. [CI final #9](https://github.com/LuigiAPCPereira/SignalTranscript/actions/runs/35555393962) passou Python 3.12/3.13 com 104 testes em Python 3.13; sem warnings SQLite no log final. Não é teste Groq real.
- **T-010 — parcial:** seleção neutra por função testada com fake, nenhum NIM/local efetivo. **T-007 — parcial:** apenas `SECTIONS_ONLY`, síntese global e validação semântica ausentes.
- **T-004 — documental bloqueada:** fonte editorial APPROVED/equivalência Project desconhecidas. **T-003/T-008/T-009:** STT/conta reais, UI, biblioteca e E2E pendentes.

**Próxima ação por ID:** T-006 — abrir PR draft empilhado sobre #9, confirmar HEAD exato e CI Python 3.12/3.13, reabrir código/doc/testes e registrar limites. A execução com Groq permanece opcional e requer escolha explícita no Linux do usuário; nunca armazenar chave ou repetir job incerto. Depois avançar para T-007 ou restantes de T-006 conforme aceites e dependências. Não mesclar nem fazer deploy automaticamente.
