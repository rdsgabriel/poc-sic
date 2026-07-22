"""
Extrator do layout Mafra Ambiental (ex.: SK Tecnologia / Mineração Taboca).

PDF exportado de sistema web (Chrome/Skia). Estrutura por CARGO:

    CARGO <NOME> - CBO: NNNNNN
    Ambientes: GSE 7 - Sala Administrativa Obra (Ambiente Principal)
    Atividades: ... / Metodologia erg.: ... / Recomendações: ...
    CONTROLE MÉDICO - <CARGO>
        <Exame>:                       Fazer no Admissional
        Código(s) eSocial: NNNN        Fazer no Periódico       O periódico será
                                       ...                      feito a cada N meses.
    RISCOS FÍSICOS - <CARGO> / RISCOS QUÍMICOS - ... (5 grupos por cargo)
         <nome do risco>         <- ícone quadrado ancora o nome
        Exposição: ... / Perigos, fontes e circunstâncias: ... / etc.

REGRA DO NEGÓCIO (definida pelo usuário, jul/2026): o risco é SEMPRE o texto
ao lado do ícone (glifo ). "Ausência de risco [grupo]" é placeholder
por grupo: se o cargo tem QUALQUER risco real, os placeholders de ausência
NÃO aparecem; se todos os grupos são ausência, ausencia_riscos=True.

Como no layout Occupare, riscos e exames são POR CARGO — cada cargo vira um
GHE próprio com setor_override = GSE do ambiente principal.

Coluna direita do bloco de exames: "O periódico será feito a cada N meses" →
periodico_meses; "Em adição, este exame deverá ser realizado N meses após a
contratação" → apos_adm_meses (perfil Após Admissão).

DE-PARA DO CLIENTE SK (jul/2026, "De para - Riscos e exames_SK.xls"):
aplicado SOMENTE na geração das planilhas (`preparar_para_planilha`,
chamado pelo pipeline) — a extração, a tela de conferência e os goldens
mantêm a nomenclatura exata do PDF, senão o validador não consegue bater
a tela com o documento:
- riscos: remover o sufixo "eSocial NN.NN.NNN" dos nomes;
- exames: renomear para o catálogo do sistema BR MED
  (data/mafra_depara_exames_sk.json), incluindo desdobramentos 1->N
  ("FUNÇÃO RENAL (UREIA + CREATININA)" vira UREIA e CREATININA) e fusões
  N->1 ("EXAME CLÍNICO" e "anamnese e exame físico" viram CLÍNICO
  OCUPACIONAL, com os perfis mesclados). Exame fora do De-para mantém a
  nomenclatura do PDF.
"""

from __future__ import annotations

import copy
import json
import re
from difflib import SequenceMatcher
from pathlib import Path

from .base import GHE, Exame, Line, Risco, montar_foco, norm as _norm

_DEPARA_EXAMES = Path(__file__).parent / "data" / "mafra_depara_exames_sk.json"
_RE_ESOCIAL_RISCO = re.compile(r"\s*eSocial\s*[\d.]+\s*$", re.IGNORECASE)

_ICONE = "\uf0c8"  # quadradinho (Wingdings) que ancora cada risco
_RE_CARGO = re.compile(r"^CARGO\s+(.+?)\s*-\s*CBO:\s*\d+", re.IGNORECASE)
_RE_AMBIENTE = re.compile(r"Ambientes:\s*(.+?)\s*\(Ambiente Principal\)")
_RE_RISCOS_HDR = re.compile(
    r"^RISCOS\s+(FÍSICOS|QUÍMICOS|BIOLÓGICOS|ERGONÔMICOS|ACIDENTES(?:\s*/\s*MECÂNICOS)?)\s*-\s*(.+)$"
)
_RE_CONTROLE = re.compile(r"^CONTROLE MÉDICO\s*-\s*(.+)$")
_RE_FAZER = re.compile(
    r"Fazer n[oa]\s+(Admissional|Demissional|Retorno Ao Trabalho|Mudança de Riscos|Periódico)",
    re.IGNORECASE,
)
_RE_PERIODICO = re.compile(r"a cada\s*(\d+)\s*meses", re.IGNORECASE)
_RE_APOS_ADM = re.compile(r"realizado\s*(\d+)\s*meses após a contratação", re.IGNORECASE)
_RE_LABEL_RISCO = re.compile(
    r"^(Exposição|Perigos, fontes|Metodologia|Medidas administrativas|"
    r"Descrição do Agente|Possíveis danos|Observações)"
)
_RE_FOOTER = re.compile(
    r"PCMSO - Programa de Controle|Rua Eduardo Geronasso|CEP: 82510-280|"
    r"maframbiental\.com\.br"
)
# nota de rodapé da tabela de exames: encerra o bloco (o texto dela quebra em
# várias linhas que não podem virar "exame")
_RE_FIM_EXAMES = re.compile(r"^\*\s*Nos casos de mudança")
_RE_AUSENCIA = re.compile(r"^Ausência de risco", re.IGNORECASE)

