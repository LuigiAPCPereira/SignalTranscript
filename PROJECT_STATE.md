# PROJECT_STATE — SignalTranscript / checkpoint

**Observado em:** 2026-09-20. **Escopo:** MVP v0.1, arquitetura em revisão e teste offline limitado. **Fontes:** [TASKLIST](TASKLIST.md), [PRD](PRD.md), [DESIGN](DESIGN.md), [AGENTS](AGENTS.md), [relatório documental](docs/ADOPTION_REPORT.md).

## Git e decisões

- Repositório: https://github.com/LuigiAPCPereira/SignalTranscript. Base `main` observada em `e4fe22d6fee4120af33d9436f4b0e27864eb5df1`.
- PR #1: branch `docs/mvp-architecture-v0.1`, HEAD observado `11f893e5d2cb1cf1ef663b4d838f34cbc9152a2f`, aberto em draft, sem merge na consulta.
- Fatia independente T-003: branch `feat/t003-groq-contract-offline`, derivada do PR #1; revalidar HEAD e PR após publicar. Não presumir integração com a `main` nem execução de CI remoto.
- Confirmado pelo usuário: produto generalista, Python + FastAPI e Whisper Large V3 Turbo via Groq. Demais partes da stack estão propostas.

## Protocolo e cobertura

O índice editorial do protocolo no Notion foi reaberto em 20/09/2026: v2.2 segue **STAGING**; a publicação integral, equivalência com a cópia do Project e acesso por Codex/agendamentos não foram comprovados. [Relatório](docs/ADOPTION_REPORT.md): ADOÇÃO PARCIAL, não concluída. Nenhuma worktree local do repositório foi inspecionada.

## Tarefas e evidências

- **T-004 (checkpoint principal):** revisão documental e origem canônica ainda pendentes. Não duplicar adoção nem promover STAGING.
- **T-003 (trabalho independente parcial):** validação offline de parâmetros, segmentos, timestamps e offset; 8 testes unitários passaram no ambiente da sessão. Sem chamada Groq real, cota da conta, teste de tamanho, sobreposição, FFmpeg, CI ou testes E2E.
- T-005–T-009: sem implementação, validação ou integração. A fatia de T-003 não prova o contrato de produção.

**Próxima ação:** revalidar o PR/HEAD da fatia e os arquivos publicados; manter T-004 bloqueada em sua parte editorial enquanto a release aprovada não estiver comprovada. Para concluir T-003, usar áudio autorizado e chave local, sem publicar credenciais, verificar resposta real, erros/limites e política de sobreposição.
