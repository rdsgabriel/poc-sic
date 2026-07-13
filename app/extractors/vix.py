"""
Extrator do layout VIX Logística (ex.: contrato CENIBRA Belo Oriente).

Estrutura do documento (uma seção por Empresa × Cargo × Ocupação, 1 página cada):

    Empresa  VIX LOGÍSTICA S/A   Contrato: CENIBRA   CNPJ: ...
                 Motorista de Caminhão                  <- cargo
    Ocupação  FPC_BLO_OPE_A_03  N° de empregados: 01  Setor: Operacional
    Atividade ... / Local da Atividade ...
    PROCEDIMENTOS
      ASO | EXAMES A EXECUTAR | EXAMES POR EXIGÊNCIA CONTRATUAL |
          RISCOS EXPOSTOS | PARÂMETROS INTERPRETAÇÃO
      Admissional / Periódico Anual / Demissional / Mudança de Risco / Retorno

O "GHE" deste layout é o código da Ocupação (FPC_...), que se repete em várias
seções (uma por cargo e por empresa). Riscos ficam numa célula vertical única
("Risco Físico: Ruído ...") que atravessa todas as linhas de ASO. Exames são
listados por perfil, unidos por "+"; "Periódico Anual" = 12 meses.

As linhas de "Mudança de Risco" e "Retorno Trabalho" contêm REGRAS condicionais.
Tratamento acordado com o cliente VIX (jul/2026):
  - Mudança de Risco Ocupacional -> perfil "Mudança de função" repete os
    exames do Admissional;
  - Retorno ao Trabalho -> perfil recebe somente "Exame Clínico".

Há ainda o "QUADRO FUNCIONAL" (capítulo 11): tabela GHE -> cargos usada como
conferência — cargo no quadro sem seção correspondente vira aviso.
"""

from __future__ import annotations

import re
from collections import defaultdict

from .base import GHE, Exame, Line, Risco, Word, norm as _norm

_RE_CODIGO = re.compile(r"^[A-Z0-9]+(?:_[A-Z0-9]+){2,}$")
_RE_QUANT = re.compile(r"^\d{1,3}$")
_RE_COD_NUM = re.compile(r"^\d{10,}")

_GRUPOS = {
    "fisico": "Físico",
    "quimico": "Químico",
    "biologico": "Biológico",
    "ergonomico": "Ergonômicos",
    "ergonomicos": "Ergonômicos",
    "acidente": "Acidente",
    "acidente ou mecanico": "Acidente",
}

_PERIODICIDADE = {"anual": 12, "semestral": 6, "bienal": 24}

_ASOS_COM_EXAMES = ("admissional", "periodico", "demissional")


def _celulas(ln: Line, gap: float = 12.0) -> list[list[Word]]:
    cells: list[list[Word]] = []
    for w in sorted(ln.words, key=lambda w: w.x0):
        if cells and w.x0 - cells[-1][-1].x1 < gap:
            cells[-1].append(w)
        else:
            cells.append([w])
    return cells


def e_documento_vix(lines: list[Line]) -> bool:
    for ln in lines:
        palavras = [w.text for w in ln.words]
        if any(_norm(p) == "ocupacao" for p in palavras) and any(
            _RE_CODIGO.match(p) for p in palavras
        ):
            return True
    return False


# ----------------------------------------------------------------------------
# Seções (uma página por Empresa × Cargo × Ocupação)
# ----------------------------------------------------------------------------

