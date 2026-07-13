"""
Validação da extração.

1. Validação cruzada: compara a extração feita com dois leitores independentes
   (docling e pdfplumber). Divergência = sinal de erro de leitura.
2. Regras de consistência: todo GHE tem riscos/exames/funções; todo exame
   periódico tem meses; padrão de nomenclatura do setor.

Uso:
    python -m app.validate <caminho_do_pdf>
"""

from __future__ import annotations

import sys
from dataclasses import asdict

from .backends import BACKENDS
from .extractors import GHE, extrair_auto


def comparar_backends(pdf_path: str, ghes_docling: list[GHE] | None = None) -> list[str]:
    """Compara a extração dos dois leitores.

    `ghes_docling`: extração docling já feita pelo pipeline — evita reparsear
    o PDF (documentos grandes custam minutos por parse).
    """
    resultados = {}
    for nome, leitor in BACKENDS.items():
        if nome == "docling" and ghes_docling is not None:
            resultados[nome] = {g.codigo: g for g in ghes_docling}
            continue
        ghes, _ = extrair_auto(leitor(pdf_path))
        resultados[nome] = {g.codigo: g for g in ghes}

    a, b = resultados["docling"], resultados["pdfplumber"]
    problemas: list[str] = []

    if set(a) != set(b):
        problemas.append(f"GHEs divergem: docling={sorted(a)} pdfplumber={sorted(b)}")

    for cod in sorted(set(a) & set(b)):
        ga, gb = a[cod], b[cod]
        if ga.nome != gb.nome:
            problemas.append(f"[{cod}] nome: {ga.nome!r} != {gb.nome!r}")
        ra = {(r.nome, r.grupo) for r in ga.riscos}
        rb = {(r.nome, r.grupo) for r in gb.riscos}
        if ra != rb:
            problemas.append(f"[{cod}] riscos divergem: {ra ^ rb}")
        ea = {tuple(sorted(asdict(e).items())) for e in ga.exames}
        eb = {tuple(sorted(asdict(e).items())) for e in gb.exames}
        if ea != eb:
            so_a = [dict(t)["nome"] for t in ea - eb]
            so_b = [dict(t)["nome"] for t in eb - ea]
            problemas.append(f"[{cod}] exames divergem: docling={so_a} pdfplumber={so_b}")
        if set(ga.cargos) != set(gb.cargos):
            problemas.append(
                f"[{cod}] cargos divergem: {set(ga.cargos) ^ set(gb.cargos)}"
            )
    return problemas


def checar_regras(ghes: list[GHE]) -> list[str]:
    problemas: list[str] = []
    for g in ghes:
        if not g.nome and not g.setor_override:
            problemas.append(f"[{g.codigo}] setor sem nome")
        if not g.riscos and not g.ausencia_riscos:
            problemas.append(f"[{g.codigo}] nenhum risco extraído")
        if not g.exames:
            problemas.append(f"[{g.codigo}] nenhum exame extraído")
        if not g.cargos:
            problemas.append(f"[{g.codigo}] nenhuma função extraída")
        for e in g.exames:
            if not any([e.admissao, e.periodico_meses, e.apos_adm,
                        e.apos_adm_meses, e.ret_trab, e.mud_riscos, e.demissao]):
                problemas.append(f"[{g.codigo}] exame {e.nome!r} sem nenhum perfil")
        for a in g.avisos:
            if not a.startswith("INFO:"):  # informativos não reprovam a extração
                problemas.append(f"[{g.codigo}] aviso: {a}")
    return problemas


def main() -> None:
    pdf = sys.argv[1]
    print("== Validação cruzada docling x pdfplumber ==")
    problemas = comparar_backends(pdf)
    if problemas:
        for p in problemas:
            print("  DIVERGÊNCIA:", p)
    else:
        print("  OK — os dois leitores produzem extração idêntica.")



    print("== Regras de consistência (docling) ==")
    ghes, _ = extrair_auto(BACKENDS["docling"](pdf))
    regras = checar_regras(ghes)
    if regras:
        for p in regras:
            print("  PROBLEMA:", p)
    else:
        print("  OK — todos os GHEs completos e consistentes.")

    sys.exit(1 if (problemas or regras) else 0)


if __name__ == "__main__":
    main()
