# PROJECT_STATE — SignalTranscript / checkpoint

**Ref de trabalho:** `feat/t006-caption-import`, [PR #10](https://github.com/LuigiAPCPereira/SignalTranscript/pull/10) sobre PR #9, sem merge. **Tarefa ativa: [T-005](TASKLIST.md)** — runtime/persistência e recuperação segura; T-007 é a fatia associada de síntese e T-006 permanece bloqueada para identidade/autorização real da mídia. [PRD](PRD.md) · [DESIGN](DESIGN.md) · [AGENTS](AGENTS.md) · [relatório de adoção](docs/ADOPTION_REPORT.md).

## Git e validação

- PR #10 permanece Draft e empilhado. Nenhum merge/deploy foi autorizado nesta fatia e nenhuma chamada autenticada à Groq foi executada.
- A primeira revisão da verificação server-side (`a3c1f734087a8f31ed0c65238a2c37996320dec0`) falhou porque `caption_verification=None`, campo somente de transporte, entrou em serialização usada pelo smoke. A causa foi corrigida sem relaxar o contrato de proveniência.
- **Checkpoint T-006 validado:** SHA `a8b775ea7d10b3e834cafa0d50629d3cd264443e`, GitHub Actions 35884798012, `completed/success`, Python 3.12/3.13.
- **Checkpoint T-005 de recuperação validado:** SHA `ec627014fe5e038cc74e5fc8d09516dd3e62d26a`, GitHub Actions 35989071501, `completed/success`, Python 3.12/3.13. Inclui cancelamento conservador, schema de jobs versionado/fail-closed, snapshot SQLite WAL-safe, inspeção/pinning SHA-256, restore staging para caminho novo e `RecoveryReceipt` schema v1 persistente/verificável.
- Alterações documentais posteriores a esses SHAs exigem CI próprio no HEAD final antes de afirmar que a revisão final do PR está verde.
- O trabalho desta execução é remoto pelo conector GitHub; não alegar checkout local integral.

## Protocolo e fontes

`AGENTS.md`, TASKLIST, checkpoint, PRD, DESIGN, ROADMAP, SESSION_LOG e ADRs foram reconciliados. O protocolo v2.2 usado no ChatGPT Project teve SHA-256 `7e64d070e7ed419b225a92edb4a17ac4ff7d63f9c2bec22e35b47188d2639213`, exatamente o hash de origem registrado no manifesto central; Engineering DNA também coincidiu (`c19c5d97…a0e373`). [Fonte/pin](docs/PROTOCOL_SOURCE.md). As nove funções passam o Adoption Gate v2 nesta ref: **ADOÇÃO CONCLUÍDA NA BRANCH**. O índice Notion continua STAGING como estado de distribuição; `main`, Codex e operação agendada são dimensões separadas.

## Estado por ID

- **T-006 — PARCIAL, checkpoint validado offline:** o manifesto v2 continua entrando como `UNVERIFIED` e qualquer `VERIFIED` autodeclarado é rejeitado. O campo de transporte opcional `caption_verification` permite que a API local receba o texto SRT/VTT exato, confira `caption_sha256`, reexecute o parser e exija igualdade integral dos cues/IDs/texto/timestamps com a transcrição. Somente após essa recomputação o backend pode persistir `timeline_match_status=VERIFIED`.
- **Escopo desse VERIFIED:** corresponde apenas à igualdade **legenda submetida → transcrição importada**. `authorization_status` e `video_identity_status` permanecem `UNVERIFIED`; não há prova de que a legenda pertença ao vídeo declarado nem de sincronia com a mídia real. `deep_links_allowed=false` permanece invariável. [Guia](docs/T006_CAPTION_IMPORT.md).
- **T-005 — PARCIAL:** journal SQLite agora é schema v3 com `created_seq` monotônico persistido. Migração atribui sequência permanente aos jobs antigos; worker usa sequência crescente para FIFO e `GET /api/jobs?limit=&before=` usa ordem decrescente estável para UI. A lista expõe estado/proveniência e somente presença de seções/síntese, sem transcript text, sem validar/abrir artefatos e sem iniciar IA. SHA `c65353714f1204a164407a0130c9521ca91ceddc`, Actions 36257023821 PASS Python 3.12/3.13, **240 testes**.
- **T-007 — PARCIAL:** análise por seções, síntese global, checkpoint, adaptador Groq, consentimento e recuperação histórica estão validados offline. `POST` ainda exige provider atual explícito; `GET` lê resultado persistido independentemente da configuração viva e revalida fingerprint/evidências. Qualidade real, Groq autenticada e E2E continuam pendentes.
- **T-010 — PARCIAL:** STT, análise por seção e síntese global permanecem funções separadas. O runtime/smoke agora exige seleção e consentimento próprios para análise e síntese, sem fallback ou herança silenciosa, testados offline. Groq continua primeiro fornecedor implementado; NIM/local não são operacionais.
- **T-004 — VALIDADA NA REF DE TRABALHO:** Adoption Gate v2 concluído com nove funções verificadas e fonte v2.2 pinada por hash. O estado STAGING do Notion é Publication Gate central separado. `main` ainda não contém a adoção porque PR #10 permanece Draft.

## Próxima ação concreta

A listagem de jobs remove a dependência de IDs conhecidos manualmente e estabelece uma boundary read-only para futura T-008, mas ainda não existe biblioteca. A próxima fatia segura pode acrescentar **leitura da transcrição importada por job** com contrato explícito e sem deep links, preparando leitura/busca local; alternativamente, persistir entidade de vídeo/biblioteca exigiria desenho de schema maior e deve ser tratada como T-008 própria. Manter T-005 parcial até o conjunto de persistência/retomada exigido pelo MVP estar fechado. T-006 continua bloqueada para identidade/autorização real da mídia; não executar Groq real, merge ou deploy sem autorização.

**Operação separada:** o agendamento “SignalTranscript Dev Loop” permanece observado como desabilitado.
