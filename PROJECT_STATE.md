# PROJECT_STATE — SignalTranscript / checkpoint

**Ref de trabalho:** `feat/t006-caption-import`, derivada do HEAD `b726344368b387f2e0e6cbd12a7e9d95bbdb8163` do PR #9 em 20/09/2026 (Bahia; commits GitHub podem constar como 21/09 UTC). **Tarefa ativa: [T-006](TASKLIST.md)** — fatia de importação de legendas locais, não aquisição/vídeo→biblioteca completo. [PRD](PRD.md) · [DESIGN](DESIGN.md) · [AGENTS](AGENTS.md) · [adoção](docs/ADOPTION_REPORT.md).

## Git e decisões

- Repositório: https://github.com/LuigiAPCPereira/SignalTranscript. [PR #10](https://github.com/LuigiAPCPereira/SignalTranscript/pull/10) aberto Draft sobre #9, que depende de #8 → … → #1; nenhum foi mesclado nesta etapa. `main` anteriormente verificada no commit inicial `e4fe22d6fee4120af33d9436f4b0e27864eb5df1`. Não houve merge/deploy nem chamada Groq autenticada.
- Decisões: produto generalista, Python + FastAPI, Groq inicial e fronteiras STT/análise independentes. SQLite implementado em jobs/checkpoints; React, biblioteca e aquisição ainda não concluídos. A conversão SRT/VTT é local e não seleciona provedor.

## Protocolo

`AGENTS.md` da ref #9 consultado. Snapshot `DOCUMENTATION_AND_CONTINUITY.md` v2.2 disponível no Project foi lido; Notion v2.2 estava STAGING e `verification=unverified` na última consulta, equivalência integral Project↔fonte canônica não certificada. Nove funções documentais mapeadas no relatório; **ADOÇÃO PARCIAL**, não completar o gate por uma nova branch. Não supor acesso em Codex/agendamentos nem autorização de merge. GitHub examinado por conector; arquivos locais isolados não são checkout Git integral.

## Estado por ID e evidências

- **T-006 — parcial, fatia atual:** `backend/caption_import.py` converte SRT e WebVTT fornecidos pelo usuário para JSON `manual_import` aceito pelo smoke do PR #9. Timestamps lidos, IDs sequenciais, limites de bytes/cues, rejeição de formatos/timebase não suportados, JSON privado e sem overwrite. [Contrato e comandos](docs/T006_CAPTION_IMPORT.md). Treze testes novos passaram primeiro em cópia isolada com stubs e, depois, no CI com contratos reais de API/domínio. [GitHub Actions #10](https://github.com/LuigiAPCPereira/SignalTranscript/actions/runs/35556110432) validou o HEAD de implementação `12672770de761928acd2fe5a55a42ff174ac4d58`, `completed/success` Python 3.12 e 3.13, log 3.13 **117 testes PASS**. Atualizações documentais posteriores exigem CI do HEAD final. Nenhuma legenda/vídeo real foi verificada quanto a autorização, origem e timebase; nenhuma chamada externa. Aquisição, áudio, STT, chunks, proveniência completa e E2E pendentes.
- **T-005 — parcial:** PR #9 adicionou smoke opt-in, checagem pré-envio, FastAPI/SQLite e worker. [CI final #9](https://github.com/LuigiAPCPereira/SignalTranscript/actions/runs/35555393962) passou Python 3.12/3.13 com 104 testes em Python 3.13; sem avisos SQLite no log final. Não é teste Groq real.
- **T-010 — parcial:** seleção neutra por função testada com fake, nenhum NIM/local efetivo. **T-007 — parcial:** apenas `SECTIONS_ONLY`, síntese global e validação semântica ausentes.
- **T-004 — documental bloqueada:** fonte editorial APPROVED/equivalência Project desconhecidas. **T-003/T-008/T-009:** STT/conta reais, UI, biblioteca e E2E pendentes.

**Próxima ação por ID:** T-006 — conferir HEAD final/CI após estes commits documentais e, depois, avaliar importação autorizada com prova de correspondência de vídeo e metadados de proveniência sem executar chamadas remotas implícitas. T-007 continua aguardando síntese global fundamentada; Groq real é opcional e exige decisão explícita no Linux do usuário, sem revelar chave ou repetir job incerto. Não mesclar nem fazer deploy automaticamente.
