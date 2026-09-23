# T-006 — Importação local, manifesto e proveniência persistente

**Estado:** T-006 permanece **PARCIAL** na branch `feat/t006-caption-import`, PR #10 sobre #9. O fluxo implementado cobre SRT/WebVTT fornecido pelo usuário, manifesto local de integridade v2, passagem opcional pelo smoke, validação HTTP e persistência SQLite. A API local agora também pode reprocessar o texto exato da legenda submetida e verificar que seus cues/timestamps correspondem exatamente à transcrição importada. Isso **não** cobre aquisição do YouTube, comprovação de direitos, identidade/sincronização com o vídeo real, áudio/FFmpeg, STT real ou E2E completo. [TASKLIST](../TASKLIST.md) · [PRD](../PRD.md) · [DESIGN](../DESIGN.md).

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

O manifesto criado pelo usuário continua deliberadamente restrito:

- `authorization_status = UNVERIFIED`;
- `video_identity_status = UNVERIFIED`;
- `timeline_match_status = UNVERIFIED`;
- `deep_links_allowed = false`.

A API rejeita qualquer `VERIFIED` **recebido no manifesto**. `video_id` diferente, hash canônico divergente, esquema/campos inesperados e manifesto de origem incompatível também falham.

### Verificação server-side limitada da timeline da legenda

`POST /api/jobs` aceita opcionalmente `caption_verification = {"format": "srt|vtt", "text": "..."}` **somente junto do manifesto**. Nesse caminho, o backend:

1. valida o manifesto ainda com todos os estados `UNVERIFIED`;
2. recalcula SHA-256 dos bytes UTF-8 da legenda submetida e exige igualdade com `caption_sha256`;
3. reprocessa SRT/WebVTT com o mesmo parser limitado da importação;
4. exige igualdade exata de `video_id`, `source`, `language`, IDs, texto e timestamps com a transcrição submetida;
5. somente então persiste `timeline_match_status = VERIFIED`.

Esse `VERIFIED` tem escopo estrito: **a timeline da legenda submetida corresponde à timeline da transcrição importada**. Ele não demonstra que a legenda pertence ao vídeo declarado nem que seus tempos estão sincronizados com o vídeo real. Por isso `authorization_status` e `video_identity_status` continuam `UNVERIFIED` e `deep_links_allowed` continua `false`. Um cliente não consegue promover o estado apenas editando o manifesto: essa alegação é rejeitada antes da recomputação.

## Persistência e respostas HTTP

`POST /api/jobs` aceita o campo opcional `evidence`. Se presente, ele é validado antes de enfileirar o job e persistido em `jobs.evidence_json`. `SQLiteJobs.initialize()` adiciona a coluna a bancos antigos que ainda não a possuam. Registros cujo `timeline_match_status=VERIFIED` só são produzidos pelo caminho de recomputação acima; a leitura do banco permite recarregar esse checkpoint já decidido pelo backend.

`GET /api/jobs/{id}` e `GET /api/jobs/{id}/sections` devolvem somente o estado seguro de proveniência — presença/esquema, estados de verificação e `deep_links_allowed=false` — sem expor hashes desnecessariamente. Importações sem manifesto continuam não verificadas e com deep links desabilitados.

O smoke existente verifica o estado conservador do manifesto e não envia `caption_verification`; portanto, ele continua esperando `UNVERIFIED` e não promove nada por si só. Um sidecar adulterado ou uma transcrição alterada depois da criação do manifesto falha antes do POST.

## Parser e limites da legenda

- SRT `HH:MM:SS,mmm` e WebVTT `MM:SS.mmm`/`HH:MM:SS.mmm`, UTF-8/BOM, texto multilinha e settings VTT conhecidos.
- Tempos são copiados do arquivo; cues simultâneos/sobrepostos são mantidos; não há deduplicação, tradução ou sincronização com mídia.
- Entrada vazia, timestamps regressivos/inválidos, cue malformado, symlink, formato desconhecido, mais de 4.096 cues, cue acima de 12.000 caracteres, arquivo/JSON acima de 512.000 bytes e WebVTT com timebase especial são rejeitados.
- Saídas ficam em diretório privado, arquivos `0600`, sem overwrite.

## Evidência de validação e lacunas

A revisão anterior `ea103b08617726cd74130dfe755fbb7d53821938` passou no GitHub Actions em Python 3.12 e 3.13 com **129 testes PASS**. A nova fatia de verificação server-side adiciona testes offline específicos para recomputação, rejeição de `VERIFIED` autodeclarado, adulteração da legenda, persistência e manutenção de `deep_links_allowed=false`; a revisão final desta fatia precisa de CI verde no HEAD exato antes de ser tratada como validada.

T-006 continua parcial: ainda não existe critério implementado que verifique autorização, identidade do vídeo ou sincronização da legenda com a mídia real. Portanto, **nenhum deep link temporal deve ser criado a partir de importação manual nesta fase**, inclusive quando a correspondência legenda→transcrição foi verificada. Permanecem pendentes aquisição permitida, identidade/sincronia com mídia real, áudio/FFmpeg/chunks, Groq autenticada ou outro STT real, frontend/biblioteca e E2E. O protocolo do projeto continua em ADOÇÃO PARCIAL enquanto a fonte canônica aprovada/equivalência não estiver comprovada.
