# TASKLIST — SignalTranscript MVP v0.1

**Fonte de tarefas:** este arquivo na branch/ref consultada, sem tracker paralelo. [PRD](PRD.md) · [DESIGN](DESIGN.md) · [ROADMAP](ROADMAP.md) · [Checkpoint](PROJECT_STATE.md). Documentação criada não é implementação do produto.

| ID | Marco | Resultado | Estado | Dependências | Aceite / REQ | Evidência e validação | Branch / PR |
| --- | --- | --- | --- | --- | --- | --- | --- |
| T-001 | M0 | Consolidar requisitos e arquitetura recuperáveis. | documentação produzida e reaberta | nenhuma | PRD/DESIGN, critérios REQ-001–012, decisões distinguidas | PRD/DESIGN reabertos no commit `403a8b2d`; sem testes do app | docs/mvp-architecture-v0.1 / #1 draft |
| T-002 | M0 | Contrato de aquisição/importação, proveniência e falhas. | documentação produzida e reaberta; execução pendente | T-001 | REQ-001–003; fallback sem coleta, autorização, estados | DESIGN reaberto em `403a8b2d`; não houve vídeo real | docs/mvp-architecture-v0.1 / #1 draft |
| T-003 | M0 | Teste de contrato Groq: timestamp, formato, tamanho, cotas. | pendente | T-001 | REQ-004–005; resposta real usando áudio autorizado | Não houve acesso à chave/cota individual nem teste | nenhum |
| T-004 | M1 | Reconciliar documentos, instruções AGENTS, fonte aprovada do protocolo e revisão PR. | em andamento — bloqueio de origem v2.2 | T-001,T-002 | Nove funções mapeadas, arquivos reabertos, source/ref, checkpoint ID e fonte aprovada ou lacuna documentada | Dez arquivos reabertos no commit `403a8b2d`, PR #1 draft aberto; Notion v2.2 STAGING | docs/mvp-architecture-v0.1 / #1 draft |
| T-005 | M1 | FastAPI, persistência e worker recuperável. | pendente | T-004 | REQ-008–010; reinício validado | Sem código/testes | nenhum |
| T-006 | M2 | Importação/aquisição permitida, FFmpeg/Groq, chunks. | pendente | T-002,T-003,T-005 | REQ-001–005,REQ-011; timestamps reais | Sem código/testes | nenhum |
| T-007 | M2 | Extração, síntese e referências versionadas. | pendente | T-005,T-006 | REQ-006–009; referências válidas | Sem código/testes | nenhum |
| T-008 | M3 | Frontend, jobs, biblioteca, busca, links. | pendente | T-005,T-007 | REQ-001,007,010,012; fluxo navegável | Sem código/testes | nenhum |
| T-009 | M3 | Validação integração, limites, retomada, segurança. | pendente | T-006,T-007,T-008 | REQ-001–012; testes na revisão exata | CI/E2E/merge não verificados | nenhum |

IDs e estados são estáveis; T-009 não substitui aceites individuais. `T-004` é a tarefa de continuidade do checkpoint; não usar estado documental para anunciar MVP pronto.
