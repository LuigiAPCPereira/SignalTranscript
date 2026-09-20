# TASKLIST — SignalTranscript MVP v0.1

**Fonte de tarefas:** este arquivo na branch/ref consultada, sem tracker paralelo. [PRD](PRD.md) · [DESIGN](DESIGN.md) · [ROADMAP](ROADMAP.md) · [Checkpoint](PROJECT_STATE.md). Documentação criada não é implementação do produto.

| ID | Marco | Resultado | Estado | Dependências | Aceite / REQ | Evidência e validação | Branch / PR |
| --- | --- | --- | --- | --- | --- | --- | --- |
| T-001 | M0 | Consolidar requisitos e arquitetura recuperáveis. | documentação produzida e reaberta | nenhuma | PRD/DESIGN, critérios REQ-001–012, decisões distinguidas | PRD/DESIGN reabertos no commit `403a8b2d`; sem testes do app | docs/mvp-architecture-v0.1 / #1 draft |
| T-002 | M0 | Contrato de aquisição/importação, proveniência e falhas. | documentação produzida e reaberta; execução pendente | T-001 | REQ-001–003; fallback sem coleta, autorização, estados | DESIGN reaberto em `403a8b2d`; não houve vídeo real | docs/mvp-architecture-v0.1 / #1 draft |
| T-003 | M0 | Teste de contrato Groq: timestamp, formato, tamanho, cotas. | implementação parcial com testes locais; validação remota pendente | T-001 | REQ-004–005; resposta real usando áudio autorizado | Normalização offline: 8 testes unittest passaram no ambiente da sessão; chamada real, cota, tamanho, chunk overlap ainda não verificados | feat/t003-groq-contract-offline / #2 draft |
| T-004 | M1 | Reconciliar documentos, instruções AGENTS, fonte aprovada do protocolo e revisão PR. | em andamento — bloqueio de origem v2.2 | T-001,T-002 | Nove funções mapeadas, arquivos reabertos, source/ref, checkpoint ID e fonte aprovada ou lacuna documentada | Dez arquivos reabertos no commit `403a8b2d`, PR #1 draft; Notion v2.2 STAGING reconfirmado em 20/09/2026 | docs/mvp-architecture-v0.1 / #1 draft |
| T-005 | M1 | FastAPI, persistência e worker recuperável. | pendente | T-004 | REQ-008–010; reinício validado | Sem código/testes | nenhum |
| T-006 | M2 | Importação/aquisição permitida, FFmpeg/Groq, chunks. | pendente | T-002,T-003,T-005,T-010 | REQ-001–005,REQ-011,REQ-013; timestamps reais e uso da porta neutra | Sem integração/testes | nenhum |
| T-007 | M2 | Extração, síntese e referências versionadas. | pendente | T-005,T-006,T-010 | REQ-006–009,REQ-013; referências válidas e uso da porta neutra | Sem código/testes | nenhum |
| T-008 | M3 | Frontend, jobs, biblioteca, busca, links. | pendente | T-005,T-007 | REQ-001,007,010,012; fluxo navegável | Sem código/testes | nenhum |
| T-009 | M3 | Validação integração, limites, retomada, segurança. | pendente | T-006,T-007,T-008 | REQ-001–013; testes na revisão exata | CI/E2E/merge não verificados | nenhum |
| T-010 | M0 | Isolar transcrição e análise de fornecedores específicos; seleção independente e sem fallback implícito. | contratos e seleção implementados; validação local parcial | T-001 | REQ-013; portas não importam SDK, alternância com fakes, nomes não registrados rejeitados, análise valida referências | 9 testes offline novos passaram na cópia local da sessão; sem adaptadores reais, CI, integração ou E2E; ver docs/T010_PROVIDER_BOUNDARY.md e ADR-002 | feat/t003-groq-contract-offline / #2 draft |

IDs e estados são estáveis; T-009 não substitui aceites individuais. `T-004` é a tarefa de continuidade documental do checkpoint; T-010 é fatia técnica independente. A fatia offline de T-003 não desbloqueia T-006 até teste real da Groq. Modelos locais/NIM não estão implementados.
