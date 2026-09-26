# T-010 — Fronteira independente de provedores

**Estado:** código de contrato e seleção implementados, nove testes offline locais aprovados; integração operacional não realizada. **Decisão:** [ADR-002](adr/ADR-002-provider-independence.md). **Tarefas:** [TASKLIST](../TASKLIST.md), checkpoint em [PROJECT_STATE](../PROJECT_STATE.md).

## Domínio e portas

- `ai/ports.py`: `Segment`, `Transcript`, `Idea` e `Analysis`; contratos `TranscriptionProvider.transcribe(audio_path, video_id, language)` e `AnalysisProvider.analyze(transcript)` são independentes de SDKs externos. O campo `source` cobre importação e legendas sem necessidade de STT. Timestamps desconhecidos ficam `None`.
- `ai/selection.py`: mantém a separação inicial entre transcrição e análise. A composição FastAPI posterior também trata **análise por seção** e **síntese global** como funções diferentes, cada uma com registro/identidade/revisão próprios.
- `backend/serve.py`: composição explícita. `--analysis-provider` é obrigatório; `--synthesis-provider` é opcional e nunca herdado automaticamente da análise. Hoje Groq possui adaptadores reais para análise por seção e síntese global, mas ambos permanecem sem validação autenticada nesta revisão. NIM e modelos locais continuam apenas possibilidades futuras/fakes de teste, sem inferência real.
- Dados de provedor são normalizados no adaptador antes de passar ao domínio. `validate_analysis` rejeita referências inexistentes mas **não comprova veracidade** da síntese ou sua aderência semântica à fala.

## Regras operacionais

1. Seleção independente por função: STT, análise por seção e síntese global não são aliases entre si. O runtime preserva identidade/revisão e não converte a escolha de uma função em escolha automática de outra.
2. Falha não deve alternar provedores, transmitir dados a novos destinos ou gerar custos silenciosamente. Qualquer política de fallback exige decisão/consentimento separado.
3. Nenhuma chave/API/HTTP/FFmpeg/yt-dlp no domínio, na UI ou nos logs. Cada adaptador responde por autenticação, limites, timeouts, validação e normalização de payload.
4. Modelos locais e NVIDIA NIM são **possibilidades futuras**, não suporte atual. Verificação real de contrato para cada implementação antes de habilitar na UI.
5. Transcrição importada percorre a análise sem usar provedor de STT.

## Validação disponível e pendente

A fronteira inicial foi validada incrementalmente desde o PR #2. No checkpoint atual, o adaptador Groq de síntese e a composição independente passaram no Actions **36245879695** em Python 3.12/3.13; o log Python 3.13 registrou **227 testes PASS**. Os testes usam clientes/fakes injetados e não executam inferência autenticada.

Pendem: validação real Groq para cada função, NIM/local operacional, persistência de preferências do usuário, UI de seleção e E2E. Ter dois adaptadores Groq não transforma Groq em dependência do domínio e não conclui T-003/T-005/T-006/T-007/T-010.