_GRUPOS = {
    "fisicos": "Físico",
    "quimicos": "Químico",
    "biologicos": "Biológico",
    "ergonomicos": "Ergonômicos",
    "acidentes": "Acidente",
    "acidentes / mecanicos": "Acidente",
    "acidentes/mecanicos": "Acidente",
}

# fronteiras de coluna do bloco de exames (medidas no PDF: nome termina <215,
# "Fazer" começa em ~227, periodicidade em >=394)
_X_FAZER = 220.0
_X_DIREITA = 385.0


def detectar(lines: list[Line]) -> bool:
    tem_cargo = any(_RE_CARGO.match(ln.text.strip()) for ln in lines)
    tem_controle = any(_RE_CONTROLE.match(ln.text.strip()) for ln in lines)
    return tem_cargo and tem_controle


def _fechar_riscos(ghe: GHE | None) -> None:
    """REGRA: placeholders "Ausência de risco" somem se houver risco real."""
    if ghe is None:
        return
    reais = [r for r in ghe.riscos if not _RE_AUSENCIA.match(r.nome)]
    if reais:
        ghe.riscos = reais
    elif ghe.riscos:  # só havia placeholders de ausência
        ghe.riscos = []
        ghe.ausencia_riscos = True


def _y(ln: Line) -> float:
    return ln.page * 10_000 + ln.top


def _processar_bloco_exames(buf: list[Line], ghe: GHE) -> None:
    """Monta os exames do bloco CONTROLE MÉDICO.

    As células "Fazer no ..." e a periodicidade são centradas verticalmente na
    linha da tabela e podem começar ANTES do nome do exame — a atribuição é
    feita em duas passadas: (1) identificar as linhas da tabela pela célula
    esquerda (nome + "Código(s) eSocial"), com âncora = centro vertical da
    célula; (2) atribuir cada "Fazer"/periodicidade à âncora mais próxima.
    """
    rows: list[dict] = []
    eventos: list[tuple[float, list[str], str]] = []
    atual: dict | None = None

    for ln in buf:
        esquerda = " ".join(
            w.text for w in ln.words if w.x1 < _X_FAZER and w.text.strip()
        ).strip()
        direita = " ".join(
            w.text for w in ln.words if w.x0 >= _X_DIREITA and w.text.strip()
        ).strip()
        fazer = _RE_FAZER.findall(ln.text)

        if esquerda:
            if esquerda.startswith("Código(s) eSocial"):
                if atual is not None:
                    atual["codigo_visto"] = True
                    atual["tops"].append(_y(ln))
            elif atual is None or atual["codigo_visto"]:
                atual = {"nome": [esquerda], "tops": [_y(ln)], "codigo_visto": False,
                         "perfis": [], "direita": []}
                rows.append(atual)
            else:
                atual["nome"].append(esquerda)
                atual["tops"].append(_y(ln))

        if fazer or direita:
            eventos.append((_y(ln), fazer, direita))

    if not rows:
        return
    for r in rows:
        r["anchor"] = sum(r["tops"]) / len(r["tops"])
    for y, fazer, direita in eventos:
        r = min(rows, key=lambda r: abs(r["anchor"] - y))
        r["perfis"].extend(fazer)
        if direita:
            r["direita"].append(direita)

    for r in rows:
        nome = re.sub(r"\s+", " ", " ".join(r["nome"])).strip().rstrip(":")
        if not nome:
            continue
        e = Exame(nome=nome)
        for perfil in r["perfis"]:
            p = _norm(perfil)
            if p == "admissional":
                e.admissao = True
            elif p == "demissional":
                e.demissao = True
            elif p.startswith("retorno"):
                e.ret_trab = True
            elif p.startswith("mudanca"):
                e.mud_riscos = True
            # "Periódico": os meses vêm da coluna da direita
        direita = " ".join(r["direita"])
        m = _RE_PERIODICO.search(direita)
        if m:
            e.periodico_meses = int(m.group(1))
        m = _RE_APOS_ADM.search(direita)
        if m:
            e.apos_adm_meses = int(m.group(1))
            e.apos_adm = True
        ghe.exames.append(e)