def _achar_secoes(lines: list[Line]) -> list[dict]:
    """Localiza cada linha 'Ocupação FPC_... Setor: X' e o contexto dela."""
    secoes = []
    for i, ln in enumerate(lines):
        palavras = [w.text for w in ln.words]
        if not any(_norm(p) == "ocupacao" for p in palavras):
            continue
        codigo = next((p for p in palavras if _RE_CODIGO.match(p)), None)
        if not codigo:
            continue
        m = re.search(r"Setor:\s*(.+)$", ln.text)
        setor = m.group(1).strip() if m else ""
        # cargo = linha imediatamente acima (entre a linha Empresa e a Ocupação)
        cargo = ""
        for prev in reversed(lines[max(0, i - 3):i]):
            t = prev.text.strip()
            if not t:
                continue
            if t.startswith("Empresa") or t == "PCMSO" or t.startswith("Página"):
                break
            cargo = re.sub(r"\s+", " ", t)
            break
        empresa = contrato = ""
        for prev in reversed(lines[max(0, i - 4):i]):
            if prev.text.strip().startswith("Empresa"):
                me = re.search(r"Empresa\s+(.+?)\s+Contrato:", prev.text)
                mc = re.search(r"Contrato:\s*(\S+)", prev.text)
                empresa = me.group(1).strip() if me else ""
                contrato = mc.group(1).strip() if mc else ""
                break
        secoes.append(
            {
                "codigo": codigo, "cargo": cargo, "setor": setor,
                "empresa": empresa, "contrato": contrato,
                "page": ln.page, "top": ln.top, "idx": i,
            }
        )
    return secoes


def _y(ln: Line) -> float:
    """Posição vertical global (seções podem atravessar páginas)."""
    return ln.page * 10_000 + ln.top


def _ancoras_procedimentos(lines: list[Line]) -> dict | None:
    """Extensões (x0, x1) das colunas a partir do cabeçalho da tabela."""
    spans: dict[str, tuple[float, float]] = {}
    for ln in lines:
        norm_words = {_norm(w.text): w for w in ln.words}
        if "aso" in norm_words and "executar" in norm_words:
            aso = norm_words["aso"]
            spans["aso"] = (aso.x0, aso.x1)
            ex0 = next(w for w in ln.words if _norm(w.text) == "exames")
            ex1 = norm_words["executar"]
            spans["exames"] = (ex0.x0, ex1.x1)
            r0 = next((w for w in ln.words if _norm(w.text) == "riscos"), None)
            r1 = next((w for w in ln.words if _norm(w.text) == "expostos"), None)
            if r0 and r1:
                spans["riscos"] = (r0.x0, r1.x1)
        if "exigencia" in norm_words:
            e0 = norm_words["exigencia"]
            e1 = norm_words.get("contratual", e0)
            spans["exigencia"] = (e0.x0, e1.x1)
        if "interpretacao" in norm_words:
            p = norm_words["interpretacao"]
            spans["parametros"] = (p.x0, p.x1)
        if len(spans) == 5:
            return spans
    return spans if "aso" in spans and "exames" in spans else None


def _coluna_da_celula(cell: list[Word], spans: dict) -> str | None:
    cx0, cx1 = cell[0].x0, cell[-1].x1
    melhor, melhor_overlap = None, 0.0
    for nome, (sx0, sx1) in spans.items():
        overlap = min(cx1, sx1) - max(cx0, sx0)
        if overlap > melhor_overlap:
            melhor, melhor_overlap = nome, overlap
    if melhor:
        return melhor
    centro = (cx0 + cx1) / 2
    return min(spans, key=lambda n: abs((spans[n][0] + spans[n][1]) / 2 - centro))


_HEADER_CELLS = {
    "procedimentos", "exames por", "parametros", "aso", "exames a executar",
    "riscos expostos", "exigencia contratual", "interpretacao",
}


