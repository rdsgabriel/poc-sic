from pathlib import Path

from tests.treinar import _nome_caso


def test_nome_caso_solstad_usa_embarcacao() -> None:
    pdf = Path(
        "PCMSO-SOLSTAD_SHIPPING_N (6)_EMBARCAÇÃO NORMAND SAGARIS.pdf"
    )
    assert _nome_caso(pdf, "solstad") == "normand_sagaris"


def test_nome_caso_generico_usa_nome_do_arquivo() -> None:
    assert _nome_caso(Path("Documento Exemplo.pdf"), "sicolos") == "documento_exemplo"

