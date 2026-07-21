"""
API da POC: recebe o PDF do PCMSO e devolve as planilhas PGR e PCMSO.

O front (React, em front-end/) é servido como estático a partir de
front-end/dist quando o build existir:

    cd front-end && npm install && npm run build
    uvicorn app.main:app --host 0.0.0.0 --port 8000

Em desenvolvimento do front, use `npm run dev` (Vite proxia a API em :8000).
"""

from __future__ import annotations

import json
import logging
import shutil
import tempfile
import uuid
from pathlib import Path
from time import perf_counter

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse, JSONResponse

from .pipeline import processar_pdf

LOGGER = logging.getLogger("uvicorn.error")

app = FastAPI(title="POC PCMSO -> Planilhas")

JOBS_DIR = Path(tempfile.gettempdir()) / "poc_pcmso_jobs"
JOBS_DIR.mkdir(parents=True, exist_ok=True)

DIST_DIR = Path(__file__).resolve().parent.parent / "front-end" / "dist"


@app.post("/processar")
async def processar(pdf: UploadFile = File(...)) -> JSONResponse:
    if not (pdf.filename or "").lower().endswith(".pdf"):
        raise HTTPException(400, "Envie um arquivo PDF.")

    job_id = uuid.uuid4().hex[:12]
    job_dir = JOBS_DIR / job_id
    job_dir.mkdir(parents=True)
    pdf_path = job_dir / "entrada.pdf"
    with pdf_path.open("wb") as f:
        shutil.copyfileobj(pdf.file, f)

    inicio = perf_counter()
    tamanho_mb = pdf_path.stat().st_size / (1024 * 1024)
    LOGGER.info(
        "JOB %s | recebido | arquivo=%r | tamanho=%.2f MB",
        job_id,
        pdf.filename,
        tamanho_mb,
    )

    try:
        ghes_docling: list = []
        resumo = processar_pdf(
            pdf_path,
            job_dir,
            backend="docling",
            coletar_ghes=ghes_docling,
            job_id=job_id,
        )
    except Exception as exc:  # noqa: BLE001 — erro vira resposta legível
        LOGGER.exception(
            "JOB %s | falhou na extração | duracao=%.1fs",
            job_id,
            perf_counter() - inicio,
        )
        raise HTTPException(422, f"Não foi possível processar o PDF: {exc}") from exc

    dump = json.loads(Path(resumo["arquivos"]["json"]).read_text(encoding="utf-8"))

    # validação cruzada + regras do documento, reusando a extração docling
    from .validate import checar_documento, comparar_backends

    validacao_inicio = perf_counter()
    LOGGER.info(
        "JOB %s | validação cruzada iniciada | leitor_secundario=pdfplumber",
        job_id,
    )
    try:
        divergencias = comparar_backends(str(pdf_path), ghes_docling=ghes_docling)
        divergencias.extend(checar_documento(ghes_docling, dump["meta"]))
    except Exception as exc:  # noqa: BLE001
        divergencias = [f"validação cruzada indisponível: {exc}"]
        LOGGER.exception("JOB %s | validação cruzada falhou", job_id)
    LOGGER.info(
        "JOB %s | validação cruzada concluída | resultado=%s | pendencias=%d | duracao=%.1fs",
        job_id,
        "OK" if not divergencias else "REVISAR",
        len(divergencias),
        perf_counter() - validacao_inicio,
    )
    for divergencia in divergencias[:5]:
        LOGGER.warning("JOB %s | pendencia | %s", job_id, divergencia)
    if len(divergencias) > 5:
        LOGGER.warning(
            "JOB %s | pendencias adicionais omitidas | quantidade=%d",
            job_id,
            len(divergencias) - 5,
        )

    downloads = {}
    for rotulo, caminho in [
        ("Planilha PGR", resumo["arquivos"]["pgr"]),
        ("Planilha PCMSO", resumo["arquivos"]["pcmso"]),
        ("JSON de debug", resumo["arquivos"]["json"]),
    ]:
        nome = Path(caminho).name
        downloads[rotulo] = f"/download/{job_id}/{nome}"

    # detalhe por GHE para a tela de conferência (PDF x extraído lado a lado)
    from .auditoria import auditar

    auditorias = auditar(dump["ghes"], divergencias)
    ghes_detalhe = [
        {
            "setor": g_resumo["setor"],
            "codigo": g_dump["codigo"],
            "pagina": g_dump.get("pagina"),
            "foco": dump["meta"].get("focos", {}).get(g_dump["codigo"]),
            "cargos": g_dump["cargos"],
            "riscos": g_dump["riscos"],
            "exames": g_dump["exames"],
            "ausencia_riscos": g_dump.get("ausencia_riscos", False),
            "avisos": g_dump["avisos"],
            "confianca": aud["confianca"],
            "fatores_confianca": aud["fatores_confianca"],
            "pontos_atencao": aud["pontos_atencao"],
        }
        for g_resumo, g_dump, aud in zip(resumo["ghes"], dump["ghes"], auditorias)
    ]

    LOGGER.info(
        "JOB %s | concluído | layout=%s | empresa=%r | ghes=%d | funcoes=%d | avisos_documento=%d | validacao=%s | total=%.1fs",
        job_id,
        dump["meta"].get("layout", "desconhecido"),
        resumo["empresa"],
        resumo["total_ghes"],
        resumo["total_funcoes"],
        len(resumo.get("avisos_documento", [])),
        "OK" if not divergencias else "REVISAR",
        perf_counter() - inicio,
    )

    return JSONResponse(
        {
            "job_id": job_id,
            "resumo": resumo,
            "validacao_ok": not divergencias,
            "divergencias": divergencias,
            "downloads": downloads,
            "ghes_detalhe": ghes_detalhe,
        }
    )


@app.get("/pdf/{job_id}")
def ver_pdf(job_id: str) -> FileResponse:
    """PDF original inline, para o iframe da tela de conferência."""
    caminho = (JOBS_DIR / job_id / "entrada.pdf").resolve()
    if not caminho.is_file() or JOBS_DIR.resolve() not in caminho.parents:
        LOGGER.warning("JOB %s | PDF não encontrado", job_id)
        raise HTTPException(404, "Documento não encontrado.")
    response = FileResponse(caminho, media_type="application/pdf")
    response.headers["Content-Disposition"] = 'inline; filename="documento.pdf"'
    return response


@app.get("/download/{job_id}/{nome}")
def download(job_id: str, nome: str) -> FileResponse:
    caminho = (JOBS_DIR / job_id / nome).resolve()
    if not caminho.is_file() or JOBS_DIR.resolve() not in caminho.parents:
        LOGGER.warning("JOB %s | download não encontrado | arquivo=%r", job_id, nome)
        raise HTTPException(404, "Arquivo não encontrado.")
    LOGGER.info("JOB %s | download | arquivo=%s", job_id, caminho.name)
    return FileResponse(caminho, filename=nome)


# front React buildado (front-end/dist) servido na raiz — registrado por
# último para não engolir as rotas da API
if DIST_DIR.is_dir():
    from fastapi.staticfiles import StaticFiles

    app.mount("/", StaticFiles(directory=DIST_DIR, html=True), name="front")
else:  # build ausente: instrução amigável em vez de 404

    @app.get("/")
    def sem_front() -> JSONResponse:
        return JSONResponse(
            {
                "aviso": "Front não buildado. Rode: cd front-end && npm install "
                "&& npm run build — ou use a API diretamente em /processar."
            }
        )
