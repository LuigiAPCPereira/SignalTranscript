# DESIGN — SignalTranscript v0.1

**Estado:** proposta de arquitetura, não implementação. **Decidido:** backend Python + FastAPI; Groq Whisper Large V3 Turbo. **Proposto:** React/TypeScript, SQLite, yt-dlp/FFmpeg, GPT-OSS 120B, worker local. [Requisitos](PRD.md) · [Tarefas](TASKLIST.md) · [ADR backend](docs/adr/ADR-001-python-fastapi.md).

## Topologia e fronteiras

```text
React/TypeScript [proposto] --HTTP localhost--> FastAPI [decidido]
                                                 |
                                    orquestração / jobs
                            _________|__________|__________
                           |         |          |          |
                      aquisição  transcrição  análise    biblioteca
                       yt-dlp     Groq ASR    Groq LLM     SQLite
                       FFmpeg     [decidido] [proposto] [proposto]
```

Monólito modular: domínio e contratos não importam FastAPI, yt_dlp, Groq ou banco; adaptadores implementam portas e o ponto de composição injeta dependências. A API nunca guarda segredos no frontend ou bloqueia requisições durante o processamento. Um worker com estado persistido substitui jobs apenas em memória. Não criar microserviços, Redis ou Celery sem necessidade medida.

## Aquisição — contrato T-002 proposto

`inspect(video_id) -> VideoMetadata + AvailableSources`; `acquire_transcript(source) -> TranscriptArtifact`; `acquire_audio(source) -> AudioArtifact`. Normalizar somente formatos e hosts do YouTube permitidos, extrair identificador canônico sem aceitar URLs remotas genéricas e rejeitar playlist/short link malformado ou redirecionamento para host não permitido. URL sozinha não é autorização de download. Não importar cookies automaticamente nem contornar bloqueios; validar tamanho/duração/armazenamento e limitar concorrência.

Seleção: (1) reutilizar transcrição íntegra já persistida e correspondente à trilha/idioma; (2) procurar legenda utilizável acessível por meio permitido, priorizando a língua original correspondente ao áudio e preservando se é manual/automática; (3) obter áudio **somente se permitido e autorizado**, preparar com FFmpeg e enviar à Groq; (4) se não houver fonte, registrar `WAITING_SOURCE` e aceitar arquivo ou texto fornecido pelo usuário. Nenhum caminho garante vídeo arbitrário.

Guardar proveniência `platform`, `canonical_video_id`, `source_kind` (manual_caption, auto_caption, authorized_audio, manual_import), `source_language`, `track_id` se conhecido, `retrieved_at`, `timebase`, `artifact_hash` quando possível e informações de autorização observáveis sem fabricar comprovação jurídica. Não confundir tradução com áudio original. Se uma fonte muda, não reutilizar cache incompatível.

Erros classificados: `INVALID_INPUT`/`UNSUPPORTED_URL` (sem retry), `NOT_FOUND`/`ACCESS_DENIED`/`SOURCE_UNAVAILABLE` (exibir importação), `AUDIO_NOT_AUTHORIZED` (não baixar), `TEMPORARY_FAILURE` (retry limitado), `RATE_LIMITED` (respeitar retry-after), `ARTIFACT_INVALID` (não reutilizar), `CANCELLED`. Nunca transformar erro de aquisição em transcrição vazia marcada como êxito.

## Transcript v1

```json
{
  "schema_version": 1,
  "video_id": "v1",
  "source": {"kind": "manual_caption", "language": "pt-BR", "track_id": null},
  "segments": [{"id": "s1", "start_ms": 12000, "end_ms": 18500, "text": "Exemplo ilustrativo."}]
}
```

