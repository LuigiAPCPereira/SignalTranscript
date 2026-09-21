# T-006 — Primeira fatia: importação local de legendas SRT/WebVTT

**Estado:** conversão local implementada na branch `feat/t006-caption-import`, dependente do PR #9. A execução real com vídeo, aquisição, download, STT Groq, interface e biblioteca continuam pendentes. [TASKLIST](../TASKLIST.md) · [PRD](../PRD.md) · [DESIGN](../DESIGN.md) · [teste operacional](T005_SMOKE_TEST.md).

## Fluxo reproduzível no Linux

Na branch deste PR, use uma legenda `.srt` ou `.vtt` **já obtida de forma permitida**. Nenhum vídeo é baixado e nenhuma API é consultada por este conversor. A aplicação não verifica direitos de uso, identidade do vídeo nem correspondência da legenda ao áudio. O `video_id` deve ser informado conscientemente pelo usuário; ele não é extraído/verificado do arquivo.

```bash
python -m pip install -e '.[test]'
mkdir -p "$HOME/.local/share/signaltranscript"
chmod 700 "$HOME/.local/share/signaltranscript"
python -m signaltranscript.backend.caption_import \
  --input "/caminho/para/legenda.vtt" \
  --video-id "id-do-video" --language pt-BR \
  --output "$HOME/.local/share/signaltranscript/transcricao-importada.json"
python -m signaltranscript.backend.smoke \
  --transcript "$HOME/.local/share/signaltranscript/transcricao-importada.json"
```

A última chamada é apenas pré-validação local, sem HTTP/IA. O JSON resultante é compatível com a entrada `ImportInput` de `POST /api/jobs` e com o cliente do PR #9. Para uso remoto **separadamente autorizado**, seguir as opções explícitas e instruções de segurança em [T005_SMOKE_TEST](T005_SMOKE_TEST.md). Não executar `--submit` sem consentir no envio da transcrição a um provedor e possível consumo de cota. A chave da Groq permanece somente no ambiente local do servidor, nunca no JSON, CLI, repositório ou chat.

## Contrato e limites

- Suporta cues simples de SRT (`HH:MM:SS,mmm`) e WebVTT (`MM:SS.mmm` ou `HH:MM:SS.mmm`), UTF-8/BOM, texto multilinha e configurações de posicionamento VTT conhecidas. Produz `manual_import`, IDs sequenciais estáveis por posição e intervalos em milissegundos **copiados do arquivo**, não verificados contra o vídeo.
- Mantém cues simultâneos/sobrepostos sem deduplicar, preserva marcação inline de texto como `<c>` e desconsidera blocos não falados `NOTE`/`STYLE`/`REGION`. Não faz limpeza de tags, tradução, correção de legenda, transcrição de áudio nem sincronização.
- Rejeita entrada vazia, timestamps inválidos ou regressivos, cues malformados, symlink de entrada, extensões desconhecidas, arquivo/JSON acima de 512.000 bytes, mais de 4.096 cues e cue acima de 12.000 caracteres. WebVTT com `X-TIMESTAMP-MAP`/timebase especial é recusado em vez de fabricar offset. Não faz truncamento silencioso.
- Exige diretório de saída existente, absoluto e privado (sem acesso a grupo/outros), cria JSON `0600` e nunca sobrescreve destino existente. Só imprime quantidade de segmentos e códigos seguros, não o conteúdo da legenda.
- Proveniência `manual_import` significa importação fornecida pelo usuário, **não** legenda oficial/manual da plataforma; faltam metadados completos de trilha/licença/hash e verificação do timebase. Links temporais só poderão ser considerados após conferir a origem do vídeo e a correspondência dos tempos.

## Verificação e lacunas

`python -m compileall -q src tests`; `python -m unittest discover -s tests -v`. `tests/test_caption_import.py` cobre parsing, fronteira HTTP/domínio, limites, integridade de tempos, arquivo privado, ausência de overwrite e CLI. A validação estática isolada não substitui CI no HEAD do PR. **T-006 permanece parcial:** faltam aquisição legalmente permitida, upload de áudio, Groq autenticada, tratamento de chunks, proveniência completa e integração E2E. T-004/protocolo continua em ADOÇÃO PARCIAL enquanto a fonte editorial v2.2 estiver STAGING.
