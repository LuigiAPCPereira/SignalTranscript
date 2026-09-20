# PRD — SignalTranscript / MVP v0.1

**Situação:** planejamento proposto em 2026-09-20; não há aplicativo funcional. Fonte das decisões: conversa do usuário; [README](README.md). [Inventário](TASKLIST.md) e [arquitetura](DESIGN.md).

## Problema, público, jornada e limites

Público inicial: pessoa que quer absorver conhecimento de vídeos de **qualquer tema** sem assistir integralmente a cada um. Jornada: informar URL do YouTube ou importar transcrição/áudio autorizado → acompanhar processamento → ler síntese e ideias → consultar trechos originais e pesquisar biblioteca.

Confirmado pelo usuário: caráter generalista, Python + FastAPI no backend, Whisper Large V3 Turbo pela Groq como integração inicial e **independência futura de provedores de IA**. React/TypeScript, SQLite, yt-dlp, GPT-OSS 120B e worker local são propostas; não afirmar implantação nem aceitação individual desses detalhes. [Decisão de independência](docs/adr/ADR-002-provider-independence.md).

## Requisitos e aceites

| ID | Requisito | Aceite verificável |
| --- | --- | --- |
| REQ-001 | Entrada por URL ou importação | URL permitida normalizada para ID canônico; entrada inválida é rejeitada; transcrição/áudio autorizado é importável sem depender da extração automática. |
| REQ-002 | Aquisição condicional | Diferencia conteúdo acessível, indisponível e acesso negado; oferece importação alternativa; não promete obter vídeos arbitrários. |
| REQ-003 | Reaproveitar legenda adequada | Se houver legenda utilizável e permitida, evita transcrição remota e registra idioma, tipo, origem e timestamps existentes. |
| REQ-004 | Transcrição Groq | Áudio autorizado e dentro dos limites efetivos produz texto; áudio maior segue preparação/divisão; erro não gera sucesso aparente. |
| REQ-005 | Transcrição normalizada | Segmentos com IDs estáveis, texto não vazio, tempos válidos ou nulos; offsets de chunks convertidos para tempo absoluto, sem fabricar timestamp. |
| REQ-006 | Síntese representativa | Vídeo de teste com pontos no início/meio/fim recebe resumo e ideias sustentados por segmentos reais; ações não são inventadas. |
| REQ-007 | Proveniência | Cada ideia referencia segmentos da própria transcrição; links temporais somente se origem e timestamp reais permitirem. |
| REQ-008 | Biblioteca persistente | Vídeos, transcrições, análises versionadas e estados sobrevivem a reinício; nova análise não destrói versão anterior. |
| REQ-009 | Retomada de tarefas | Reinício entre transcrição e análise reutiliza artefato íntegro; resposta remota perdida permanece resultado desconhecido, não sucesso presumido. |
| REQ-010 | Progressão e falhas | UI mostra estados, erros úteis e cancelamento cooperativo sem declarar interrupção remota não confirmada. |
| REQ-011 | Segurança e limites | Chaves só no backend; entradas, temporários, duração, concorrência, URLs e logs tratados com limites e validações. |
| REQ-012 | Leitura e busca | Buscar transcrição, ler síntese e abrir trecho apenas quando existir timestamp efetivo. |
| REQ-013 | Independência de provedores | Transcrição e análise são portas distintas com resultados internos canônicos; seleção por função é independente e validada; um provedor não registrado falha explicitamente, sem fallback/custo ou envio a outro serviço silencioso. Importação de transcrição não exige STT. Substituição é demonstrável com fakes; adaptadores NIM/local exigem validação própria antes de serem anunciados. |

## MVP e exclusões

Inclui um vídeo por vez, importações, aquisição por URL quando permitida, transcrição em segmentos, síntese, biblioteca local e pesquisa textual. Inclui contratos neutros para os dois serviços de IA, mas **não** exige dois provedores reais nesta fase. Exclui chat entre vídeos, busca vetorial, leitura visual de slides, multiusuário, processamento em massa, deploy na nuvem, custos extras sem autorização e verificação factual externa automática.

O resumo descreve o conteúdo, não comprova a veracidade. Alegações não verificadas externamente devem continuar identificadas como tal. A transcrição é dado externo não confiável, não uma instrução para executar.

## Restrições, falhas e pendências

- Downloads/acesso automatizado dependem de permissões e termos aplicáveis; não implementar contorno de restrições. `captions.download` oficial exige acesso de edição no vídeo; importação alternativa é essencial.
- Groq documenta limite de upload direto de 25 MB no plano gratuito; **limites efetivos da conta não foram verificados**. Obedecer `retry-after` em 429, sem repetição infinita em acesso negado.
- Timestamps ausentes permanecem `null`; não oferecer deep link simulado. Legenda e áudio podem divergir: armazenar idioma e proveniência para deduplicação correta.
- Pendentes: permissões de vídeos reais, idioma padrão da síntese, política de retenção/backup, cota e faturamento, verificação semântica das referências, integração operacional de adaptadores e configuração por função.

## Fontes técnicas consultadas (20/09/2026)

[Groq STT](https://console.groq.com/docs/speech-to-text) · [Groq Structured Outputs](https://console.groq.com/docs/structured-outputs) · [Groq Rate Limits](https://console.groq.com/docs/rate-limits) · [YouTube captions.download](https://developers.google.com/youtube/v3/docs/captions/download) · [YouTube Terms](https://www.youtube.com/t/terms). Consulta não constitui teste de API nem permissão sobre um vídeo.
