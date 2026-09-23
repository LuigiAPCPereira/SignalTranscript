# PROJECT_STATE — SignalTranscript / checkpoint

**Ref de trabalho:** `feat/t006-caption-import`, [PR #10](https://github.com/LuigiAPCPereira/SignalTranscript/pull/10) sobre PR #9, sem merge. **Tarefa ativa: [T-006](TASKLIST.md)** — importação/proveniência de legendas autorizadas; não pipeline YouTube → biblioteca. [PRD](PRD.md) · [DESIGN](DESIGN.md) · [AGENTS](AGENTS.md) · [relatório de adoção](docs/ADOPTION_REPORT.md).

## Git e validação

- PR #10 permanece Draft e empilhado. Nenhum merge/deploy foi autorizado nesta fatia e nenhuma chamada autenticada à Groq foi executada.
- Último HEAD verde anterior à fatia atual: `ea103b08617726cd74130dfe755fbb7d53821938`, Actions 35857122357, Python 3.12/3.13 e 129 testes PASS.
- A primeira revisão da nova fatia (`a3c1f734087a8f31ed0c65238a2c37996320dec0`) falhou em ambos os jobs porque `caption_verification=None`, novo campo somente de transporte, entrou em um `model_dump()` usado pelo teste do smoke para o hash canônico. O log confirmou os demais testes existentes até esse ponto; a causa foi corrigida em `91e2d6388e65ace1f7f0fa7f2f1dab8ddfa1820a` marcando o campo como excluído da serialização canônica. **Ainda não usar a nova fatia como validada até CI verde no HEAD final.**
- O trabalho desta execução foi remoto pelo conector GitHub; não alegar checkout local integral.

## Protocolo e fontes

`AGENTS.md`, TASKLIST, este checkpoint, PRD, DESIGN, ADR-001, ADR-002 e a documentação T-006 foram lidos na ref efetiva antes da escrita. `DOCUMENTATION_AND_CONTINUITY.md` canônico/aprovado não esteve acessível nesta execução; portanto nenhuma equivalência foi presumida. O repositório registra o último estado editorial como STAGING. As nove funções permanecem mapeadas, mas **ADOÇÃO PARCIAL**.

## Estado por ID

- **T-006 — PARCIAL, candidato atual:** o manifesto v2 continua entrando como `UNVERIFIED` e qualquer `VERIFIED` autodeclarado é rejeitado. Um novo campo de transporte opcional `caption_verification` permite que a API local receba o texto SRT/VTT exato, confira `caption_sha256`, reexecute o parser e exija igualdade integral dos cues/IDs/texto/timestamps com a transcrição. Somente após essa recomputação o backend pode persistir `timeline_match_status=VERIFIED`.
- **Escopo desse VERIFIED:** corresponde apenas à igualdade **legenda submetida → transcrição importada**. `authorization_status` e `video_identity_status` permanecem `UNVERIFIED`; não há prova de que a legenda pertença ao vídeo declarado nem de sincronia com a mídia real. `deep_links_allowed=false` permanece invariável. [Guia](docs/T006_CAPTION_IMPORT.md).
- Testes novos em `tests/test_caption_timeline_verification.py` cobrem recomputação, adulteração, rejeição de alegação autodeclarada, persistência e proibição de deep links. CI do HEAD final ainda é gate.
- **T-005 — PARCIAL:** API/worker/smoke recuperáveis; cancelamento HTTP, backup/migrações gerais e E2E seguem pendentes.
- **T-007 — PARCIAL:** somente `SECTIONS_ONLY`; síntese global/validação semântica ausentes.
- **T-010 — PARCIAL:** portas e seleção independentes testadas offline; Groq é apenas primeiro provedor, sem NIM/local operacional.
- **T-004 — bloqueio documental:** publicação/equivalência da fonte canônica aprovada pendente. T-003/T-008/T-009 também permanecem incompletas.

## Próxima ação concreta

Primeiro, recuperar o HEAD efetivo e exigir GitHub Actions verde **nessa revisão exata**; se falhar, ler o log e corrigir somente regressões da fatia. Depois, ainda em T-006, não promover `video_identity_status`, autorização nem deep links sem um critério independente verificável para a mídia real. Se isso exigir fonte/credencial/permissão externa, escolher outra fatia desbloqueada em vez de inventar verificação. Sem merge/deploy automático.
