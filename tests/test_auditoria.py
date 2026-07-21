from app.auditoria import auditar_ghe


def _ghe(**mudancas) -> dict:
    base = {
        "riscos": [{"nome": "RUÍDO", "grupo": "Físico"}],
        "exames": [{
            "nome": "EXAME CLÍNICO",
            "admissao": True,
            "periodico_meses": 12,
            "apos_adm": False,
            "apos_adm_meses": None,
            "ret_trab": True,
            "mud_riscos": True,
            "demissao": True,
        }],
        "cargos": ["ELETRICISTA"],
        "avisos": [],
        "ausencia_riscos": False,
    }
    base.update(mudancas)
    return base


def test_score_expoe_memoria_do_calculo() -> None:
    resultado = auditar_ghe(
        _ghe(avisos=["INFO: conferir abreviação", "falha de estrutura"]),
        ["[GHE 1] riscos divergem"],
    )

    assert resultado["confianca"] == 25
    assert resultado["fatores_confianca"] == [
        {"desconto": 40, "descricao": "Leitores divergem: [GHE 1] riscos divergem"},
        {"desconto": 25, "descricao": "falha de estrutura"},
        {"desconto": 10, "descricao": "conferir abreviação"},
    ]
    assert resultado["pontos_atencao"] == [
        fator["descricao"] for fator in resultado["fatores_confianca"]
    ]


def test_score_perfeito_nao_tem_descontos() -> None:
    resultado = auditar_ghe(_ghe(), [])

    assert resultado["confianca"] == 100
    assert resultado["fatores_confianca"] == []
    assert resultado["pontos_atencao"] == []
