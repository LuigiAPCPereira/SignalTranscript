# SignalTranscript

Ferramenta **generalista** para transformar vídeos em conhecimento consultável sem exigir assistir a cada vídeo. Uma fonte válida (URL do YouTube quando acessível e permitida, transcrição importada ou áudio autorizado) origina transcrição, síntese estruturada, referências à origem e biblioteca pessoal.

**Estado:** planejamento do MVP v0.1; nenhuma aplicação implementada, testada ou publicada. A aquisição automática não é garantida para qualquer vídeo. Um resumo representa o que o vídeo diz; não equivale a verificação independente dos fatos.

## Decisões e propostas

- **Decidido pelo usuário:** backend Python + FastAPI; Whisper Large V3 Turbo via Groq para transcrição; produto generalista.
- **Propostas de arquitetura ainda sujeitas a validação:** frontend React + TypeScript, yt-dlp/FFmpeg como adaptadores de aquisição permitida, GPT-OSS 120B via Groq para análise, SQLite e worker persistente local. As cotas específicas da conta e a autorização de conteúdos concretos não foram verificadas.

## Documentação do produto

- [PRD e critérios de aceite](PRD.md) · [DESIGN e contratos](DESIGN.md) · [Tarefas](TASKLIST.md) · [Marcos](ROADMAP.md).
- [Decisão aceita de backend](docs/adr/ADR-001-python-fastapi.md) · [Histórico](SESSION_LOG.md) · [Checkpoint](PROJECT_STATE.md) · [Instruções dos agentes](AGENTS.md) · [Cobertura documental](docs/ADOPTION_REPORT.md).

A versão de referência do Agent Development Protocol fornecida no Project é snapshot v2.2. Seu índice de distribuição Notion foi observado em **STAGING** em 20/09/2026, sem equivalência integral certificada; não tratar a v2.2 como release canônica aprovada nem presumir acesso a arquivos do Project em Codex ou tarefas agendadas.
