# T-005 / T-007 / T-010 — smoke operacional com consentimento em duas etapas

**Estado:** implementado e validado offline no PR #10. A ferramenta não executa rede no modo padrão e nenhuma chamada autenticada à Groq foi realizada nesta validação. [TASKLIST](../TASKLIST.md) · [checkpoint](../PROJECT_STATE.md) · [runtime](T005_LOCAL_RUNTIME.md).

## Princípio

Análise por seções e síntese global são **duas operações diferentes**. Cada uma pode transmitir dados e consumir cota separadamente. O smoke nunca transforma a autorização da primeira em autorização da segunda.

O modo padrão apenas valida a transcrição local:

```bash
python -m signaltranscript.backend.smoke \
  --transcript examples/synthetic_transcript.json
```

Nenhum HTTP ou provedor é usado.

## Operação 1 — análise por seções

Para permitir **uma submissão de análise**, são exigidos simultaneamente:

- `--submit-analysis`;
- `--confirm-analysis-upload`;
- `--expect-analysis-provider NOME`.

Os aliases antigos `--submit`, `--confirm-provider-upload` e `--expect-provider` continuam aceitos somente para compatibilidade.

Antes do POST, o cliente consulta `GET /api/config` em `127.0.0.1` e exige que `analysis_provider`, modelo e `SECTIONS_ONLY` correspondam ao esperado. O job é submetido uma única vez. Timeout ou resultado desconhecido não provoca novo POST, resume ou fallback.

Exemplo explícito:

```bash
python -m signaltranscript.backend.smoke \
  --transcript examples/synthetic_transcript.json \
  --submit-analysis \
  --confirm-analysis-upload \
  --expect-analysis-provider groq
```

## Operação 2 — síntese global

A síntese **não é consequência automática** da análise. Para solicitá-la no mesmo smoke, além de todos os argumentos da análise são exigidos:

- `--synthesize-global`;
- `--confirm-synthesis-upload`;
- `--expect-synthesis-provider NOME`.

Todas essas opções são validadas **antes do primeiro POST**. Portanto, um comando que pede síntese mas esquece o segundo consentimento não envia nem a análise.

Depois de `SECTIONS_ONLY` concluir, o cliente consulta `GET /api/config` novamente e exige `synthesis_provider` e `synthesis_model` correspondentes antes de executar exatamente um `POST /api/jobs/{id}/synthesis`.

Exemplo com Groq selecionada separadamente nas duas funções:

```bash
python -m signaltranscript.backend.smoke \
  --transcript examples/synthetic_transcript.json \
  --submit-analysis \
  --confirm-analysis-upload \
  --expect-analysis-provider groq \
  --synthesize-global \
  --confirm-synthesis-upload \
  --expect-synthesis-provider groq
```

Mesmo quando os nomes são iguais, são dois consentimentos e duas operações potencialmente cobradas.

## Validação estrutural

Para seções, o smoke exige job `COMPLETED`, ordem/cobertura integral dos IDs, identidade de provedor/modelo e referências pertencentes à própria seção. Ele recalcula cobertura posicional início/meio/fim; isso não é uma síntese nem prova semântica.

Para `GLOBAL_SYNTHESIS`, o cliente valida novamente job ID, tipo de resultado, identidade do provedor/modelo, estrutura das ideias, IDs existentes e proveniência. A cobertura retornada pelo servidor é comparada com uma cobertura **recalculada localmente a partir das referências da síntese**. Divergência falha fechado.

Nenhum dos dois caminhos comprova factualidade ou habilita deep links.

## Timeout e resultado remoto desconhecido

O smoke nunca reenvia automaticamente análise ou síntese. Se houver timeout do POST de análise antes de receber job ID, o resultado é desconhecido. Se a síntese já tiver sido enviada e a resposta HTTP for perdida, também não deve ser repetida cegamente.

Hoje existe checkpoint de síntese no backend, mas ainda não existe um GET dedicado para consultar o resultado global sem novo POST. Essa lacuna permanece explícita e é uma boa próxima fatia de T-005/T-007.

## Evidência

SHA `93168c1d6a5038d6e5f70775500f6db5a9b80581`, GitHub Actions **36253734809**: PASS Python 3.12 e 3.13; **232 testes PASS** em ambos os logs. Os testes novos comprovam consentimento separado, preflight antes de HTTP, recusa de provedor de síntese divergente, recomputação de cobertura e fluxo HTTP completo com analysis/synthesis fakes separados.

A suíte não instala credencial nem faz requisição externa. Groq real, cotas e qualidade permanecem não validadas. PR segue Draft; sem merge/deploy automático; adoção do protocolo continua parcial.
