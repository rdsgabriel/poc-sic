"""
Treino de layouts — adiciona/atualiza um PDF de referência e seu golden.

"Treinar" um layout = alimentá-lo com mais PDFs reais até cobrir todas as
variações do emissor. Este script encapsula o fluxo seguro de sempre:
extrair com os dois leitores, exigir que eles concordem, conferir as regras
de consistência e só então gravar o golden (a regra de ouro do
GUIA_MELHORIAS.md vira código, não disciplina).

Roda DENTRO do container (onde o docling existe). Com o bind mount do
docker-compose, os goldens gravados aparecem direto no host para commitar:

    # adicionar/atualizar um caso (nome do golden = nome do arquivo, ou 3º arg)
    docker compose exec poc-pcmso python -m tests.treinar solstad \\
        "/srv/entrada/NORMAND TURQUESA.pdf" normand_turquesa

    # rodar a suíte de um layout (ou de todos, sem argumento)
    docker compose exec poc-pcmso python -m tests.treinar --check solstad

    # ver a cobertura atual (quantos PDFs por layout, e se o PDF está presente)
    docker compose exec poc-pcmso python -m tests.treinar --list

Convenção: tests/pdfs/<layout>/<nome>.pdf  <->  tests/golden/<layout>/<nome>.json
Os PDFs ficam fora do git (LGPD); os goldens são versionados.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
import unicodedata
from dataclasses import asdict
from pathlib import Path

from app.backends import BACKENDS
from app.extractors import EXTRATORES, extrair_auto
from app.validate import checar_documento, comparar_backends

RAIZ = Path(__file__).resolve().parent
GOLDEN = RAIZ / "golden"
PDFS = RAIZ / "pdfs"
INBOX = RAIZ / "inbox"
LAYOUTS = [nome for nome, _ in EXTRATORES]

_CAMPOS_CONTRATO = (
    "codigo", "nome", "riscos", "exames", "cargos",
    "ausencia_riscos", "setor_override", "nrs",
)
_PADROES_GHE = {
    "ausencia_riscos": False, "setor_override": None, "nrs": {},
}


def _slug(texto: str) -> str:
    texto = unicodedata.normalize("NFKD", texto)
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]+", "_", texto.lower()).strip("_")


def _nome_caso(pdf: Path, layout: str) -> str:
    """Nome estável do caso; Solstad usa a embarcação, não o prefixo do PDF."""
    if layout == "solstad":
        m = re.search(r"\bNORMAND[\s_-]+([A-Z0-9]+)", pdf.stem, re.IGNORECASE)
        if m:
            return f"normand_{_slug(m.group(1))}"
    return _slug(pdf.stem)


def _ghe_contrato(ghe: dict) -> dict:
    return {
        campo: ghe.get(campo, _PADROES_GHE.get(campo))
        for campo in _CAMPOS_CONTRATO
    }


def _extrair(pdf: Path, backend: str):
    return extrair_auto(BACKENDS[backend](str(pdf)), pdf_path=str(pdf))


def _resumo(ghes) -> str:
    linhas = [
        f"  {len(ghes)} GHEs, "
        f"{sum(len(g.cargos) for g in ghes)} funções, "
        f"{sum(len(g.riscos) for g in ghes)} riscos, "
        f"{sum(len(g.exames) for g in ghes)} exames"
    ]
    for g in ghes:
        linhas.append(
            f"    [{g.codigo}] {g.setor} — "
            f"{len(g.riscos)}r/{len(g.exames)}e/{len(g.cargos)}f"
        )
    return "\n".join(linhas)


def _diff_golden(antigo: dict, novo: dict) -> list[str]:
    """Mudanças legíveis entre o golden atual e a nova extração."""
    ant = {g["codigo"]: g for g in antigo["ghes"]}
    nov = {g["codigo"]: g for g in novo["ghes"]}
    difs: list[str] = []
    if set(ant) != set(nov):
        so_ant = sorted(set(ant) - set(nov))
        so_nov = sorted(set(nov) - set(ant))
        if so_ant:
            difs.append(f"  GHEs removidos: {so_ant}")
        if so_nov:
            difs.append(f"  GHEs novos: {so_nov}")
    for cod in sorted(set(ant) & set(nov)):
        for campo in _CAMPOS_CONTRATO[1:]:
            a = _ghe_contrato(ant[cod])[campo]
            n = _ghe_contrato(nov[cod])[campo]
            if a != n:
                if isinstance(a, list):
                    na = {json.dumps(x, sort_keys=True, ensure_ascii=False) for x in a}
                    nn = {json.dumps(x, sort_keys=True, ensure_ascii=False) for x in n}
                    saiu = [json.loads(x) for x in na - nn]
                    entrou = [json.loads(x) for x in nn - na]
                    resumo = []
                    if saiu:
                        resumo.append(
                            f"-{[x.get('nome', x) if isinstance(x, dict) else x for x in saiu]}"
                        )
                    if entrou:
                        resumo.append(
                            f"+{[x.get('nome', x) if isinstance(x, dict) else x for x in entrou]}"
                        )
                    difs.append(f"  [{cod}] {campo}: {' '.join(resumo)}")
                else:
                    difs.append(f"  [{cod}] {campo}: {a!r} -> {n!r}")
    return difs


def treinar(layout: str, pdf_arg: str, nome: str | None, sim: bool) -> int:
    if layout not in LAYOUTS:
        print(f"layout desconhecido: {layout!r}. Conhecidos: {', '.join(LAYOUTS)}")
        return 2
    origem = Path(pdf_arg)
    if not origem.is_file():
        print(f"PDF não encontrado: {origem}")
        return 2

    nome = nome or _nome_caso(origem, layout)
    destino = PDFS / layout / f"{nome}.pdf"
    golden = GOLDEN / layout / f"{nome}.json"
    destino.parent.mkdir(parents=True, exist_ok=True)
    if origem.resolve() != destino.resolve():
        shutil.copyfile(origem, destino)
        print(f"PDF copiado para {destino.relative_to(RAIZ.parent)}")

    print(f"\nExtraindo {nome!r} (layout {layout})…")
    try:
        ghes_d, meta = _extrair(destino, "docling")
    except Exception as exc:  # noqa: BLE001
        print(f"FALHA na extração (docling): {type(exc).__name__}: {exc}")
        return 1
    print(f"empresa: {meta.get('empresa')!r}")
    print(_resumo(ghes_d))

    # a rede de segurança: os dois leitores TÊM de concordar, e as regras de
    # consistência têm de passar — senão o golden nasceria capturando um erro
    print("\nValidação cruzada docling × pdfplumber…")
    divergencias = comparar_backends(str(destino), ghes_docling=ghes_d)
    if meta.get("layout") != layout:
        print(
            f"  REGRA: layout informado={layout!r}, "
            f"layout detectado={meta.get('layout')!r}"
        )
        return 1
    regras = checar_documento(ghes_d, meta)
    if divergencias or regras:
        for d in divergencias:
            print("  DIVERGÊNCIA:", d)
        for r in regras:
            print("  REGRA:", r)
        print("\nGolden NÃO gravado — resolva as divergências antes de treinar.")
        return 1
    print("  OK — leitores concordam e regras passam.")

    novo = {"meta": meta, "ghes": [asdict(g) for g in ghes_d]}
    if golden.is_file():
        atual = json.loads(golden.read_text(encoding="utf-8"))
        difs = _diff_golden(atual, novo)
        if not difs:
            print("\nGolden já está idêntico — nada a fazer.")
            return 0
        print(f"\nMudanças em relação ao golden atual ({golden.name}):")
        print("\n".join(difs))
    else:
        print(f"\nGolden novo: {golden.relative_to(RAIZ.parent)}")

    if not sim:
        resp = input("\nConfere com o PDF? Gravar golden? [s/N] ").strip().lower()
        if resp not in ("s", "sim", "y"):
            print("Cancelado — golden não gravado.")
            return 0
    golden.parent.mkdir(parents=True, exist_ok=True)
    golden.write_text(
        json.dumps(novo, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"Golden gravado: {golden.relative_to(RAIZ.parent)}")
    print("Rode a suíte do layout para confirmar: "
          f"python -m tests.treinar --check {layout}")
    return 0


def auditar_inbox(layout: str) -> int:
    """Varre novos PDFs sem gravar goldens nem alterar o corpus aprovado."""
    if layout not in LAYOUTS:
        print(f"layout desconhecido: {layout!r}. Conhecidos: {', '.join(LAYOUTS)}")
        return 2
    pasta = INBOX / layout
    pdfs = sorted(pasta.glob("*.pdf")) if pasta.is_dir() else []
    if not pdfs:
        print(f"Nenhum PDF em {pasta.relative_to(RAIZ.parent)}/")
        return 2

    contagem = {"APROVADO": 0, "CANDIDATO": 0, "REPROVADO": 0}
    for pdf in pdfs:
        caso = _nome_caso(pdf, layout)
        golden = GOLDEN / layout / f"{caso}.json"
        print(f"\n{'=' * 72}\n{pdf.name}\ncaso: {caso}")
        problemas: list[str] = []
        try:
            ghes, meta = _extrair(pdf, "docling")
            if meta.get("layout") != layout:
                problemas.append(
                    f"layout detectado={meta.get('layout')!r}; esperado={layout!r}"
                )
            problemas.extend(comparar_backends(str(pdf), ghes_docling=ghes))
            problemas.extend(checar_documento(ghes, meta))

            nr_contagem: dict[str, int] = {}
            for g in ghes:
                for nrs in g.nrs.values():
                    for nr in nrs:
                        nr_contagem[nr] = nr_contagem.get(nr, 0) + 1
            print(_resumo(ghes))
            if nr_contagem:
                print("  NRs: " + ", ".join(
                    f"{nr}={qtd}" for nr, qtd in sorted(nr_contagem.items())
                ))

            novo = {"meta": meta, "ghes": [asdict(g) for g in ghes]}
            if golden.is_file():
                antigo = json.loads(golden.read_text(encoding="utf-8"))
                problemas.extend(_diff_golden(antigo, novo))
                status = "APROVADO" if not problemas else "REPROVADO"
            else:
                status = "CANDIDATO" if not problemas else "REPROVADO"
        except Exception as exc:  # noqa: BLE001
            status = "REPROVADO"
            problemas.append(f"{type(exc).__name__}: {exc}")

        contagem[status] += 1
        print(f"\n{status}: {pdf.name}")
        if problemas:
            for problema in problemas:
                print(f"  - {problema.strip()}")
        elif status == "CANDIDATO":
            print("  - passou nos gates automáticos; falta conferir e promover o golden")

    print("\n" + "=" * 72)
    print("Resumo: " + ", ".join(f"{k}={v}" for k, v in contagem.items()))
    return 0 if contagem["APROVADO"] == len(pdfs) else 1


def listar() -> int:
    print("Cobertura por layout (golden ↔ PDF):\n")
    total_g = total_pdf = 0
    for layout in LAYOUTS:
        goldens = sorted((GOLDEN / layout).glob("*.json")) if (GOLDEN / layout).is_dir() else []
        print(f"  {layout} ({len(goldens)})")
        for g in goldens:
            pdf = PDFS / layout / f"{g.stem}.pdf"
            marca = "✓ pdf" if pdf.is_file() else "· pdf ausente"
            total_pdf += pdf.is_file()
            try:
                d = json.loads(g.read_text(encoding="utf-8"))
                info = (f"{d['meta']['total_ghes']} GHEs, "
                        f"{sum(len(x['exames']) for x in d['ghes'])} exames")
            except Exception:  # noqa: BLE001
                info = "?"
            print(f"      {g.stem:<28} {marca:<14} {info}")
        total_g += len(goldens)
    print(f"\n  total: {total_g} goldens, {total_pdf} com PDF disponível")
    return 0


def check(layout: str | None) -> int:
    alvo = ["tests/"]
    if layout:
        alvo += ["-k", layout]
    print(f"$ pytest {' '.join(alvo)} -q\n")
    return subprocess.call([sys.executable, "-m", "pytest", *alvo, "-q"], cwd=RAIZ.parent)


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Treino de layouts de PCMSO (add/atualiza golden a partir de um PDF).",
    )
    ap.add_argument("layout", nargs="?", help=f"um de: {', '.join(LAYOUTS)}")
    ap.add_argument("pdf", nargs="?", help="caminho do PDF de referência")
    ap.add_argument("nome", nargs="?", help="nome do caso (default: nome do arquivo)")
    ap.add_argument("--yes", "-y", action="store_true", help="grava sem confirmar")
    ap.add_argument("--check", action="store_true", help="roda a suíte (do layout, se informado)")
    ap.add_argument("--list", action="store_true", help="mostra a cobertura atual")
    ap.add_argument(
        "--inbox", metavar="LAYOUT",
        help="analisa em lote tests/inbox/<layout> sem gravar goldens",
    )
    args = ap.parse_args()

    if args.list:
        return listar()
    if args.inbox:
        return auditar_inbox(args.inbox)
    if args.check:
        return check(args.layout)
    if not args.layout or not args.pdf:
        ap.print_help()
        return 2
    return treinar(args.layout, args.pdf, args.nome, args.yes)


if __name__ == "__main__":
    raise SystemExit(main())
