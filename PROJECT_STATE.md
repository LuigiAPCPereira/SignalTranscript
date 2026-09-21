# PROJECT_STATE — SignalTranscript / checkpoint

**Observado em:** 2026-09-20. **Escopo:** MVP v0.1, contratos e adaptadores offline; sem aplicativo funcional ponta a ponta. **Fontes:** [TASKLIST](TASKLIST.md), [PRD](PRD.md), [DESIGN](DESIGN.md), [AGENTS](AGENTS.md), [relatório de adoção](docs/ADOPTION_REPORT.md).

## Git e decisões

- Repositório: https://github.com/LuigiAPCPereira/SignalTranscript. `main` observada anteriormente no commit inicial `e4fe22d6fee4120af33d9436f4b0e27864eb5df1`; revalidar antes de merge.
- PRs empilhados: [#1 documentação](https://github.com/LuigiAPCPereira/SignalTranscript/pull/1) -> [#2 portas/contrato](https://github.com/LuigiAPCPereira/SignalTranscript/pull/2) -> [#3 Groq STT](https://github.com/LuigiAPCPereira/SignalTranscript/pull/3) -> [#4 Groq análise](https://github.com/LuigiAPCPereira/SignalTranscript/pull/4). #4 observado aberto, draft e não mesclado; branch `feat/t010-groq-analysis-adapter`, base `feat/t003-groq-stt-adapter`. Consultar HEAD final do GitHub, nunca inferi-lo deste checkpoint autorreferencial.
- Decidido pelo usuário: produto generalista, backend Python + FastAPI, Whisper Turbo/Groq como primeiro serviço e independência de provedores de transcrição e análise. GPT-OSS 120B possui adaptador técnico offline, mas operação real não verificada. NIM e modelos locais não estão integrados.

## Protocolo

Índice central Notion v2.2 observado STAGING; release editorial APPROVED/PUBLISHED, equivalência do snapshot Project e acessibilidade em Codex/agendamentos **não certificadas**. [Relatório](docs/ADOPTION_REPORT.md): **ADOÇÃO PARCIAL**. Inspeção de GitHub via conector, não de worktree local autenticada.

## Tarefas, evidências e bloqueios

- **T-004 (documental):** nove funções mapeadas, aprovação/equivalência da fonte canônica e merge pendentes.
- **T-003 (parcial):** normalizador e adaptador STT com validação offline; nenhuma chamada autenticada Groq, áudio real, tamanho/cota efetiva ou chunk overlap. A suíte que os cobre passou no CI do PR #4, mas não valida seu contrato remoto.
- **T-010 (parcial):** portas neutras, seleção independente sem fallback, adaptadores Groq STT/análise e classificador compartilhado de erros. No commit `0892000003a69fdb6ff4d6047b784ab1ad11aeef`, [GitHub Actions run 35548079915](https://github.com/LuigiAPCPereira/SignalTranscript/actions/runs/35548079915) concluiu **success** nos jobs Python 3.12/3.13, incluindo `compileall` e a suíte offline (47 testes declarados na revisão). Workflow `.github/workflows/offline-contracts.yml` foi reaberto após publicação. Documentos deste checkpoint vieram depois desse commit: revalidar CI no HEAD final antes de qualquer integração.
- **T-007:** adaptador de análise não substitui pipeline: faltam chunks de vídeos longos, consolidação, versões/persistência e validação semântica/referências em conteúdo real.
- **T-005/T-006/T-008/T-009:** aplicação, aquisição, jobs, interface e E2E continuam pendentes. Nenhum SDK instalado ou chave/API real validada nesta etapa.

**Próxima ação por ID:** verificar o CI no HEAD mais recente de #4 e preservar a evidência; para T-010/T-003, testar SDK e endpoints Groq somente em ambiente seguro com conteúdo autorizado e chave configurada localmente. T-007 depende de implementar pipeline de chunks, não de repetir experimentos isolados. T-004 continua com bloqueio editorial. Não fazer merge/deploy automaticamente.
