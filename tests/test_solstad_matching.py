from app.extractors import solstad


def test_niveis_agrupados_casam_com_cada_funcao() -> None:
    agrupada = "OFIC. QTO. MAQ III/IV"
    assert solstad._tier("OFIC. QTO. MAQ III", agrupada) > 0
    assert solstad._tier("OFIC. QTO. MAQ IV", agrupada) > 0


def test_ocr_sem_nivel_casa_com_todos_os_niveis_do_radical() -> None:
    ocr = solstad._normalizar_funcao_ocr("DFIC. M&Q")
    assert ocr == "OFIC. QTO. MAQ"
    assert solstad._tier("OFIC. QTO. MAQ III", ocr) > 0
    assert solstad._tier("OFIC. QTO. MAQ IV", ocr) > 0

