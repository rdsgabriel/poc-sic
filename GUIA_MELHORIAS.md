# Guia de melhorias — como evoluir o parser sem quebrar o que funciona

Este guia é o **contrato de trabalho para qualquer IA (ou pessoa) que for
alterar este projeto**. Ele existe porque o risco nº 1 deste tipo de sistema é:
ao ajustar o parser para um PDF novo, quebrar silenciosamente a extração dos
PDFs que já funcionavam.

## A regra de ouro

> **Nenhuma alteração no parser é aceitável se `pytest tests/` não passar.**
> Os golden files em `tests/golden/<layout>/` são o registro do comportamento
> validado por humanos. Eles NUNCA são editados à mão e NUNCA são regenerados
> para "fazer o teste passar" — só são atualizados quando um humano re-valida
> o conteúdo contra o PDF original.

## Organização de testes e o processo de "treino"

Cada layout tem sua pasta de goldens e de PDFs, casados por convenção de nome:

    tests/golden/<layout>/<nome>.json   ← contrato de regressão, VERSIONADO
    tests/pdfs/<layout>/<nome>.pdf      ← PDF real, FORA do git (LGPD)

A suíte (`tests/test_regressao.py`) **auto-descobre** os casos varrendo os
goldens — não há lista manual de PDFs. PDF ausente é pulado (a máquina de CI
não tem os documentos do cliente); o golden continua sendo o contrato.

"Treinar" um layout = alimentá-lo com mais PDFs reais até cobrir as variações
do emissor. O container monta `app/` e `tests/` do host (bind mount no
docker-compose), então isto roda sem `docker cp` e os goldens gravados
aparecem direto no host para commitar:

```bash
# cobertura atual (quantos PDFs por layout)
docker compose exec poc-pcmso python -m tests.treinar --list

# adicionar/atualizar um caso: extrai, EXIGE que os 2 leitores concordem +
# regras OK, mostra o diff contra o golden e só grava sob confirmação
docker compose exec poc-pcmso python -m tests.treinar solstad \
    "/srv/entrada/NORMAND TURQUESA.pdf" normand_turquesa

# rodar a suíte de UM layout enquanto trabalha nele (~2min vs ~12min do todo)
docker compose exec poc-pcmso python -m tests.treinar --check solstad
#   equivale a: pytest tests/ -k solstad -q
```

O `treinar` recusa gravar golden se docling e pdfplumber divergirem ou se uma
regra de consistência falhar — a regra de ouro vira código, não disciplina.
Ainda assim, **confira o resumo/diff contra o PDF antes de confirmar**: os dois
leitores podem concordar num erro de leitura que só o olho humano pega.

## Arquitetura (o que cada arquivo faz)

| Arquivo | Papel | Risco ao mexer |
|---|---|---|
| `app/extractors/base.py` | Modelo neutro compartilhado (`Word`, `Line`, `GHE`, `Risco`, `Exame`) | ALTO — todos os layouts dependem dele |
| `app/extractors/sicolos.py` | Parser do layout Sicolos ("GHE: - 01 - NOME") | ALTO — é aqui que regressões nascem |
| `app/extractors/vix.py` | Parser do layout VIX Logística (seções "Ocupação FPC_...") | ALTO |
| `app/extractors/occupare.py` | Parser do layout Occupare (SETOR: GSE → FUNÇÃO) | ALTO |
| `app/extractors/mafra.py` | Parser do layout Mafra Ambiental (CARGO → ícone de risco) | ALTO |
| `app/extractors/solstad.py` | Parser do layout Intl. SOS/Solstad (GHE\|FUNÇÃO\|RISCOS + grade + OCR) | ALTO |
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

### 2. Rode a suíte do layout ANTES de alterar qualquer coisa
```bash
docker compose exec poc-pcmso python -m tests.treinar --check <layout>
```
Ela deve estar verde. Se não estiver, pare e investigue — você não sabe o
estado do terreno. (Sem `<layout>` roda a suíte inteira, ~12min.)

### 3. Coloque o PDF novo na pasta do layout
`tests/pdfs/<layout>/<nome>.pdf`. A suíte auto-descobre; ainda não há golden,
então ele não entra como caso de regressão até você promovê-lo no passo 6.

### 4. Altere o parser de forma aditiva
Preferência de estratégia, na ordem:
1. **Ajustar tolerâncias/regex existentes** só se o caso novo for variação
   pequena do padrão atual (ex.: cabeçalho com acento diferente).