def _parse_secao(secao_lines: list[Line], sec: dict) -> dict:
    """Extrai exames por ASO e o texto de riscos de uma seção.

    A seção começa na linha 'Ocupação' e vai até a próxima seção — a tabela
    PROCEDIMENTOS pode cair na página seguinte quando a descrição da
    atividade é longa (ex.: Mecânico).
    """
    spans = _ancoras_procedimentos(secao_lines)
    avisos: list[str] = []
    if not spans:
        return {"exames_aso": {}, "riscos_txt": "", "avisos": [
            f"Seção {sec['codigo']}/{sec['cargo']}: tabela PROCEDIMENTOS não encontrada"
        ]}

    hdr_y = None
    for ln in secao_lines:
        if {_norm(w.text) for w in ln.words} >= {"aso", "executar"}:
            hdr_y = _y(ln)
            break

    # 1º passe: classifica células e localiza os rótulos de ASO (bandas)
    bandas: list[tuple[float, str]] = []
    tabela: list[tuple[Line, list[tuple[str, list[Word]]]]] = []
    for ln in secao_lines:
        if hdr_y is None or _y(ln) <= hdr_y:
            continue
        t = ln.text.strip()
        if t.startswith("Página") or t == "PCMSO" or t.startswith("Empresa"):
            continue
        cells_raw = _celulas(ln)
        # descarta linhas/células remanescentes do cabeçalho da tabela
        cells = []
        for c in cells_raw:
            texto_norm = _norm(" ".join(w.text for w in c))
            if texto_norm in _HEADER_CELLS:
                continue
            cells.append((_coluna_da_celula(c, spans), c))
        cells = [(col, c) for col, c in cells if col]
        if not cells:
            continue
        tabela.append((ln, cells))
        for col, c in cells:
            if col == "aso":
                rotulo = _norm(" ".join(w.text for w in c))
                if rotulo.startswith(("admissional", "periodico", "demissional",
                                      "mudanca", "retorno")):
                    bandas.append((_y(ln), rotulo))

    def banda_de(y: float) -> str:
        if not bandas:
            return ""
        return min(bandas, key=lambda b: abs(b[0] - y))[1]

    # 2º passe: distribui células de exames/exigência por banda; riscos: global
    exames_txt: dict[str, list[str]] = defaultdict(list)
    exig_txt: dict[str, list[str]] = defaultdict(list)
    riscos_parts: list[str] = []
    for ln, cells in tabela:
        b = banda_de(_y(ln))
        for col, c in cells:
            texto = " ".join(w.text for w in c)
            if col == "exames" and b.startswith(_ASOS_COM_EXAMES):
                exames_txt[b.split()[0]].append(texto)
            elif col == "exigencia" and b.startswith(_ASOS_COM_EXAMES):
                exig_txt[b.split()[0]].append(texto)
            elif col == "riscos":
                riscos_parts.append(texto)

    exames_aso: dict[str, list[str]] = {}
    for banda in set(exames_txt) | set(exig_txt):
        texto = " ".join(exames_txt.get(banda, []))
        itens = [re.sub(r"\s+", " ", e).strip() for e in texto.split("+")]
        extra = " ".join(exig_txt.get(banda, [])).strip()
        if extra and extra != "-":
            itens += [re.sub(r"\s+", " ", e).strip() for e in extra.split("+")]
        exames_aso[banda] = [e for e in itens if e and e != "-"]

    return {
        "exames_aso": exames_aso,
        "riscos_txt": re.sub(r"\s+", " ", " ".join(riscos_parts)).strip(),
        "avisos": avisos,
    }


def _parse_riscos(texto: str) -> tuple[list[Risco], bool]:
    """'Risco Físico: Ruído ... Risco de Acidente ou Mecânico: ...' -> Riscos."""
    if not texto:
        return [], False
    if _norm(texto).startswith("ausencia de risco"):
        return [], True
    riscos: list[Risco] = []
    for item in re.split(r"(?=\bRiscos?\s)", texto):
        item = item.strip()
        if not item:
            continue
        m = re.match(
            r"Riscos?\s+(?:de\s+)?([A-Za-zÀ-ÿ]+(?:\s+ou\s+[A-Za-zÀ-ÿ]+)?)\s*:\s*(.+)",
            item,
        )
        if not m:
            continue
        grupo = _GRUPOS.get(_norm(m.group(1)))
        nome = m.group(2).strip().rstrip(";,")
        if grupo and nome:
            riscos.append(Risco(nome=nome, grupo=grupo))
    return riscos, False


