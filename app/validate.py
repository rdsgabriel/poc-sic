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

import re
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
        ghes, _ = extrair_auto(leitor(pdf_path), pdf_path=pdf_path)
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
        if ga.setor_override != gb.setor_override:
            problemas.append(
                f"[{cod}] setor diverge: "
                f"{ga.setor_override!r} != {gb.setor_override!r}"
            )
        if ga.ausencia_riscos != gb.ausencia_riscos:
            problemas.append(
                f"[{cod}] declaração de ausência de riscos diverge"
            )
        if ga.nrs != gb.nrs:
            problemas.append(f"[{cod}] NRs divergem: {ga.nrs!r} != {gb.nrs!r}")
    return problemas


_ROTULOS_QUE_NAO_SAO_FUNCAO = {
    "atividade", "atividades", "funcao", "funcoes", "mineral", "risco", "riscos",
}
_NRS_VALIDAS = {
    "NR10", "NR11", "NR20", "NR30", "NR33", "NR34", "NR35",
    "NR37_TRANSBORDO", "NR37_EMBARQUE", "NR37_BRIGADA",
}


def _funcao_suspeita(nome: str) -> str | None:
    """Devolve o motivo quando uma função parece vazamento de outra coluna."""
    limpo = re.sub(r"[^A-Za-zÀ-ÿ]+", " ", nome).strip().lower()
    if limpo in _ROTULOS_QUE_NAO_SAO_FUNCAO:
        return f"rótulo estrutural extraído como função: {nome!r}"
    if re.fullmatch(r"\s*\d{5,}\s*", nome):
        return f"identificador numérico extraído como função: {nome!r}"
    if re.search(r"(?:^|\s)\d{6,}(?:\s|$)", nome):
        return f"função contém identificador numérico suspeito: {nome!r}"
    return None


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
        for cargo in g.cargos:
            motivo = _funcao_suspeita(cargo.split(" / ", 1)[0])
            if motivo:
                problemas.append(f"[{g.codigo}] {motivo}")
        for cargo, nrs in g.nrs.items():
            if cargo not in g.cargos:
                problemas.append(
                    f"[{g.codigo}] NRs associadas a função inexistente: {cargo!r}"
                )
            invalidas = sorted(set(nrs) - _NRS_VALIDAS)
            if invalidas:
                problemas.append(f"[{g.codigo}] NRs desconhecidas: {invalidas}")
        for e in g.exames:
            if not any([e.admissao, e.periodico_meses, e.apos_adm,
                        e.apos_adm_meses, e.ret_trab, e.mud_riscos, e.demissao]):
                problemas.append(f"[{g.codigo}] exame {e.nome!r} sem nenhum perfil")
        for a in g.avisos:
            if not a.startswith("INFO:"):  # informativos não reprovam a extração
                problemas.append(f"[{g.codigo}] aviso: {a}")
    return problemas


def checar_documento(ghes: list[GHE], meta: dict) -> list[str]:
    """Regras que dependem do conjunto completo e da família do documento."""
    problemas = checar_regras(ghes)

    if meta.get("layout") == "solstad":
        todas_nrs = {
            nr
            for g in ghes
            for nrs in g.nrs.values()
            for nr in nrs
        }
        if "NR30" not in todas_nrs:
            problemas.append("[documento] Solstad sem NR30")
        for nr in ("NR33", "NR35"):
            if nr not in todas_nrs:
                problemas.append(
                    f"[documento] Solstad sem nenhuma {nr}; provável falha no OCR "
                    "ou no casamento da tabela de atividades críticas"
                )
        if not any(nr.startswith("NR37_") for nr in todas_nrs):
            problemas.append(
                "[documento] Solstad sem nenhuma NR37; provável falha no OCR "
                "ou no casamento da tabela de atividades críticas"
            )

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
    ghes, meta = extrair_auto(BACKENDS["docling"](pdf), pdf_path=pdf)
    regras = checar_documento(ghes, meta)
    if regras:
        for p in regras:
            print("  PROBLEMA:", p)
    else:
        print("  OK — todos os GHEs completos e consistentes.")

    sys.exit(1 if (problemas or regras) else 0)


if __name__ == "__main__":
    main()
