# Adoção do Agent Development Protocol — SignalTranscript

**Projeto/ref verificada:** `LuigiAPCPereira/SignalTranscript` · `feat/t006-caption-import` / PR #10 Draft  
**Modo:** Aplicar — autorizado pelo usuário em 2026-09-26 ao pedir correção do estado “ADOÇÃO PARCIAL” e continuidade do desenvolvimento.  
**Resultado:** **ADOÇÃO CONCLUÍDA NA REF DE TRABALHO**  
**Integração:** `main` ainda não contém esta adoção; merge/deploy não foram autorizados nem realizados.  
**Fonte/versão:** Agent Development Protocol / Documentation & Continuity Protocol v2.2; evidência em [PROTOCOL_SOURCE.md](PROTOCOL_SOURCE.md).  
**Acesso indisponível/separado:** publicação central Notion continua STAGING; acesso de Codex não foi testado nesta aplicação; o agendamento SignalTranscript foi observado desabilitado.

## Resumo executivo

O diagnóstico antigo confundia o **Publication Gate da distribuição central** com o **Adoption Gate do SignalTranscript** e ainda descrevia o estado dos PRs #1/#2. O v2.2 exige separar distribuição, adoção por projeto e operação integrada. A cópia do protocolo usada no Project foi verificada por SHA-256 contra o hash de origem registrado no manifesto central; depois de reconciliar documentos vivos, TASKLIST, checkpoint e instruções, as nove funções aplicáveis possuem fonte verificável e nenhuma permanece pendente para o Adoption Gate desta ref.

Isso **não** significa produto concluído, PR mesclado, Groq real validada, central Notion publicada ou agendamento ativo.

## Adoption Gate v2 — matriz de nove funções

| Função | Fonte/evidência na ref | Estado | Lacuna/ação |
| --- | --- | --- | --- |
| 1. Identidade e visão | [README](../README.md) + [PRD](../PRD.md): objetivo generalista, público, limites, estado da branch/main | **EXISTENTE E VERIFICADA** | Preservar; produto segue parcial. |
| 2. Requisitos e aceites | [PRD](../PRD.md), REQ-001–013 com critérios verificáveis e pendências | **EXISTENTE E VERIFICADA** | Aceites de produto ainda podem estar pendentes sem bloquear cobertura documental. |
| 3. Arquitetura e contratos | [DESIGN](../DESIGN.md), docs T-003/T-005/T-006/T-007/T-010 e código de portas/adaptadores | **EXISTENTE E VERIFICADA** | Arquitetura distingue implementado offline de pendente/remoto. |
| 4. Decisões duráveis | [ADR-001](adr/ADR-001-python-fastapi.md) e [ADR-002](adr/ADR-002-provider-independence.md) | **EXISTENTE E VERIFICADA** | Não fabricar ADR para decisões ainda abertas. |
| 5. Inventário de tarefas | [TASKLIST](../TASKLIST.md), T-001–T-010 com marco, resultado, estado, dependências, aceite, evidência e PR | **EXISTENTE E VERIFICADA** | É o inventário canônico; não existe tracker concorrente. |
| 6. Planejamento e marcos | [ROADMAP](../ROADMAP.md), M0–M3 reconciliados ao estado atual e sem datas fictícias | **EXISTENTE E VERIFICADA** | Atualizar por mudança de marco, não por ritual. |
| 7. Histórico recuperável | [SESSION_LOG](../SESSION_LOG.md) + PRs/commits reais; marcos de 20/09 e 26/09 preservam decisões/incidentes | **EXISTENTE E VERIFICADA** | Commits/PR complementam, não substituem contexto durável. |
| 8. Estado e próxima ação | [PROJECT_STATE](../PROJECT_STATE.md) vinculado a T-004/T-005/T-006/T-007/T-010, branch/PR, evidências, bloqueios e próxima ação | **EXISTENTE E VERIFICADA** | Snapshot derivado; revalidar HEAD em cada execução. |
| 9. Instruções e protocolo | [AGENTS](../AGENTS.md) + [PROTOCOL_SOURCE](PROTOCOL_SOURCE.md). Protocolo Project SHA-256 `7e64d070…39213` = hash de origem do manifesto central | **EXISTENTE E VERIFICADA** | Notion STAGING é distribuição separada; hosts sem Project devem declarar acesso externo indisponível. |

