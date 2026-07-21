from __future__ import annotations

from app.extractors.base import Exame, GHE, Risco
from app.validate import checar_documento, checar_regras


def _ghe(cargo: str = "MARINHEIRO DE CONVÉS") -> GHE:
    g = GHE(
        codigo="4/MARINHEIRO DE CONVÉS",
        nome="MARINHEIRO DE CONVÉS",
        cargos=[cargo],
        riscos=[Risco(nome="RUÍDO", grupo="Físico")],
        exames=[Exame(nome="CLÍNICO", admissao=True)],
        setor_override="GHE 4",
    )
    g.nrs = {cargo: ["NR30", "NR33", "NR35", "NR37_BRIGADA"]}
    return g


def test_reprova_rotulo_estrutural_como_funcao() -> None:
    problemas = checar_regras([_ghe("ATIVIDADES")])
    assert any("rótulo estrutural" in p for p in problemas)


def test_reprova_id_numerico_como_funcao() -> None:
    problemas = checar_regras([_ghe("123456789")])
    assert any("identificador numérico" in p for p in problemas)


def test_solstad_reprova_quando_ocr_resulta_so_em_nr30() -> None:
    g = _ghe()
    g.nrs = {g.cargos[0]: ["NR30"]}
    problemas = checar_documento([g], {"layout": "solstad"})
    assert any("sem nenhuma NR33" in p for p in problemas)
    assert any("sem nenhuma NR35" in p for p in problemas)
    assert any("sem nenhuma NR37" in p for p in problemas)


def test_solstad_aceita_cobertura_de_nrs_criticas() -> None:
    assert checar_documento([_ghe()], {"layout": "solstad"}) == []

