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


## 2026-09-29 — T-008 biblioteca local e busca textual

- T-008 iniciou com um `LibraryReadModel` derivado do journal para evitar duplicar transcripts em uma segunda fonte de verdade; FTS/materialização permanecem otimizações futuras dependentes de medição.
- `GET /api/library` agrupa versões persistidas por `video_id`, mantém o job mais recente como versão corrente e expõe `version_count`. `GET /api/library/search` faz busca substring case-insensitive apenas na versão corrente de cada vídeo e sinaliza `truncated` quando o limite é excedido.
- A primeira revisão `a382c317` falhou no teste de integração porque o texto do fixture ultrapassou o orçamento deliberadamente reduzido usado para forçar seções. O fixture foi encurtado sem alterar limites de produção. `3367ee1db04ee1147f1794bc2d22a0d862c8177b` passou Actions 36574287374 em Python 3.12/3.13 com 246 testes.
- Não há frontend, FTS, deep links, Groq real, merge ou deploy nesta fatia.


## 2026-09-29 — T-008 primeiro frontend local

- Após recuperar Frontend DNA, boundary de engenharia e dependências, foi escolhido um tracer sem dependências externas: HTML/CSS/ES modules servidos pelo próprio FastAPI. React/Vite foram avaliados como opções atuais, mas não adotados porque a primeira superfície não justificava build/lockfile/runtime adicional.
- A UI consome somente `/api/library`, `/api/library/search` e `/api/jobs/{id}/transcript`; não possui POST de IA. Visual Thesis: Operate→Read, tom calmo/editorial, dois painéis no desktop, composição empilhada no mobile, sem título/thumbnail inventados e sem deep links enquanto a proveniência não permitir.
- Commit inicial `ee2b7a22b458e85b15b53c2f382b32f60c52a91f` passou Actions 36581307388 em Python 3.12/3.13 com 248 testes.
- Render em Chromium com bytes da revisão e fixtures de fetch encontrou defeito real: regra `.reader-empty {display:grid}` sobrepunha o atributo `hidden`. O guardrail `[hidden]{display:none!important}` e teste foram instalados; `682c08427191117cc2528530c5f4626f3bf5e7d8` passou Actions 36582197169 com 248 testes.
- Render corrigido: desktop 1440×1000 (biblioteca, transcript, busca truncada) e mobile 390×844 (transcript), sem overflow horizontal. O Chromium do ambiente bloqueou localhost por política administrativa; portanto o render validou os assets/estados com fixtures, não E2E browser→FastAPI.


## 2026-09-29 — T-008 leitor de seções e síntese persistidas

- O primeiro frontend foi expandido sem adicionar endpoints de escrita: abas Transcrição, Seções e Síntese global usam apenas GET. O cliente exige `SECTIONS_ONLY` e `GLOBAL_SYNTHESIS` explicitamente e não contém `POST`.
- Seções mostram resumos locais, ideias e referências, com aviso de que não são síntese global. A síntese mostra resumo global, ideias e cobertura de evidências, com aviso de que não é verificação factual independente. Síntese ausente (404) é estado normal e não dispara geração.
- Commit funcional `a8225c6a393a24a4c96fd09ad1a6cfa8bc27b8c9` passou Actions 36609696964 em Python 3.12/3.13 com 248 testes.
- Render representativo com CSS exato da revisão: seções desktop 1440×1000, síntese desktop 1440×1000 e síntese mobile 390×844; sem overflow horizontal. A política administrativa do Chromium bloqueia navegação local, então o render valida estrutura/CSS, não E2E browser→FastAPI.
