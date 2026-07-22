"""
Extrator do layout Sicolos (ex.: Águas do Brasil / RIO + SANEAMENTO).

O parser trabalha sobre o modelo neutro de "linhas de palavras com coordenadas
x" (List[Line]) de `base.py`, produzido por um backend de leitura (docling ou
pdfplumber). Isso permite validar a extração com dois leitores independentes.

Estrutura reconhecida por seção de GHE:
  GHE: - <CÓDIGO> - <NOME>
  Descrição Atividade ...
  Perigo / Fator de Risco | Grupo | Descrições...      -> tabela de riscos
  Exames | ADMISSÃO | APÓS ADM. | PERIÓDICO | ...      -> tabela de exames
  Funcionários | Unidade | Setor | Cargo               -> ignorada
  Unidade | Setor | Cargo                              -> tabela de cargos únicos
"""

from __future__ import annotations

import re

from .base import GHE, Exame, Line, Risco, Word, montar_foco, norm as _norm


def detectar(lines: list[Line]) -> bool:
    return any(ln.text.strip().startswith("GHE: -") for ln in lines)


GRUPOS_VALIDOS = {
    "Físico", "Quimico", "Químico", "Biológico", "Biologico",
    "Ergonômicos", "Ergonômico", "Ergonomicos", "Ergonomico",
    "Acidente", "Acidentes", "Periculoso", "Penoso",
}

# Cabeçalhos de página repetidos (filtrados por conteúdo, não só posição)
_RE_PAGE_HEADER = re.compile(
    r"^(PCMSO|Programa de Controle Médico de Saúde Ocupacional.*|RIO \+ SANEAMENTO.*|\d{2}/\d{2}/\d{4})$"
)
_RE_SECTION = re.compile(r"^GHE:\s*-\s*(\S+)\s*-?\s*(.*)$")
_RE_MESES = re.compile(r"^(\d+)\s*meses?$", re.IGNORECASE)
_RE_END_DOC = re.compile(r"SOCSIG|^_{5,}|Médico respons[aá]vel", re.IGNORECASE)


def _grupo_canonico(g: str) -> str:
    n = _norm(g)
    return {
        "fisico": "Físico", "quimico": "Químico", "biologico": "Biológico",
        "ergonomicos": "Ergonômicos", "ergonomico": "Ergonômicos",
        "acidente": "Acidente", "acidentes": "Acidente",
        "periculoso": "Periculoso", "penoso": "Penoso",
    }.get(n, g)


# ----------------------------------------------------------------------------
# Parser principal
# ----------------------------------------------------------------------------

