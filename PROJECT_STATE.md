# PROJECT_STATE — SignalTranscript / checkpoint

**Observado em:** 2026-09-20 (horário da Bahia). **Escopo:** MVP v0.1, portas/adaptadores offline, análise por seções e checkpoint local de seções; aplicativo completo não existe. **Autoridades:** [TASKLIST](TASKLIST.md), [PRD](PRD.md), [DESIGN](DESIGN.md), [AGENTS](AGENTS.md), [adoção](docs/ADOPTION_REPORT.md).

## Git e decisões

- Repositório: https://github.com/LuigiAPCPereira/SignalTranscript. Base `main` vista antes em `e4fe22d6fee4120af33d9436f4b0e27864eb5df1`, revalidar antes de merge. A cadeia PR #1 (docs) -> #2 (portas) -> #3 (STT) -> #4 (análise) -> #5 (seções) foi observada aberta em Draft.
- **Fatia atual T-007:** branch `feat/t007-section-checkpoints` derivada do HEAD `c0f35a6bd7e9a14c6ba330d2bc29b8bed7720d64` do PR #5. PR, HEAD final e CI devem ser confirmados após publicação; nenhum merge/deploy realizado por esta fatia. Git checkout remoto não disponível neste ambiente (DNS), embora conteúdos sejam acessíveis pelo conector GitHub.
- Decidido pelo usuário: produto generalista, Python + FastAPI, Groq Whisper Turbo inicial e independência por função para IA. GPT-OSS 120B é adaptador offline; NIM e modelos locais não foram integrados.

## Protocolo

Manifesto v2.2 disponível no Project está marcado STAGING/NÃO PUBLICADO INTEGRALMENTE; versão editorial aprovada, equivalência de conteúdo ao Project e disponibilidade em outras sessões/agendamentos não verificadas. [ADOPTION_REPORT](docs/ADOPTION_REPORT.md): **ADOÇÃO PARCIAL**. Nove funções documentadas, fonte aprovada pendente; não inventar autoridade.

## Tarefas e evidências

- **T-004:** documentação e mapeamento de nove funções existem na branch documental; fonte aprovada, equivalência e integração não confirmadas.
- **T-003/T-010 (parciais):** portas neutras e adaptadores Groq STT/análise testados offline; CI [run 35548137252](https://github.com/LuigiAPCPereira/SignalTranscript/actions/runs/35548137252) aprovado Python 3.12/3.13 no PR #4. SDK real, áudio, API autenticada, cotas e NIM/local pendentes.
- **T-007 (fatia parcial de persistência):** `ai/long_form.py` executa plano imutável com prefixo validado; `ai/section_checkpoint.py` guarda runs e seções em SQLite, vinculando run ID, digest de transcrição/plano, provedor/modelo e revisão explícita. Reabre seções íntegras, rejeita alterações/corrupção/ordem inválida e não marca resposta remota desconhecida como sucesso. Em cópia local: 32 testes das duas fatias + compileall PASS; hashes dos três arquivos Python novos/modificados confrontados com blobs publicados. **CI desta branch no HEAD final ainda requer confirmação.** [Nota técnica](docs/T007_LONG_FORM.md).
- **T-005:** não há FastAPI, scheduler, lease multiworker, persistência de vídeos/transcrições nem recuperação de job; a biblioteca SQLite de seções não conclui T-005.
- **T-006/T-008/T-009:** aquisição, interface e E2E ausentes. T-007 ainda precisa de síntese global referenciada, cobertura semântica real e integração com worker.

**Próxima ação por ID:** confirmar PR/HEAD/CI desta fatia; avançar T-005 em backend/worker ao resolver critérios documentais, sem confundir checkpoint com job durável. T-007 exige síntese global representativa, versões/persistência da análise completa e validação real. T-003/T-010 exigem testes reais autorizados. Nunca efetuar merge/deploy sem autorização e gates.
