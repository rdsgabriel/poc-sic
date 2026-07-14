"""
Registro de extratores por família de layout de PCMSO.

Cada família de documento (emissor/empresa) tem um módulo próprio expondo:
  - detectar(lines) -> bool   : reconhece a família
  - extrair(lines) -> (ghes, meta) : extração para o modelo neutro
    (extratores que precisam do arquivo original — ex.: OCR de tabelas que são
    imagem, caso Solstad — declaram o parâmetro extra `pdf_path`)

Para adicionar uma família nova, crie o módulo e registre-o em EXTRATORES
(a ordem importa: o primeiro detector que casar vence). Processo completo em
GUIA_MELHORIAS.md.
"""

from __future__ import annotations

import inspect

from .base import GHE, Exame, Line, Risco, Word, norm
from . import mafra, occupare, sicolos, solstad, vix

EXTRATORES = [
    ("sicolos", sicolos),
    ("vix", vix),
    ("occupare", occupare),
    ("mafra", mafra),
    ("solstad", solstad),
]


def extrair_auto(
    lines: list[Line], pdf_path: str | None = None
) -> tuple[list[GHE], dict]:
    """Detecta a família de layout do PCMSO e roteia para o extrator certo."""
    for nome, modulo in EXTRATORES:
        if modulo.detectar(lines):
            if "pdf_path" in inspect.signature(modulo.extrair).parameters:
                ghes, meta = modulo.extrair(lines, pdf_path=pdf_path)
            else:
                ghes, meta = modulo.extrair(lines)
            meta.setdefault("layout", nome)
            return ghes, meta
    raise ValueError(
        "Layout de PCMSO não reconhecido por nenhum extrator registrado "
        f"({', '.join(n for n, _ in EXTRATORES)}). "
        "Ver GUIA_MELHORIAS.md para adicionar um layout novo."
    )


__all__ = [
    "GHE", "Exame", "Line", "Risco", "Word", "norm",
    "EXTRATORES", "extrair_auto",
]
