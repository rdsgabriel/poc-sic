"""
Modelo neutro compartilhado por todos os extratores de layout.

Os backends de leitura (docling, pdfplumber) produzem List[Line]; cada
extrator de família de documento consome esse modelo e devolve List[GHE].
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field


@dataclass
class Word:
    text: str
    x0: float
    x1: float


@dataclass
class Line:
    page: int
    top: float
    words: list[Word]

    @property
    def text(self) -> str:
        return " ".join(w.text for w in self.words)


@dataclass
class Risco:
    nome: str
    grupo: str


@dataclass
class Exame:
    nome: str
    admissao: bool = False
    apos_adm_meses: int | None = None
    apos_adm: bool = False
    periodico_meses: int | None = None
    ret_trab: bool = False
    mud_riscos: bool = False
    demissao: bool = False


@dataclass
class GHE:
    codigo: str
    nome: str
    riscos: list[Risco] = field(default_factory=list)
    exames: list[Exame] = field(default_factory=list)
    cargos: list[str] = field(default_factory=list)
    avisos: list[str] = field(default_factory=list)
    # documento declara explicitamente "Ausência de Riscos" (layout VIX)
    ausencia_riscos: bool = False
    # layouts sem o padrão "GHE 01 - NOME" definem o texto do setor diretamente
    setor_override: str | None = None
    # página do PDF onde a seção do GHE começa (para a tela de conferência)
    pagina: int | None = None
    # NRs aplicáveis por cargo (layout Solstad: tabela de atividades críticas).
    # cargo -> lista de chaves de builder.NR_COLS (ex.: "NR33", "NR35").
    # Quando preenchido, o builder usa SOMENTE isto (ignora NR_TRIGGERS).
    nrs: dict[str, list[str]] = field(default_factory=dict)

    @property
    def setor(self) -> str:
        if self.setor_override:
            return self.setor_override
        # Padrão exigido: "GHE 01 - ADMINISTRATIVO" (sem hífen extra)
        return f"GHE {self.codigo} - {self.nome}".strip().rstrip("-").strip()


def norm(s: str) -> str:
    """minúsculas, sem acentos, espaços colapsados — para comparações."""
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", s).strip().lower()


# --------------------------------------------------------------- foco (spotlight)
# Coordenadas para a tela de conferência destacar, na página do PDF, ONDE cada
# GHE está. O contrato consumido pelo front (PdfSpotlight) é, por código de GHE:
#     {pagina, top, bottom, funcao?: {pagina, top, bottom, left, right}}
# `top`/`bottom` são a banda vertical da seção (o visualizador escurece o resto
# e rola até ela); `funcao` é a caixa opcional destacada em âmbar. Todas as
# coordenadas em pontos PDF (origem no topo), como em Line.top / Word.x0.


def faixa_pdf(
    linhas: list[Line], pagina: int, *,
    margem_topo: float = 7.0, margem_base: float = 16.0,
) -> dict | None:
    """Banda vertical {pagina, top, bottom} das linhas na página dada."""
    da_pagina = [ln for ln in linhas if ln.page == pagina]
    if not da_pagina:
        return None
    return {
        "pagina": pagina,
        "top": round(max(0.0, min(ln.top for ln in da_pagina) - margem_topo), 1),
        "bottom": round(max(ln.top for ln in da_pagina) + margem_base, 1),
    }


def caixa_pdf(linhas: list[Line], *, filtro=None) -> dict | None:
    """Caixa {pagina, top, bottom, left, right} ao redor das palavras das
    `linhas` (restritas à primeira página encontrada). `filtro(Word)->bool`
    limita as palavras consideradas (ex.: só a coluna da função)."""
    if not linhas:
        return None
    pagina = linhas[0].page
    da_pagina = [
        ln for ln in linhas
        if ln.page == pagina and any(filtro is None or filtro(w) for w in ln.words)
    ]
    palavras = [
        w for ln in da_pagina for w in ln.words if filtro is None or filtro(w)
    ]
    if not palavras:
        return None
    return {
        "pagina": pagina,
        "top": round(max(0.0, min(ln.top for ln in da_pagina) - 1), 1),
        "bottom": round(max(ln.top for ln in da_pagina) + 9, 1),
        "left": round(max(0.0, min(w.x0 for w in palavras) - 3), 1),
        "right": round(max(w.x1 for w in palavras) + 3, 1),
    }


def montar_foco(
    secao: list[Line], pagina: int | None,
    funcao: list[Line] | None = None, *, filtro_funcao=None,
) -> dict | None:
    """Foco de um GHE: banda da seção em `pagina` + caixa opcional da função
    (só anexada se cair na mesma página da banda)."""
    if pagina is None:
        return None
    faixa = faixa_pdf(secao, pagina)
    if faixa is None:
        return None
    if funcao:
        caixa = caixa_pdf(funcao, filtro=filtro_funcao)
        if caixa and caixa["pagina"] == pagina:
            faixa["funcao"] = caixa
    return faixa
