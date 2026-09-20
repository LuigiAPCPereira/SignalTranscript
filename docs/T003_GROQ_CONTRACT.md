# T-003 — Contrato Groq (fatia offline)

Esta fatia implementa somente a validação de entrada/saída do endpoint de transcrição. O motor Groq não foi chamado; não houve acesso a chave, cota individual ou validação do tamanho real de upload.

```bash
PYTHONPATH=src python -m unittest discover -s tests -v
```

- `transcription_options` prepara `whisper-large-v3-turbo` com `verbose_json` e `segment` (idioma opcional em ISO-639-1).
- `normalize_segments` valida campos mínimos, tempos, ordenação e offset informado pelo chamador; não inventa timestamps, não remove sobreposições de chunks nem mede qualidade de fala.
- Para concluir T-003: obter áudio autorizado e testar Groq em conta real, validar formato retornado pelo SDK, limites, erros e recomposição com sobreposição. Não adicionar segredos ao GitHub.

Documentação oficial consultada em 20/09/2026: https://console.groq.com/docs/api-reference e https://console.groq.com/docs/speech-to-text
