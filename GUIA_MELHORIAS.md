# Guia de melhorias — como evoluir o parser sem quebrar o que funciona

Este guia é o **contrato de trabalho para qualquer IA (ou pessoa) que for
alterar este projeto**. Ele existe porque o risco nº 1 deste tipo de sistema é:
ao ajustar o parser para um PDF novo, quebrar silenciosamente a extração dos
PDFs que já funcionavam.

## A regra de ouro

> **Nenhuma alteração no parser é aceitável se `pytest tests/` não passar.**
> Os golden files em `tests/golden/` são o registro do comportamento validado
> por humanos. Eles NUNCA são editados à mão e NUNCA são regenerados para
> "fazer o teste passar" — só são atualizados quando um humano re-valida o
> conteúdo contra o PDF original.

## Arquitetura (o que cada arquivo faz)

| Arquivo | Papel | Risco ao mexer |
|---|---|---|
| `app/extractors/base.py` | Modelo neutro compartilhado (`Word`, `Line`, `GHE`, `Risco`, `Exame`) | ALTO — todos os layouts dependem dele |
| `app/extractors/sicolos.py` | Parser do layout Sicolos ("GHE: - 01 - NOME") | ALTO — é aqui que regressões nascem |
| `app/extractors/vix.py` | Parser do layout VIX Logística (seções "Ocupação FPC_...") | ALTO |
| `app/extractors/occupare.py` | Parser do layout Occupare (SETOR: GSE → FUNÇÃO) | ALTO |
| `app/extractors/mafra.py` | Parser do layout Mafra Ambiental (CARGO → ícone de risco) | ALTO |
| `app/extractors/__init__.py` | Registro de extratores + `extrair_auto` (detecção/roteamento) | MÉDIO |
| `app/backends.py` | Leitores de PDF (docling e pdfplumber) → modelo neutro `Line`/`Word` | ALTO |
| `app/auditoria.py` | Score de confiança por GHE + pontos de atenção (heurístico) | BAIXO |
| `front-end/` | Front React (Vite+TS); build servido pelo FastAPI em `/` | BAIXO |
| `app/builder.py` | GHEs → planilhas xlsx (formato de importação) | MÉDIO — formato é contrato com o sistema BRMED |
| `app/pipeline.py` | Orquestra: PDF → extração → planilhas + JSON de auditoria | BAIXO |
| `app/validate.py` | Validação cruzada entre leitores + regras de consistência | BAIXO |
| `app/main.py` | Front web (upload → download) | BAIXO |

Decisões de design que NÃO devem ser desfeitas sem justificativa forte:

1. **Dois leitores independentes (docling + pdfplumber) sobre um modelo
   neutro.** A validação cruzada é o detector de erro de leitura. Se um
   leitor for removido, perde-se a rede de segurança por documento.
2. **Parsing por coordenadas x (âncoras de coluna), não por regex sobre texto
   corrido.** As tabelas do PCMSO não têm linhas desenhadas; a posição
   horizontal é a única fonte confiável de "em qual coluna está o X".
3. **Nomenclatura exata do PDF, sem correção gramatical.** O PDF é o
   gabarito. "SUPERVISOR SERVICOS" não vira "SUPERVISOR DE SERVIÇOS";
   "Fatores Psicosociais" (erro de grafia do documento) fica como está.
   Isso é exigência do time de validação (ver `Validação PCMSO_Notas...md`).
4. **Cargos = união da tabela final (Unidade/Setor/Cargo) com a coluna Cargo
   da tabela de Funcionários.** Há GHEs sem a tabela final e há PDFs em que a
   tabela final omite cargos presentes em Funcionários (caso real: GHE 20A).
5. **Registros de tabela distinguidos por espaçamento vertical** (linhas do
   mesmo registro a ~12pt; registros novos a ≥16pt). Nome, unidade e cargo
   podem quebrar linha ao mesmo tempo — só o espaçamento distingue.
6. **Dedup de texto duplicado** (`PPCCMMSSOO` / "PCMSO PCMSO"): páginas com
   negrito re-pintado produzem caracteres/palavras dobradas nos dois leitores,
   de formas diferentes. Tratado em `backends.py`.

## Passo a passo para inserir uma melhoria

### 1. Reproduza antes de mexer
```bash
python -m app.pipeline caminho/do/pdf_novo.pdf --out /tmp/saida
python -m app.validate caminho/do/pdf_novo.pdf
```
Leia o JSON de auditoria e os avisos. Identifique EXATAMENTE o que está
errado (qual GHE, qual tabela, qual linha do PDF). Use
`pdftotext -layout arquivo.pdf -` para inspecionar o texto com layout.

