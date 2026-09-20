# ADR-001 — Backend Python + FastAPI

**Estado:** aceita pelo usuário na conversa de 20/09/2026. **Escopo:** MVP SignalTranscript. **Decisão:** Python + FastAPI para o backend. Não confundir com aprovação independente de toda a stack.

## Contexto e alternativas de fato discutidas

Considerados Python/FastAPI, Node.js/TypeScript e Go. O serviço integra aquisição de conteúdo, áudio e APIs remotas. Python permite API de biblioteca para yt-dlp e amplo ecossistema de áudio e modelos locais; Node oferece linguagem única com frontend; Go oferece backend compilado e concorrência nativa. Desempenho da transcrição remota não depende diretamente da linguagem do backend.

## Consequências

Backend Python + FastAPI é decisão documentada; frontend React + TS, armazenamento SQLite, Groq GPT-OSS 120B, yt-dlp condicionado e worker persistente permanecem propostas. Integração por bibliotecas requer fixar versões e adaptar mudanças de terceiros. Não criar serviço Go/Node paralelo sem necessidade demonstrada.

**Evidência:** decisão expressa pelo usuário na conversa do projeto em 20/09/2026; vinculada à identidade em [README](../../README.md), aos requisitos em [PRD](../../PRD.md) e ao [DESIGN](../../DESIGN.md). Não há commit ou PR anteriores de produto que a validem operacionalmente.
