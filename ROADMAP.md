# ROADMAP — SignalTranscript MVP v0.1

**Estado:** proposta de marcos sem prazos prometidos. [PRD](PRD.md) · [TASKLIST](TASKLIST.md).

| Marco | Resultado verificável | Dependências | Tarefas | Estado |
| --- | --- | --- | --- | --- |
| M0 — Contratos | PRD/arquitetura e aquisição documentados; contrato Groq validado em chamada real. | Fonte autorizada e cota disponíveis para teste. | T-001,T-002,T-003 | Parcial: documentação em branch; Groq não testada. |
| M1 — Fundação | Docs de projeto reconciliados, backend FastAPI e job persistente recuperável em reinício. | M0 e repo/ref. | T-004,T-005 | Parcial apenas quanto à documentação; sem código. |
| M2 — Conhecimento | Importação/áudio autorizado até análise com referências válidas. | M1 e contrato de transcrição. | T-006,T-007 | Pendente. |
| M3 — Experiência | Frontend, biblioteca, pesquisa e cenários E2E/falhas. | M2. | T-008,T-009 | Pendente. |

**Ordem:** M0 → M1 → M2 → M3. Não há autorização nem configuração de custos, hospedagem ou deploy. Marco documental não prova produto implementado.
