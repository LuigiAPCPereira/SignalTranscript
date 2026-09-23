# PROJECT_STATE — SignalTranscript / checkpoint

**Ref de trabalho:** `feat/t006-caption-import`, [PR #10](https://github.com/LuigiAPCPereira/SignalTranscript/pull/10) sobre PR #9, sem merge. **Tarefa ativa: [T-006](TASKLIST.md)** — importação/proveniência de legendas autorizadas; não pipeline YouTube → biblioteca. [PRD](PRD.md) · [DESIGN](DESIGN.md) · [AGENTS](AGENTS.md) · [relatório de adoção](docs/ADOPTION_REPORT.md).

## Git e validação

- PR #10 permanece Draft e empilhado. Nenhum merge/deploy foi autorizado nesta fatia e nenhuma chamada autenticada à Groq foi executada.
- Revisão funcional validada: `4d39b441094afece691854654829e18953e6c25f`. [GitHub Actions 35856877544](https://github.com/LuigiAPCPereira/SignalTranscript/actions/runs/35856877544) aprovou Python 3.12 e 3.13; log 3.13: **129 testes PASS**. Uma revisão anterior do novo smoke falhou por incluir o campo opcional `evidence=None` no hash canônico; a causa foi corrigida e revalidada.
- Commits documentais posteriores a essa revisão devem ter CI confirmado no HEAD final antes de usar “CI verde” como evidência do commit documental.
- O ambiente shell desta conversa não conseguiu resolver `github.com`; trabalho remoto foi feito pelo conector GitHub. Não alegar checkout local integral.

## Protocolo e fontes

`AGENTS.md` da ref exata foi consultado. O snapshot `DOCUMENTATION_AND_CONTINUITY.md` v2.2 disponível no Project também foi lido nesta sessão; ele exige que execuções agendadas não presumam acesso aos arquivos do Project ou memória de conversa. A equivalência Project↔fonte canônica aprovada continua não comprovada; o último estado editorial registrado era STAGING. As nove funções permanecem mapeadas, mas **ADOÇÃO PARCIAL**. Não inferir permissões de merge/deploy.

## Estado por ID

- **T-006 — PARCIAL, bloco atual:** `caption_evidence.py` usa manifesto v2 com SHA-256 da legenda/JSON e hash canônico do contrato de transcrição. `POST /api/jobs` aceita manifesto opcional, valida hash/ID/esquema e rejeita qualquer alegação `VERIFIED`; SQLite persiste `evidence_json` e migra bancos antigos adicionando a coluna. GET job/seções devolve estado seguro de proveniência; `deep_links_allowed=false` em todos os caminhos atuais. O smoke aceita `--evidence`, valida o sidecar antes de HTTP e confere que o backend não promove o estado. [Guia](docs/T006_CAPTION_IMPORT.md).
- **Limite T-006:** hashes demonstram integridade/correspondência da legenda local com o JSON e do manifesto com a transcrição enviada, mas **não** direitos, identidade real do vídeo ou sincronização. Não existe transição implementada de `UNVERIFIED` para `VERIFIED`; deep links permanecem proibidos. Aquisição, áudio/FFmpeg/chunks e STT real continuam pendentes.
- **T-005 — PARCIAL:** API/worker/smoke recuperáveis; proveniência manual agora persistida na fatia T-006. Cancelamento HTTP, backup/migrações gerais e E2E seguem pendentes.
- **T-007 — PARCIAL:** somente `SECTIONS_ONLY`; síntese global/validação semântica ausentes.
- **T-010 — PARCIAL:** portas e seleção independentes testadas offline; Groq é apenas primeiro provedor, sem NIM/local operacional.
- **T-004 — bloqueio documental:** publicação/equivalência da fonte canônica aprovada pendente. T-003/T-008/T-009 também permanecem incompletas.

## Próxima ação concreta

Por T-006, não promover proveniência por declaração. A próxima fatia deve ou (a) definir/testar um critério verificável de identidade e sincronia para uma fonte permitida, ou (b) escolher outra tarefa desbloqueada do TASKLIST se esse critério depender de acesso externo/humano. Qualquer execução agendada deve recuperar PRs/HEAD, ler `AGENTS.md`, `TASKLIST.md` e este checkpoint na ref efetiva, validar CI na revisão exata, preservar Draft PRs e parar em bloqueio real. Não presumir acesso aos arquivos do ChatGPT Project, segredos ou autorização para custos/merge/deploy.