## Integridade e fonte do protocolo

- `DOCUMENTATION_AND_CONTINUITY.md` v2.2 lido no Project: 37.930 bytes; SHA-256 `7e64d070e7ed419b225a92edb4a17ac4ff7d63f9c2bec22e35b47188d2639213`.
- Manifesto central Notion v2.2 reaberto nesta aplicação registra exatamente o mesmo tamanho/hash para o arquivo-fonte.
- `ENGINEERING_DNA.md` local: SHA-256 `c19c5d97f8e42b311d6c15440e2e9f58cec64fadf1a48b9575e1f2e4dba0e373`, também igual ao hash de origem do manifesto.
- A central continua **STAGING / Publication Gate não aprovado**. Pelo próprio protocolo §17.2, isso não é o mesmo estado que o Adoption Gate de um projeto.
- `AGENTS.md` não inventa permissões; merge/deploy/custos/segredos continuam sujeitos a autorização.
- TASKLIST permanece autoridade única de tarefas; ROADMAP e PROJECT_STATE não a substituem.
- Checkpoint aponta para IDs existentes e separa implementação, validação, integração e deploy.

## Alterações desta aplicação

**Criado:** [PROTOCOL_SOURCE.md](PROTOCOL_SOURCE.md), registro de fonte/versionamento e hashes, sem duplicar o texto normativo.

**Reconciliados:** AGENTS, README, PRD (estado), DESIGN (implementado versus pendente), ROADMAP, SESSION_LOG, TASKLIST, PROJECT_STATE, este relatório e docs T-005/T-007.

**Preservados:** requisitos REQ-001–013, ADRs, histórico anterior, pilha de PRs Draft, decisões de independência de provedores.

## Produto e validação — separados da adoção

Adoção documental concluída não conclui o MVP. No bloco técnico imediatamente anterior, `GET /api/jobs/{id}/synthesis` e `--check-synthesis-job` foram implementados; a primeira revisão `488e31df` falhou em um teste de injeção do smoke, corrigido em `e6c159777f12c8f51a9ee085c07e5e1b062ba8a6`. GitHub Actions **36255131808** passou em Python 3.12 e 3.13, **234 testes** em cada log.

Groq autenticada, aquisição real, frontend, qualidade semântica e E2E continuam pendentes. PR #10 segue Draft; `main` permanece separada. Nenhum merge/deploy foi realizado.

## Gate e idempotência

- Nove funções: **9/9 verificadas**.
- TASKLIST ou equivalente: **TASKLIST.md verificado**.
- Checkpoint ligado a tarefa ID: **confirmado**.
- Fonte/versionamento do protocolo: **confirmados por hash de origem**.
- Duas autoridades concorrentes: **não identificadas**; `PROTOCOL_SOURCE.md` é pin/proveniência, não segunda especificação.
- Alterações limitadas à autorização: **sim**; correção documental + continuidade técnica solicitadas pelo usuário.
- Publication Gate central: **STAGING**, explicitamente fora do denominador do Adoption Gate do projeto.
- Operação agendada: **não ativa** na observação atual; isso não altera o resultado documental.

**Resultado final inequívoco: ADOÇÃO CONCLUÍDA NA REF DE TRABALHO.**

Próxima ação documental: nenhuma lacuna impeditiva do Adoption Gate. Próxima ação de produto deve vir do TASKLIST/PROJECT_STATE. Integração em `main`, publicação central e reativação de automação são ações distintas e não foram executadas.
