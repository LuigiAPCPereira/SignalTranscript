# SignalTranscript

Ferramenta **generalista** para transformar vídeos em conhecimento consultável sem exigir assistir a cada vídeo. Uma fonte válida (URL do YouTube quando acessível e permitida, transcrição importada ou áudio autorizado) deverá originar transcrição, síntese estruturada, referências à origem e biblioteca pessoal.

**Estado real:** MVP v0.1 em implementação parcial na pilha de PRs *draft*. A branch do PR #10 já contém FastAPI/SQLite, jobs recuperáveis, análise longa por seções, síntese global explícita/checkpointada, adaptadores Groq STT/análise/síntese validados offline, importação SRT/WebVTT com proveniência e smoke com consentimento separado. **Groq autenticada, aquisição de vídeo/áudio real, frontend, E2E, merge e deploy não foram validados.** A `main` ainda não incorpora essas funcionalidades. Um resumo representa o que a fonte diz, sem verificação independente dos fatos.

## Decisões e propostas

- **Decidido pelo usuário:** produto generalista; backend Python + FastAPI; Groq como primeira opção de transcrição, mas nunca dependência obrigatória. Transcrição e análise têm portas separadas e provedores escolhidos explicitamente.
- **Arquitetura parcialmente implementada:** SQLite para jobs e checkpoints, worker local, adaptadores Groq STT/análise testados offline. GPT-OSS 120B é o modelo registrado de análise Groq, sem execução remota autenticada. NVIDIA NIM/modelos locais não integrados.
- **Propostas não concluídas:** React + TypeScript, yt-dlp/FFmpeg como adaptadores condicionados a aquisição permitida, biblioteca pesquisável, síntese global. Cotas específicas da conta e permissões sobre vídeos concretos não foram verificadas.

## Documentação e execução

- [PRD/aceites](PRD.md) · [DESIGN/contratos](DESIGN.md) · [TASKLIST](TASKLIST.md) · [ROADMAP](ROADMAP.md) · [Checkpoint](PROJECT_STATE.md).
- [Instruções dos agentes](AGENTS.md) · [Decisões](docs/adr/ADR-001-python-fastapi.md) · [Histórico](SESSION_LOG.md) · [Cobertura documental](docs/ADOPTION_REPORT.md).
- [API local](docs/T005_LOCAL_JOB_API.md) · [Composição e instruções de execução opt-in](docs/T005_LOCAL_RUNTIME.md). Esses documentos descrevem a branch proposta, **não a `main`**.

**Agent Development Protocol:** adoção v2.2 do SignalTranscript está **CONCLUÍDA na ref de trabalho** pelo Adoption Gate documentado em [docs/ADOPTION_REPORT.md](docs/ADOPTION_REPORT.md), com fonte/hash registrados em [docs/PROTOCOL_SOURCE.md](docs/PROTOCOL_SOURCE.md). A distribuição central Notion continua **STAGING** e a `main` não está integrada; esses estados são separados. Não presumir acesso aos arquivos do Project em Codex ou tarefas agendadas.
