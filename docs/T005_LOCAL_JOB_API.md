# T-005 — API local, journal e worker recuperável

**Estado:** implementação **PARCIAL** na pilha de PRs Draft, com incremento atual no PR #10. A `main` não contém estas funcionalidades. [TASKLIST](../TASKLIST.md) · [Checkpoint](../PROJECT_STATE.md) · [Arquitetura](../DESIGN.md) · [Runtime](T005_LOCAL_RUNTIME.md).

## Journal SQLite e ordenação

`backend/jobs.py` persiste jobs e a transcrição importada em SQLite/WAL. O schema atual é **v3**. `created_seq` é uma sequência monotônica persistida:

- jobs novos recebem `MAX(created_seq)+1` dentro de `BEGIN IMMEDIATE`;
- migração de bancos compatíveis antigos atribui uma sequência uma única vez, usando `rowid` apenas como ordem de migração;
- depois da migração, nenhum contrato de API/worker depende de `rowid`;
- índice único protege a sequência;
- o worker reivindica `QUEUED` em `created_seq ASC` (FIFO);
- listagem usa `created_seq DESC` (mais recentes primeiro).

O journal continua fail-closed para schema futuro/incompatível e integridade SQLite inválida. Backup/recovery staging e recibos estão documentados separadamente em [T005_RECOVERY](T005_RECOVERY.md).

## API implementada nesta branch

A aplicação é local, bindada em `127.0.0.1` pelo composition root e sem autenticação para exposição pública. Não usar túnel/rede externa.

Operações atuais:

- `POST /api/jobs` — registra **transcrição importada**, não URL/áudio;
- `GET /api/jobs?limit=20&before=N` — lista journal newest-first, `limit` 1–50;
- `GET /api/jobs/{id}` — estado/progresso;
- `GET /api/jobs/{id}/sections` — resultado por seções;
- `POST /api/jobs/{id}/resume` — retomada explícita;
- `POST /api/jobs/{id}/cancel` — cancelamento conservador; não declara cancelamento remoto de trabalho `RUNNING`;
- `POST /api/jobs/{id}/synthesis` — síntese global explícita quando provider está configurado;
- `GET /api/jobs/{id}/synthesis` — leitura histórica read-only, independente da configuração atual de provider.

A listagem devolve metadados seguros do job, proveniência e:

```json
{
  "artifacts": {
    "sections_present": true,
    "synthesis_present": false
  }
}
```

Esses campos significam **presença física**, não integridade validada. Abrir seções/síntese usa os endpoints específicos, que revalidam checkpoints. A listagem não devolve texto da transcrição, não abre artefatos e não chama IA.

Paginação retorna `next_before`; quando `null`, não há página seguinte naquele snapshot lógico.

## Worker e recovery

Existe um único executor local por banco, protegido por `flock`. Não há lease multiworker nem suporte a `uvicorn --workers N`.

Ao iniciar, jobs `RUNNING` antigos viram `INTERRUPTED/REMOTE_OUTCOME_UNKNOWN`, sem retransmissão automática. Jobs enfileirados só executam quando provider/model/revision/orçamento coincidem com a instância. Retomada manual exige configuração idêntica para análise por seção.

Nenhuma transação SQLite permanece aberta durante chamadas de IA. Resultado remoto desconhecido nunca vira sucesso presumido.

Síntese histórica é diferente de nova inferência: o GET usa provider/model/revision gravados com o checkpoint e continua legível após restart sem provider de síntese; o POST continua exigindo provider atual explicitamente configurado.

## Evidência

A primeira revisão desta fatia, `7d090ddd5e7a24689ad188191e514d5a864d2932`, compilou mas o CI falhou por um `json` ausente **no fixture de migração do teste**, antes de exercitar o cenário. O teste foi corrigido sem mudança de contrato.

SHA validado: `c65353714f1204a164407a0130c9521ca91ceddc`. GitHub Actions **36257023821**: PASS Python 3.12 e 3.13; **240 testes PASS**. A suíte é offline e não usa credenciais/provedores externos.

## Limites

T-005 continua parcial. Não há ainda entidade completa de biblioteca/vídeo, busca textual, frontend, aquisição YouTube/áudio, STT E2E, autenticação para serviço público ou multiworker. A listagem de jobs é uma boundary para T-008, não uma implementação de T-008.

Nenhuma chamada Groq autenticada, merge ou deploy foi realizada nesta fatia.
