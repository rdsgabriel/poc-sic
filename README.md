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

Os PDFs conhecidos têm golden files (`tests/golden/`) com a extração
validada. **Qualquer mudança no parser deve manter esses testes verdes.**
Antes de alterar qualquer coisa, leia `GUIA_MELHORIAS.md`.

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
