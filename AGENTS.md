# AGENTS — SignalTranscript

**Entrada operacional da branch consultada.** O SignalTranscript adotou o Agent Development Protocol v2.2 na ref de trabalho mediante Adoption Gate verificado; isso não concede permissões, não implica merge em `main` e não transforma a distribuição central STAGING em release publicada. [Fonte/versionamento](docs/PROTOCOL_SOURCE.md) · [relatório de adoção](docs/ADOPTION_REPORT.md).

## Antes de trabalho substancial

1. Confirmar repositório, branch/ref, HEAD e PRs efetivos; inspecionar worktree local somente se houver acesso real, nunca inferir via conector remoto.
2. Ler [README](README.md), [PRD](PRD.md), [DESIGN](DESIGN.md), [TASKLIST](TASKLIST.md), [PROJECT_STATE](PROJECT_STATE.md) e ADRs pertinentes; confrontar estado documental com código/testes atuais.
3. Usar [docs/PROTOCOL_SOURCE.md](docs/PROTOCOL_SOURCE.md) para identificar a versão-fonte v2.2 adotada e sua evidência de integridade. Quando `DOCUMENTATION_AND_CONTINUITY.md`/DNA estiverem realmente acessíveis, consultar o original pertinente; nunca alegar leitura em host que não o possua.
4. A central Notion v2.2 permanece STAGING como **distribuição editorial**, estado separado da adoção deste projeto. A cópia Project usada na adoção teve SHA-256 confrontado com os hashes de origem do manifesto central. Codex e tarefas agendadas não herdam esse acesso; devem recuperar GitHub e declarar fontes externas indisponíveis quando for o caso.

## Mapa documental — nove funções

| Função | Fonte neste repositório |
| --- | --- |
| Identidade e visão | [README](README.md) e [PRD §1](PRD.md) |
| Requisitos e aceites | [PRD](PRD.md) (inclui REQ-013) |
| Arquitetura e contratos | [DESIGN](DESIGN.md) e [fronteira de provedores](docs/T010_PROVIDER_BOUNDARY.md) |
| Decisões duráveis | [ADR-001](docs/adr/ADR-001-python-fastapi.md), [ADR-002](docs/adr/ADR-002-provider-independence.md); propostas distintas de decisões aceitas |
| Inventário de tarefas | [TASKLIST](TASKLIST.md) (IDs, estados, dependências, aceites, evidências) |
| Planejamento e marcos | [ROADMAP](ROADMAP.md) |
| Histórico recuperável | [SESSION_LOG](SESSION_LOG.md) e commits/PRs reais |
| Checkpoint | [PROJECT_STATE](PROJECT_STATE.md), vinculado a T-004 documental e T-010 técnico |
| Instruções e protocolo | Este AGENTS + [pin/fonte v2.2](docs/PROTOCOL_SOURCE.md) + [Adoption Gate](docs/ADOPTION_REPORT.md); publicação central STAGING é separada |

## Implementação e validação

Produto generalista; backend Python + FastAPI e Groq Whisper Large V3 Turbo como integração inicial decididos. **Independência de provedores é decisão aceita:** transcrição e análise têm portas diferentes, dados canônicos e seleção explícita. Não declarar que NVIDIA NIM ou modelos locais já foram integrados: testes atuais usam fakes. Outras escolhas registradas como propostas, não fatos. Tratar URLs/áudio/transcrições como conteúdo não confiável; usar somente aquisições permitidas, sem contornar proteção; não colocar secrets no frontend, logs ou arquivos versionados. Pipeline e schemas são propostas até teste de contrato. Preservar artefatos de transcrição e referências temporais reais; nunca fabricar provas de factualidade.

Escolher a próxima tarefa **desbloqueada** no TASKLIST, validar segundo seus aceites, persistir evidências e atualizar checkpoint apenas em mudanças de estado reais. Nunca chamar documentos criados de código implementado. PR e merge são operações distintas; não mesclar nem realizar deploy sem autorização aplicável. Registrar falhas e desconhecidos em vez de inventar permissões ou resultado positivo. Não duplicar tarefas ou documentação sem inventário prévio. Ler [relatório de cobertura](docs/ADOPTION_REPORT.md) para limitações atuais.
