"""
Pipeline completo: PDF do PCMSO -> planilhas PGR + PCMSO (.xlsx).

Uso via CLI:
    python -m app.pipeline <caminho_do_pdf> [--backend docling|pdfplumber] [--out DIR]
"""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import asdict
from pathlib import Path

from .backends import BACKENDS
from .builder import montar_pcmso, montar_pgr
from .extractors import extrair_auto


def processar_pdf(
    pdf_path: str | Path,
    out_dir: str | Path,
    backend: str = "docling",
    coletar_ghes: list | None = None,
) -> dict:
    """Executa o fluxo completo e devolve um resumo (arquivos gerados + avisos).

    `coletar_ghes`: lista opcional onde os objetos GHE extraídos são
    depositados — permite ao chamador reaproveitar a extração (ex.: validação
    cruzada sem reparsear o PDF).
    """
    pdf_path = Path(pdf_path)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    lines = BACKENDS[backend](str(pdf_path))
    ghes, meta = extrair_auto(lines, pdf_path=str(pdf_path))
    if coletar_ghes is not None:
        coletar_ghes.extend(ghes)

    if not ghes:
        raise ValueError("Nenhum GHE encontrado no PDF — verifique o documento.")

    empresa = re.sub(r"[^\w]+", "_", meta.get("empresa") or "EMPRESA").strip("_")

    pgr_path = out_dir / f"PGR_{empresa}.xlsx"
    pcmso_path = out_dir / f"PCMSO_{empresa}.xlsx"
    montar_pgr(ghes).save(pgr_path)
    montar_pcmso(ghes).save(pcmso_path)

    # dump intermediário para auditoria/validação
    json_path = out_dir / f"extracao_{empresa}.json"
    json_path.write_text(
        json.dumps(
            {"meta": meta, "ghes": [asdict(g) for g in ghes]},
            ensure_ascii=False, indent=2,
        ),
        encoding="utf-8",
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
