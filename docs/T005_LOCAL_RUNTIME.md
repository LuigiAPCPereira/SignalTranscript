# T-005 / T-010 — Composição e execução local de análise

**Escopo:** complemento à [API local](T005_LOCAL_JOB_API.md), [TASKLIST](../TASKLIST.md) e [PROJECT_STATE](../PROJECT_STATE.md). Somente análise de **transcrições importadas**. A Groq é o primeiro provedor registrado na composição; `AnalysisProvider` e o núcleo permanecem neutros. Esta documentação não prova execução autenticada.

## Instalação e execução no Linux

Na branch deste PR (não na `main` ainda), criar um ambiente virtual Python 3.12+ e instalar `python -m pip install -e '.[serve,groq]'`. O extra `groq` instala somente o SDK de análise requerido quando Groq é escolhida; a suíte offline instala `.[test]` e não precisa do SDK ou de uma chave.

A chave `GROQ_API_KEY` deve estar disponível **somente no ambiente local do processo**; não passá-la por argumento CLI, URL, commit, logs ou frontend. Em Bash, uma opção para digitar sem eco/histórico é `read -rsp 'Groq API key: ' GROQ_API_KEY; echo; export GROQ_API_KEY`. Não persistir credenciais em arquivos versionados.

Iniciar explicitamente com `python -m signaltranscript.backend.serve --analysis-provider groq`. Opcionalmente `--data-dir /caminho/absoluto/privado` e `--port 8765`. O diretório existente precisa ser privado (`0700`) e não ser symlink; banco existente não pode ser symlink nem legível por grupo/outros (`0600`). Arquivos novos são criados sob `umask 077`. O servidor usa **somente 127.0.0.1**, um processo, sem reload, headers de proxy ou access logs; não é um serviço autenticado para publicação em rede ou exposição via túnel.

## API mínima

`POST http://127.0.0.1:8765/api/jobs` com `Content-Type: application/json` e corpo conforme abaixo; ele envia a transcrição escolhida ao provedor explicitamente configurado assim que o worker a processar, podendo consumir cota. Não executar esse POST de exemplo sem desejar uma chamada remota:

```json
{"video_id":"video-autorizado","source":"manual_import","language":"pt","segments":[{"id":"seg-1","text":"Texto transcrito com permissão.","start_ms":0,"end_ms":1000}]}
```

Consultar `GET /api/jobs/{id}` e `GET /api/jobs/{id}/sections`. Se houver falha/interrupção, `POST /api/jobs/{id}/resume` é ato explícito: um timeout pode ter consumido recursos remotos. O resultado é `SECTIONS_ONLY`, nunca uma síntese global. Não há endpoints de aquisição de URL/áudio ou transcrição neste recorte.

## Garantias e pendências

- O registro contém nome/modelo/revisão/orçamento. A revisão Groq é um SHA-256 do modelo, prompt, schema, limite de saída e modo estruturado. Alterações semânticas na lógica do adaptador que não estejam nesse material exigem revisão explícita do contrato; o hash não detecta tudo.
- Jobs enfileirados com configuração diferente da instância atual são interrompidos **antes de chamar o provedor**, sem fallback. Checkpoints concluídos só são reutilizados quando a identidade e a transcrição/plano conferem.
- O cliente do provedor é fechado no shutdown do FastAPI. Isso não garante cancelamento remoto nem execução exatamente uma vez.
- Groq real, limites da conta, qualidade da análise, privacidade operacional, modelo local/NIM, backup/migração, cancelamento HTTP, aquisição e ponta a ponta com vídeo continuam não validados. T-005 e T-010 permanecem parciais; adoção documental v2.2 permanece parcial enquanto a fonte central estiver STAGING.

## Verificação

`python -m pip install -e '.[test]'`; `python -m compileall -q src tests`; `python -m unittest discover -s tests -v`. Os testes `test_local_serve.py` usam injeção de fake e não fazem rede. Confirmar CI no HEAD final do PR; um CI anterior não valida commits posteriores.
