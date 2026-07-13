"""
Backends de leitura do PDF -> List[Line] (modelo neutro do extractor).

- ler_com_docling: usa o parser do projeto docling (docling-parse), que devolve
  células de texto com bounding boxes. É o leitor principal do fluxo.
- ler_com_pdfplumber: leitor independente, usado para validação cruzada
  (dois leitores concordando = alta confiança na extração).
"""

from __future__ import annotations

from .extractors.base import Line, Word

_LINE_TOL = 3.0  # tolerância vertical para agrupar palavras na mesma linha


def _agrupar_linhas(page_no: int, words: list[Word], tops: list[float]) -> list[Line]:
    pares = sorted(zip(tops, words), key=lambda p: (p[0], p[1].x0))
    lines: list[Line] = []
    for top, w in pares:
        if lines and abs(top - lines[-1].top) <= _LINE_TOL:
            lines[-1].words.append(w)
        else:
            lines.append(Line(page=page_no, top=top, words=[w]))
    for ln in lines:
        ln.words.sort(key=lambda w: w.x0)
        # texto em negrito pintado 2x pode virar palavras duplicadas sobrepostas
        dedup: list[Word] = []
        for w in ln.words:
            if dedup and w.text == dedup[-1].text and w.x0 - dedup[-1].x0 < 2.0:
                continue
            dedup.append(w)
        ln.words = dedup
    return lines


def _dedup_texto(t: str) -> str:
    """Corrige texto com caracteres duplicados por re-pintura de negrito.

    Algumas páginas do PDF pintam o texto duas vezes ("PCMSO" -> "PPCCMMSSOO").
    Detecta o padrão de duplicação exata e reduz para o texto original.
    Também normaliza travessões tipográficos: docling e pdfplumber mapeiam o
    mesmo glifo de forma diferente ("–" vs "-"), o que quebraria a validação
    cruzada.
    """
    if len(t) >= 4 and len(t) % 2 == 0:
        if all(t[i] == t[i + 1] for i in range(0, len(t), 2)):
            t = t[0::2]
    return t.replace("–", "-").replace("—", "-")


# ----------------------------------------------------------------------------
# docling
# ----------------------------------------------------------------------------

def ler_com_docling(pdf_path: str) -> list[Line]:
    from docling_parse.pdf_parser import DoclingPdfParser
    from docling_core.types.doc.page import TextCellUnit

    parser = DoclingPdfParser()
    doc = parser.load(path_or_stream=pdf_path)

    all_lines: list[Line] = []
    for page_no, page in doc.iterate_pages():
        words: list[Word] = []
        tops: list[float] = []
        page_h = page.dimension.height
        for cell in page.iterate_cells(unit_type=TextCellUnit.WORD):
            r = cell.rect
            x0 = min(r.r_x0, r.r_x1, r.r_x2, r.r_x3)
            x1 = max(r.r_x0, r.r_x1, r.r_x2, r.r_x3)
            y_top_pdf = max(r.r_y0, r.r_y1, r.r_y2, r.r_y3)
            top = page_h - y_top_pdf  # origem docling é bottom-left
            text = _dedup_texto(cell.text.strip())
            if not text:
                continue
            words.append(Word(text=text, x0=x0, x1=x1))
            tops.append(top)
        all_lines.extend(_agrupar_linhas(page_no, words, tops))
    return all_lines


# ----------------------------------------------------------------------------
# pdfplumber (validação cruzada)
# ----------------------------------------------------------------------------

def ler_com_pdfplumber(pdf_path: str) -> list[Line]:
    import pdfplumber

    all_lines: list[Line] = []
    with pdfplumber.open(pdf_path) as pdf:
        for page_no, page in enumerate(pdf.pages, start=1):
            page = page.dedupe_chars(tolerance=1)
            words: list[Word] = []
            tops: list[float] = []
            for w in page.extract_words():
                text = _dedup_texto(w["text"].strip())
                if not text:
                    continue
                words.append(Word(text=text, x0=w["x0"], x1=w["x1"]))
                tops.append(w["top"])
            all_lines.extend(_agrupar_linhas(page_no, words, tops))
    return all_lines


BACKENDS = {
    "docling": ler_com_docling,
    "pdfplumber": ler_com_pdfplumber,
}
