# T-007 — Análise longa e síntese global explícita

**Estado:** T-007 permanece **PARCIAL**. O repositório já possui planejamento por seções, checkpoints SQLite e um contrato separado de síntese global. Nesta revisão, a síntese passa a ter uma fronteira HTTP explícita e opcional; não é chamada automaticamente quando a análise por seções termina. [TASKLIST](../TASKLIST.md) · [DESIGN](../DESIGN.md) · [Contrato de provedores](T010_PROVIDER_BOUNDARY.md).

## Seções e checkpoints

- `ai/long_form.py` planeja seções contíguas usando segmentos completos e preserva IDs, texto, idioma e timestamps. Não há truncamento silencioso nem fallback de provedor.
- `ai/section_checkpoint.py` vincula cada run à transcrição/plano/provedor/modelo/revisão e salva somente prefixos válidos. Resultado remoto desconhecido permanece sem checkpoint.
- `SectionedAnalysis.section_summaries` e `collected_ideas` são resultados por seção. Eles nunca são promovidos por concatenação a um resumo global.
- O worker FastAPI continua marcando o job concluído como `SECTIONS_ONLY` quando todas as seções foram validadas. Isso não dispara nova chamada de IA.

## Síntese global neutra

- `ai/synthesis.py` define `GlobalSynthesisProvider`, separado de `AnalysisProvider`. Assim, a síntese global pode usar um provedor/modelo diferente da análise por seções sem contaminar o domínio com Groq.
- `synthesize_global` só aceita seções completas e com cobertura ordenada exata da transcrição. A saída precisa usar referências de segmentos originais; para transcrições com pelo menos três segmentos, a política padrão exige evidência estrutural de início, meio e fim.
- Cobertura posicional é **evidência estrutural**, não verificação semântica ou factual.
- `ai/synthesis_checkpoint.py` persiste uma síntese global versionada por run/transcrição/plano/provedor/modelo/revisão. Replay idêntico é reutilizado; rewrite divergente, resultado inválido e configuração alterada falham fechado.

## Fronteira HTTP — incremento atual

`create_app` aceita opcionalmente um `GlobalSynthesisProvider` com identidade explícita (`provider/model/revision`). Se não houver provedor configurado, `POST /api/jobs/{job_id}/synthesis` responde conflito seguro e **não escolhe Groq ou outro fornecedor automaticamente**.

Quando configurado:

1. o endpoint exige que o job esteja `COMPLETED` em `SECTIONS_ONLY`;
2. reabre e valida todas as seções antes da síntese;
3. usa `SQLiteGlobalSynthesisCheckpoint`;
4. faz no máximo uma chamada não checkpointada por vez no processo local;
5. um segundo POST com a mesma configuração reutiliza o resultado persistido, sem nova chamada;
6. resposta usa `result_kind=GLOBAL_SYNTHESIS` e não modifica o resultado de seções;
7. proveniência temporal continua independente: síntese global não habilita deep links.

Falhas conhecidas de provedor são reduzidas a códigos seguros. Resultado remoto desconhecido não é repetido automaticamente; uma nova tentativa exigiria outro POST explícito. Rate limit também não causa retry implícito.

## Limites operacionais

O `serve.py` normal **ainda não registra um provedor real de síntese** nesta fatia. Portanto, a nova fronteira está implementada e testada com fake, mas não significa GPT-OSS/Groq operacional para síntese global. Isso é intencional: registrar Groq exigirá um adaptador/prompt/orçamento próprios atrás de `GlobalSynthesisProvider`, sem reutilizar silenciosamente o contrato de análise de seção.

Também permanecem pendentes verificação semântica das referências, avaliação de qualidade com vídeo autorizado, política de retry explícita para resultados remotos desconhecidos, frontend e E2E.

## Evidência

A revisão de código `6016d041beb7bdbcbe12533ec86683016d36479d` passou no GitHub Actions **36244624678** em Python 3.12 e 3.13; o log Python 3.13 registrou **212 testes PASS**. Os testes novos comprovam: síntese somente após seções completas, ausência de provedor sem fallback, checkpoint reutilizado sem segunda chamada e resultado inválido não persistido.

T-007 continua parcial e a adoção do protocolo continua parcial. Nenhum merge, deploy ou chamada autenticada/paga é evidência desta fatia.
