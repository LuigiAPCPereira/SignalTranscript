# SESSION_LOG — Histórico recuperável

## 2026-09-20 — Planejamento e primeira revisão documental

- O usuário definiu o produto generalista, escolheu Python + FastAPI e aceitou Whisper Large V3 Turbo pela Groq. GPT-OSS 120B, React/TS, SQLite, yt-dlp e worker foram discutidos como propostas, sem testes.
- Cinco rascunhos locais foram produzidos na conversa. Depois o usuário informou `https://github.com/LuigiAPCPereira/SignalTranscript`. Verificação remota inicial: `main` em `e4fe22d6fee4120af33d9436f4b0e27864eb5df1` com apenas README original; worktree local não inspecionada.
- Branch documental `docs/mvp-architecture-v0.1`; HEAD observado `11f893e5d2cb1cf1ef663b4d838f34cbc9152a2f`; PR #1 aberto como draft e não mesclado na consulta.
- A central do protocolo v2.2 no Notion foi reaberta e continuava STAGING, sem prova de equivalência à cópia do Project nem de acesso independente em Codex/agendamentos. ADOÇÃO PARCIAL.

## 2026-09-20 — Fatia offline do contrato de transcrição

- T-003: referência oficial da Groq confirma `whisper-large-v3-turbo`, `response_format=verbose_json` e timestamps de `segment`. Um comentário de exemplo apresenta inconsistência textual e não substitui a referência de parâmetros.
- Normalizador isolado em Python, sem SDK, rede ou segredos, valida segmento, ID determinístico por chunk/posição, timestamps em milissegundos e offset explícito. Oito testes `unittest` passaram no ambiente da sessão anterior, e `compileall` terminou sem erros; execução no CI GitHub não verificada.
- Publicada a branch `feat/t003-groq-contract-offline` e aberto [PR #2](https://github.com/LuigiAPCPereira/SignalTranscript/pull/2) em draft, empilhado no PR #1. T-003 não verifica contas, chamada real, limite de upload, sobreposição ou aplicativo completo.

## 2026-09-20 — Independência de provedores (T-010)

- O usuário determinou que a Groq não seja dependência permanente e que transcrição e análise possam escolher provedores diferentes, inclusive locais no futuro. [ADR-002](docs/adr/ADR-002-provider-independence.md) registra a decisão; REQ-013 e T-010 registram aceites e dependências.
- Na branch do PR #2, acrescentados os protocolos Python `TranscriptionProvider`/`AnalysisProvider`, dados canônicos, seleção independente sem fallback e validação estrutural de referências. Nove testes novos passaram no diretório isolado desta sessão após corrigir um erro no teste inicial; `compileall` passou. Testes usam implementações simuladas, não NIM/local/Groq de verdade.
- Tentativa de `git clone` para executar a suíte inteira sobre a revisão remota falhou por resolução de DNS do GitHub no ambiente. Arquivos são verificáveis pelo conector; CI, integração remota, E2E e faturamento seguem sem teste.
- A decisão arquitetural adicionou uma fatia pequena ao PR #2 existente; não foi criado outro PR, e a `main` não foi alterada por essas operações.

## 2026-09-20 — Adaptadores Groq STT e análise (T-003/T-010 parciais)

- [PR #3](https://github.com/LuigiAPCPereira/SignalTranscript/pull/3) publicou `GroqTranscriptionAdapter` isolado, injeção de `AsyncGroq`, sem retries automáticos e classificação de erros; 31 testes locais passaram na cópia correspondente, sem chamada Groq real.
- A pesquisa oficial confirmou suporte do GPT-OSS 120B a JSON Schema estrito, exigindo campos obrigatórios/objetos fechados e sem streaming/tools; documentação publica 8K TPM gratuito, não comprovado para esta conta. A partir do HEAD do PR #3 `8bec26d4`, criada branch `feat/t010-groq-analysis-adapter`.
- Foi criado `GroqAnalysisAdapter` atrás da porta neutra, com entrada limitada sem truncamento, prompt que trata transcrição como dados, resposta fechada e validação de IDs. Mapeamento de erro Groq compartilhado com o STT. A cópia local de arquivos correspondentes passou 47 testes (16 novos) e `compileall`. Os arquivos tocados foram publicados via GitHub e devem ter SHA/PR final revalidados.
- Limites: nenhum SDK instalado na verificação, requisição real, CI, modelo local/NIM, chunking de vídeo longo, verificação de aderência semântica, persistência ou E2E. A análise inicial produz resumo sem referências próprias e ideias com referências de segmentos; isso não comprova a veracidade de qualquer alegação.

**Checkpoint vinculado:** T-004 documental, T-010 técnico e T-003 parcial. Conferir [TASKLIST](TASKLIST.md), [PROJECT_STATE](PROJECT_STATE.md) e PRs/HEAD atuais antes de continuar. Nenhum merge/deploy foi realizado nesta fatia.


## 2026-09-26 — Runtime de síntese recuperável e Adoption Gate v2

- T-005/T-007: análise por seções e síntese global passaram a exigir consentimentos separados no smoke; adaptador Groq de síntese permanece função independente e opt-in. A síntese possui checkpoint SQLite e agora também leitura `GET /api/jobs/{id}/synthesis` que não chama IA nem cria a tabela quando nenhum resultado existe.
- A primeira revisão do GET (`488e31df`) compilou, mas o CI falhou em um teste porque o mock não interceptava um default de função capturado no import. A injeção foi corrigida em `e6c159777f12c8f51a9ee085c07e5e1b062ba8a6`; Actions 36255131808 passou Python 3.12/3.13 com 234 testes.
- Adoption Gate v2 reaplicado em modo Aplicar por solicitação explícita do usuário. O SHA-256 do `DOCUMENTATION_AND_CONTINUITY.md` do Project (`7e64d070...39213`) e do `ENGINEERING_DNA.md` (`c19c5d97...a0e373`) coincidem exatamente com os hashes de origem registrados no manifesto central v2.2.
- Corrigida a interpretação anterior que tratava o estado editorial Notion STAGING como bloqueio automático da adoção do projeto. O protocolo v2.2 separa distribuição/publicação central, adoção por projeto e operação integrada. A distribuição central segue STAGING; o Adoption Gate do SignalTranscript passa na ref de trabalho após reconciliação das nove funções.
- A `main` continua não integrada; PR #10 permanece Draft. O loop agendado SignalTranscript foi observado desabilitado e não foi reativado nem alterado.
