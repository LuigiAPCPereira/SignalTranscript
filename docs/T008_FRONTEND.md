# T-008 — Frontend da biblioteca local

**Estado:** **PARCIAL** na branch do PR #10. Existe um primeiro fluxo visual biblioteca → busca → leitura de transcript. Não há frontend de aquisição, análise/síntese acionável, deep links ou E2E browser→FastAPI validado. [Biblioteca](T008_LIBRARY.md) · [TASKLIST](../TASKLIST.md) · [Checkpoint](../PROJECT_STATE.md).

## Visual Thesis

- **Audience:** pessoa que guarda vídeos/transcrições para consultar conhecimento depois.
- **Primary task:** localizar uma transcrição persistida, buscar um trecho e ler o conteúdo sem disparar IA.
- **Surface mode:** Operate → Read.
- **Tone:** calmo, confiável, local e editorial; tecnologia fica em segundo plano.
- **Expression:** contida; hierarquia tipográfica e estrutura antes de decoração.
- **Motion:** mínima e somente para loading; respeita `prefers-reduced-motion`.
- **Density:** média; lista escaneável à esquerda e leitura confortável à direita.
- **Primary anchor:** biblioteca + leitor em dois painéis no desktop; composição empilhada no mobile.
- **Typography:** system sans; nenhuma fonte externa.
- **Constraints de verdade:** não inventar título, thumbnail, canal ou duração que o backend não possui; usar `video_id` como identificador visível. Timestamps são texto, nunca links enquanto `deep_links_allowed=false`.
- **Evitar deliberadamente:** dashboard de métricas, “AI magic”, cards decorativos, animação sem função, dependência de CDN e badges que sugiram verificação inexistente.

## Stack desta fatia

O tracer usa HTML semântico, CSS e ES modules nativos, servidos na mesma origem do FastAPI:

- `GET /` → shell da biblioteca;
- `GET /assets/app.css`;
- `GET /assets/app.js`.

Não há React/Vite, npm, bundle, CDN, fonte remota ou runtime frontend adicional. React/TypeScript continuam uma opção futura, **não uma decisão adotada**. Um framework só deve entrar quando oferecer alavancagem concreta superior ao custo de build, lockfile, dependências e migração.

Os arquivos web são incluídos no pacote Python via `tool.setuptools.package-data`.

## Fluxo e estados implementados

A UI consome apenas read models já existentes:

1. carrega `GET /api/library`;
2. permite busca com `GET /api/library/search`;
3. ao selecionar um item/hit, abre `GET /api/jobs/{id}/transcript`.

Estados modelados:

- **loading:** skeleton estrutural sem dados falsos;
- **empty library:** informa que não existem itens persistidos;
- **search empty:** query válida sem ocorrências;
- **search truncated:** informa explicitamente que há mais resultados e pede refinamento;
- **error:** mensagem local genérica sem vazar internals;
- **reader empty:** orientação antes da seleção;
- **reader loaded:** transcript canônico, idioma/origem/contagem e proveniência;
- **artifact partial:** chips distinguem transcript, seções e síntese presentes/ausentes.

Conteúdo dinâmico entra via `textContent`/criação de nós; o código não usa `innerHTML`, `window.open` ou navegação temporal.

## Responsivo e acessibilidade

- skip link para `main`;
- label real no campo de busca;
- botões nativos e foco visível;
- `aria-live` nos estados de biblioteca/leitor;
- targets de ação com pelo menos 44 px;
- informação de disponibilidade tem texto, não depende apenas de cor;
- breakpoint de composição em 860 px e refinamento mobile em 560 px;
- no mobile validado a 390 px, `document.documentElement.scrollWidth === 390`;
- `[hidden]{display:none!important}` garante que estados mutuamente exclusivos não sejam reexibidos por regras de layout.

## Evidência determinística

Commit inicial do frontend: `ee2b7a22b458e85b15b53c2f382b32f60c52a91f`. GitHub Actions 36581307388 passou Python 3.12/3.13 com **248 testes**.

