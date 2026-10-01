# Fonte do Agent Development Protocol — adoção do SignalTranscript

**Projeto:** `LuigiAPCPereira/SignalTranscript`  
**Versão adotada pelo projeto:** Agent Development Protocol / Documentation & Continuity Protocol **v2.2**  
**Entrada operacional:** [AGENTS.md](../AGENTS.md)  
**Relatório do Adoption Gate:** [ADOPTION_REPORT.md](ADOPTION_REPORT.md)

## Fonte e integridade verificadas

A adoção deste projeto usa o arquivo `DOCUMENTATION_AND_CONTINUITY.md` v2.2 disponibilizado no ChatGPT Project durante a aplicação de 2026-09-26. A cópia efetivamente lida foi confrontada com o manifesto da distribuição central:

- `DOCUMENTATION_AND_CONTINUITY.md`: 37.930 bytes; SHA-256 local **`7e64d070e7ed419b225a92edb4a17ac4ff7d63f9c2bec22e35b47188d2639213`**.
- O manifesto central v2.2 registra para o arquivo-fonte exatamente o mesmo tamanho e SHA-256.
- `ENGINEERING_DNA.md`: SHA-256 local **`c19c5d97f8e42b311d6c15440e2e9f58cec64fadf1a48b9575e1f2e4dba0e373`**, também igual ao hash de origem registrado no manifesto.
- `FRONTEND_DNA.md`: SHA-256 local **`d1b84fd9510d207d99c98ccbfc7cffa38e2c55ba720704d67b99345b901fd147`**, igual ao hash de origem registrado na auditoria central.

Índice/manifesto consultados:
- https://app.notion.com/p/3e18d9773fea81e0853ec74730b91073
- https://app.notion.com/p/3e18d9773fea8170b54ec366b51cc49a

Isso confirma que a cópia do Project usada nesta adoção **reflete os bytes de origem registrados para a versão 2.2** do protocolo principal e do Engineering DNA. Não atribui hash às páginas transpostas do Notion.

## STAGING da distribuição versus adoção do projeto

A central Notion permanece **v2.2 STAGING / Publication Gate não aprovado**. Esse é o estado da **distribuição/publicação editorial central**. O próprio protocolo v2.2 exige separar esse estado da **adoção por projeto** e da **operação integrada**.

Por autorização explícita do usuário para corrigir/aplicar o Agent Protocol neste projeto, o SignalTranscript adota a versão-fonte v2.2 verificada acima. A publicação Notion continuar STAGING não rebaixa automaticamente o Adoption Gate deste repositório, desde que o projeto tenha mapa, inventário, checkpoint, instruções e fonte/versionamento verificáveis — conferidos em [ADOPTION_REPORT.md](ADOPTION_REPORT.md).

## Acesso por ambiente

- **ChatGPT Project nesta aplicação:** protocolo principal e DNA foram realmente lidos; os hashes acima foram calculados na cópia montada.
- **GitHub/ref:** `AGENTS.md`, TASKLIST, checkpoint e este registro de fonte ficam versionados na branch/PR. Este arquivo é um registro de proveniência, não uma cópia concorrente do protocolo.
- **Notion:** índice e manifesto foram reabertos; continuam STAGING. Não usar a transposição como prova de igualdade byte a byte.
- **Codex/outros hosts:** devem começar por `AGENTS.md` e verificar se a fonte externa necessária está acessível; não presumir memória do Project.
- **Tarefas agendadas:** acesso ao Project/Notion não é presumido. O loop SignalTranscript observado em 2026-09-26 está **desabilitado**; seu prompt é autocontido e orientado a recuperar GitHub, mas isso não prova acesso ao arquivo canônico nem operação ativa.

## Política de atualização

Uma futura v2.3+ não substitui esta adoção silenciosamente. Para atualizar: verificar versão/fonte, confrontar mudanças relevantes, atualizar este pin e `AGENTS.md`, executar novamente as condições do Adoption Gate e registrar a nova evidência. O estado da publicação central e o estado de adoção do SignalTranscript permanecem dimensões distintas.
