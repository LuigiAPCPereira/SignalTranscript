# PROJECT_STATE — SignalTranscript / checkpoint

**Observado em:** 2026-09-20 (horário local). **Escopo:** MVP v0.1; contratos, adaptadores e planejamento de análise por seções, sem aplicação ponta a ponta. **Fontes:** [TASKLIST](TASKLIST.md), [PRD](PRD.md), [DESIGN](DESIGN.md), [AGENTS](AGENTS.md), [relatório de adoção](docs/ADOPTION_REPORT.md).

## Git e decisões

- Repositório: https://github.com/LuigiAPCPereira/SignalTranscript. `main` foi observada antes em `e4fe22d6fee4120af33d9436f4b0e27864eb5df1`; revalidar antes de qualquer integração.
- Cadeia empilhada: PR #1 (documentação) -> #2 (portas/contrato) -> #3 (Groq STT) -> #4 (Groq análise). O PR #4 estava em Draft, aberto e não mesclado, HEAD `da71b922148608650b64f5481c25f3158562155d` na consulta desta etapa.
- **Fatia T-007 atual:** branch `feat/t007-long-form-sections` criada desse HEAD do PR #4; conferir PR, HEAD e CI finais no GitHub após commits documentais. Sem merge/deploy autorizado nesta etapa; checkout Git remoto indisponível por DNS, embora arquivos sejam acessíveis via conector.
- Decisões do usuário: produto generalista, Python + FastAPI, Groq Whisper Turbo como primeiro serviço e independência STT/LLM. GPT-OSS 120B possui adaptador offline. NIM e modelos locais ainda não estão integrados.

## Protocolo

Notion v2.2 observado STAGING na última consulta: publicação editorial aprovada e igualdade integral ao Project ainda não certificadas; acessibilidade em outras sessões/agendamentos desconhecida. O [ADOPTION_REPORT](docs/ADOPTION_REPORT.md) permanece em **ADOÇÃO PARCIAL**. Não declarar adoção concluída, nem inferir acesso ou permissões.

## Tarefas e evidência

- **T-004:** nove funções mapeadas no repositório, fonte canônica aprovada/equivalência e merge documental pendentes.
- **T-003 (parcial):** normalizador/adaptador STT testados offline; API autenticada, áudio e limites reais não validados.
- **T-010 (parcial):** portas neutras, seleção independente e Groq STT/análise offline; GitHub Actions no HEAD de #4 `da71b922`: [run 35548137252](https://github.com/LuigiAPCPereira/SignalTranscript/actions/runs/35548137252) `success` em Python 3.12/3.13 com 47 testes existentes; não comprova uso real de provedores.
- **T-007 (fatia implementada offline, tarefa não concluída):** [nota](docs/T007_LONG_FORM.md), planejador pré-valida todos os segmentos sem truncar, execução sequencial usa `AnalysisProvider`, referências por seção e resultados parciais explícitos; 17 testes locais de comportamento passaram e arquivos novos foram publicados com hashes conferidos. CI desta branch e PR final ainda devem ser consultados; sem síntese global, sobreposição, persistência, modelo real ou prova semântica de conteúdo.
- T-005/T-006/T-008/T-009 continuam pendentes: sem API FastAPI funcional, aquisição operacional, worker persistente, interface ou E2E.

**Próxima ação por ID:** T-007 — verificar CI na ref final, depois integrar política de seções ao worker persistente quando T-005 estiver disponível; preservar seções e prover síntese global verificável sem fabricar evidências. T-003/T-010 — contrato real em ambiente seguro com conteúdo autorizado, nunca chave no repo; T-004 — reconciliar fonte canônica quando estiver aprovada. Não fazer merge/deploy automático.
