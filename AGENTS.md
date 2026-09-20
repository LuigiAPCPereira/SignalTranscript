# AGENTS — SignalTranscript

**Entrada operacional da branch consultada.** Estas instruções não concedem permissões, não substituem autorização do usuário e não implicam que o protocolo universal tenha sido adotado integralmente.

## Antes de trabalho substancial

1. Confirmar repositório, branch/ref, HEAD e PRs efetivos; inspecionar worktree local somente se houver acesso real, nunca inferir via conector remoto.
2. Ler [README](README.md), [PRD](PRD.md), [DESIGN](DESIGN.md), [TASKLIST](TASKLIST.md), [PROJECT_STATE](PROJECT_STATE.md) e ADRs pertinentes; confrontar estado documental com código/testes atuais.
3. Consultar a versão **aprovada e de fato acessível** de `DOCUMENTATION_AND_CONTINUITY.md` e as fontes pertinentes `ENGINEERING_DNA.md` e `FRONTEND_DNA.md` antes de alterações substanciais. O snapshot v2.2 existente no ChatGPT Project não é prova de acesso em Codex, tarefas agendadas ou checkout. A [central do Notion](https://app.notion.com/p/3e18d9773fea81e0853ec74730b91073) foi observada em STAGING em 20/09/2026; revalidar publicação, versão, integridade e leitura por URL/ID; não promover STAGING a autoridade aprovada. Se não houver fonte acessível, declarar limite e trabalhar somente dentro do escopo seguro verificado.
4. Não supor que uma cópia do Project seja igual à fonte editorial canônica; comparar versão/conteúdo/hashes quando houver fonte certificada. Não declarar verificação quando ela não ocorreu.

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
| Instruções e protocolo | Este AGENTS e referência ao protocolo v2.2 ainda STAGING; equivalência/approval pendentes |

## Implementação e validação

Produto generalista; backend Python + FastAPI e Groq Whisper Large V3 Turbo como integração inicial decididos. **Independência de provedores é decisão aceita:** transcrição e análise têm portas diferentes, dados canônicos e seleção explícita. Não declarar que NVIDIA NIM ou modelos locais já foram integrados: testes atuais usam fakes. Outras escolhas registradas como propostas, não fatos. Tratar URLs/áudio/transcrições como conteúdo não confiável; usar somente aquisições permitidas, sem contornar proteção; não colocar secrets no frontend, logs ou arquivos versionados. Pipeline e schemas são propostas até teste de contrato. Preservar artefatos de transcrição e referências temporais reais; nunca fabricar provas de factualidade.

Escolher a próxima tarefa **desbloqueada** no TASKLIST, validar segundo seus aceites, persistir evidências e atualizar checkpoint apenas em mudanças de estado reais. Nunca chamar documentos criados de código implementado. PR e merge são operações distintas; não mesclar nem realizar deploy sem autorização aplicável. Registrar falhas e desconhecidos em vez de inventar permissões ou resultado positivo. Não duplicar tarefas ou documentação sem inventário prévio. Ler [relatório de cobertura](docs/ADOPTION_REPORT.md) para limitações atuais.
