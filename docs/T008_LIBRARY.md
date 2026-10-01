# T-008 — Biblioteca local e busca textual

**Estado:** **PARCIAL** na branch do PR #10. O read model abaixo agora possui um primeiro consumidor visual em [T008_FRONTEND](T008_FRONTEND.md). FTS, deep links e experiência completa continuam pendentes. [TASKLIST](../TASKLIST.md) · [DESIGN](../DESIGN.md) · [Checkpoint](../PROJECT_STATE.md).

## Ownership

O journal SQLite de T-005 continua sendo a **única fonte de verdade** para jobs e transcripts importados. A biblioteca não copia transcripts para uma segunda tabela.

`LibraryReadModel` deriva projeções usando a interface pública de `SQLiteJobs`:

- cada `video_id` forma uma entrada de biblioteca;
- o job com maior `created_seq` é a versão corrente;
- `version_count` conta todos os jobs persistidos daquele vídeo;
- versões antigas continuam no journal e podem ser acessadas por job ID;
- leitura da biblioteca nunca inicia IA, aquisição, retry ou mutação de checkpoint.

Essa escolha evita decidir prematuramente por FTS/materialized view antes de haver medição real de volume/performance.

## API

### `GET /api/library?limit=20&before=N`

Retorna `result_kind=LIBRARY`, entradas newest-first pela sequência da **versão corrente** e cursor `next_before`.

Cada item contém `video_id`, `latest_job_id`, `version_count`, estado do job corrente, `source`, `language`, proveniência e presença de transcript/seções/síntese.

Paginação é sobre entradas de vídeo, não jobs individuais. Uma versão antiga do mesmo vídeo não reaparece em páginas posteriores.

### `GET /api/library/search?q=texto&limit=20`

Busca Unicode case-insensitive por **substring** nos segmentos da versão corrente de cada vídeo. Resultados são ordenados por vídeos mais recentemente atualizados e ordem original dos segmentos.

A resposta contém `result_kind=TRANSCRIPT_SEARCH`, a query com trim, `items` e `truncated`. `truncated=true` significa que existem mais matches além do limite; não significa erro externo.

Cada hit aponta para `video_id`, `job_id`, segmento canônico e proveniência. Texto de versões antigas não participa da busca enquanto houver uma versão mais nova daquele `video_id`.

## Segurança/proveniência

A busca não cria URLs temporais. Mesmo quando segmentos possuem `start_ms/end_ms`, `deep_links_allowed` continua vindo da proveniência e permanece falso no estado atual do produto.

Nenhuma query é enviada a Groq ou outro provedor. A busca acontece somente sobre transcripts persistidos localmente.

## Performance e limites atuais

Esta primeira implementação recompõe a projeção percorrendo o journal paginado e faz busca em memória nos transcripts correntes. Isso é simples e exato para validar semântica/UX do MVP local, mas **não há benchmark de biblioteca grande**.

Se medição demonstrar necessidade, um índice FTS pode ser introduzido depois como projeção reconstruível, sem tornar-se source of truth. Não anunciar FTS, ranking de relevância, stemming, fuzzy search ou escalabilidade antes de implementação/medição.

## Evidência

A primeira revisão `a382c3176030db73b94e851c7baf1198e473eb1a` compilou, mas o CI encontrou um erro de fixture: os textos de teste eram maiores que o orçamento mínimo deliberado do app de integração e o POST foi corretamente rejeitado. O fixture foi reduzido sem modificar limites ou comportamento.

SHA validado: `3367ee1db04ee1147f1794bc2d22a0d862c8177b`. GitHub Actions **36574287374**: PASS Python 3.12 e 3.13; **246 testes PASS**.

Adoção do Agent Protocol v2.2 permanece concluída na ref de trabalho. PR segue Draft; sem merge/deploy ou chamada autenticada a provedor.