def _montar_exames(exames_aso: dict[str, list[str]]) -> list[Exame]:
    por_nome: dict[str, Exame] = {}

    def obter(nome: str) -> Exame:
        # chave só alfanumérica: o mesmo exame aparece com typos de pontuação
        # entre linhas de ASO ("(AP e Perfil))"); a grafia da 1ª ocorrência vence
        chave = re.sub(r"[^a-z0-9]", "", _norm(nome))
        if chave not in por_nome:
            por_nome[chave] = Exame(nome=nome)
        return por_nome[chave]

    for nome in exames_aso.get("admissional", []):
        exame = obter(nome)
        exame.admissao = True
        # regra acordada com o cliente VIX: "Mudança de Risco Ocupacional —
        # exames iguais ao Admissional" => repetir o admissional no perfil
        # "Mudança de função" da planilha
        exame.mud_riscos = True
    for banda, itens in exames_aso.items():
        if banda.startswith("periodico"):
            sufixo = banda.split()[-1] if " " in banda else "anual"
            meses = _PERIODICIDADE.get(sufixo, 12)
            for nome in itens:
                obter(nome).periodico_meses = meses
    for nome in exames_aso.get("demissional", []):
        obter(nome).demissao = True
    # regra acordada com o cliente VIX: "Retorno ao Trabalho" recebe somente
    # o clínico ocupacional (demais casos do documento são condicionais)
    if por_nome:
        obter("Exame Clínico").ret_trab = True
    return list(por_nome.values())


# ----------------------------------------------------------------------------
# Quadro funcional (capítulo 11) — conferência de cargos por GHE
# ----------------------------------------------------------------------------

_RE_SUFIXO_NIVEL = re.compile(r"^([ivxl]+|\d+)$")
_SIMILARIDADE_MINIMA = 0.85


def _chave_cargo(s: str) -> str:
    """Chave alfanumérica: espaçamento/pontuação/acento não diferenciam cargo."""
    return re.sub(r"[^a-z0-9]", "", _norm(s))


def _radical_e_nivel(s: str) -> tuple[str, str]:
    """Separa o sufixo de nível ('MECÂNICO II' -> ('mecanico', 'ii')).

    Níveis (I/II/III ou dígitos) diferenciam FUNÇÕES e nunca podem casar por
    aproximação — 'Mecânico I' e 'Mecânico II' têm 1 caractere de diferença.
    """
    tokens = _norm(s).split()
    if tokens and _RE_SUFIXO_NIVEL.match(tokens[-1]):
        return re.sub(r"[^a-z0-9]", "", " ".join(tokens[:-1])), tokens[-1]
    return re.sub(r"[^a-z0-9]", "", " ".join(tokens)), ""


def _mais_parecido(cargo: str, candidatos: list[str]) -> str | None:
    """Cargo de seção mais similar (typo, preposição, acento), se houver.

    Fuzzy só no radical; o sufixo de nível precisa ser idêntico.
    """
    from difflib import SequenceMatcher

    radical, nivel = _radical_e_nivel(cargo)
    melhor, melhor_ratio = None, 0.0
    for cand in candidatos:
        radical_c, nivel_c = _radical_e_nivel(cand)
        if nivel_c != nivel:
            continue
        ratio = SequenceMatcher(None, radical, radical_c).ratio()
        if ratio > melhor_ratio:
            melhor, melhor_ratio = cand, ratio
    return melhor if melhor_ratio >= _SIMILARIDADE_MINIMA else None


def _parse_quadro_funcional(lines: list[Line]) -> list[str]:
    """Cargos listados no Quadro Funcional (capítulo 11), sem vínculo por GHE.

    O código do GHE fica centralizado verticalmente no grupo de cargos, então
    a associação linha-a-linha código->cargo não é confiável; o quadro é usado
    apenas como lista de conferência global de cargos.
    """
    cargos: list[str] = []
    dentro = False
    for ln in lines:
        t = ln.text.strip()
        if "QUADRO FUNCIONAL" in t:
            dentro = True
            continue
        if not dentro:
            continue
        if re.match(r"^\s*TOTAL\b", t):
            break
        if t.startswith("Página") or t == "PCMSO":
            continue
        for cell in _celulas(ln):
            texto = " ".join(w.text for w in cell).strip()
            primeiro = texto.split()[0] if texto else ""
            if not texto or _RE_CODIGO.match(primeiro) or _RE_COD_NUM.match(primeiro):
                continue
            if _RE_QUANT.match(texto) or texto in ("GHE", "CARGO", "QUANT."):
                continue
            if texto.startswith("A VIX") or texto.startswith("("):
                continue
            cargo = re.sub(r"\s+\d{1,3}$", "", re.sub(r"\s+", " ", texto)).strip()
            if cargo:
                cargos.append(cargo)
    return cargos