def extrair(lines: list[Line]) -> tuple[list[GHE], dict]:
    ghes: list[GHE] = []
    ghe: GHE | None = None
    estado: str | None = None  # None | EXAMES | RISCOS
    grupo_atual: str | None = None
    exames_buf: list[Line] = []
    risco_atual: Risco | None = None
    empresa = ""
    # foco: linhas de cada seção CARGO + a própria linha CARGO (caixa da função).
    # O código do GHE é reescrito ao achar o Ambiente, então chaveamos no fim.
    secoes_foco: list[tuple[GHE, list[Line], Line]] = []
    foco_linhas: list[Line] = []

    def flush_exames():
        nonlocal exames_buf
        if exames_buf and ghe is not None:
            _processar_bloco_exames(exames_buf, ghe)
        exames_buf = []

    for ln in lines:
        txt = ln.text.strip()
        if not txt or _RE_FOOTER.search(txt):
            continue

        if not empresa:
            m = re.search(r"Dados do local:\s*(.+?)\s*\(CNPJ", txt)
            if m:
                empresa = m.group(1).strip()

        m = _RE_CARGO.match(txt)
        if m:
            flush_exames()
            _fechar_riscos(ghe)
            cargo = m.group(1).strip()
            ghe = GHE(codigo=cargo, nome=cargo, cargos=[cargo], pagina=ln.page)
            ghes.append(ghe)
            foco_linhas = [ln]
            secoes_foco.append((ghe, foco_linhas, ln))
            estado = None
            grupo_atual = None
            risco_atual = None
            continue

        if ghe is None:
            continue

        foco_linhas.append(ln)  # linha de conteúdo do cargo atual

        m = _RE_AMBIENTE.search(txt)
        if m:
            gse = m.group(1).strip()
            ghe.setor_override = gse
            ghe.codigo = f"{gse.split(' - ')[0]}/{ghe.nome}"
            continue

        if _RE_CONTROLE.match(txt):
            flush_exames()
            estado = "EXAMES"
            continue

        m = _RE_RISCOS_HDR.match(txt)
        if m:
            flush_exames()
            estado = "RISCOS"
            grupo_atual = _GRUPOS.get(_norm(m.group(1)), "Acidente")
            risco_atual = None
            continue

        # ------------- bloco de exames: acumula e processa por âncoras -------------
        if estado == "EXAMES":
            if _RE_FIM_EXAMES.match(txt):
                flush_exames()
                estado = None
                continue
            exames_buf.append(ln)
            continue

        # ------------- blocos de riscos: ícone ancora o nome -------------
        if estado == "RISCOS":
            if ln.words and ln.words[0].text == _ICONE:
                # REGRA: o risco é sempre o texto ao lado do ícone
                nome = re.sub(r"\s+", " ", " ".join(w.text for w in ln.words[1:])).strip()
                risco_atual = Risco(nome=nome, grupo=grupo_atual or "Acidente")
                ghe.riscos.append(risco_atual)
                continue
            if _RE_LABEL_RISCO.match(txt):
                risco_atual = None
                continue
            if risco_atual is not None and ln.words and ln.words[0].x0 < 150:
                # continuação do nome (quebra logo após a linha do ícone)
                risco_atual.nome = re.sub(r"\s+", " ", risco_atual.nome + " " + txt).strip()
                risco_atual = None  # nomes não passam de 2 linhas
            continue

    flush_exames()
    _fechar_riscos(ghe)

    for g in ghes:
        if not g.setor_override:
            g.setor_override = g.nome  # documento não informa o GSE deste cargo
            g.avisos.append(
                "INFO: documento não informa o GSE (Ambiente Principal) deste "
                "cargo — coluna Setor recebe o nome do cargo; conferir."
            )
        for e in g.exames:
            tem_perfil = any([e.admissao, e.demissao, e.ret_trab, e.mud_riscos,
                              e.periodico_meses, e.apos_adm])
            if not tem_perfil:
                g.avisos.append(f"Exame {e.nome!r} sem nenhum perfil marcado")

    focos: dict[str, dict] = {}
    for g, secao, linha_cargo in secoes_foco:
        foco = montar_foco(secao, g.pagina, [linha_cargo])
        if foco:
            focos[g.codigo] = foco  # g.codigo já é o final (GSE/cargo)

    meta = {
        "empresa": empresa or "EMPRESA",
        "total_ghes": len(ghes),
        "layout": "mafra",
        "focos": focos,
    }
    return ghes, meta


