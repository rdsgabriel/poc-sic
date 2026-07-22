"""
Extrator do layout Occupare (ex.: ITAJUI ENGENHARIA / SK TECNOLOGIA).

PDF gerado em Word, estrutura linear numerada:

    5.x SETOR: GSE 1 - VEÍCULOS LEVES
    5.x.y FUNÇÃO: MOTORISTA
        Setor: ... / CBO: ... / Descrição da Função: ...
        Agentes Ambientais
          - Físicos | - Químicos | - Biológicos | - Ergonômicos | - Mecânico/Acidentes
          Perigo /Fator de Risco - <nome>          Data de Avaliação: ...
          Possíveis Agravos à Saúde: ...
        Exames Obrigatórios da Função
          - Exame: <nome> (Código eSocial: NNNN)
          [ x ] Admissional [ ] Demissional [ x ] Periódico [ x ] Retorno ao
                Trabalho [ x ] Mudança de Riscos Ocupacionais
          - Periodicidade do Exame: A cada N meses

Diferente dos outros emissores, riscos e exames são POR FUNÇÃO (funções do
mesmo GSE podem divergir). Cada FUNÇÃO vira um GHE próprio com
setor_override = "GSE N - NOME" — a planilha sai com a granularidade certa.

O sufixo "(Código eSocial: ...)" é removido dos nomes de exames e riscos
(metadado do emissor, não nomenclatura).
"""

from __future__ import annotations

import re

from .base import GHE, Exame, Line, Risco, montar_foco, norm as _norm

_RE_TOC = re.compile(r"\.{4,}")
_RE_SETOR = re.compile(r"^(?:\d+(?:\.\d+)*\s+)?SETOR:\s*(GSE\s*\S+)\s*-\s*(.+)$")
_RE_FUNCAO = re.compile(r"^\d+(?:\.\d+)+\s+FUNÇÃO:\s*(.+)$")
_RE_CAPITULO = re.compile(r"^\d+\.\s+[A-ZÀ-Ü]")
_RE_RISCO = re.compile(r"Perigo\s*/\s*Fator de Risco\s*-\s*")
_RE_ESOCIAL = re.compile(r"\s*\(?\s*Código eSocial:\s*[\d.]+\s*\)?\s*", re.IGNORECASE)
_RE_CHECKBOX = re.compile(
    r"\[\s*([xX]?)\s*\]\s*(Admissional|Demissional|Periódico|Retorno\s+ao\s+Trabalho|"
    r"Mudança\s+de\s+Riscos\s+Ocupacionais)"
)
_RE_PERIODICIDADE = re.compile(r"Periodicidade do Exame:\s*(.+?)\s*$", re.IGNORECASE)
_RE_A_CADA = re.compile(r"A cada\s*(\d+)\s*mes", re.IGNORECASE)
_RE_FOOTER = re.compile(
    r"OCCUPARE - Fone|Av\. Sete de Setembro|Tel\. 41|www\.occupare|CNPJ: 04\.260\.801"
)

_GRUPOS = {
    "fisicos": "Físico",
    "quimicos": "Químico",
    "biologicos": "Biológico",
    "ergonomicos": "Ergonômicos",
    "mecanico/acidentes": "Acidente",
    "acidentes": "Acidente",
}


def detectar(lines: list[Line]) -> bool:
    tem_setor = any(_RE_SETOR.match(ln.text.strip()) for ln in lines)
    tem_exames = any("Exames Obrigatórios da Função" in ln.text for ln in lines)
    return tem_setor and tem_exames


def _limpar_nome(nome: str) -> str:
    return re.sub(r"\s+", " ", _RE_ESOCIAL.sub(" ", nome)).strip()


