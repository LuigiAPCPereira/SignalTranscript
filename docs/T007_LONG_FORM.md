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

## Adaptador Groq de síntese — separado da análise por seção

`ai/adapters/groq_synthesis.py` implementa `GlobalSynthesisProvider` sem reutilizar `GroqAnalysisAdapter`. O adaptador tem prompt, JSON Schema, orçamento, revisão e cliente próprios. `serve.py` registra síntese separadamente e só a constrói quando o operador informa `--synthesis-provider groq`; omitir esse argumento mantém a síntese desabilitada.

O payload enviado à síntese não reenvia cegamente a transcrição inteira. Para cada seção concluída ele envia o resumo/ideias anteriores como **dados não confiáveis** e acrescenta texto original de segmentos selecionados por política determinística: primeiro, meio e último segmento da seção, mais todos os segmentos citados pelas ideias daquela seção. O resultado só pode citar IDs cujo texto foi realmente enviado ao sintetizador. Timestamps e caminhos locais não entram no payload.

A política atual é `section-anchors-first-middle-last-plus-idea-refs-v1`. O limite local é 96.000 caracteres Unicode e é deliberadamente uma proteção própria do adaptador, **não** uma tradução de tokens/cota. A documentação Groq consultada em 2026-09-26 lista `openai/gpt-oss-120b` com janela de 131.072 tokens e suporte a Structured Outputs estrito; o contrato local continua menor e versionado para reduzir dependência do limite máximo do fornecedor.

Fontes oficiais: https://console.groq.com/docs/model/openai/gpt-oss-120b e https://console.groq.com/docs/structured-outputs.

## Composição e consentimento

Análise por seção e síntese global são selecionadas independentemente. Exemplo operacional possível:

```bash
python -m signaltranscript.backend.serve \
  --analysis-provider groq \
  --synthesis-provider groq
```

Isso cria identidades/clientes separados, mesmo quando ambos usam Groq. Não há default de síntese, fallback ou promoção automática após `SECTIONS_ONLY`. O endpoint de síntese continua sendo um POST explícito e pode consumir cota quando um provedor remoto estiver configurado.

## Limites operacionais

O adaptador Groq de síntese está implementado e testado **offline com cliente injetado**. Não houve nesta revisão chamada autenticada, medição da cota da conta, avaliação de qualidade com vídeo real ou comparação semântica/factual. O limite de 96.000 caracteres não garante enquadramento em limites de tokens/rate limits de uma conta específica.

Também permanecem pendentes provedor local/NIM real, política explícita para nova tentativa após resultado remoto desconhecido, frontend e E2E.

## Evidência

- `6016d041beb7bdbcbe12533ec86683016d36479d`: Actions 36244624678 PASS Python 3.12/3.13, 212 testes no log 3.13 — fronteira HTTP/checkpoint global.
- `1d78f93a52fbef6817374fd10ac7692d0901bcd5`: Actions **36245879695** PASS Python 3.12/3.13, **227 testes PASS** no log 3.13 — adaptador Groq de síntese, política de evidência e composição independente.

T-007 continua parcial. A adoção do Agent Protocol v2.2 está concluída na ref de trabalho; isso é separado do estado parcial do produto. Nenhum merge, deploy ou chamada autenticada/paga é evidência desta fatia.


## Recuperação read-only da síntese

`GET /api/jobs/{job_id}/synthesis` reconstrói seções/transcrição a partir do job e carrega a identidade histórica diretamente da linha persistida (`provider/model/revision`). Ele usa `SQLiteGlobalSynthesisCheckpoint.load_persisted()`, que consulta uma tabela existente sem DDL e independe da configuração atual de síntese. Se nenhuma síntese foi persistida, retorna 404 e não cria `global_syntheses`; se existir, revalida fingerprint, provider/model/revision, referências e cobertura antes de responder.

O smoke oferece `--check-synthesis-job JOB_ID --expect-synthesis-provider NOME`. Esse modo executa um único GET e compara o provider esperado com a identidade persistida do resultado; continua funcional mesmo se o servidor reiniciar sem provider de síntese configurado. Nenhum retry automático foi introduzido.

Evidência: SHA `43f6b135d962d09a93de460d5c94f61b4a5fe1f5`, Actions 36256244587 PASS Python 3.12/3.13, 237 testes.