2. **Adicionar um caminho novo condicionado** (ex.: reconhecer um segundo
   formato de cabeçalho de seção) sem alterar o caminho existente.
3. **Nunca** relaxar uma regra a ponto de aceitar lixo (ex.: aumentar uma
   tolerância de 12pt para 50pt "para pegar o caso novo" — isso quebra
   outros PDFs de forma silenciosa).

### 5. Valide os PDFs já cobertos do layout
```bash
docker compose exec poc-pcmso python -m tests.treinar --check <layout>
```
Os goldens existentes do layout precisam continuar verdes. Só depois valide
o PDF novo (próximo passo).

### 6. Promova o PDF novo a golden
Depois que um humano conferir a extração (spot-check de 2–3 GHEs contra o
PDF), use o script de treino — ele extrai, exige que os dois leitores
concordem, mostra o diff e grava sob confirmação:
```bash
docker compose exec poc-pcmso python -m tests.treinar <layout> \
    tests/pdfs/<layout>/<nome>.pdf
```
O golden aparece em `tests/golden/<layout>/<nome>.json` (via bind mount, já no
host). Não há lista para editar — a auto-descoberta acha o novo caso.

### 7. Checklist final antes de entregar
- [ ] `--check <layout>` verde para o layout mexido (ambos os leitores)
- [ ] suíte completa verde se você tocou em `base.py`/`builder.py`/`backends.py`
      (que afetam todos os layouts)
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
4. Coloque o PDF em `tests/pdfs/<familia>/<nome>.pdf` e promova o golden com
   `python -m tests.treinar <familia> tests/pdfs/<familia>/<nome>.pdf` (após
   validação humana). Rode a suíte COMPLETA — os PDFs antigos continuam sendo
   o contrato. Extractor que precise do arquivo original (OCR, como o Solstad)
   declara o parâmetro extra `pdf_path` em `extrair`.

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
- DE-PARA DO CLIENTE SK (jul/2026): exceção CONSCIENTE à regra da
  nomenclatura exata — o cliente forneceu a tabela "De para - Riscos e
  exames_SK.xls" mapeando os nomes do PDF para o catálogo do sistema BR MED
  (`data/mafra_depara_exames_sk.json`). Riscos perdem o sufixo
  "eSocial N.N.N"; exames são renomeados, com desdobramentos 1->N (FUNÇÃO
  RENAL -> UREIA + CREATININA) e fusões N->1 (EXAME CLÍNICO + anamnese ->
  CLÍNICO OCUPACIONAL, perfis mesclados). Casamento por chave alfanumérica
  + fuzzy 0.9 (absorve "ANAMNSE"/"anamnese", "Raio-X"/"Rx"). Exame fora do
  De-para mantém a nomenclatura do PDF. ATENÇÃO: as chaves "De" são os
  nomes do PDF Taboca — o De-para NÃO se aplica ao Itajui/Occupare
  (verificado: 0/16 chaves casam lá).

Armadilhas do layout Occupare (não regredir):
- Riscos e exames são POR FUNÇÃO (funções do mesmo GSE divergem) — cada
  FUNÇÃO vira um GHE próprio com `setor_override` compartilhado.
- Nomes de risco quebram linha na célula; a coluna direita da tabela
  (Data/Reavaliação/Característica) começa em x>=424 — fronteira fixa 415.
- Periodicidades não numéricas — REGRA CONFIRMADA PELO NEGÓCIO (jul/2026):
  "Todas as Vezes" E "Uma única Vez" com Periódico marcado entram AMBAS no
  Perfil Periódico com 12 meses (a contradição do documento foi decidida
  a favor do periódico). Não gera mais aviso.
- "(Código eSocial: NNNN)" é removido de nomes de exames E riscos.
- Sumário tem as mesmas linhas SETOR/FUNÇÃO das seções — filtrar linhas
  com "....." (pontilhado do índice).

Armadilhas do layout International SOS / Solstad (não regredir):
- A tabela de atividades críticas (Trabalho em Altura/Espaço Confinado/
  Eletricidade/Resgate/Resposta a Emergência) é IMAGEM no PDF — nenhum
  leitor de texto a enxerga. É extraída por OCR (tesseract, `pytesseract`),
  com a receita que a torna confiável: renderizar SÓ o retângulo da imagem
  em 400dpi e APAGAR as linhas de grade (numpy: runs >50% de tinta) antes
  do `--psm 6`. Sem isso o OCR devolve lixo. OCR é determinístico para a
  mesma versão do tesseract — mudanças de versão podem exigir revalidação
  do golden.
