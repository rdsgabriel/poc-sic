# POC — PCMSO (PDF) → Planilhas PGR e PCMSO

Fluxo automatizado que lê o PDF do PCMSO (gabarito emitido pelo Sicolos),
extrai todos os GHEs — riscos, exames com periodicidade e funções — e produz
as duas planilhas de importação (PGR e PCMSO) no formato definido em
`PROMPT_PRODUCAO_PLANILHAS_PCMSO.md`.

## Como funciona

```
PDF ──► docling (leitura: palavras + coordenadas)
     ──► extractor (âncoras de coluna + regex → GHEs)
     ──► builder (planilhas xlsx) + JSON de auditoria
     └─► validação cruzada com pdfplumber (2º leitor independente)
```

A cada documento processado, a extração é refeita por um segundo leitor de
PDF independente e os resultados são comparados campo a campo. Divergência é
reportada na tela — é o alarme de "este PDF tem algo que o parser não domina".

## Rodando com Docker (recomendado)

```bash
docker compose up --build
# abra http://localhost:8890
```

### Acompanhando um processamento

Os logs de negócio mostram cada job por etapa, com duração, layout e
quantidades extraídas. As leituras parciais do PDF feitas pelo visualizador
não aparecem, para não esconder o que importa.

```bash
docker compose logs -f --tail=50 poc-pcmso
```

Exemplo resumido:

```text
JOB 5f14f279df53 | recebido | arquivo='documento.pdf' | tamanho=0.36 MB
JOB 5f14f279df53 | leitura do PDF concluída | paginas=58 | duracao=8.8s
JOB 5f14f279df53 | extração concluída | layout=sicolos | ghes=34 | funcoes=108
JOB 5f14f279df53 | validação cruzada concluída | resultado=OK | pendencias=0
JOB 5f14f279df53 | concluído | validacao=OK | total=28.7s
```

## Rodando local (sem Docker)

```bash
# API
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --port 8000

# Front (React/Vite) — build de produção servido pelo FastAPI em /
cd front-end && npm install && npm run build

# ou, para desenvolver o front com hot reload (proxia a API em :8000):
cd front-end && npm run dev   # http://localhost:5173
```

### Linha de comando (sem front)

```bash
python -m app.pipeline "PCMSO_CAMPO_GRANDE_22_09__Brmed by sicolos.pdf" --out output
python -m app.validate "PCMSO_CAMPO_GRANDE_22_09__Brmed by sicolos.pdf"
```

## Testes de regressão

```bash
pytest tests/ -q
```

Os PDFs de teste **não são versionados** (contêm dados pessoais — LGPD).
A suíte pula automaticamente os PDFs ausentes; para rodá-la completa,
obtenha os PDFs internamente e coloque nos caminhos listados em
`tests/test_regressao.py`.

Os PDFs conhecidos têm golden files (`tests/golden/`) como referência de
regressão; pendências de validação humana ficam registradas em `pendencias.md`.
**Qualquer mudança no parser deve manter esses testes verdes.** Antes de
alterar qualquer coisa, leia `GUIA_MELHORIAS.md`.

### Laboratório de documentos novos

PDF novo não vira golden automaticamente. Coloque os documentos ainda não
validados no inbox da família, por exemplo:

```text
tests/inbox/solstad/*.pdf
```

E rode a varredura sem alterar o corpus aprovado:

```bash
docker compose exec poc-pcmso python -m tests.treinar --inbox solstad
```

O relatório distingue `REPROVADO` (falhou em algum gate), `CANDIDATO`
(passou automaticamente, mas falta conferência humana) e `APROVADO`
(idêntico a um golden existente). Veja `tests/inbox/README.md` para promover
um caso depois da conferência.

## Resultados desta POC (Campo Grande)

- 34 GHEs no PDF de 22/09 e 33 no de 27/08 — extração completa nos dois,
  com validação cruzada limpa (docling ≡ pdfplumber).
- Todos os 13 itens que a validação humana apontou como perdidos pela
  tentativa anterior (riscos faltantes, NRs, funções, nomenclatura de setor
  e cargos) são capturados corretamente — ver `Validação PCMSO_Notas...md`.
- Nomenclatura preservada exatamente como no PDF (sem correção gramatical),
  setor no padrão `GHE 01 - ADMINISTRATIVO`, periódico no formato
  `Exame,MESES`, NRs disparadas pelos riscos correspondentes.

## Limites conhecidos

- Assume PDF com texto nativo (não escaneado). Exceção pontual: no layout
  Solstad a tabela de atividades críticas é imagem e é lida por OCR
  (tesseract). Para documentos inteiros escaneados, ativar OCR do docling
  como backend adicional (ver GUIA_MELHORIAS.md).
- Layouts suportados (detecção automática, um extractor por família em
  `app/extractors/`): Sicolos (Águas do Brasil), VIX Logística (Cenibra),
  Occupare (SK/Itajui), Mafra Ambiental (SK/Taboca) e International SOS /
  Solstad (NORMAND POSEIDON). Emissor novo = módulo novo (processo no guia).