O primeiro render revelou um defeito que testes HTTP não detectavam: `.reader-empty { display:grid }` sobrepunha o comportamento nativo de `hidden`, mantendo o estado vazio acima do transcript. Foi instalado guardrail CSS + teste em `682c08427191117cc2528530c5f4626f3bf5e7d8`. Actions **36582197169** passou Python 3.12/3.13 com **248 testes**.

Os contratos testam também que os assets são same-origin, estão empacotados, não referenciam URLs externas e que abrir o shell/assets não chama o provider.

## Evidência renderizada

Chromium headless foi usado com os bytes do frontend da revisão corrigida em:

- desktop 1440×1000: biblioteca;
- desktop 1440×1000: transcript selecionado;
- desktop 1440×1000: busca com `truncated=true`;
- mobile 390×844: transcript selecionado.

Após a correção, o estado vazio desaparece corretamente quando o leitor abre, a composição desktop permanece em dois painéis e o mobile empilha biblioteca/leitor sem overflow horizontal.

**Limitação do render:** a política administrativa do Chromium deste ambiente bloqueou navegação para `127.0.0.1` com `ERR_BLOCKED_BY_ADMINISTRATOR`. Portanto, a renderização usou exatamente os mesmos bytes de HTML/CSS/JS, mas substituiu `fetch` por fixtures locais no harness. Isso valida layout/estados/interação dos assets, **não** constitui E2E browser→FastAPI. O contrato HTTP same-origin é coberto separadamente pelos testes FastAPI.

## Leitura de conhecimento persistido

O leitor agora possui três modos explícitos:

- **Transcrição** — artefato canônico persistido;
- **Seções** — `GET /api/jobs/{id}/sections`, exigindo `result_kind=SECTIONS_ONLY`;
- **Síntese global** — `GET /api/jobs/{id}/synthesis`, exigindo `result_kind=GLOBAL_SYNTHESIS`.

A UI não faz POST. Se não houver síntese global, 404 é tratado como estado normal: “Não há síntese global persistida para este item.” Seções parciais exibem a contagem existente versus `planned_sections` e nunca são apresentadas como síntese global.

Seções mostram resumo local, ideias e IDs de evidência/segmentos. Síntese global mostra resumo, ideias e cobertura de evidências. A cópia da síntese avisa explicitamente que resumir a transcrição não constitui verificação independente dos fatos.

Commit funcional: `a8225c6a393a24a4c96fd09ad1a6cfa8bc27b8c9`. GitHub Actions **36609696964** passou Python 3.12/3.13 com **248 testes**. O contrato frontend também verifica presença de `SECTIONS_ONLY`/`GLOBAL_SYNTHESIS` e ausência de strings `POST` no módulo cliente.

### Render desta fatia

Estados representativos foram renderizados com o CSS exato da revisão e DOM equivalente ao produzido pelo módulo:

- Seções — desktop 1440×1000;
- Síntese global — desktop 1440×1000;
- Síntese global — mobile 390×844.

Nos três casos não houve overflow horizontal; no mobile `scrollWidth === clientWidth === 390`. A hierarquia entre “Seções” e “Síntese global” permaneceu visualmente inequívoca.

**Limitação:** como o Chromium deste ambiente bloqueia navegação local por política administrativa, estes renders não são E2E nem executam o `fetch` real do app. O CSS/estrutura visual foi renderizado separadamente; os contratos HTTP/read-only/result_kind/no-POST continuam validados pela suíte FastAPI/CI.

## Próxima fatia

Evitar que o leitor descubra indisponibilidade apenas por erro: expor/consumir **disponibilidade read-only de artefatos** para o job selecionado, incluindo seleções vindas da busca, e refletir isso nas abas sem disparar nenhum POST. Depois disso, a fronteira de T-008 estará pronta para decidir entre ampliar experiência local ou mover o foco para T-009 conforme bloqueios de T-006.
