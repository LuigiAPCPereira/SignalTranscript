# T-007 — Análise de transcrições longas: primeira fatia

**Escopo:** planejador e execução sequencial offline por seções; ainda não é o pipeline completo de T-007. Base da branch: PR #4, HEAD `da71b922148608650b64f5481c25f3158562155d`. [TASKLIST](../TASKLIST.md) · [DESIGN](../DESIGN.md) · [Contrato de provedores](T010_PROVIDER_BOUNDARY.md).

## Responsabilidades e fronteiras

- `ai/long_form.py` é independente de Groq, FastAPI, SQLite e aquisição. Recebe um `AnalysisProvider` já escolhido; não seleciona outro provedor, não faz retry, não envia conteúdos extras e não gera custos sem que o chamador inicie a operação.
- `plan_sections` testa **todo o plano antes de qualquer chamada**. Cada seção reúne segmentos completos, contíguos, com os mesmos IDs, texto, ordem, idioma, source e tempos da transcrição original. Segmento maior que o orçamento ou mais de 64 seções gera erro explícito; nunca truncar nem omitir segmentos.
- `compact_source_chars` mede o envelope JSON compacto de idioma/IDs/texto usado pelo adaptador Groq atual. A medida é de caracteres Unicode, **não** de tokens; não garante limite de contexto nem TPM/RPM. Outros provedores podem fornecer `measure` e orçamento adequados. Para o adaptador Groq atual, o chamador pode passar `max_chars=12000`, desde que confirme sua configuração; não existe ponto de composição operacional ainda.
- `analyze_in_sections` usa um provedor por execução, mantém metadados e valida IDs contra cada seção; mudança inesperada de provedor/modelo é erro. Falhas conhecidas retornam `SectionedAnalysis(complete=False, failure=...)` com seções concluídas; falha inesperada de programação/armazenamento é propagada. Um callback assíncrono permite um futuro worker gravar cada seção, mas **nenhuma persistência foi implementada**.
- `SectionedAnalysis.section_summaries` e `collected_ideas` são resultados **por seção**; a deduplicação é somente exata (título, explicação, IDs). Não existe propriedade `summary` global: concatenar resumos não equivale a uma síntese representativa de todo o vídeo.

## Limitações e aceites pendentes

- Não há sobreposição entre seções nesta primeira fatia. Definir e testar contexto de fronteira, controle de duplicatas e chamadas adicionais antes de introduzi-la; nenhuma fala pode ser removida.
- A análise global do vídeo, verificação semântica das referências, cobertura do início/meio/fim em conteúdos reais, política de custos, tokenização real, idempotência, retomada persistida, cancelamento, configuração por função e teste de API seguem pendentes.
- Não converter `SectionedAnalysis` incompleta para `Analysis` final nem anunciar modelo local/NIM operacional. `T-005`, `T-006`, `T-007`, `T-009` e `T-010` continuam sujeitos aos critérios do tracker.

## Evidências verificáveis

Testes novos: `PYTHONPATH=src python -m unittest tests/test_long_form.py -v` (ou `discover -s tests`). Casos: preservação de todos os segmentos/timestamps e ordem; envelope; orçamento configurável; segmento individual ou número de seções excessivo sem chamadas remotas; sucesso e falha parcial; referências inválidas; provedor/modelo alterado; callback de checkpoint; erro inesperado não disfarçado. Testes usam fake, sem segredos nem rede. Para confirmar integração, exigir suíte total no HEAD do PR e depois casos reais autorizados com custos explícitos.