# ----------------------------------------------------------------------------
# Entrada principal
# ----------------------------------------------------------------------------

def extrair_ghes_vix(lines: list[Line]) -> tuple[list[GHE], dict]:
    secoes = _achar_secoes(lines)
    if not secoes:
        return [], {"empresa": "", "total_ghes": 0}

    por_codigo: dict[str, GHE] = {}
    assinaturas: dict[str, tuple] = {}
    for n, sec in enumerate(secoes):
        fim = secoes[n + 1]["idx"] if n + 1 < len(secoes) else len(lines)
        dados = _parse_secao(lines[sec["idx"]:fim], sec)
        riscos, ausencia = _parse_riscos(dados["riscos_txt"])
        exames = _montar_exames(dados["exames_aso"])

        ghe = por_codigo.get(sec["codigo"])
        if ghe is None:
            ghe = GHE(
                codigo=sec["codigo"], nome=sec["setor"],
                riscos=riscos, exames=exames,
                ausencia_riscos=ausencia, setor_override=sec["codigo"],
                pagina=sec["page"],
            )
            por_codigo[sec["codigo"]] = ghe
            assinaturas[sec["codigo"]] = (
                {(r.nome, r.grupo) for r in riscos},
                {(e.nome, e.admissao, e.periodico_meses, e.demissao) for e in exames},
            )
        else:
            # mesmo código em outra seção (outro cargo/empresa): confere coerência
            assin = (
                {(r.nome, r.grupo) for r in riscos},
                {(e.nome, e.admissao, e.periodico_meses, e.demissao) for e in exames},
            )
            if assin != assinaturas[sec["codigo"]]:
                ghe.avisos.append(
                    f"Seção do cargo {sec['cargo']!r} tem riscos/exames diferentes "
                    f"das demais seções do {sec['codigo']} — usando a primeira; conferir."
                )
        if sec["cargo"] and _norm(sec["cargo"]) not in {_norm(c) for c in ghe.cargos}:
            ghe.cargos.append(sec["cargo"])
        ghe.avisos.extend(dados["avisos"])

    # conferência global com o quadro funcional — achados são do DOCUMENTO,
    # não de um GHE específico. A planilha usa os cargos das SEÇÕES; o quadro
    # é só lista de conferência. Dois níveis:
    #   - casou por similaridade (typo/preposição/acento/pontuação): aviso
    #     informativo de grafia divergente, apontando as duas formas;
    #   - não casou com nada: alerta forte — a função pode estar sem seção
    #     (e portanto fora da planilha).
    ghes = list(por_codigo.values())
    avisos_documento: list[str] = []
    cargos_secoes = [c for g in ghes for c in g.cargos]
    chaves_secoes = {_chave_cargo(c) for c in cargos_secoes}
    for cargo in _parse_quadro_funcional(lines):
        if _chave_cargo(cargo) in chaves_secoes:
            continue  # mesmo cargo, só variação de espaço/pontuação/acento
        parecido = _mais_parecido(cargo, cargos_secoes)
        if parecido:
            avisos_documento.append(
                f"Grafia divergente no documento: {cargo!r} (Quadro Funcional) × "
                f"{parecido!r} (seção) — a planilha usa a grafia da seção."
            )
        else:
            avisos_documento.append(
                f"Cargo {cargo!r} do Quadro Funcional sem seção correspondente — "
                f"a função pode estar fora da planilha; conferir no documento."
            )
    empresa = secoes[0]["empresa"] or "EMPRESA"
    contrato = secoes[0]["contrato"]
    meta = {
        "empresa": f"{empresa} {contrato}".strip(),
        "total_ghes": len(ghes),
        "layout": "vix",
        "avisos_documento": avisos_documento,
    }
    return ghes, meta


# interface uniforme do registro de extratores
detectar = e_documento_vix
extrair = extrair_ghes_vix
