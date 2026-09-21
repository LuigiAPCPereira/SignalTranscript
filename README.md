# SignalTranscript

Ferramenta **generalista** para transformar vídeos em conhecimento consultável sem exigir assistir a cada vídeo. Uma fonte válida (URL do YouTube quando acessível e permitida, transcrição importada ou áudio autorizado) deverá originar transcrição, síntese estruturada, referências à origem e biblioteca pessoal.

**Estado real:** MVP v0.1 em implementação parcial, apenas nas branches dos PRs em *draft*. O backend já possui uma fatia HTTP/SQLite para analisar **transcrições importadas por seções** com testes offline e provedor simulado. O PR #8 acrescenta composição de Groq opt-in e executável local; **Groq autenticada, vídeo real, aquisição, síntese global, interface, E2E, merge e deploy não foram validados**. A `main` não incorpora essas funcionalidades. Um resumo representa o que a fonte diz, sem verificação independente dos fatos.

## Decisões e propostas

- **Decidido pelo usuário:** produto generalista; backend Python + FastAPI; Groq como primeira opção de transcrição, mas nunca dependência obrigatória. Transcrição e análise têm portas separadas e provedores escolhidos explicitamente.
- **Arquitetura parcialmente implementada:** SQLite para jobs e checkpoints, worker local, adaptadores Groq STT/análise testados offline. GPT-OSS 120B é o modelo registrado de análise Groq, sem execução remota autenticada. NVIDIA NIM/modelos locais não integrados.
- **Propostas não concluídas:** React + TypeScript, yt-dlp/FFmpeg como adaptadores condicionados a aquisição permitida, biblioteca pesquisável, síntese global. Cotas específicas da conta e permissões sobre vídeos concretos não foram verificadas.

## Documentação e execução

- [PRD/aceites](PRD.md) · [DESIGN/contratos](DESIGN.md) · [TASKLIST](TASKLIST.md) · [ROADMAP](ROADMAP.md) · [Checkpoint](PROJECT_STATE.md).
- [Instruções dos agentes](AGENTS.md) · [Decisões](docs/adr/ADR-001-python-fastapi.md) · [Histórico](SESSION_LOG.md) · [Cobertura documental](docs/ADOPTION_REPORT.md).
- [API local](docs/T005_LOCAL_JOB_API.md) · [Composição e instruções de execução opt-in](docs/T005_LOCAL_RUNTIME.md). Esses documentos descrevem a branch proposta, **não a `main`**.

O Agent Development Protocol v2.2 disponível no Project é um snapshot; seu índice de distribuição no Notion permanece **STAGING** na consulta desta etapa, sem equivalência integral certificada. A adoção é PARCIAL; não presumir acesso ao Project em Codex ou tarefas agendadas.
