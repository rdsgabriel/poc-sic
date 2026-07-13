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
