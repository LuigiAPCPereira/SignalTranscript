# T-006 — Importação local, manifesto e proveniência persistente

**Estado:** T-006 permanece **PARCIAL** na branch `feat/t006-caption-import`, PR #10 sobre #9. O fluxo implementado cobre SRT/WebVTT fornecido pelo usuário, manifesto local de integridade v2, passagem opcional pelo smoke, validação HTTP e persistência SQLite. Não cobre aquisição do YouTube, comprovação de direitos, identidade/sincronização real do vídeo, áudio/FFmpeg, STT real ou E2E completo. [TASKLIST](../TASKLIST.md) · [PRD](../PRD.md) · [DESIGN](../DESIGN.md).

## Fluxo reproduzível no Linux

Use uma legenda `.srt` ou `.vtt` **já obtida de forma permitida**. Nenhum vídeo é baixado e nenhuma API é consultada pelos passos de importação/evidência.

```bash
python -m pip install -e '.[test]'
mkdir -p "$HOME/.local/share/signaltranscript"
chmod 700 "$HOME/.local/share/signaltranscript"

python -m signaltranscript.backend.caption_import \
  --input "/caminho/para/legenda.vtt" \
  --video-id "id-declarado-do-video" --language pt-BR \
  --output "$HOME/.local/share/signaltranscript/transcricao-importada.json"

python -m signaltranscript.backend.caption_evidence create \
  --caption "/caminho/para/legenda.vtt" \
  --transcript "$HOME/.local/share/signaltranscript/transcricao-importada.json" \
  --manifest "$HOME/.local/share/signaltranscript/legenda-evidence.json"

python -m signaltranscript.backend.caption_evidence verify \
  --caption "/caminho/para/legenda.vtt" \
  --transcript "$HOME/.local/share/signaltranscript/transcricao-importada.json" \
  --manifest "$HOME/.local/share/signaltranscript/legenda-evidence.json"

python -m signaltranscript.backend.smoke \
  --transcript "$HOME/.local/share/signaltranscript/transcricao-importada.json" \
  --evidence "$HOME/.local/share/signaltranscript/legenda-evidence.json"
```

A última chamada é somente pré-validação local enquanto `--submit` não for informado. O smoke confere o hash canônico da transcrição e o manifesto **antes de qualquer HTTP**. Envio para um provedor continua uma operação separada, opt-in, com as proteções de [T005_SMOKE_TEST](T005_SMOKE_TEST.md).

## Contrato do manifesto v2

O manifesto contém SHA-256 dos bytes da legenda, SHA-256 dos bytes do JSON importado e `transcript_content_sha256`, calculado sobre o contrato canônico `video_id/source/language/segments` com serialização determinística. O hash canônico permite que a API confirme que o manifesto apresentado corresponde ao conteúdo da transcrição mesmo que espaçamento/ordem das chaves do arquivo JSON sejam diferentes.

Os estados são deliberadamente restritos:

- `authorization_status = UNVERIFIED`;
- `video_identity_status = UNVERIFIED`;
- `timeline_match_status = UNVERIFIED`;
- `deep_links_allowed = false`.

A API rejeita estados `VERIFIED` autodeclarados, `video_id` diferente, hash canônico divergente, esquema/campos inesperados e manifesto de origem incompatível. Isso **não comprova** o hash da legenda no servidor, porque a legenda não é enviada à API; ele permanece evidência sidecar fornecida pelo usuário.

## Persistência e respostas HTTP

`POST /api/jobs` aceita o campo opcional `evidence`. Se presente, ele é validado antes de enfileirar o job e persistido em `jobs.evidence_json`. `SQLiteJobs.initialize()` adiciona a coluna a bancos antigos que ainda não a possuam.

`GET /api/jobs/{id}` e `GET /api/jobs/{id}/sections` devolvem somente o estado seguro de proveniência — presença/esquema, os três estados `UNVERIFIED` e `deep_links_allowed=false` — sem expor hashes desnecessariamente. Importações sem manifesto também permanecem não verificadas e com deep links desabilitados.

O smoke verifica esse estado na criação, durante polling e no resultado de seções. Um sidecar adulterado ou uma transcrição alterada depois da criação do manifesto falha antes do POST.

## Parser e limites da legenda

- SRT `HH:MM:SS,mmm` e WebVTT `MM:SS.mmm`/`HH:MM:SS.mmm`, UTF-8/BOM, texto multilinha e settings VTT conhecidos.
- Tempos são copiados do arquivo; cues simultâneos/sobrepostos são mantidos; não há deduplicação, tradução ou sincronização.
- Entrada vazia, timestamps regressivos/inválidos, cue malformado, symlink, formato desconhecido, mais de 4.096 cues, cue acima de 12.000 caracteres, arquivo/JSON acima de 512.000 bytes e WebVTT com timebase especial são rejeitados.
- Saídas ficam em diretório privado, arquivos `0600`, sem overwrite.

## Evidência de validação e lacunas

A revisão de integração `4d39b441094afece691854654829e18953e6c25f` passou no GitHub Actions em Python 3.12 e 3.13; o log Python 3.13 registrou **129 testes PASS**. Houve uma revisão anterior do novo smoke que falhou porque o teste incluiu o campo opcional `evidence=None` no cálculo do hash canônico; a causa foi identificada e corrigida antes desta validação.

T-006 continua parcial: não existe critério implementado que transforme `UNVERIFIED` em `VERIFIED`. Portanto, **nenhum deep link temporal deve ser criado a partir de importação manual nesta fase**. Permanecem pendentes aquisição permitida, validação real de identidade/sincronia, áudio/FFmpeg/chunks, Groq autenticada ou outro STT real, frontend/biblioteca e E2E. O protocolo do projeto continua em ADOÇÃO PARCIAL enquanto a fonte canônica aprovada/equivalência não estiver comprovada.