- Na LISTA DE GHEs (GHE|FUNÇÃO|RISCOS), o código do GHE fica verticalmente
  centrado no topo do bloco: âncora = linha do código, subindo enquanto o
  gap for de linha (≤13pt). Gap entre blocos pode ser ~39pt e gap interno
  ~38pt — segmentar por gap simples NÃO funciona.
- Funções quebram linha ("SUBCHEFE DE" + "MÁQUINAS") — juntar quando a
  linha termina em conector (DE/DA/DO/E).
- Casamento de nomes de função (OCR↔lista, PDF↔planilha bilíngue) é por
  CAMADAS de prioridade (exato > radical sem níveis > abreviação por
  prefixo de token > prefixo > fuzzy 0.85) — o fuzzy sozinho confunde
  SUBCHEFE DE MÁQUINAS com CHEFE DE MÁQUINAS (ratio 0.897!).
- Grade de exames: linhas ancoradas pelo valor da coluna ADMISSIONAL
  (TODOS/NÃO/GHE/GHEs); "VER ITENS 3 e 4 NAS PAGS. 5 e 6" em Retorno/
  Mudança = REGRA DO CLIENTE (jul/2026): segue a grade do Periódico.
  "GHE 3" expande por prefixo para 3.1/3.2/3.3.
- Notas de rodapé da grade: "***" (RX Tórax/Espirometria) → 24 meses.
- ECG: REGRA DO NEGÓCIO (jul/2026) — NUNCA entra na planilha (é sempre
  PQV, fora do PCMSO); função COM atividade crítica recebe Teste
  Ergométrico no lugar; SEM atividade crítica fica sem ambos (aviso INFO).
- As embarcações variam o MESMO layout (POSEIDON vs PIONEER): colunas em
  x diferentes (derivar do header "GHE" e dos rótulos de grupo, nunca
  fixar); código do GHE pode aparecer 6+ linhas abaixo do início do bloco
  (fronteira entre blocos = MAIOR gap vertical entre códigos consecutivos);
  tabela de atividades críticas pode ser 1 imagem (478x403) ou 4 fatias
  empilhadas com grade CINZA anti-aliased (por isso o pré-processamento
  binariza <140 antes de remover runs — limiar alto apaga o cabeçalho de
  fundo cinza junto); bullets dos exames específicos podem ser "•" ou
  glifo Wingdings U+F0B7; níveis por extenso (JUNIOR/PLENO) equivalem a
  JR/PL da planilha bilíngue (_ALIAS_NIVEL).
- SAGARIS desloca os rótulos de grupo de risco para a direita, mas recua
  linhas de continuação como `MINERAL,` e `ATIVIDADES CRÍTICAS`; uma fronteira
  derivada apenas do rótulo transforma esses textos em funções. O teto da
  fronteira acompanha o deslocamento da coluna GHE/FUNÇÃO para também preservar
  sufixos reais como o `I` de `OPERADOR DE GUINDASTE FIXO I` no PIONEER.
- No GHE 9 do SAGARIS, texto repintado chega como `E RGONÔMICO:` no
  pdfplumber e `ERGONÔMICO :` no docling. Recompor a inicial antes de detectar
  o grupo; sem isso os leitores divergem em riscos ergonômicos.
- NRs vêm da tabela de atividades críticas POR FUNÇÃO (GHE.nrs) + NR30 em
  todos (regra do cliente) — o builder ignora NR_TRIGGERS quando GHE.nrs
  está preenchido. Riscos citam "CHOQUE ELÉTRICO" em GHEs cuja tabela NÃO
  marca eletricidade — a tabela é a autoridade.
- Funções bilíngues ("COMANDANTE / CAPTAIN") vêm de
  `extractors/data/solstad_funcoes_bilingues.json` (gerado da planilha do
  cliente; a .xlsx em si fica FORA do git). Nome sem correspondência fica
  só em português + aviso INFO.
- Grupo "PSICOSSOCIAS:" (grafia do documento) → grupo `Psicossociais` →
  coluna "Riscos do Tipo Ergonômicos – Psicossociais" da PGR.

## Onde as melhorias futuras provavelmente serão necessárias

- **PDFs escaneados (imagem):** os leitores atuais assumem texto nativo.
  O layout Solstad já usa OCR pontual (tesseract) para UMA tabela-imagem;
  para documentos INTEIROS escaneados, ativar o OCR do docling
  (`DocumentConverter` com `do_ocr=True`) como terceiro backend, mantendo
  o modelo neutro `Line`/`Word`.
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