def extrair_ghes(lines: list[Line]) -> tuple[list[GHE], dict]:
    """Percorre as linhas do documento e devolve a lista de GHEs + metadados."""

    # Nomes do sumário como fallback (caso o cabeçalho da seção venha sem nome)
    toc_nomes: dict[str, str] = {}
    re_toc = re.compile(r"^GHE:\s+(\S+)\s+-\s+(.+?)(?:\s+\d+)?$")
    for ln in lines:
        m = re_toc.match(ln.text)
        if m and not ln.text.startswith("GHE: -"):
            toc_nomes[m.group(1)] = m.group(2).strip()

    empresa = ""
    for i, ln in enumerate(lines):
        if ln.text.strip() == "Empresa" and i + 1 < len(lines):
            empresa = lines[i + 1].text.strip()
            break

    ghes: list[GHE] = []
    ghe: GHE | None = None
    estado = None            # None | RISCOS | EXAMES | FUNC | CARGOS
    grupo_x = desc_x = None  # âncoras da tabela de riscos
    exame_cols: list[tuple[str, float]] = []  # âncoras da tabela de exames
    func_anchors: list[tuple[str, float]] = []   # tabela Funcionários
    cargo_anchors: list[tuple[str, float]] = []  # tabela final Unidade/Setor/Cargo
    func_rows: list[list[str]] = []
    cargo_rows: list[list[str]] = []
    ultima_linha_tab: tuple[int, float] | None = None
    # foco: linhas de cada seção de GHE (banda vertical; cargos vêm em tabela,
    # então não há uma única caixa de função a destacar)
    secoes_foco: list[tuple[GHE, list[Line]]] = []
    foco_linhas: list[Line] = []

    def fechar_cargos():
        """Consolida os cargos do GHE.

        União da tabela final (Unidade/Setor/Cargo) com a coluna Cargo da
        tabela de Funcionários: há GHEs sem a tabela final e há casos em que
        a tabela final do próprio PDF omite um cargo presente em Funcionários.
        """
        nonlocal cargo_rows, func_rows
        if ghe is not None:
            vistos = set()
            for parts in cargo_rows + func_rows:
                nome = limpar_cargo(" ".join(parts))
                if nome and _norm(nome) not in vistos:
                    vistos.add(_norm(nome))
                    ghe.cargos.append(nome)
        cargo_rows = []
        func_rows = []

    for ln in lines:
        txt = ln.text.strip()
        if not txt:
            continue
        if _RE_PAGE_HEADER.match(txt):
            continue
        if _RE_END_DOC.search(txt):
            if estado == "CARGOS":
                fechar_cargos()
                estado = None
            continue

        m = _RE_SECTION.match(txt)
        if m:
            fechar_cargos()
            codigo, nome = m.group(1).strip(), m.group(2).strip()
            if not nome:
                nome = toc_nomes.get(codigo, "")
            ghe = GHE(codigo=codigo, nome=nome, pagina=ln.page)
            ghes.append(ghe)
            foco_linhas = [ln]
            secoes_foco.append((ghe, foco_linhas))
            estado = None
            continue

        if ghe is None:
            continue

        foco_linhas.append(ln)  # linha de conteúdo da seção do GHE atual

        # ------------------------------------------------ cabeçalhos de tabela
        if "Perigo / Fator de Risco" in txt or (
            "Perigo" in txt and "Fator" in txt and "Grupo" in txt
        ):
            grupo_w = next((w for w in ln.words if _norm(w.text) == "grupo"), None)
            if grupo_w:
                grupo_x = grupo_w.x0
                # "Descrições" pode não estar na mesma linha; usa folga generosa
                desc_w = next((w for w in ln.words if "Descri" in w.text), None)
                desc_x = desc_w.x0 if desc_w else grupo_x + 90
                estado = "RISCOS"
            continue

        if txt.startswith("Exames") and "ADMISS" in txt.upper():
            exame_cols = _ancoras_exames(ln)
            estado = "EXAMES"
            continue

        if txt.startswith("Funcionários"):
            func_anchors = _ancoras_header(
                ln, ["funcionarios", "unidade", "setor", "cargo"]
            )
            estado = "FUNC"
            ultima_linha_tab = None
            continue

        if estado in ("FUNC", None) and _e_header_cargos(ln):
            cargo_anchors = _ancoras_header(ln, ["unidade", "setor", "cargo"])
            estado = "CARGOS"
            cargo_rows = []
            ultima_linha_tab = None
            continue

        # ------------------------------------------------ linhas de dados
        if estado == "RISCOS":
            _linha_risco(ln, ghe, grupo_x, desc_x)
        elif estado == "EXAMES":
            _linha_exame(ln, ghe, exame_cols)
        elif estado == "FUNC":
            _linha_tabela_cargo(ln, func_anchors, "funcionarios", func_rows, ultima_linha_tab)
            ultima_linha_tab = (ln.page, ln.top)
        elif estado == "CARGOS":
            _linha_tabela_cargo(ln, cargo_anchors, "unidade", cargo_rows, ultima_linha_tab)
            ultima_linha_tab = (ln.page, ln.top)

    fechar_cargos()

    focos: dict[str, dict] = {}
    for g, secao in secoes_foco:
        foco = montar_foco(secao, g.pagina)
        if foco:
            focos[g.codigo] = foco

    meta = {"empresa": empresa, "total_ghes": len(ghes), "focos": focos}
    return ghes, meta


