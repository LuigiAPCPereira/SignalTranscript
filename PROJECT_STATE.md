# PROJECT_STATE — SignalTranscript / checkpoint

**Ref de trabalho:** `feat/t006-caption-import`, [PR #10](https://github.com/LuigiAPCPereira/SignalTranscript/pull/10) sobre PR #9, sem merge. **Tarefa ativa: [T-008](TASKLIST.md)** — biblioteca local, busca e futura experiência de leitura; T-005/T-007 fornecem as boundaries read-only já validadas e T-006 permanece bloqueada para identidade/autorização real da mídia. [PRD](PRD.md) · [DESIGN](DESIGN.md) · [AGENTS](AGENTS.md) · [relatório de adoção](docs/ADOPTION_REPORT.md).

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
- **T-005 — PARCIAL:** além do journal v3/listagem, `GET /api/jobs/{id}/transcript` devolve o `Transcript` canônico já persistido e a mesma proveniência do job. O endpoint não inicia IA, funciona independentemente do estado do job e não promove `deep_links_allowed`; a listagem sinaliza `transcript_present=true`. SHA `5b3bb0958a654ff83168bf85c4c8f814141c3bdc`, Actions 36432546089 PASS Python 3.12/3.13, **241 testes**.
- **T-007 — PARCIAL:** análise por seções, síntese global, checkpoint, adaptador Groq, consentimento e recuperação histórica estão validados offline. `POST` ainda exige provider atual explícito; `GET` lê resultado persistido independentemente da configuração viva e revalida fingerprint/evidências. Qualidade real, Groq autenticada e E2E continuam pendentes.
- **T-008 — PARCIAL:** biblioteca/search + frontend local agora lê transcript, análise por seções e síntese global já persistidos. As abas usam somente GET e exigem `SECTIONS_ONLY` para seções e `GLOBAL_SYNTHESIS` para síntese; 404 de síntese é estado normal, nunca gatilho para geração. O módulo cliente não contém POST. SHA `a8225c6a393a24a4c96fd09ad1a6cfa8bc27b8c9`, Actions 36609696964 PASS Python 3.12/3.13, **248 testes**. Render representativo desktop/mobile não apresentou overflow horizontal; continua não sendo E2E browser→FastAPI devido ao bloqueio administrativo de navegação local.
- **T-010 — PARCIAL:** STT, análise por seção e síntese global permanecem funções separadas. O runtime/smoke agora exige seleção e consentimento próprios para análise e síntese, sem fallback ou herança silenciosa, testados offline. Groq continua primeiro fornecedor implementado; NIM/local não são operacionais.
- **T-004 — VALIDADA NA REF DE TRABALHO:** Adoption Gate v2 concluído com nove funções verificadas e fonte v2.2 pinada por hash. O estado STAGING do Notion é Publication Gate central separado. `main` ainda não contém a adoção porque PR #10 permanece Draft.

## Próxima ação concreta

O leitor já distingue e apresenta transcript, `SECTIONS_ONLY` e `GLOBAL_SYNTHESIS` persistidos sem qualquer POST. A próxima fatia segura de T-008 é tornar a **disponibilidade de artefatos explícita no leitor**, inclusive quando a seleção vem de `/api/library/search`, para que abas indisponíveis possam ser anunciadas/disabled sem depender de um GET que retorne 404.

Manter a regra: disponibilidade é read-only e não pode iniciar geração. Depois dessa boundary, reavaliar o frontier entre continuar UX local em T-008 e avançar T-009 dentro do que não dependa da identidade real da mídia. T-006 continua bloqueada para identidade/autorização do vídeo. Não executar Groq real, merge ou deploy sem autorização.

**Operação separada:** o agendamento “SignalTranscript Dev Loop” permanece observado como desabilitado.
