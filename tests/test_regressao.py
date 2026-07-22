"""
Testes de regressão da extração — um golden por layout de PCMSO.

Estrutura (convenção de nome + pasta, sem lista manual de PDFs):

    tests/golden/<layout>/<nome>.json   ← contrato, versionado
    tests/pdfs/<layout>/<nome>.pdf      ← PDF real, FORA do git (LGPD)

Os casos são auto-descobertos varrendo os goldens; o PDF é procurado pela
convenção de nome. PDFs ausentes (a suíte roda em máquina sem os documentos
do cliente) são pulados — os goldens continuam versionados.

Rodar só um layout enquanto trabalha nele:  pytest tests/ -k solstad
Adicionar/atualizar um caso:                 python -m tests.treinar <layout> <pdf>
Regra de ouro (ver GUIA_MELHORIAS.md): golden só é regravado após validação
humana e com os dois leitores concordando.
"""

from __future__ import annotations

import json
from dataclasses import asdict
from functools import lru_cache
from pathlib import Path

import pytest

from app.backends import BACKENDS
from app.extractors import extrair_auto
from app.validate import checar_documento

GOLDEN = Path(__file__).resolve().parent / "golden"
PDFS = Path(__file__).resolve().parent / "pdfs"


def _casos() -> list[tuple[str, Path, Path]]:
    """(layout, pdf, golden) para cada golden/<layout>/<nome>.json."""
    casos = []
    for golden in sorted(GOLDEN.glob("*/*.json")):
        layout = golden.parent.name
        pdf = PDFS / layout / f"{golden.stem}.pdf"
        casos.append((layout, pdf, golden))
    return casos


_CASOS = _casos()
_EXISTENTES = [c for c in _CASOS if c[1].is_file()]
# id "<layout>-<nome>" para filtrar por layout: pytest tests/ -k solstad
_IDS = [f"{lay}-{golden.stem}" for lay, _, golden in _EXISTENTES]

_CASOS_PARAM = pytest.mark.parametrize("layout,pdf,golden", _EXISTENTES, ids=_IDS)

_CAMPOS_CONTRATO = (
    "codigo", "nome", "riscos", "exames", "cargos",
    "ausencia_riscos", "setor_override", "nrs",
)
_PADROES_GHE = {
    "ausencia_riscos": False, "setor_override": None, "nrs": {},
}


def _contrato(ghe: dict) -> dict:
    return {
        campo: ghe.get(campo, _PADROES_GHE.get(campo))
        for campo in _CAMPOS_CONTRATO
    }


@lru_cache(maxsize=None)
def _extrair_objetos(pdf: Path, backend: str):
    ghes, meta = extrair_auto(BACKENDS[backend](str(pdf)), pdf_path=str(pdf))
    return ghes, meta


def _extrair(pdf: Path, backend: str) -> dict:
    ghes, meta = _extrair_objetos(pdf, backend)
    return {"meta": meta, "ghes": [asdict(g) for g in ghes]}


def test_ha_goldens_registrados() -> None:
    """Guarda contra suíte vazia (glob que não casa nada = falso verde)."""
    assert _CASOS, "nenhum golden encontrado em tests/golden/<layout>/"


@_CASOS_PARAM
@pytest.mark.parametrize("backend", ["docling", "pdfplumber"])
def test_extracao_igual_ao_golden(
    layout: str, pdf: Path, golden: Path, backend: str
) -> None:
    esperado = json.loads(golden.read_text(encoding="utf-8"))
    obtido = _extrair(pdf, backend)
    assert obtido["meta"]["total_ghes"] == esperado["meta"]["total_ghes"]

    esperado_por_codigo = {g["codigo"]: g for g in esperado["ghes"]}
    obtido_por_codigo = {g["codigo"]: g for g in obtido["ghes"]}
    assert set(obtido_por_codigo) == set(esperado_por_codigo)

    for cod, exp in esperado_por_codigo.items():
        obt = obtido_por_codigo[cod]
        assert _contrato(obt) == _contrato(exp), f"GHE {cod}: contrato diverge"


@_CASOS_PARAM
def test_regras_de_consistencia(layout: str, pdf: Path, golden: Path) -> None:
    ghes, meta = _extrair_objetos(pdf, "pdfplumber")
    problemas = checar_documento(ghes, meta)
    assert not problemas, "\n".join(problemas)

    # foco (spotlight da tela de conferência): TODO layout emite a banda
    # vertical de cada GHE; quando há caixa de função, ela é validada; o
    # Solstad garante a caixa em todos os GHEs.
    focos = meta.get("focos", {})
    assert set(focos) == {g.codigo for g in ghes}, "todo GHE precisa de foco"
    for f in focos.values():
        assert f["pagina"] >= 1 and 0 <= f["top"] < f["bottom"]
        cx = f.get("funcao")
        if cx is not None:
            assert cx["pagina"] == f["pagina"]
            assert 0 <= cx["top"] < cx["bottom"]
            assert 0 <= cx["left"] < cx["right"]
    if layout == "solstad":
        assert all("funcao" in f for f in focos.values())


@_CASOS_PARAM
def test_backends_concordam(layout: str, pdf: Path, golden: Path) -> None:
    a = _extrair(pdf, "docling")
    b = _extrair(pdf, "pdfplumber")
    assert a["ghes"] == b["ghes"]
