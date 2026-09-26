# T-005 / T-010 — Composição e execução local de análise

**Escopo:** complemento à [API local](T005_LOCAL_JOB_API.md), [TASKLIST](../TASKLIST.md) e [PROJECT_STATE](../PROJECT_STATE.md). Somente análise de **transcrições importadas**. A Groq é o primeiro provedor registrado na composição; `AnalysisProvider` e o núcleo permanecem neutros. Esta documentação não prova execução autenticada.

## Instalação e execução no Linux

Na branch deste PR (não na `main` ainda), criar um ambiente virtual Python 3.12+ e instalar `python -m pip install -e '.[serve,groq]'`. O extra `groq` instala somente o SDK de análise requerido quando Groq é escolhida; a suíte offline instala `.[test]` e não precisa do SDK ou de uma chave.

A chave `GROQ_API_KEY` deve estar disponível **somente no ambiente local do processo**; não passá-la por argumento CLI, URL, commit, logs ou frontend. Em Bash, uma opção para digitar sem eco/histórico é `read -rsp 'Groq API key: ' GROQ_API_KEY; echo; export GROQ_API_KEY`. Não persistir credenciais em arquivos versionados.

Iniciar explicitamente com `python -m signaltranscript.backend.serve --analysis-provider groq`. A síntese global fica **desabilitada por padrão**; para registrá-la separadamente, acrescentar `--synthesis-provider groq`. Opcionalmente `--data-dir /caminho/absoluto/privado` e `--port 8765`. O diretório existente precisa ser privado (`0700`) e não ser symlink; banco existente não pode ser symlink nem legível por grupo/outros (`0600`). Arquivos novos são criados sob `umask 077`. O servidor usa **somente 127.0.0.1**, um processo, sem reload, headers de proxy ou access logs; não é um serviço autenticado para publicação em rede ou exposição via túnel.

## API mínima

`POST http://127.0.0.1:8765/api/jobs` com `Content-Type: application/json` e corpo conforme abaixo; ele envia a transcrição escolhida ao provedor explicitamente configurado assim que o worker a processar, podendo consumir cota. Não executar esse POST de exemplo sem desejar uma chamada remota:

```json
{"video_id":"video-autorizado","source":"manual_import","language":"pt","segments":[{"id":"seg-1","text":"Texto transcrito com permissão.","start_ms":0,"end_ms":1000}]}
```

Consultar `GET /api/jobs/{id}` e `GET /api/jobs/{id}/sections`. Se houver falha/interrupção, `POST /api/jobs/{id}/resume` é ato explícito: um timeout pode ter consumido recursos remotos. A conclusão automática do worker continua sendo `SECTIONS_ONLY`.

Se `--synthesis-provider` foi escolhido explicitamente, `POST /api/jobs/{id}/synthesis` inicia a síntese global após as seções completas. Essa é uma segunda operação potencialmente remota e pode consumir cota; não é chamada pelo worker nem pelo GET. Repetição idêntica reutiliza checkpoint validado. Um resultado remoto desconhecido não gera retry automático. Não há endpoints de aquisição de URL/áudio ou transcrição neste recorte.

## Backup e recovery staging offline

O caminho de recuperação é deliberadamente **não destrutivo**: ele nunca substitui automaticamente o banco ativo. Primeiro crie/inspecione um snapshot pelas primitivas de `signaltranscript.backend.backup`; para preparar uma recuperação, escolha um **novo** caminho de destino e execute:

```bash
python -m signaltranscript.backend.recovery \
  --snapshot /caminho/backup.db \
  --destination /caminho/restored-staging.db \
  --expect-sha256 SHA256_DO_SNAPSHOT \
  --receipt-out /caminho/restored-staging.receipt.json
```

A operação inspeciona a origem, fixa sua identidade por SHA-256, restaura para o novo banco usando o caminho SQLite verificado e só então emite um `RecoveryReceipt` schema v1. O receipt registra hashes da origem/destino, tamanho e metadados SQLite; quando persistido, usa arquivo privado `0600`, criação exclusiva e não segue symlink quando a plataforma oferece `O_NOFOLLOW`. Se a persistência do receipt falhar, o CLI tenta remover o banco staging criado por aquela invocação em vez de reportar sucesso parcial.

Para auditar posteriormente o mesmo par sem modificá-lo:

```bash
python -m signaltranscript.backend.recovery \
  --snapshot /caminho/backup.db \
  --destination /caminho/restored-staging.db \
  --verify-receipt /caminho/restored-staging.receipt.json
```

A leitura do receipt aceita somente arquivo regular pequeno, schema exato e versão conhecida; hashes/metadados impossíveis, versão futura, symlink, conteúdo excessivo ou divergência dos artefatos falham fechado. O comando de recovery **não é cutover**: não troca o banco usado pelo servidor, não sobrescreve destino, não implementa retenção/rotação, rollback de cutover nem política completa de disaster recovery. A decisão de substituir dados ativos permanece fora desta ferramenta.

## Garantias e pendências

- Análise por seção e síntese têm registros/revisões separados. A revisão de análise cobre seu modelo/prompt/schema; a revisão de síntese cobre modelo, prompt, schema, limite local, limite de saída, política de seleção de evidências e modo estruturado. Alterações semânticas fora desse material ainda exigem revisão explícita.
- Jobs enfileirados com configuração diferente da instância atual são interrompidos **antes de chamar o provedor**, sem fallback. Checkpoints concluídos só são reutilizados quando a identidade e a transcrição/plano conferem.
- O cliente do provedor é fechado no shutdown do FastAPI. Isso não garante cancelamento remoto nem execução exatamente uma vez.
- Groq real, limites da conta, qualidade da análise/síntese, privacidade operacional, modelo local/NIM, cutover/rollback de recuperação, retenção, cancelamento remoto, aquisição e ponta a ponta com vídeo continuam não validados. T-005 e T-010 permanecem parciais; adoção documental v2.2 permanece parcial enquanto a fonte central aprovada não estiver acessível.

## Verificação

`python -m pip install -e '.[test]'`; `python -m compileall -q src tests`; `python -m unittest discover -s tests -v`. Os testes de runtime/smoke/recovery são offline e não fazem chamada autenticada à Groq. O checkpoint de recovery no SHA `ec627014fe5e038cc74e5fc8d09516dd3e62d26a` passou no GitHub Actions 35989071501. O adaptador/composição de síntese no SHA `1d78f93a52fbef6817374fd10ac7692d0901bcd5` passou no Actions **36245879695**, Python 3.12/3.13, com **227 testes** no log 3.13. Confirmar CI novamente no HEAD final do PR; um CI anterior não valida commits posteriores.
