# T-005 / T-010 — smoke test operacional de análise

**Status:** ferramenta proposta em `feat/t005-smoke-test` (PR empilhado sobre #8); a execução autenticada NÃO foi realizada por esta sessão. Consulte [TASKLIST](../TASKLIST.md), [checkpoint](../PROJECT_STATE.md) e [configuração local](T005_LOCAL_RUNTIME.md).

## Alcance

`python -m signaltranscript.backend.smoke` trabalha apenas com **transcrições importadas**, nunca baixa vídeos ou transcreve áudio. A entrada padrão é `examples/synthetic_transcript.json`, texto inventado e não sensível; não constitui vídeo real. O modo padrão valida o JSON com o mesmo esquema de entrada HTTP e com o contrato neutro `Transcript`; não abre conexões. Nenhum segredo vai para argumentos ou para arquivos versionados.

A opção `--submit` só funciona com **`--confirm-provider-upload` e `--expect-provider NOME`**. Antes de `POST /api/jobs`, o cliente consulta `GET /api/config` no endereço fixo `127.0.0.1` e exige o provedor esperado, modelo identificado e saída `SECTIONS_ONLY`. O servidor divulga somente nome/modelo/tipo, não chave. Um job é submetido uma vez; o cliente imprime seu ID e consulta estado/seções. Timeout, falha ou resultado remoto incerto **não provocam outro POST, resume ou fallback**.

A validação estrutural exige tarefa `COMPLETED`, seções íntegras/ordenadas, cobertura de todos os IDs na ordem original, mesmas identidades de provedor/modelo e referências apenas a IDs pertencentes à seção. Não verifica verdade factual, adequação semântica ou síntese global.

## Passos no Linux (na branch desta alteração)

No terminal do servidor, use ambiente virtual Python 3.12+ e instale: `python -m pip install -e '.[serve,groq]'`. Prepare um diretório privado: `mkdir -p "$HOME/.local/share/signaltranscript" && chmod 700 "$HOME/.local/share/signaltranscript"`. Configure `GROQ_API_KEY` **apenas no processo local** (por exemplo, `read -rsp 'Groq API key: ' GROQ_API_KEY; echo; export GROQ_API_KEY`), sem colá-la no chat ou GitHub. Inicie:

```bash
python -m signaltranscript.backend.serve --analysis-provider groq
```

Em outro terminal no mesmo checkout/venv, primeiro execute **sem rede**:

```bash
python -m signaltranscript.backend.smoke --transcript examples/synthetic_transcript.json
```

**Somente se você decidir consumir uma chamada da Groq e enviar esse conteúdo sintético**, execute:

```bash
python -m signaltranscript.backend.smoke --transcript examples/synthetic_transcript.json \
  --submit --confirm-provider-upload --expect-provider groq
```

O servidor deve permanecer restrito a `127.0.0.1` sem túnel, proxy público ou publicação de porta. O comando acima usa um exemplo criado para testes; para arquivo próprio, substitua `--transcript` apenas por material que você pode enviar ao provedor. Consulte regras de privacidade e quota da sua conta antes de executar.

Em caso de `POLL_TIMEOUT_JOB_ID_DO_NOT_RESUBMIT`, consulte o job existente com `GET /api/jobs/{id}`. Se o `POST` falhar antes de receber ID, o resultado é desconhecido; não repita automaticamente. `POST /api/jobs/{id}/resume` pertence à decisão explícita do usuário, pois a chamada anterior pode ter consumido recursos remotos. Nunca publicar chave, logs de SDK ou transcrições privadas.

## Evidências e limites

O CI testa cliente, rota de configuração e fluxo completo HTTP/SQLite com **provedor fake**; nenhuma chave é configurada, nenhum SDK Groq é instalado para a suíte e não há requisição externa. O funcionamento efetivo com GPT-OSS 120B, suas cotas e a qualidade da saída dependem de execução local autorizada e evidência separada. T-005/T-010 permanecem parciais, assim como T-003/T-006 e T-007; adoção do protocolo v2.2 permanece parcial enquanto a fonte editorial estiver STAGING. PR em Draft; sem merge ou deploy automático.
