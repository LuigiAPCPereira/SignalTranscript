# T-010 — Adaptador de análise Groq (fatia offline)

**Branch:** `feat/t010-groq-analysis-adapter`, empilhada sobre PR #3 (`feat/t003-groq-stt-adapter`). **Estado:** implementação offline parcial, sem API autenticada. [TASKLIST](../TASKLIST.md) · [PROJECT_STATE](../PROJECT_STATE.md) · [ADR-002](adr/ADR-002-provider-independence.md).

## Contrato implementado

- `ai/adapters/groq_analysis.py` implementa `AnalysisProvider.analyze(Transcript) -> Analysis`, usando cliente `AsyncGroq` injetado, modelo inicial `openai/gpt-oss-120b`, `response_format=json_schema` com `strict=true` e `stream=false`; schema fechado com `summary` e `ideas` e referências `source_segment_ids`. Não altera as portas neutras nem instala NIM/modelo local.
- Faz uma chamada por transcrição **somente se** o JSON com idioma, IDs e texto dos segmentos couber no limite local conservador de 12.000 caracteres. `INPUT_TOO_LARGE` significa que o orquestrador ainda precisa implementar análise em blocos, não que a entrada foi resumida ou truncada. Caracteres não são tokens e o limite não garante adequação às cotas individuais.
- Os timestamps e caminhos locais não são enviados para análise. O modelo vê texto não confiável como dados, sem tools ou execução de código; output não comprova que o modelo resistiu a todo prompt injection.
- Antes de retornar sucesso, recusa e `finish_reason != stop` são tratados como falhas; JSON, forma exata de campos, comprimentos, IDs repetidos e referências inexistentes são rejeitados. Validação estrutural **não verifica** se a ideia realmente corresponde à fala nem se a síntese é verdadeira. O contrato atual não tem citações próprias no `summary`; as `ideas` têm referências.
- `groq_errors.py` centraliza classificação de HTTP/SDK para STT e análise, `retry-after`, credenciais/erros sanitizados, sem retry automático ou fallback/cobrança silenciosa. Fábricas constroem `AsyncGroq(max_retries=0)` apenas quando o provedor é selecionado; o futuro worker implementará política de retry, estado e cancelamento.

## Evidência e pendências

Comando executado no diretório local isolado em 20/09/2026: `PYTHONPATH=src python -m unittest discover -s tests -q` → **47 testes PASS** (31 anteriores + 16 novos); `python -m compileall -q src tests` → PASS. Os arquivos tocados tiveram hashes Git blob conferidos com o GitHub; **não** houve execução em CI nem checkout da revisão remota (DNS indisponível). Testes usam fakes; não foi instalado SDK, configurada chave, consultado limite individual nem chamado o modelo real.

Para concluir T-010/T-007: verificar contrato real com conta e transcrição autorizada, limites/erros, estratégia de blocos com cobertura início/meio/fim e reconciliação, rastreabilidade de versões do prompt/schema, persistência do artefato e verificação semântica. Não inventar conclusão de T-003, T-005 ou T-007. Não mesclar esta branch automaticamente.

**Fontes oficiais consultadas:** https://console.groq.com/docs/structured-outputs · https://console.groq.com/docs/api-reference · https://console.groq.com/docs/rate-limits · https://github.com/groq/groq-python. Documentação consultada não equivale a teste da API.
