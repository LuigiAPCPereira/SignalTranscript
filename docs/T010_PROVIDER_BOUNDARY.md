# T-010 — Fronteira independente de provedores

**Estado:** código de contrato e seleção implementados, nove testes offline locais aprovados; integração operacional não realizada. **Decisão:** [ADR-002](adr/ADR-002-provider-independence.md). **Tarefas:** [TASKLIST](../TASKLIST.md), checkpoint em [PROJECT_STATE](../PROJECT_STATE.md).

## Domínio e portas

- `ai/ports.py`: `Segment`, `Transcript`, `Idea` e `Analysis`; contratos `TranscriptionProvider.transcribe(audio_path, video_id, language)` e `AnalysisProvider.analyze(transcript)` são independentes de SDKs externos. O campo `source` cobre importação e legendas sem necessidade de STT. Timestamps desconhecidos ficam `None`.
- `ai/selection.py`: recebe registros de adaptadores **já montados** e dois nomes escolhidos separadamente. Exemplo: `ProviderSelection(transcription="local", analysis="groq")`, somente se ambas as implementações forem realmente registradas. Provedores desconhecidos são rejeitados sem fallback implícito.
- O ponto de composição definitivo, parsing/validação de configuração, implementação Groq HTTP, NIM e modelos locais **ainda não existem**. Os exemplos `local` e `nim` nos testes são somente fakes em memória, sem inferência.
- Dados de provedor são normalizados no adaptador antes de passar ao domínio. `validate_analysis` rejeita referências inexistentes mas **não comprova veracidade** da síntese ou sua aderência semântica à fala.

## Regras operacionais

1. Seleção independente para ASR e LLM, preservada por job junto a modelo/provedor efetivamente usado. Mudanças de configuração não reescrevem históricos.
2. Falha não deve alternar provedores, transmitir dados a novos destinos ou gerar custos silenciosamente. Qualquer política de fallback exige decisão/consentimento separado.
3. Nenhuma chave/API/HTTP/FFmpeg/yt-dlp no domínio, na UI ou nos logs. Cada adaptador responde por autenticação, limites, timeouts, validação e normalização de payload.
4. Modelos locais e NVIDIA NIM são **possibilidades futuras**, não suporte atual. Verificação real de contrato para cada implementação antes de habilitar na UI.
5. Transcrição importada percorre a análise sem usar provedor de STT.

## Validação disponível e pendente

`PYTHONPATH=src python -m unittest discover -s tests -v` — na sessão isolada, nove testes adicionais da fronteira passaram; o PR #2 já registra oito testes do normalizador Groq executados anteriormente, mas a suíte completa na revisão atual ainda não foi executada em CI. Sem chaves ou testes remotos, integração Groq/NIM/local, configuração persistida ou E2E. Esta fatia não conclui T-003, T-005, T-006 ou T-007.
