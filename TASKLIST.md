# TASKLIST — SignalTranscript MVP v0.1

**Fonte de tarefas do projeto:** este arquivo na branch/ref efetivamente consultada; não duplicar em issues sem reconciliação. **Estado:** inventário inicial; evidência de execução do produto inexistente. [PRD](PRD.md) · [DESIGN](DESIGN.md) · [ROADMAP](ROADMAP.md) · [Checkpoint](PROJECT_STATE.md).

| ID | Marco | Resultado | Estado | Dependências | Aceite / requisitos | Evidência / validação | Branch / PR |
| --- | --- | --- | --- | --- | --- | --- | --- |
| T-001 | M0 | Consolidar requisitos e arquitetura em documentos recuperáveis. | implementada, validação remota pendente | nenhuma | PRD e DESIGN completos, links e decisões distintos | Rascunhos produzidos; confirmar leitura dos arquivos na ref final | docs/mvp-architecture-v0.1; PR pendente |
| T-002 | M0 | Especificar entrada/extração/importação, proveniência e falhas. | implementada, validação remota pendente | T-001 | REQ-001–003; fallback sem coleta e restrições explícitas | Contrato proposto em DESIGN; sem teste real | docs/mvp-architecture-v0.1; PR pendente |
| T-003 | M0 | Verificar contratos Groq (parâmetros, timestamps, tamanho, cotas). | pendente | T-001 | REQ-004–005; resposta real demonstrada com áudio autorizado | Sem chave, cota da conta ou chamada real | nenhum |
| T-004 | M1 | Instalar docs/entrada AGENTS, reconciliar fonte do protocolo e ref; preparar revisão. | em andamento | T-001, T-002 | Nove funções mapeadas, checkpoint vinculado, arquivos reabertos; protocolo aprovado ou limitação relatada | Repo main e4fe22d6 identificado; documentação de branch aguardando verificação final | docs/mvp-architecture-v0.1; PR pendente |
| T-005 | M1 | Implementar FastAPI, persistência e worker recuperável. | pendente | T-004 | REQ-008–010; teste de reinício e estados | Nenhum código/teste | nenhum |
| T-006 | M2 | Integrar importação, aquisição condicional, FFmpeg/Groq e chunks. | pendente | T-002,T-003,T-005 | REQ-001–005,REQ-011; segmentos/timestamps reais | Nenhum código/teste | nenhum |
| T-007 | M2 | Implementar extração/síntese e referências versionadas. | pendente | T-005,T-006 | REQ-006–009; refs pertencem à transcrição | Nenhum código/teste | nenhum |
| T-008 | M3 | Interface: URL/importação, jobs, biblioteca, busca e links válidos. | pendente | T-005,T-007 | REQ-001,007,010,012; E2E navegável | Nenhum código/teste | nenhum |
| T-009 | M3 | Testar integração, limites, recuperação e segurança. | pendente | T-006,T-007,T-008 | REQ-001–012; evidências na revisão exata | CI, E2E e merge não verificados | nenhum |

**Escopo:** REQ-001 a REQ-012 vinculados a tarefas acima; T-009 integra, mas não substitui aceites individuais. Estados documentais não são estados de implementação do aplicativo. Revisar estados e PR links após publicação, sem inventar sucesso de CI ou integração.
