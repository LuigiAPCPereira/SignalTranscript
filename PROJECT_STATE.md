# PROJECT_STATE — SignalTranscript / checkpoint

**Ref de trabalho:** `feat/t006-caption-import`, [PR #10](https://github.com/LuigiAPCPereira/SignalTranscript/pull/10) sobre PR #9, sem merge. **Tarefa ativa: [T-006](TASKLIST.md)** — importação de legenda local e evidência de integridade; não pipeline YouTube → biblioteca. [PRD](PRD.md) · [DESIGN](DESIGN.md) · [AGENTS](AGENTS.md) · [relatório de adoção](docs/ADOPTION_REPORT.md).

## Git e observações verificadas

- A branch desta fatia deriva do HEAD do PR #9 `b726344368b387f2e0e6cbd12a7e9d95bbdb8163`. PR #10 permanece Draft. Não foi realizado merge, deploy nem requisição Groq nesta fatia; revalidar `main` antes de integração futura. Trabalho remoto pelo conector GitHub, sem alegar checkout local completo.
- Implementação T-006 no commit `dd7a04464b594f68b47c1b9f08ec98542ef98355`: importação SRT/VTT preexistente + novo `caption_evidence.py` e `test_caption_evidence.py`. Os hashes Git blob dos dois arquivos novos publicados foram conferidos com a cópia local. [CI 35679355342](https://github.com/LuigiAPCPereira/SignalTranscript/actions/runs/35679355342) `completed/success` nessa revisão de código: jobs Python **3.12 e 3.13** aprovaram instalação, `compileall` e unittest; log 3.13 **124 testes PASS** (117+7). O aviso de depreciação Starlette/TestClient permanece na dependência. Atualizações documentais subsequentes requerem CI do HEAD documental final; não atribuir a execução anterior a outro commit.
- Produto decidido: generalista, Python + FastAPI e Groq como integração inicial, com portas de análise/transcrição independentes. SQLite existe para jobs/checkpoints; aquisição de vídeo, biblioteca, frontend e provedor alternativo operacional pendentes.

## Protocolo e fontes

`AGENTS.md` da ref #10 foi consultado; snapshot v2.2 de `DOCUMENTATION_AND_CONTINUITY.md` e ENGINEERING_DNA disponível no Project foi consultado, mas **a equivalência com versão canônica aprovada e acesso em outros ambientes não estão comprovados**. O último estado editorial Notion observado era STAGING; não o promover a APPROVED sem evidência nova. As nove funções documentais estão mapeadas no relatório, com a função de fonte canônica pendente: **ADOÇÃO PARCIAL**. Nenhuma autorização de merge/deploy inferida.

## Estado por ID

- **T-006 — PARCIAL, bloco atual:** `caption_import.py` lê arquivo permitido fornecido pelo usuário e cria JSON privado, tempos preservados mas não confirmados externamente. Novo `caption_evidence.py` cria/verifica **manifesto separado** com SHA-256 dos bytes da legenda e do JSON e reconversão estrita. Recusa mutação de fonte/JSON, manifesto com alegações de verificação inventadas, campos extras, symlinks e overwrite. `authorization_status`, `video_identity_status` e `timeline_match_status` ficam invariavelmente `UNVERIFIED`; `deep_links_allowed=false`. Hashes **não** provam origem/licença/sincronia, nem fornecem assinatura. [Guia](docs/T006_CAPTION_IMPORT.md). A API FastAPI, SQLite e smoke não preservam/verificam esse manifesto. Não foi testado vídeo real ou aquisição/áudio/Groq.
- **T-005 — PARCIAL:** API local, worker e smoke opt-in testados com fake, mas sem persistência de proveniência, cancelamento HTTP, backup/migrações e E2E. **T-007 — PARCIAL:** somente seções, sem síntese global/validação semântica. **T-010 — PARCIAL:** portas e seleção implementadas offline; outros provedores reais pendentes.
- **T-004 — bloqueada quanto ao gate documental:** publicação/equivalência de fonte aprovada pendente. **T-003/T-008/T-009:** validação Groq real com conteúdo autorizado, frontend/biblioteca e E2E pendentes.

**Próxima ação concreta vinculada a T-006:** conferir HEAD final e CI após documentação; então especificar e testar a passagem do manifesto pelo domínio/API/SQLite sem aceitar estados `VERIFIED` autodeclarados. Só criar links de tempo em etapa futura após critério verificável de identidade do vídeo e sincronia real. O usuário deve optar explicitamente por qualquer chamada Groq e manter chave apenas no próprio ambiente. Sem merge/deploy automático.