# ------------------- De-para do cliente SK (riscos e exames) -------------------
# Regra de IMPORTAÇÃO, não de extração: o pipeline chama
# preparar_para_planilha() só na hora de montar os xlsx. A conferência e os
# goldens seguem com a nomenclatura do PDF.

def _chave(s: str) -> str:
    """chave de comparação: só letras/dígitos, sem acento/caixa — absorve
    hífens, espaços e pontuação divergentes entre planilha e PDF."""
    return re.sub(r"[^a-z0-9]", "", _norm(s))


def _carregar_depara() -> list[tuple[str, str, list[str]]]:
    if not _DEPARA_EXAMES.is_file():
        return []
    dados = json.loads(_DEPARA_EXAMES.read_text(encoding="utf-8"))
    return [(_chave(de), de, paras) for de, paras in dados["exames"]]


def preparar_para_planilha(ghes: list[GHE]) -> list[GHE]:
    """Cópia dos GHEs com o De-para do cliente SK aplicado (nomes de risco
    sem sufixo eSocial; exames no catálogo BR MED)."""
    ghes = copy.deepcopy(ghes)
    depara = _carregar_depara()

    for g in ghes:
        for r in g.riscos:
            r.nome = _RE_ESOCIAL_RISCO.sub("", r.nome).strip()
        if not depara:
            continue

        novos: list[Exame] = []
        for e in g.exames:
            ce = _chave(e.nome)
            paras = next((p for c, _, p in depara if c == ce), None)
            if paras is None:
                # tolerância a variações mínimas entre planilha e PDF
                # ("ANAMNSE"/"anamnese", "Raio-X"/"Rx", "e"/"ou frações")
                melhor = max(depara, key=lambda d: SequenceMatcher(None, ce, d[0]).ratio())
                if SequenceMatcher(None, ce, melhor[0]).ratio() >= 0.9:
                    paras = melhor[2]
            if paras is None:
                novos.append(e)  # fora do De-para: nomenclatura do PDF
                continue
            for nome_para in paras:  # 1->N desdobra mantendo os perfis
                novos.append(Exame(
                    nome=nome_para, admissao=e.admissao,
                    apos_adm_meses=e.apos_adm_meses, apos_adm=e.apos_adm,
                    periodico_meses=e.periodico_meses, ret_trab=e.ret_trab,
                    mud_riscos=e.mud_riscos, demissao=e.demissao,
                ))

        # N->1 (ex.: EXAME CLÍNICO + anamnese -> CLÍNICO OCUPACIONAL):
        # mescla perfis dos duplicados, preservando a ordem da 1ª ocorrência
        por_nome: dict[str, Exame] = {}
        g.exames = []
        for e in novos:
            alvo = por_nome.get(e.nome)
            if alvo is None:
                por_nome[e.nome] = e
                g.exames.append(e)
                continue
            alvo.admissao = alvo.admissao or e.admissao
            alvo.apos_adm = alvo.apos_adm or e.apos_adm
            alvo.ret_trab = alvo.ret_trab or e.ret_trab
            alvo.mud_riscos = alvo.mud_riscos or e.mud_riscos
            alvo.demissao = alvo.demissao or e.demissao
            alvo.periodico_meses = alvo.periodico_meses or e.periodico_meses
            alvo.apos_adm_meses = alvo.apos_adm_meses or e.apos_adm_meses

    return ghes
