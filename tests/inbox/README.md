# Inbox de documentos

Coloque aqui PDFs novos, separados pela família de layout:

```text
tests/inbox/solstad/*.pdf
tests/inbox/sicolos/*.pdf
tests/inbox/vix/*.pdf
tests/inbox/occupare/*.pdf
tests/inbox/mafra/*.pdf
```

Os PDFs são ignorados pelo Git. Para analisar todos os documentos de uma
família sem criar ou alterar goldens:

```bash
docker compose exec poc-pcmso python -m tests.treinar --inbox solstad
```

Estados do relatório:

- `APROVADO`: extração idêntica a um golden humano já existente.
- `CANDIDATO`: passou nas regras automáticas, mas ainda precisa de conferência
  humana antes de virar golden.
- `REPROVADO`: houve divergência, regra violada, layout incorreto ou diferença
  em relação ao golden.

Depois da conferência humana, promova um caso explicitamente:

```bash
docker compose exec poc-pcmso python -m tests.treinar solstad \
  "/srv/tests/inbox/solstad/arquivo.pdf"
```

Para Solstad, o nome do caso é derivado automaticamente da embarcação
(`NORMAND SAGARIS` → `normand_sagaris`). O terceiro argumento continua
disponível quando for necessário escolher outro nome.

Nunca use `--yes` sem ter conferido o PDF contra a extração.
