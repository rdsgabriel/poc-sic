"""
Pipeline completo: PDF do PCMSO -> planilhas PGR + PCMSO (.xlsx).

Uso via CLI:
    python -m app.pipeline <caminho_do_pdf> [--backend docling|pdfplumber] [--out DIR]
"""

from __future__ import annotations

import argparse
import json
import logging
import re
from dataclasses import asdict
from pathlib import Path
from time import perf_counter

from .backends import BACKENDS
from .builder import montar_pcmso, montar_pgr
from .extractors import EXTRATORES, extrair_auto

LOGGER = logging.getLogger("uvicorn.error")


def _log(job_id: str | None, etapa: str, **dados: object) -> None:
    contexto = f"JOB {job_id}" if job_id else "PIPELINE"
    detalhes = " | ".join(f"{chave}={valor}" for chave, valor in dados.items())
    LOGGER.info("%s | %s%s", contexto, etapa, f" | {detalhes}" if detalhes else "")


def processar_pdf(
    pdf_path: str | Path,
    out_dir: str | Path,
    backend: str = "docling",
    coletar_ghes: list | None = None,
    job_id: str | None = None,
) -> dict:
    """Executa o fluxo completo e devolve um resumo (arquivos gerados + avisos).

    `coletar_ghes`: lista opcional onde os objetos GHE extraídos são
    depositados — permite ao chamador reaproveitar a extração (ex.: validação
    cruzada sem reparsear o PDF).
    """
    pdf_path = Path(pdf_path)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    inicio = perf_counter()
    etapa = perf_counter()
    _log(job_id, "leitura do PDF iniciada", leitor=backend)
    lines = BACKENDS[backend](str(pdf_path))
    _log(
        job_id,
        "leitura do PDF concluída",
        leitor=backend,
        paginas=max((linha.page for linha in lines), default=0),
        linhas=len(lines),
        duracao=f"{perf_counter() - etapa:.1f}s",
    )

    etapa = perf_counter()
    _log(job_id, "extração iniciada")
    ghes, meta = extrair_auto(lines, pdf_path=str(pdf_path))
    _log(
        job_id,
        "extração concluída",
        layout=meta.get("layout", "desconhecido"),
        ocr="aplicado" if meta.get("layout") == "solstad" else "não necessário",
        ghes=len(ghes),
        funcoes=sum(len(g.cargos) for g in ghes),
        duracao=f"{perf_counter() - etapa:.2f}s",
    )
    if coletar_ghes is not None:
        coletar_ghes.extend(ghes)

    if not ghes:
        raise ValueError("Nenhum GHE encontrado no PDF — verifique o documento.")

    empresa = re.sub(r"[^\w]+", "_", meta.get("empresa") or "EMPRESA").strip("_")

    # regras de IMPORTAÇÃO por layout (ex.: De-para de nomes do cliente SK no
    # mafra): valem só para as planilhas — a extração, a tela de conferência e
    # os goldens mantêm a nomenclatura exata do PDF
    modulo = dict(EXTRATORES).get(meta.get("layout"))
    ghes_planilha = (
        modulo.preparar_para_planilha(ghes)
        if modulo is not None and hasattr(modulo, "preparar_para_planilha")
        else ghes
    )

    etapa = perf_counter()
    _log(job_id, "geração das planilhas iniciada")
    pgr_path = out_dir / f"PGR_{empresa}.xlsx"
    pcmso_path = out_dir / f"PCMSO_{empresa}.xlsx"
    montar_pgr(ghes_planilha).save(pgr_path)
    montar_pcmso(ghes_planilha).save(pcmso_path)

    # dump intermediário para auditoria/validação
    json_path = out_dir / f"extracao_{empresa}.json"
    json_path.write_text(
        json.dumps(
            {"meta": meta, "ghes": [asdict(g) for g in ghes]},
            ensure_ascii=False, indent=2,
        ),
        encoding="utf-8",
    )
    _log(
        job_id,
        "arquivos gerados",
        pgr=pgr_path.name,
        pcmso=pcmso_path.name,
        auditoria=json_path.name,
        duracao=f"{perf_counter() - etapa:.2f}s",
        total=f"{perf_counter() - inicio:.1f}s",
    )

    avisos = [f"[{g.codigo}] {a}" for g in ghes for a in g.avisos]
    return {
        "empresa": meta.get("empresa", ""),
        "backend": backend,
        "avisos_documento": meta.get("avisos_documento", []),
        "total_ghes": len(ghes),
        "total_funcoes": sum(len(g.cargos) for g in ghes),
        "ghes": [
            {
                "setor": g.setor,
                "riscos": len(g.riscos),
                "exames": len(g.exames),
                "funcoes": len(g.cargos),
            }
            for g in ghes
        ],
        "avisos": avisos,
        "arquivos": {
            "pgr": str(pgr_path),
            "pcmso": str(pcmso_path),
            "json": str(json_path),
        },
    }


def main() -> None:
    ap = argparse.ArgumentParser(description="PDF PCMSO -> planilhas PGR/PCMSO")
    ap.add_argument("pdf")
    ap.add_argument("--backend", choices=list(BACKENDS), default="docling")
    ap.add_argument("--out", default="output")
    args = ap.parse_args()

    resumo = processar_pdf(args.pdf, args.out, args.backend)
    print(json.dumps(resumo, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