def limpar_cargo(nome: str) -> str:
    nome = re.sub(r"\s+", " ", nome).strip()
    # Prefixo/sufixo "PESS" não faz parte do cargo (vaza da coluna Setor)
    nome = re.sub(r"^PESS\s+", "", nome)
    nome = re.sub(r"\s+PESS$", "", nome)
    return nome


def _e_header_cargos(ln: Line) -> bool:
    labels = [_norm(w.text) for w in ln.words]
    return labels[:1] == ["unidade"] and "setor" in labels and "cargo" in labels


def _ancoras_header(ln: Line, nomes: list[str]) -> list[tuple[str, float]]:
    anchors = []
    for w in ln.words:
        n = _norm(w.text)
        if n in nomes:
            anchors.append((n, w.x0))
    return anchors


def _celulas(ln: Line, gap: float = 18.0) -> list[list[Word]]:
    """Agrupa palavras contíguas em células (colunas separadas por gaps grandes)."""
    cells: list[list[Word]] = []
    for w in sorted(ln.words, key=lambda w: w.x0):
        if cells and w.x0 - cells[-1][-1].x1 < gap:
            cells[-1].append(w)
        else:
            cells.append([w])
    return cells


_ROW_GAP_MIN = 13.5  # linhas de um mesmo registro ficam a ~12pt; registros novos a >=16pt


def _linha_tabela_cargo(
    ln: Line,
    anchors: list[tuple[str, float]],
    col_inicio: str,
    rows: list[list[str]],
    ultima_linha: tuple[int, float] | None,
    tol: float = 12.0,
) -> None:
    """Linha das tabelas Funcionários / Unidade-Setor-Cargo.

    Cada palavra é atribuída a uma coluna por intervalo de âncoras
    (coluna k cobre [x_k - tol, x_{k+1} - tol)); as posições x são
    consistentes dentro da mesma tabela, mesmo entre páginas.

    Um registro novo exige palavra na primeira coluna E espaçamento vertical
    de registro novo (>13.5pt). Nome do funcionário, unidade e cargo podem
    quebrar linha ao mesmo tempo — só o espaçamento distingue esse caso.
    Continuações (mesmo entre páginas) apenas estendem o cargo corrente.
    """
    if not anchors:
        return
    ordenadas = sorted(anchors, key=lambda a: a[1])

    def coluna(w: Word) -> str:
        col = ordenadas[0][0]
        for nome, x in ordenadas:
            if w.x0 >= x - tol:
                col = nome
            else:
                break
        return col

    tem_inicio = False
    cargo_parts: list[str] = []
    for w in ln.words:
        c = coluna(w)
        if c == col_inicio:
            tem_inicio = True
        elif c == "cargo":
            cargo_parts.append(w.text)

    gap_novo = (
        ultima_linha is None
        or ln.page != ultima_linha[0]
        or (ln.top - ultima_linha[1]) > _ROW_GAP_MIN
    )
    # quebra de página no meio de um registro: sem palavra na 1ª coluna
    partes = [" ".join(cargo_parts)] if cargo_parts else []
    if tem_inicio and gap_novo:
        rows.append(partes)
    elif partes and rows:
        rows[-1].extend(partes)  # cargo com quebra de linha


def _linha_risco(ln: Line, ghe: GHE, grupo_x: float, desc_x: float) -> None:
    if grupo_x is None:
        return
    nome_words = [w.text for w in ln.words if w.x1 < grupo_x - 4]
    grupo_words = [w.text for w in ln.words if grupo_x - 12 <= w.x0 < desc_x - 12]
    grupo_txt = " ".join(grupo_words).strip()

    if grupo_txt and _grupo_canonico(grupo_txt) in (
        "Físico", "Químico", "Biológico", "Ergonômicos",
        "Acidente", "Periculoso", "Penoso",
    ):
        nome = re.sub(r"\s+", " ", " ".join(nome_words)).strip()
        if nome:
            ghe.riscos.append(Risco(nome=nome, grupo=_grupo_canonico(grupo_txt)))
        else:
            ghe.avisos.append(f"Risco sem nome na linha: {ln.text!r}")
    elif nome_words and not grupo_txt and ghe.riscos:
        # continuação do nome do risco (quebra de linha)
        cont = " ".join(nome_words).strip()
        if cont:
            ghe.riscos[-1].nome = f"{ghe.riscos[-1].nome} {cont}"


