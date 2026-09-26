# ROADMAP — SignalTranscript MVP v0.1

**Estado:** marcos vigentes sem prazos prometidos. [PRD](PRD.md) · [TASKLIST](TASKLIST.md) · [Checkpoint](PROJECT_STATE.md).

| Marco | Resultado verificável | Dependências | Tarefas | Estado atual |
| --- | --- | --- | --- | --- |
| M0 — Contratos | Requisitos/arquitetura recuperáveis; contratos de aquisição/IA; Groq validada conforme critérios reais. | Fonte autorizada e cota para testes remotos. | T-001,T-002,T-003,T-010 | **Parcial:** documentação/portas/adaptadores e independência validados offline; Groq autenticada e aquisição real pendentes. |
| M1 — Fundação | Agent Protocol adotado no projeto; FastAPI, jobs/persistência, reinício, backup/recovery seguros. | M0 suficiente para fatias locais; integração Git conforme autorização. | T-004,T-005 | **Parcial:** T-004 passa Adoption Gate na branch; backend/jobs/backup/recovery/smoke validados offline. `main` não integrada e E2E remoto pendente. |
| M2 — Conhecimento | Fonte permitida até transcrição/análise, referências e síntese global recuperável. | M1 + fonte/contrato de transcrição. | T-006,T-007 | **Parcial:** SRT/VTT/proveniência, seções, síntese global e GET read-only implementados/testados offline; áudio/FFmpeg/STT real, identidade da mídia e qualidade semântica pendentes. |
| M3 — Experiência | Frontend, biblioteca, busca, links válidos e cenários E2E/falhas. | M2. | T-008,T-009 | **Pendente:** API parcial não equivale a frontend/biblioteca/E2E. |

**Ordem orientadora:** M0 → M1 → M2 → M3, permitindo fatias isoladas seguras quando dependências específicas estão satisfeitas. Documentação, código, CI, merge e deploy são estados separados. Não há autorização implícita para custos, hospedagem, merge ou deploy.
