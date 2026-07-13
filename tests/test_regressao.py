"""
Testes de regressão da extração.

Cada PDF conhecido tem um "golden file" (tests/golden/*.json) com a extração
validada por humanos. Qualquer mudança no parser DEVE manter estes testes
verdes — eles são o contrato do que já funciona.

Para adicionar um PDF novo:
  1. rode: python -m app.pipeline caminho/do/novo.pdf --out /tmp/novo
  2. valide o JSON gerado manualmente (spot-check contra o PDF)
  3. copie para tests/golden/ e registre em PDFS abaixo
"""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

import pytest

from app.backends import BACKENDS
from app.extractors import extrair_auto
from app.validate import checar_regras

RAIZ = Path(__file__).resolve().parent.parent
GOLDEN = Path(__file__).resolve().parent / "golden"

# (pdf, golden json) — caminhos relativos à raiz do projeto
PDFS = [
    (
        "PCMSO_CAMPO_GRANDE_22_09__Brmed by sicolos.pdf",
        "campo_grande_22_09.json",
    ),
    (
        "AguasDoBrasilPoC/Campo Grande/PCMSO_CAMPO_GRANDE_27_08_.pdf",
        "campo_grande_27_08.json",
    ),
    # layout VIX Logística (seções por Ocupação/FPC, exames por perfil de ASO)
    (
        "PCMSO_Cenibra_Belo_Orient.pdf",
        "cenibra_belo_oriente.json",
    ),
    # layout Occupare (SETOR: GSE -> FUNÇÃO, checkboxes por perfil, 1 GHE por função)
    (
        "PCMSO-SKINFRAESTRUTURALTDA-ITAJUIENGENHARIADEOBRASLTDA (1).pdf",
        "sk_itajui.json",
    ),
    # layout Mafra Ambiental (CARGO -> riscos com ícone, exames "Fazer no ...")
    (
        "PCMSO-SkTecnologia-MineraoTabocaS.A.R0.pdf",
        "sk_taboca.json",
    ),
]

_EXISTENTES = [(p, g) for p, g in PDFS if (RAIZ / p).is_file()]


def _extrair(pdf: str, backend: str) -> dict:
    ghes, meta = extrair_auto(BACKENDS[backend](str(RAIZ / pdf)))
    return {"meta": meta, "ghes": [asdict(g) for g in ghes]}


@pytest.mark.parametrize("pdf,golden", _EXISTENTES)
@pytest.mark.parametrize("backend", ["docling", "pdfplumber"])
def test_extracao_igual_ao_golden(pdf: str, golden: str, backend: str) -> None:
    esperado = json.loads((GOLDEN / golden).read_text(encoding="utf-8"))
    obtido = _extrair(pdf, backend)
    assert obtido["meta"]["total_ghes"] == esperado["meta"]["total_ghes"]

    esperado_por_codigo = {g["codigo"]: g for g in esperado["ghes"]}
    obtido_por_codigo = {g["codigo"]: g for g in obtido["ghes"]}
    assert set(obtido_por_codigo) == set(esperado_por_codigo)

    for cod, exp in esperado_por_codigo.items():
        obt = obtido_por_codigo[cod]
        assert obt["nome"] == exp["nome"], f"GHE {cod}: nome divergente"
        assert obt["riscos"] == exp["riscos"], f"GHE {cod}: riscos divergem"
        assert obt["exames"] == exp["exames"], f"GHE {cod}: exames divergem"
        assert obt["cargos"] == exp["cargos"], f"GHE {cod}: cargos divergem"


@pytest.mark.parametrize("pdf,_", _EXISTENTES)
def test_regras_de_consistencia(pdf: str, _: str) -> None:
    ghes, __ = extrair_auto(BACKENDS["pdfplumber"](str(RAIZ / pdf)))
    problemas = checar_regras(ghes)
    assert not problemas, "\n".join(problemas)


@pytest.mark.parametrize("pdf,_", _EXISTENTES)
def test_backends_concordam(pdf: str, _: str) -> None:
    a = _extrair(pdf, "docling")
    b = _extrair(pdf, "pdfplumber")
    assert a["ghes"] == b["ghes"]
