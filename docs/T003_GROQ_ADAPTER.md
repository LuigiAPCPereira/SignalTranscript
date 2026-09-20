# T-003 — Adaptador Groq de transcrição (fatia offline)

**Estado:** adaptador publicado para revisão; testes offline em cópia local correspondente, sem autenticação, áudio real, Groq SDK instalado no ambiente de testes, CI ou E2E. Esta fatia **não conclui T-003**. Contratos existentes: [Groq payload](T003_GROQ_CONTRACT.md), [independência](T010_PROVIDER_BOUNDARY.md), [TASKLIST](../TASKLIST.md).

## Responsabilidade e fluxo

`GroqTranscriptionAdapter` implementa a porta `TranscriptionProvider` sem importar Groq para o domínio. É criado no ponto de composição somente quando selecionado. `from_environment()` exige `GROQ_API_KEY`, constrói `AsyncGroq` com timeout explícito (180 s por padrão) e **`max_retries=0`**; a gestão da vida útil fecha o cliente que criou. O SDK é dependência de runtime ainda não instalada/configurada no aplicativo.

O adaptador recebe **arquivo local previamente autorizado**, nunca uma URL arbitrária. Confere arquivo regular (sem symlink), extensão, tamanho não nulo e limite conservador padrão de 25.000.000 bytes antes da requisição. O limite efetivo da conta não foi medido e pode exigir ajuste explícito. Usa `file=Path`, `whisper-large-v3-turbo`, `verbose_json` e timestamps de `segment`, idioma ISO-639-1 opcional. Normaliza pelo contrato existente para `Transcript`/`Segment` canônicos, preserva texto e provedor/modelo; não inventa idioma ISO quando Groq retorna uma descrição textual.

## Tratamento de falhas

`ProviderFailure` fica em `ai/errors.py`, independente do SDK. 429 preserva `retry-after` numérico válido; 401/403, 400/413/422 e 404 são falhas explícitas sem repetição automática. 408/409/5xx e erros de conexão/timeout marcam `remote_outcome_unknown=True`, pois uma requisição pode ter sido processada sem resposta; o futuro worker decide se e quando repetir, sem troca automática de provedor. Payload inválido **não** vira transcrição concluída. Mensagem de erro pública não inclui corpo remoto ou chave.

## Limites e próximos aceites

- Executados localmente: `PYTHONPATH=src python -m unittest discover -s tests -q` (31 testes, incluindo os 17 anteriores), `python -m compileall -q src tests` (PASS). Arquivos novos de código/testes e base foram confrontados por Git blob após publicação. Ainda não há CI executada na revisão do PR.
- **Não implementado:** chamada remota, verificação das cotas/erros reais, codec real, FFmpeg, chunking/overlap, persistência/reinício, cliente de análise GPT-OSS, NIM, modelo local e aplicativo completo. Não usar fakes como evidência operacional.
- Antes de produção: instalar/registrar versão verificada do SDK; validar interface real `AsyncGroq`, retorno `verbose_json`, um áudio autorizado com segredo somente no ambiente, rate-limit e timeout reais. Testar limites, media type e alterações do arquivo entre `lstat` e leitura pelo SDK (TOCTOU). Endurecer isolamento de arquivos na etapa de ingestão.

**Fontes consultadas 20/09/2026:** https://github.com/groq/groq-python ; https://console.groq.com/docs/api-reference ; https://console.groq.com/docs/speech-to-text ; https://console.groq.com/docs/rate-limits . Este documento não é prova de execução remota.