### 2. Rode a suíte ANTES de alterar qualquer coisa
```bash
pytest tests/ -q
```
Ela deve estar verde. Se não estiver, pare e investigue — você não sabe o
estado do terreno.

### 3. Escreva o teste do caso novo PRIMEIRO
Adicione o PDF novo ao projeto (ou a `tests/fixtures/`) e crie um teste que
capture o defeito (ex.: "GHE 07 deve ter 12 riscos"). O teste deve FALHAR
antes da correção e PASSAR depois.

### 4. Altere o parser de forma aditiva
Preferência de estratégia, na ordem:
1. **Ajustar tolerâncias/regex existentes** só se o caso novo for variação
   pequena do padrão atual (ex.: cabeçalho com acento diferente).
2. **Adicionar um caminho novo condicionado** (ex.: reconhecer um segundo
   formato de cabeçalho de seção) sem alterar o caminho existente.
3. **Nunca** relaxar uma regra a ponto de aceitar lixo (ex.: aumentar uma
   tolerância de 12pt para 50pt "para pegar o caso novo" — isso quebra
   outros PDFs de forma silenciosa).

### 5. Valide o conjunto completo
```bash
pytest tests/ -q                          # golden files intactos?
python -m app.validate pdf_novo.pdf       # leitores concordam no PDF novo?
```
Os DOIS precisam passar. Divergência entre docling e pdfplumber no PDF novo
significa que a correção está frágil — não siga em frente.

### 6. Promova o PDF novo a golden
Depois que um humano conferir a extração (spot-check de 2–3 GHEs contra o
PDF, como descrito em `PROMPT_PRODUCAO_PLANILHAS_PCMSO.md`):
```bash
python - <<'EOF'
import json
from dataclasses import asdict
from app.backends import BACKENDS
from app.extractor import extrair_ghes
ghes, meta = extrair_ghes(BACKENDS["docling"]("caminho/do/pdf_novo.pdf"))
json.dump({"meta": meta, "ghes": [asdict(g) for g in ghes]},
          open("tests/golden/pdf_novo.json", "w", encoding="utf-8"),
          ensure_ascii=False, indent=2)
EOF
```
E registre o par (pdf, golden) na lista `PDFS` de `tests/test_regressao.py`.

### 7. Checklist final antes de entregar
- [ ] `pytest tests/ -q` verde (todos os PDFs, ambos os leitores)
- [ ] PDF novo com validação cruzada limpa (`python -m app.validate`)
- [ ] Zero avisos de extração novos nos PDFs antigos
- [ ] Golden do PDF novo criado APÓS validação humana, nunca antes
- [ ] Nenhuma nomenclatura "corrigida" gramaticalmente

## Como adicionar um layout de PCMSO novo (processo usado no VIX/Cenibra)

Um "layout novo" é uma família de documento com estrutura própria (outro
emissor). NÃO estique um parser existente para aceitá-lo — crie um módulo
irmão em `app/extractors/`:

1. Mapeie o documento no texto plano (`pdftotext -layout`) e nas coordenadas
   (via `app.backends.ler_com_pdfplumber`): onde começa cada seção, onde
   estão riscos, exames e cargos, o que atravessa páginas.
2. Crie `app/extractors/<familia>.py` expondo `detectar(lines) -> bool` e
   `extrair(lines) -> (ghes, meta)`, retornando os dataclasses de
   `extractors/base.py` (`GHE`/`Risco`/`Exame`).
3. Registre o módulo na lista `EXTRATORES` de `app/extractors/__init__.py`.
   A ordem importa: cada detector deve casar só com a própria família.
4. Golden + entrada na lista `PDFS` de `tests/test_regressao.py` (após
   validação humana), e rode a suíte COMPLETA — os PDFs antigos continuam
   sendo o contrato.

Armadilhas já vistas no layout VIX (não regredir):
- A tabela PROCEDIMENTOS pode cair na PÁGINA SEGUINTE da seção (atividade
  longa, ex.: Mecânico) — a seção vai da linha "Ocupação" até a próxima.
- O cabeçalho da tabela tem 2 linhas; a 2ª ("EXIGÊNCIA CONTRATUAL" /
  "INTERPRETAÇÃO") fica ABAIXO da linha "ASO | EXAMES A EXECUTAR" e vaza
  como dado se não for filtrada.
