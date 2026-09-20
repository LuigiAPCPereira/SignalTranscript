# PROJECT_STATE — SignalTranscript / checkpoint

**Observado em:** 2026-09-20. **Escopo:** MVP v0.1 em planejamento. **Autoridades locais:** [PRD](PRD.md), [DESIGN](DESIGN.md), [TASKLIST](TASKLIST.md), [ROADMAP](ROADMAP.md), [AGENTS](AGENTS.md).

## Git / integração

- Repo: https://github.com/LuigiAPCPereira/SignalTranscript; acesso de escrita via conector confirmado.
- Base `main` verificada: `e4fe22d6fee4120af33d9436f4b0e27864eb5df1`; só README original no inventário inicial.
- Branch `docs/mvp-architecture-v0.1`; primeiro commit documental reaberto `403a8b2d1e4e2f26e6a1af76e8031c53211ec240` (dez arquivos). [PR #1](https://github.com/LuigiAPCPereira/SignalTranscript/pull/1) aberto em modo draft, sem merge confirmado na consulta. Revalidar HEAD da branch após atualizações de documentos, evitando SHA autorreferencial.
- Worktree local Git: não inspecionada; o acesso verificado foi ao repositório remoto.

## Decisões e protocolo

- Confirmado pelo usuário: produto generalista, Python + FastAPI, Whisper Large V3 Turbo pela Groq. React/TS, SQLite, yt-dlp condicionado, GPT-OSS 120B e worker são propostas.
- Snapshot `DOCUMENTATION_AND_CONTINUITY.md` v2.2 lido no Project, mas índice central Notion v2.2 observado em STAGING em 20/09/2026. Fonte editorial aprovada e equivalência integral da cópia não demonstradas. Não presumir acesso via Codex ou execução agendada.
- [Relatório das nove funções](docs/ADOPTION_REPORT.md): **ADOÇÃO PARCIAL**, apesar de documentos criados e reabertos. `main` permanece sem integração dos docs até decisão posterior.

## Tarefa ativa, implementação e próxima ação

**T-004** ([TASKLIST](TASKLIST.md)): finalizar reconciliação da versão canônica do protocolo/Project e a revisão documental do PR. T-001 e T-002 têm documentação produzida, lida remotamente e sem teste de produto. T-003: contrato Groq precisa de áudio autorizado e limites de conta reais.

**Produto/testes:** nenhum backend/frontend criado; Groq/yt-dlp não testados na máquina; CI/E2E/deploy não executados. **Integração:** PR em draft, não mesclado na consulta. **Bloqueios:** protocolo aprovado não comprovado, permissões concretas de vídeo/cotas da conta ainda desconhecidas.

**Próximo bloco verificável:** reabrir os arquivos alterados desta revisão na ref final; conferir PR #1 e `main`, fonte aprovada do protocolo e comparação de versão/hashes quando possível. Não declarar adoção concluída com origem STAGING.
