# ADR-002 — Independência de provedores de IA

**Estado:** decisão de produto aceita pelo usuário em 2026-09-20; implementação parcial. **Escopo:** SignalTranscript MVP e extensões futuras. **Tarefa:** T-010 no TASKLIST.

## Contexto
A Groq foi escolhida como integração inicial para transcrição (Whisper Large V3 Turbo) e proposta para análise (GPT-OSS 120B). O usuário determinou que o projeto não fique inteiramente dependente da Groq: futuramente deve poder usar um modelo local, NVIDIA NIM ou outro provedor. Não há autorização implícita para custos, troca automática de serviços ou envio de conteúdo a terceiros.

## Decisão
Separar as portas `TranscriptionProvider` e `AnalysisProvider`, com objetos de dados internos independentes de SDK/modelo/HTTP. A aplicação escolhe cada implementação **independentemente**, em um ponto único de composição, a partir de configuração validada. Falha de provedor é explícita; não fazer fallback, troca de cobrança ou envio a outro destino sem configuração/autorização. Legendas e transcrições importadas entram diretamente no contrato `Transcript` e não requerem STT. A proveniência real acompanha cada resultado.

## Consequências e limites
- Groq será um adaptador inicial, não a interface do domínio; todo conteúdo externo é validado e normalizado na borda.
- API, jobs, biblioteca e frontend consomem dados canônicos; não importam SDKs de provedores.
- Modelos locais e NVIDIA NIM são **extensões possíveis, não integrações existentes**. Cada adaptador futuro precisa de validação real de contrato, limites, segurança e qualidade, sem herdar suposições da Groq.
- Não construir framework de plugins, marketplace, abstração para recursos hipotéticos ou fallback automático no MVP.

**Evidência:** decisão explícita do usuário na conversa; implementação parcial em PR próprio T-010; [contrato](../T010_PROVIDER_BOUNDARY.md), [inventário](../../TASKLIST.md), [DESIGN](../../DESIGN.md). Não confundir testes com fakes com testes reais de API, modelos locais ou E2E.