_COLS_EXAME = ["ADMISSAO", "APOS_ADM", "PERIODICO", "RET_TRAB", "MUD_RISCOS", "DEMISSAO"]


def _ancoras_exames(ln: Line) -> list[tuple[str, float]]:
    """Posições x centrais de cada coluna de perfil no cabeçalho da tabela."""
    anchors: list[tuple[str, float]] = []
    words = ln.words
    i = 0
    while i < len(words):
        t = _norm(words[i].text)
        if t.startswith("admissao"):
            anchors.append(("ADMISSAO", words[i].x0))
        elif t.startswith("apos"):
            x = words[i].x0
            anchors.append(("APOS_ADM", x))
            if i + 1 < len(words) and _norm(words[i + 1].text).startswith("adm"):
                i += 1
        elif t.startswith("periodico"):
            anchors.append(("PERIODICO", words[i].x0))
        elif t.startswith("ret"):
            anchors.append(("RET_TRAB", words[i].x0))
            if i + 1 < len(words) and _norm(words[i + 1].text).startswith("trab"):
                i += 1
        elif t.startswith("mud"):
            anchors.append(("MUD_RISCOS", words[i].x0))
            if i + 1 < len(words) and _norm(words[i + 1].text).startswith("risco"):
                i += 1
        elif t.startswith("demissao"):
            anchors.append(("DEMISSAO", words[i].x0))
        i += 1
    return anchors


def _linha_exame(ln: Line, ghe: GHE, cols: list[tuple[str, float]]) -> None:
    if not cols:
        return
    first_col_x = cols[0][1]
    nome_words = [w for w in ln.words if w.x1 < first_col_x - 6]
    mark_words = [w for w in ln.words if w.x1 >= first_col_x - 6]

    if not mark_words:
        # linha só com texto de nome: continuação do exame anterior
        if nome_words and ghe.exames:
            ghe.exames[-1].nome += " " + " ".join(w.text for w in nome_words)
        return

    nome = re.sub(r"\s+", " ", " ".join(w.text for w in nome_words)).strip()
    if not nome:
        ghe.avisos.append(f"Marcações de exame sem nome: {ln.text!r}")
        return

    exame = Exame(nome=nome)
    # agrupa palavras próximas em células ("12" + "meses")
    cells: list[list[Word]] = []
    for w in sorted(mark_words, key=lambda w: w.x0):
        if cells and w.x0 - cells[-1][-1].x1 < 15:
            cells[-1].append(w)
        else:
            cells.append([w])

    for cell in cells:
        cell_txt = " ".join(w.text for w in cell).strip()
        cx = cell[0].x0
        col = min(cols, key=lambda c: abs(c[1] - cx))[0]
        m = _RE_MESES.match(cell_txt)
        if col == "PERIODICO" and m:
            exame.periodico_meses = int(m.group(1))
        elif col == "APOS_ADM" and m:
            exame.apos_adm_meses = int(m.group(1))
        elif cell_txt.upper() == "X":
            if col == "ADMISSAO":
                exame.admissao = True
            elif col == "APOS_ADM":
                exame.apos_adm = True
            elif col == "RET_TRAB":
                exame.ret_trab = True
            elif col == "MUD_RISCOS":
                exame.mud_riscos = True
            elif col == "DEMISSAO":
                exame.demissao = True
            elif col == "PERIODICO":
                ghe.avisos.append(
                    f"Exame {nome!r}: X no periódico sem meses definidos"
                )
        else:
            ghe.avisos.append(
                f"Exame {nome!r}: célula não reconhecida {cell_txt!r} (coluna {col})"
            )
    ghe.exames.append(exame)


# interface uniforme do registro de extratores
extrair = extrair_ghes
