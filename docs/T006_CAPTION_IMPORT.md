# T-006 — Importação local SRT/WebVTT e manifesto de integridade

**Estado:** importação de legenda e manifesto local implementados na branch `feat/t006-caption-import`, PR #10 empilhado sobre #9; **T-006 PARCIAL**. O trabalho não baixa vídeo, não transcreve áudio, não chama IA, não comprova licença, identidade do vídeo ou sincronização, e não produz links temporais. [TASKLIST](../TASKLIST.md) · [PRD](../PRD.md) · [DESIGN](../DESIGN.md) · [teste operacional](T005_SMOKE_TEST.md).

## Fluxo reproduzível no Linux — sem rede

Use uma legenda `.srt` ou `.vtt` já obtida de forma permitida. O `video_id` é apenas uma declaração do usuário; o arquivo não traz prova de que pertence a esse vídeo. Não inclua material confidencial em diretórios públicos.

```bash
python -m pip install -e '.[test]'
mkdir -p "$HOME/.local/share/signaltranscript"
chmod 700 "$HOME/.local/share/signaltranscript"

python -m signaltranscript.backend.caption_import \
  --input "/caminho/para/legenda.vtt" \
  --video-id "id-declarado-pelo-usuario" --language pt-BR \
  --output "$HOME/.local/share/signaltranscript/transcricao-importada.json"

python -m signaltranscript.backend.caption_evidence create \
  --caption "/caminho/para/legenda.vtt" \
  --transcript "$HOME/.local/share/signaltranscript/transcricao-importada.json" \
  --manifest "$HOME/.local/share/signaltranscript/evidencia.json"

python -m signaltranscript.backend.caption_evidence verify \
  --caption "/caminho/para/legenda.vtt" \
  --transcript "$HOME/.local/share/signaltranscript/transcricao-importada.json" \
  --manifest "$HOME/.local/share/signaltranscript/evidencia.json"

python -m signaltranscript.backend.smoke \
  --transcript "$HOME/.local/share/signaltranscript/transcricao-importada.json"
```

A última chamada é pré-validação local, sem HTTP/IA. Para eventual envio **separadamente autorizado**, consulte [T005_SMOKE_TEST](T005_SMOKE_TEST.md); `--submit` exige confirmação expressa e pode consumir cota. A chave Groq só pertence ao ambiente do servidor, nunca ao JSON, manifesto, repositório ou chat.

## Contratos e interpretações

O importador suporta cues simples de SRT (`HH:MM:SS,mmm`) e WebVTT (`MM:SS.mmm` ou `HH:MM:SS.mmm`), UTF-8/BOM, texto multilinha e configurações de posicionamento VTT conhecidas. Produz `source=manual_import`, IDs por posição e milissegundos copiados do arquivo. Preserva cues simultâneos/sobrepostos, não corrige áudio ou sincronização e rejeita timebase especial `X-TIMESTAMP-MAP`, timestamps inválidos, symlinks de entrada, arquivos/JSON acima de 512.000 bytes, mais de 4.096 cues e textos individuais acima de 12.000 caracteres. A saída é criada exclusivamente (`0600`) em diretório existente privado (`0700`); nenhuma sobrescrita.

O manifesto separado tem `schema_version=1`, `source_kind=user_supplied_caption`, formato da legenda, SHA-256 dos **bytes exatos** da legenda e do JSON, `declared_video_id`, e estados invariáveis `authorization_status=UNVERIFIED`, `video_identity_status=UNVERIFIED`, `timeline_match_status=UNVERIFIED`, `deep_links_allowed=false`. A criação reconverte a legenda e exige igualdade exata com o JSON importado; a verificação refaz essa checagem, compara hashes e rejeita campos adicionais ou estados falsamente promovidos. Não são gravados caminhos locais ou textos de legenda no manifesto.

**O que se comprova:** este par de arquivos corresponde à conversão local e não mudou desde a criação do manifesto, sob a suposição de que manifesto e arquivos não foram todos substituídos por um mesmo agente. Hash não é assinatura, prova de autoria, autorização de uso, identidade do vídeo ou prova de sincronização. `video_id` não é extraído da fonte; horários são relativos à legenda e não estão confirmados contra o vídeo. A referência de uma ideia a um segmento da transcrição também não prova factualidade externa.

**Limite de integração:** o manifesto é um artefato **local e separado**; a atual `ImportInput`, o banco SQLite e o smoke do PR #9 **não persistem nem verificam esse manifesto**. Portanto, não adicionar campos extras ao JSON esperando que a API os conserve; não derivar links YouTube do ID ou dos timestamps importados. O manifesto e a legenda original precisam ser preservados junto ao JSON; verificar antes de reutilizar. Integrar a proveniência ao domínio, à persistência e a uma futura política de habilitação de deep links requer trabalho separado com migração e testes ponta a ponta.

## Verificação e limites restantes

`python -m compileall -q src tests` e `python -m unittest discover -s tests -v` são executados no CI. Testes do importador cobrem formato, limites, privacidade e contrato HTTP; `tests/test_caption_evidence.py` cobre hashes e igualdade da conversão, mutações da legenda/JSON, falsificação de status, symlinks, sobrescrita e CLI offline. Conferir a execução de CI do **HEAD exato** após mudanças documentais. **T-006 continua PARCIAL:** vídeo real e proveniência certificada, ingestão persistente de evidências, aquisição permitida, áudio/FFmpeg, transcrição real/chunks e E2E ainda não foram executados. T-004 e a adoção do protocolo permanecem parciais enquanto a autoridade aprovada e equivalência da fonte não estiverem certificadas.