- Rótulos de ASO são centralizados verticalmente na banda: as linhas de
  exame começam ANTES do rótulo — atribuição por banda mais próxima.
- O código do GHE no Quadro Funcional é centralizado no grupo de cargos —
  associação linha-a-linha código→cargo NÃO é confiável (usar conferência
  global).
- Mesmo exame com typo de pontuação entre linhas de ASO ("(AP e Perfil))")
  — mesclar por chave alfanumérica, grafia da 1ª ocorrência vence.
- docling e pdfplumber mapeiam travessão/hífen diferente para o mesmo glifo
  — normalizado em `backends.py::_dedup_texto`.
- "Mudança de Risco" e "Retorno Trabalho" são REGRAS condicionais no PDF.
  Tratamento ACORDADO COM O CLIENTE VIX (jul/2026): Mudança de função repete
  os exames do Admissional; Retorno ao Trabalho recebe somente "Exame
  Clínico". NÃO alterar sem novo acordo (`extractors/vix.py::_montar_exames`).
- Avisos com prefixo `INFO:` são achados do documento (divergências de
  grafia do próprio PDF) e não reprovam a validação.

Armadilhas do layout Mafra Ambiental (não regredir):
- REGRA DO NEGÓCIO (jul/2026): risco = SEMPRE o texto ao lado do ícone
  (glifo ); "Ausência de risco [grupo]" é placeholder por grupo e NÃO
  aparece quando o cargo tem qualquer risco real (todos ausentes →
  ausencia_riscos).
- Células "Fazer no ..." e periodicidade são centradas verticalmente e podem
  começar ANTES do nome do exame — atribuição por âncora vertical (centro da
  célula do nome), nunca por "último exame visto".
- A nota "*Nos casos de mudança..." encerra a tabela de exames; as linhas de
  continuação dela viram "exame" fantasma se não tratadas.
- "Em adição ... realizado N meses após a contratação" → apos_adm_meses
  (perfil Semestral Após Admissão).
- Alguns cargos não têm "Ambientes: (Ambiente Principal)" (lacuna do doc) —
  Setor recebe o nome do cargo + aviso INFO.

Armadilhas do layout Occupare (não regredir):
- Riscos e exames são POR FUNÇÃO (funções do mesmo GSE divergem) — cada
  FUNÇÃO vira um GHE próprio com `setor_override` compartilhado.
- Nomes de risco quebram linha na célula; a coluna direita da tabela
  (Data/Reavaliação/Característica) começa em x>=424 — fronteira fixa 415.
- Periodicidades não numéricas: "Todas as Vezes" → 12 meses (INFO, a
  confirmar); "Uma única Vez" com Periódico marcado é contradição do
  documento → fica fora do periódico (INFO).
- "(Código eSocial: NNNN)" é removido de nomes de exames E riscos.
- Sumário tem as mesmas linhas SETOR/FUNÇÃO das seções — filtrar linhas
  com "....." (pontilhado do índice).

## Onde as melhorias futuras provavelmente serão necessárias

- **PDFs escaneados (imagem):** os leitores atuais assumem texto nativo.
  Solução: ativar o OCR do docling (`DocumentConverter` com `do_ocr=True`)
  como terceiro backend, mantendo o modelo neutro `Line`/`Word`.
- **Auditor LLM: REMOVIDO do produto (jul/2026) por decisão do time**, após
  experimento com OpenAI gpt-4o-mini no PDF Cenibra: ~60 achados em 13 GHEs,
  quase todos falsos positivos, mesmo após iteração de prompt com regras
  anti-falso-positivo — o modelo atribuía conteúdo da seção vizinha ao GHE,
  apontava boilerplate ("NR7-NR15") como risco e tratava "Anual" vs "12
  meses" como divergência. A confiança do fluxo vem das camadas
  determinísticas (validação cruzada + golden tests + auditoria heurística).
  Se alguém retomar a ideia: (1) contexto por seção EXATA (recortar pelo
  intervalo de linhas do extrator, não por páginas); (2) modelo mais forte
  que o mini; (3) montar um eval com falsos positivos conhecidos ANTES de
  confiar no resultado.
- **Colunas de exames com perfis extras** (ex.: semestral): a coluna
  "APÓS ADM." já é capturada (`apos_adm`/`apos_adm_meses`); o mapeamento
  para a planilha está em `builder.py::montar_pcmso`.

Convenção confirmada pelo negócio: as colunas NR da PGR recebem "X" —
o nome da coluna identifica a NR, o X marca presença. Não alterar.