def extrair(lines: list[Line]) -> tuple[list[GHE], dict]:
    ghes: list[GHE] = []
    ghe: GHE | None = None
    setor_atual: tuple[str, str] | None = None  # (código GSE, nome)
    grupo_atual: str | None = None
    em_exames = False
    exame_pendente: list[str] | None = None  # nome acumulando até o checkbox
    exame_atual: Exame | None = None
    risco_atual: Risco | None = None
    risco_boundary: float | None = None
    empresa = ""
    # foco: para cada GHE guardamos as linhas da seção e a linha "FUNÇÃO:"
    secoes_foco: list[tuple[GHE, list[Line], Line]] = []
    foco_linhas: list[Line] = []

    def fechar_exame_pendente():
        nonlocal exame_pendente, exame_atual
        if exame_pendente is not None and ghe is not None:
            nome = _limpar_nome(" ".join(exame_pendente))
            if nome:
                exame_atual = Exame(nome=nome)
                ghe.exames.append(exame_atual)
            exame_pendente = None

    for ln in lines:
        txt = ln.text.strip()
        if not txt or _RE_FOOTER.search(txt) or _RE_TOC.search(txt):
            continue

        if not empresa:
            m = re.match(r"^Empresa:\s*(.+)$", txt)
            if m:
                empresa = m.group(1).strip()

        m = _RE_SETOR.match(txt)
        if m:
            setor_atual = (m.group(1).strip(), m.group(2).strip())
            ghe = None
            em_exames = False
            risco_atual = None
            continue

        m = _RE_FUNCAO.match(txt)
        if m and setor_atual:
            funcao = m.group(1).strip()
            ghe = GHE(
                codigo=f"{setor_atual[0]}/{funcao}",
                nome=funcao,
                setor_override=f"{setor_atual[0]} - {setor_atual[1]}",
                cargos=[funcao],
                pagina=ln.page,
            )
            ghes.append(ghe)
            foco_linhas = [ln]
            secoes_foco.append((ghe, foco_linhas, ln))
            grupo_atual = None
            em_exames = False
            risco_atual = None
            exame_pendente = None
            continue

        if ghe is None:
            continue

        if _RE_CAPITULO.match(txt) and "SETOR" not in txt and "FUNÇÃO" not in txt:
            # capítulo novo (Cronograma, Encerramento...): fim das seções
            fechar_exame_pendente()
            ghe = None
            continue

        foco_linhas.append(ln)  # linha de conteúdo da função atual

        # ---------------- bloco de exames ----------------
        if "Exames Obrigatórios da Função" in txt:
            em_exames = True
            risco_atual = None
            continue

        if em_exames:
            m = re.match(r"^-\s*Exame:\s*(.*)$", txt)
            if m:
                fechar_exame_pendente()
                exame_pendente = [m.group(1)]
                continue
            if "[" in txt:
                fechar_exame_pendente()
                if exame_atual is not None:
                    for marca, rotulo in _RE_CHECKBOX.findall(txt):
                        marcado = marca.lower() == "x"
                        r = _norm(rotulo)
                        if r == "admissional":
                            exame_atual.admissao = marcado
                        elif r == "demissional":
                            exame_atual.demissao = marcado
                        elif r == "periodico":
                            exame_atual.periodico_meses = -1 if marcado else None
                        elif r.startswith("retorno"):
                            exame_atual.ret_trab = marcado
                        elif r.startswith("mudanca"):
                            exame_atual.mud_riscos = marcado
                continue
            m = _RE_PERIODICIDADE.search(txt)
            if m:
                if exame_atual is not None and exame_atual.periodico_meses == -1:
                    valor = m.group(1).strip()
                    meses = _RE_A_CADA.search(valor)
                    if meses:
                        exame_atual.periodico_meses = int(meses.group(1))
                    elif _norm(valor) in ("todas as vezes", "uma unica vez"):
                        # Regra confirmada pelo negócio (jul/2026): tanto
                        # "Todas as Vezes" quanto "Uma única Vez" (mesmo sendo
                        # contradição do documento quando o checkbox Periódico
                        # está marcado) entram no Perfil Periódico com 12 meses.
                        exame_atual.periodico_meses = 12
                    else:
                        exame_atual.periodico_meses = None
                        ghe.avisos.append(
                            f"Exame {exame_atual.nome!r}: periodicidade não "
                            f"reconhecida: {valor!r}"
                        )
                continue
            if exame_pendente is not None:
                exame_pendente.append(txt)  # nome de exame com quebra de linha
            continue

        # ---------------- bloco de riscos ----------------
        m = re.match(r"^-\s*([A-Za-zÀ-ÿ/]+)$", txt)
        if m and _norm(m.group(1)) in _GRUPOS:
            grupo_atual = _GRUPOS[_norm(m.group(1))]
            risco_atual = None
            continue

        if _RE_RISCO.search(txt):
            # nome = palavras do trecho esquerdo, após o separador "-".
            # A coluna direita (Data/Reavaliação/Característica) começa em
            # x>=424 neste layout; 415 é a fronteira segura quando a própria
            # linha do risco não traz âncora "Data".
            data_w = next((w for w in ln.words if w.text.startswith("Data")), None)
            risco_boundary = min(data_w.x0 - 20, 415.0) if data_w else 415.0
            depois = _RE_RISCO.split(ln.text, maxsplit=1)[1]
            # remove o que pertence à coluna da direita
            nome_parts = []
            consumido = _RE_RISCO.split(ln.text, maxsplit=1)[0] + "Perigo /Fator de Risco - "
            pos = 0
            for w in ln.words:
                pos += len(w.text) + 1
                if pos <= len(consumido):
                    continue
                if w.x0 >= risco_boundary:
                    break
                nome_parts.append(w.text)
            nome = _limpar_nome(" ".join(nome_parts) or depois)
            grupo = grupo_atual or "Acidente"
            if not grupo_atual and ghe is not None:
                ghe.avisos.append(f"Risco {nome!r} sem grupo de agente identificado")
            risco_atual = Risco(nome=nome, grupo=grupo)
            ghe.riscos.append(risco_atual)
            continue

        if risco_atual is not None:
            if txt.startswith("Possíveis Agravos") or "Característica" in txt:
                risco_atual = None
                continue
            # continuação do nome do risco (célula com quebra de linha):
            # só palavras da coluna esquerda
            cont = [w.text for w in ln.words if risco_boundary and w.x0 < risco_boundary]
            cont = [
                t for t in cont
                if _norm(t) not in ("nao", "significativo") and not re.match(r"\d{2}/\d{2}/\d{4}", t)
            ]
            if cont:
                risco_atual.nome = _limpar_nome(risco_atual.nome + " " + " ".join(cont))
            continue

    fechar_exame_pendente()

    # exame marcado como periódico mas sem periodicidade informada
    for g in ghes:
        for e in g.exames:
            if e.periodico_meses == -1:
                e.periodico_meses = None
                g.avisos.append(
                    f"Exame {e.nome!r} marcado como Periódico sem periodicidade informada"
                )

    focos: dict[str, dict] = {}
    for g, secao, linha_funcao in secoes_foco:
        foco = montar_foco(secao, g.pagina, [linha_funcao])
        if foco:
            focos[g.codigo] = foco

    meta = {
        "empresa": empresa or "EMPRESA",
        "total_ghes": len(ghes),
        "layout": "occupare",
        "focos": focos,
    }
    return ghes, meta
