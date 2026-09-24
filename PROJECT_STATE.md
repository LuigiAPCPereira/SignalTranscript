# PROJECT_STATE — SignalTranscript / checkpoint

**Ref de trabalho:** `feat/t006-caption-import`, [PR #10](https://github.com/LuigiAPCPereira/SignalTranscript/pull/10) sobre PR #9, sem merge. **Tarefa ativa: [T-006](TASKLIST.md)** — importação/proveniência de legendas autorizadas; não pipeline YouTube → biblioteca. [PRD](PRD.md) · [DESIGN](DESIGN.md) · [AGENTS](AGENTS.md) · [relatório de adoção](docs/ADOPTION_REPORT.md).

## Git e validação

- PR #10 permanece Draft e empilhado. Nenhum merge/deploy foi autorizado nesta fatia e nenhuma chamada autenticada à Groq foi executada.
- A primeira revisão da verificação server-side (`a3c1f734087a8f31ed0c65238a2c37996320dec0`) falhou porque `caption_verification=None`, campo somente de transporte, entrou em serialização usada pelo smoke. A causa foi corrigida sem relaxar o contrato de proveniência.
- **Checkpoint T-006 validado:** SHA `a8b775ea7d10b3e834cafa0d50629d3cd264443e`, GitHub Actions 35884798012, `completed/success`, Python 3.12/3.13.
- **Checkpoint T-005 de recuperação validado:** SHA `ec627014fe5e038cc74e5fc8d09516dd3e62d26a`, GitHub Actions 35989071501, `completed/success`, Python 3.12/3.13. Inclui cancelamento conservador, schema de jobs versionado/fail-closed, snapshot SQLite WAL-safe, inspeção/pinning SHA-256, restore staging para caminho novo e `RecoveryReceipt` schema v1 persistente/verificável.
- Alterações documentais posteriores a esses SHAs exigem CI próprio no HEAD final antes de afirmar que a revisão final do PR está verde.
- O trabalho desta execução é remoto pelo conector GitHub; não alegar checkout local integral.

## Protocolo e fontes

`AGENTS.md`, TASKLIST, este checkpoint, PRD, DESIGN, ADR-001, ADR-002 e a documentação T-005 foram lidos na ref efetiva antes da escrita. `DOCUMENTATION_AND_CONTINUITY.md` canônico/aprovado não existe no caminho esperado desta ref (404); portanto nenhuma equivalência foi presumida. O repositório registra o último estado editorial como STAGING. As nove funções permanecem mapeadas, mas **ADOÇÃO PARCIAL**.

## Estado por ID

- **T-006 — PARCIAL, checkpoint validado offline:** o manifesto v2 continua entrando como `UNVERIFIED` e qualquer `VERIFIED` autodeclarado é rejeitado. O campo de transporte opcional `caption_verification` permite que a API local receba o texto SRT/VTT exato, confira `caption_sha256`, reexecute o parser e exija igualdade integral dos cues/IDs/texto/timestamps com a transcrição. Somente após essa recomputação o backend pode persistir `timeline_match_status=VERIFIED`.
- **Escopo desse VERIFIED:** corresponde apenas à igualdade **legenda submetida → transcrição importada**. `authorization_status` e `video_identity_status` permanecem `UNVERIFIED`; não há prova de que a legenda pertença ao vídeo declarado nem de sincronia com a mídia real. `deep_links_allowed=false` permanece invariável. [Guia](docs/T006_CAPTION_IMPORT.md).
- **T-005 — PARCIAL, recuperação offline ampliada:** API/worker/smoke recuperáveis; jobs ainda não RUNNING podem ser cancelados persistentemente sem alegar cancelamento remoto; schema de jobs recusa versões futuras, estruturas desconhecidas e banco corrompido antes de migrar. Backup usa `sqlite3.Connection.backup()` e publicação sem overwrite. Recovery inspeciona e fixa o snapshot por SHA-256, restaura somente para caminho novo, revalida integridade e emite `RecoveryReceipt` schema v1 com identidade e metadados SQLite. O receipt pode ser persistido em arquivo privado `0600`, sem overwrite, e carregado/verificado posteriormente sem seguir symlink; versões desconhecidas falham fechado. O CLI não faz cutover nem substitui o banco ativo. Não há política completa de disaster recovery/retention/rollback de cutover; job já RUNNING não é falsamente marcado como cancelado.
- **T-007 — PARCIAL:** somente `SECTIONS_ONLY`; síntese global/validação semântica ausentes.
- **T-010 — PARCIAL:** portas e seleção independentes testadas offline; Groq é apenas primeiro provedor, sem NIM/local operacional.
- **T-004 — bloqueio documental:** publicação/equivalência da fonte canônica aprovada pendente. T-003/T-008/T-009 também permanecem incompletas.

## Próxima ação concreta

T-006 continua bloqueada para promoção de `video_identity_status`, autorização e deep links porque ainda não existe critério independente verificável para a mídia real. O caminho de recovery staging de T-005 está comprovado offline até receipt persistente/versionado e verificação posterior; cutover automático, rollback/retention e cancelamento cooperativo de operação remota continuam fora do que foi comprovado. A próxima fatia segura deve permanecer offline; se T-006 exigir fonte/credencial/permissão externa, escolher uma pendência isolável de T-005/T-007 sem chamada paga nem mudança de escopo. Antes de escrever, recuperar novamente PR/HEAD e trabalho concorrente. Sem merge/deploy automático.