Segmentos têm IDs estáveis, texto não vazio, começo/fim em inteiros não negativos com fim > começo quando conhecidos; ambos `null` se não houver timestamps. Preservar texto e idioma/origem originais. Áudio dividido: converter tempo relativo de cada chunk para tempo absoluto, gerir sobreposição sem apagar fala na fronteira, validar ordenação e intervalos. Documentação Groq indica limite grátis de 25 MB/upload, mas parâmetros exatos e limites reais exigem teste de contrato com áudio autorizado (T-003).

## Analysis v1

```json
{
  "schema_version": 1,
  "transcript_id": "tr1",
  "summary": "Síntese atribuída ao conteúdo.",
  "ideas": [{"id": "i1", "title": "Uma ideia", "explanation": "O autor afirma...", "source_segment_ids": ["s1"], "externally_verified": false}],
  "actions": [],
  "limitations": ["Não verificado externamente."]
}
```

Extrair ideias em blocos com sobreposição e IDs preservados, consolidar sem excluir menções únicas relevantes e produzir síntese referenciada. Não inventar ação prática quando `actions=[]` é adequado. Referências precisam pertencer à transcrição da análise; ausência de prova semântica não equivale a verificação factual. Validar schema estrito + IDs/semântica quando possível; só o código, e não o LLM, decide se existem segmentos. Registrar modelo, provedor, versão do prompt/schema e versão da análise.

## Tarefas, persistência e HTTP

Estados: `QUEUED -> INSPECTING -> ACQUIRING -> [TRANSCRIBING] -> NORMALIZING -> ANALYZING -> COMPLETED`; alternativas `WAITING_SOURCE`, `WAITING_RATE_LIMIT`, `FAILED`, `CANCELLED`. Persistir etapa, tentativa, datas, erro sanitizado e referências de artefatos. No reinício, verificar integridade do artefato antes de pular etapa; resultado de requisição remota perdida é `UNKNOWN_REMOTE_OUTCOME`, não sucesso. Reivindicação transacional evita dois workers locais executarem mesmo job; nenhuma transação SQLite fica aberta em chamadas de rede. Cancelamento cooperativo não presume cancelamento da API.

Banco SQLite (proposto): vídeos, fontes, transcrições e segmentos, análises/ideias/referências e jobs/tentativas; migrações e chaves estrangeiras; transações breves e política de backup compatível com WAL. Retenção de áudio ainda aberta. Busca simples inicialmente.

API HTTP proposta: `POST /api/videos`, `GET /api/videos`, `GET /api/videos/{id}`, `POST /api/videos/{id}/process`, `GET /api/jobs/{id}`, `POST /api/jobs/{id}/cancel`, `GET /api/videos/{id}/transcript`, `GET /api/videos/{id}/analysis`. Entrada binária precisa de contrato multipart separado; endpoints citados não implicam que uploads já estejam definidos. A UI consulta progresso por polling moderado.

## Segurança e testes exigidos

Secrets somente no backend, nunca no bundle, banco de vídeos ou logs. Tratar transcrição como conteúdo não confiável; não dar ferramentas, execução do sistema ou secrets ao LLM. Validar URLs, redirecionamentos, paths, arquivos e comandos de FFmpeg; sem concatenar shell. Rate-limit e falhas não geram sucesso aparente.

Aceites técnicos: teste Groq com timestamps reais; importação sem timestamps não cria link; chunking preserva offsets e fronteiras; erros 429/401/403 e URL inválida visíveis; reinício após transcrição não apaga artefatos; referências estrangeiras rejeitadas; E2E autorizado até biblioteca. **Nada disso foi executado nesta etapa.**

Fontes documentais (consultadas anteriormente em 20/09/2026): https://github.com/yt-dlp/yt-dlp · https://console.groq.com/docs/speech-to-text · https://console.groq.com/docs/structured-outputs · https://console.groq.com/docs/rate-limits · https://fastapi.tiangolo.com/tutorial/background-tasks/ · https://www.sqlite.org/wal.html · https://developers.google.com/youtube/v3/docs/captions/download · https://www.youtube.com/t/terms
