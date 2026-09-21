# T-007 — Análise de transcrições longas: seções e checkpoints

**Escopo:** planejamento/execução offline e persistência local de seções; não é o pipeline completo da T-007. PR #5 (`c0f35a6b`) é a base desta fatia. [TASKLIST](../TASKLIST.md) · [DESIGN](../DESIGN.md) · [Contrato de provedores](T010_PROVIDER_BOUNDARY.md).

## Seções e fronteiras

- `ai/long_form.py` independe de Groq, FastAPI, SQLite e aquisição. Recebe um `AnalysisProvider` previamente selecionado; não há retry, fallback ou seleção automática de serviço.
- `plan_sections` verifica o plano inteiro antes de chamadas remotas. Mantém segmentos completos e contíguos, IDs, texto, ordem, idioma, origem e timestamps. Um segmento isolado grande demais ou mais seções que o limite são erros explícitos, nunca truncamento.
- `compact_source_chars` mede caracteres Unicode do envelope JSON compacto idioma/IDs/texto do adaptador Groq inicial: **não mede tokens nem garante cota/contexto**. Outros provedores devem fornecer seus próprios medidores e orçamento.
- `analyze_in_sections` permanece utilizável sem banco. Uma rotina interna recebe um plano imutável e prefixo validado para que a retomada não replaneje silenciosamente. Mudança inesperada de modelo/provedor, referência inválida e falha parcial são tratadas explicitamente.
- `SectionedAnalysis.section_summaries` e `collected_ideas` são **por seção**, nunca resumo global. Deduplicação somente exata; não converter resultado incompleto em análise completa.

## Checkpoint SQLite — incremento nesta branch

- `ai/section_checkpoint.py` grava `analysis_runs` e `analysis_sections` no SQLite via `sqlite3` da biblioteca padrão. Requer `run_id`, provedor, modelo, `revision` da análise, transcrição e limite de seção. SHA-256 identifica a transcrição canônica (inclusive tempos e origem) e o plano efetivo. O mesmo `run_id` não pode ser reutilizado com identidade divergente; execuções/versionamentos diferentes usam IDs distintos.
- **Responsabilidade do chamador:** atualizar `revision` quando prompt, esquema ou demais configurações relevantes mudarem. O código não detecta mudanças externas no serviço e não guarda chaves de API.
- `open_and_load` rejeita índice não contíguo, dados inválidos, referências inexistentes e alterações de transcrição/plano/provedor antes de nova chamada de IA. `save` valida seção e referências, usa transação curta, impede sobrescrita diferente e permite repetição idêntica. Uma chamada remota com resposta perdida não gera checkpoint; a próxima execução poderá precisar repetir essa chamada e consumir nova cota.
- `analyze_with_checkpoint` reutiliza o prefixo validado e chama a porta neutra somente para o restante. Erro conhecido mantém resultado parcial, e erro de disco/programação se propaga. Não existe transação aberta durante chamadas de rede.
- **Limite explícito:** pressupõe somente um executor ativo por `run_id`. Ainda não há lease/reivindicação multiworker, worker persistente, API, armazenamento de transcrição/áudio, backup, limpeza, cancelamento ou integração E2E. A T-005 permanece dependente das suas próprias condições de aceite.

## Pendências de qualidade

Não há sobreposição entre seções neste estágio. Síntese global representativa, checagem semântica de referências, cobertura real início/meio/fim, configurações operacionais por função e testes com IA remota são pendentes. Um arquivo SQLite de seções não é biblioteca funcional e não equivale a execução exatamente uma vez. T-007 segue parcial; adoção do protocolo não se altera por esta implementação.

## Evidência

Testes locais: `PYTHONPATH=src python -m unittest discover -s tests -q` (32 testes de fatias: 17 existentes e 15 novos) e `python -m compileall -q src tests`; arquivos publicados devem ter seus hashes e CI na ref exata revalidados. Casos novos: reinício com reaproveitamento de seções, resultado completo sem chamadas duplicadas, timeout desconhecido, mudanças de conteúdo/tempos/plano/revisão/provedor, corrupção de payload/referências/ordem, gravação idempotente, erro de armazenamento e preflight sem criar banco. Testes sem SDK, secrets ou rede. CI da suíte inteira é um aceite distinto, a ser registrado no HEAD final.
