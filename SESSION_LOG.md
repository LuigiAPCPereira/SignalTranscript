# SESSION_LOG — Histórico recuperável

## 2026-09-20 — Planejamento e primeira revisão documental

- O usuário definiu o produto generalista, escolheu Python + FastAPI e aceitou Whisper Large V3 Turbo pela Groq. GPT-OSS 120B, React/TS, SQLite, yt-dlp e worker foram discutidos como propostas, sem testes.
- Cinco rascunhos locais foram produzidos na conversa. Depois o usuário informou `https://github.com/LuigiAPCPereira/SignalTranscript`. Verificação remota: `main` em `e4fe22d6fee4120af33d9436f4b0e27864eb5df1` com apenas README original; worktree local não inspecionada.
- Branch documental `docs/mvp-architecture-v0.1`; commit final observado `11f893e5d2cb1cf1ef663b4d838f34cbc9152a2f`; PR #1 aberto como draft e não mesclado na consulta.
- A central do protocolo v2.2 no Notion foi reaberta e continuava STAGING, sem prova de equivalência à cópia do Project nem de acesso independente em Codex/agendamentos. ADOÇÃO PARCIAL.

## 2026-09-20 — Fatia offline do contrato de transcrição

- T-003: referência oficial da Groq confirma `whisper-large-v3-turbo`, `response_format=verbose_json` e timestamps de `segment`. Um comentário de exemplo apresenta inconsistência textual e não substitui a referência de parâmetros.
- Preparada normalização isolada em Python, sem SDK, rede ou segredos, com validação de segmento, ID determinístico por chunk/posição, timestamps em milissegundos e offset explícito. Oito testes `unittest` passaram no ambiente da sessão, e `compileall` terminou sem erros; execução no CI GitHub não verificada.
- Publicar em branch `feat/t003-groq-contract-offline`, separada do PR documental. Esta fatia **não** verifica contas, chamada real, limite de upload, algoritmo de sobreposição, qualidade da transcrição ou aplicativo completo.

**Checkpoint vinculado:** T-004 documental; T-003 parcial independente. Conferir [TASKLIST](TASKLIST.md), [PROJECT_STATE](PROJECT_STATE.md) e PRs/HEAD reais antes de trabalho posterior.
