"""
Extrator do layout International SOS / Solstad (embarcações offshore).

Estrutura do documento (ex.: PCMSO-SOLSTAD_SHIPPING_N, NORMAND POSEIDON):

1. LISTA DE GHEs, FUNÇÕES E RISCOS — tabela de 3 colunas:
       GHE (x<55) | FUNÇÃO (55..205) | RISCOS (>=207)
   O código do GHE (2, 3.1, 8.2...) aparece verticalmente centrado no bloco,
   sempre a poucas linhas do início. Os riscos vêm prefixados pelo agente
   ("ERGONÔMICO:", "FÍSICO:", "PSICOSSOCIAS:"...) e separados por vírgula.

2. GRADE DE EXAMES — exame x (Admissional/Periódico/Retorno/Mudança/
   Demissional), células "TODOS", "GHE 7", "GHEs 8.1, ...", "NÃO" ou
   "VER ITENS 3 e 4 NAS PAGS. 5 e 6".
   Regras de negócio (combinadas com o cliente, jul/2026):
     - Retorno e Mudança seguem a MESMA grade do Periódico;
     - "GHE 3" na grade abrange 3.1/3.2/3.3 (expansão por prefixo);
     - nota "***" da grade: RX Tórax e Espirometria a cada 2 anos (24 meses);
     - periodicidade padrão do Periódico: 12 meses (interpretação — embarcação
       grau de risco 3/4; ver pendencias.md).

3. Tabela de Funções para Atividades Críticas (A/C) — é IMAGEM no PDF
   (nenhum leitor de texto a enxerga): extraída por OCR (tesseract) com
   pré-processamento (render 400dpi + remoção das linhas de grade).
   Regras de negócio:
     - função COM A/C recebe a grade de "Exames específicos" (lista textual
       abaixo da tabela): anual (12 meses), todos os perfis exceto demissional;
     - função COM A/C: Teste Ergométrico entra e o Eletrocardiograma sai;
       função SEM A/C: mantém o Eletrocardiograma (regra etária do documento
       não é representável na planilha — vira aviso INFO);
     - NRs por atividade: espaço confinado=NR33, altura=NR35,
       eletricidade=NR10, resgate=NR37, resposta a emergência=NR37;
     - NR30 obrigatória em TODOS os GHEs.

4. Funções bilíngues: a planilha do cliente (data/solstad_funcoes_bilingues
   .json) traduz cada função; a coluna Função sai "COMANDANTE / CAPTAIN".

Cada (GHE, função) vira um GHE próprio (como no layout Occupare), porque
atividades críticas, NRs e a troca ECG/Ergométrico variam por função.
"""

from __future__ import annotations

import json
import re
from difflib import SequenceMatcher
from pathlib import Path

from .base import GHE, Exame, Line, Risco, norm as _norm

_DADOS = Path(__file__).parent / "data" / "solstad_funcoes_bilingues.json"

# fronteiras de coluna da LISTA DE GHEs (pontos)
_X_FUNCAO = 55.0
_X_RISCOS = 207.0
# gap máximo (pt) ao "subir" do código do GHE até o início do bloco
_GAP_BLOCO = 13.0

_GRUPOS = {
    "ergonomico": "Ergonômicos", "ergonomicos": "Ergonômicos",
    "fisico": "Físico", "fisicos": "Físico",
    "quimico": "Químico", "quimicos": "Químico",
    "biologico": "Biológico", "biologicos": "Biológico",
    "mecanico": "Acidente", "mecanicos": "Acidente", "acidente": "Acidente",
    # "PSICOSSOCIAS" é a grafia do próprio documento
    "psicossocias": "Psicossociais", "psicossociais": "Psicossociais",
}

_RE_CODIGO = re.compile(r"^\d+(?:\.\d+)?$")
_RE_GRUPO = re.compile(r"^\s*([A-ZÀ-Üa-zà-ü]+)\s*:\s*(.*)$", re.DOTALL)
_CONECTORES = {"de", "da", "do", "das", "dos", "e"}
_NIVEIS_EXTRA = {"jr", "pl", "sr", "a", "b"}
_RE_NIVEL = re.compile(r"^[0-9ivx/][0-9ivx/.\-]*[ab]?$")

# atividade crítica (coluna da tabela OCR) -> chave de builder.NR_COLS
_ATIVIDADE_NR = {
    "espaco_confinado": "NR33",
    "trabalho_em_altura": "NR35",
    "eletricidade": "NR10",
    "resgate": "NR37_BRIGADA",
    "resposta_emergencia": "NR37_BRIGADA",
}
_PERIODICO_PADRAO_MESES = 12  # interpretação (pendencias.md)


def detectar(lines: list[Line]) -> bool:
    tem_lista = any(
        re.match(r"^GHE\s+FUNÇÃO\s+RISCOS$", ln.text.strip()) for ln in lines
    )
    tem_grade = any("GRADE DE EXAMES" in ln.text for ln in lines)
    return tem_lista and tem_grade


# ---------------------------------------------------------------- utilidades

def _y(ln: Line) -> float:
    return ln.page * 10000 + ln.top


def _stem(nome: str) -> str:
    """chave de comparação: só letras/dígitos, sem acento/caixa."""
    return re.sub(r"[^a-z0-9]", "", _norm(nome))


def _tokens_sem_nivel(nome: str) -> tuple[list[str], list[str]]:
    """tokens normalizados sem conectores; devolve (radical, níveis removidos
    do fim — na grafia normalizada)."""
    toks = [t for t in re.split(r"[^a-z0-9/\-]+", _norm(nome)) if t]
    toks = [t for t in toks if t not in _CONECTORES]
    niveis: list[str] = []
    while toks and (toks[-1] in _NIVEIS_EXTRA or _RE_NIVEL.match(toks[-1])):
        niveis.insert(0, toks.pop())
    return toks, niveis


def _compat_tokens(a: list[str], b: list[str]) -> bool:
    """abreviação por prefixo, token a token (MAQ ~ MAQUINAS, OFIC ~ OFICIAL)."""
    if len(a) != len(b) or not a:
        return False
    return all(x.startswith(y) or y.startswith(x) for x, y in zip(a, b))


def _tier(nome_a: str, nome_b: str) -> int:
    """Quão equivalentes são dois nomes de função? 0 = não casam;
    5 exato > 4 radical (sem níveis) > 3 abreviação > 2 prefixo > 1 fuzzy.
    Sempre casar pela MELHOR camada disponível — o fuzzy sozinho confunde
    pares como SUBCHEFE DE MÁQUINAS x CHEFE DE MÁQUINAS."""
    if _stem(nome_a) == _stem(nome_b):
        return 5
    ta, _ = _tokens_sem_nivel(nome_a)
    tb, _ = _tokens_sem_nivel(nome_b)
    ra, rb = "".join(ta), "".join(tb)
    if ra and ra == rb:
        return 4
    if _compat_tokens(ta, tb):
        return 3
    if len(ra) >= 8 and len(rb) >= 8 and (ra.startswith(rb) or rb.startswith(ra)):
        return 2
    if SequenceMatcher(None, ra, rb).ratio() >= 0.85:
        return 1
    return 0


# ------------------------------------------------- 1. lista de GHEs/funções

def _parse_lista_ghes(lines: list[Line]) -> list[dict]:
    """Blocos da tabela GHE|FUNÇÃO|RISCOS -> [{codigo, funcoes, riscos, pagina}]."""
    ini = fim = None
    for i, ln in enumerate(lines):
        if re.match(r"^GHE\s+FUNÇÃO\s+RISCOS$", ln.text.strip()):
            ini = i + 1
        elif ini is not None and "GRADE DE EXAMES" in ln.text:
            fim = i
            break
    if ini is None or fim is None:
        raise ValueError("layout solstad: tabela 'LISTA DE GHEs' não encontrada")

    tabela = [ln for ln in lines[ini:fim]
              if ln.text.strip() and ln.text.strip() != "Confidential"]

    # âncoras: linhas com o código do GHE na coluna da esquerda
    codigos: list[tuple[int, str]] = []
    for i, ln in enumerate(tabela):
        for w in ln.words:
            if w.x1 <= _X_FUNCAO and _RE_CODIGO.match(w.text):
                codigos.append((i, w.text))
                break
    if not codigos:
        raise ValueError("layout solstad: nenhum código de GHE encontrado")

    # início do bloco: sobe a partir do código enquanto o espaçamento for
    # de linha (o código fica verticalmente centrado no cabeçalho do bloco)
    inicios: list[tuple[int, str]] = []
    for i, cod in codigos:
        j = i
        while j > 0 and tabela[j].page == tabela[j - 1].page \
                and tabela[j].top - tabela[j - 1].top <= _GAP_BLOCO:
            j -= 1
        inicios.append((j, cod))

    blocos: list[dict] = []
    for n, (j, cod) in enumerate(inicios):
        j_fim = inicios[n + 1][0] if n + 1 < len(inicios) else len(tabela)
        blocos.append(_parse_bloco(cod, tabela[j:j_fim]))
    return blocos


def _parse_bloco(codigo: str, linhas: list[Line]) -> dict:
    funcoes: list[str] = []
    pendente = ""  # função com quebra de linha (termina em conector)
    grupos: list[tuple[str, str]] = []  # (grupo, texto acumulado)

    for ln in linhas:
        parte_func = " ".join(
            w.text for w in ln.words if _X_FUNCAO <= w.x0 < _X_RISCOS
        ).strip()
        parte_risco = " ".join(w.text for w in ln.words if w.x0 >= _X_RISCOS).strip()

        if parte_func:
            if pendente:
                parte_func = f"{pendente} {parte_func}"
                pendente = ""
            if parte_func.split()[-1].lower() in _CONECTORES:
                pendente = parte_func
            else:
                funcoes.append(parte_func)

        if parte_risco:
            m = _RE_GRUPO.match(parte_risco)
            grupo = _GRUPOS.get(_norm(m.group(1))) if m else None
            if grupo:
                grupos.append((grupo, m.group(2).strip()))
            elif grupos:
                grupos[-1] = (grupos[-1][0], f"{grupos[-1][1]} {parte_risco}".strip())

    if pendente:
        funcoes.append(pendente)

    riscos: list[Risco] = []
    for grupo, texto in grupos:
        for nome in _split_virgulas(texto.rstrip(".").strip()):
            if nome:
                riscos.append(Risco(nome=nome, grupo=grupo))
    return {
        "codigo": codigo,
        "funcoes": funcoes,
        "riscos": riscos,
        "pagina": linhas[0].page if linhas else None,
    }


def _split_virgulas(texto: str) -> list[str]:
    """separa por vírgulas fora de parênteses."""
    partes, atual, nivel = [], [], 0
    for c in texto:
        if c == "(":
            nivel += 1
        elif c == ")":
            nivel = max(0, nivel - 1)
        if c == "," and nivel == 0:
            partes.append("".join(atual).strip())
            atual = []
        else:
            atual.append(c)
    partes.append("".join(atual).strip())
    return [re.sub(r"\s+", " ", p) for p in partes if p.strip()]


# ------------------------------------------------------- 2. grade de exames

def _parse_grade(lines: list[Line]) -> tuple[list[dict], dict[str, str]]:
    """Grade de exames -> ([{nome, marcadores, colunas:{perfil: valor}}],
    {marcador: texto da nota})."""
    ini = None
    for i, ln in enumerate(lines):
        if re.match(r"^-?\s*GRADE DE EXAMES", ln.text.strip()):
            ini = i + 1
    if ini is None:
        raise ValueError("layout solstad: GRADE DE EXAMES não encontrada")

    # cabeçalho -> centro x de cada coluna de perfil
    cab = None
    centros: dict[str, float] = {}
    for i in range(ini, min(ini + 5, len(lines))):
        palavras = {_norm(w.text): w for w in lines[i].words}
        if "admissional" in palavras and "demissional" in palavras:
            cab = i
            for chave in ("admissional", "periodico", "retorno", "mudanca",
                          "demissional"):
                w = palavras.get(chave)
                if w is not None:
                    centros[chave] = (w.x0 + w.x1) / 2
            break
    if cab is None or len(centros) < 5:
        raise ValueError("layout solstad: cabeçalho da grade não reconhecido")
    x_nome_max = min(centros.values()) - 45  # coluna EXAMES

    # linhas da grade até as notas de rodapé (* ...) ou fim do assunto
    corpo: list[Line] = []
    notas: dict[str, str] = {}
    nota_atual: str | None = None
    for ln in lines[cab + 1:]:
        txt = ln.text.strip()
        if not txt or txt == "Confidential":
            continue
        m = re.match(r"^(\*{1,3})\s+(.*)$", txt)
        if m:
            nota_atual = m.group(1)
            notas[nota_atual] = m.group(2).strip()
            continue
        if "Tabela de Funções" in txt or "CRONOGRAMA" in txt:
            break
        if nota_atual:
            notas[nota_atual] += " " + txt
            continue
        corpo.append(ln)

    # âncora de linha de exame: valor na coluna ADMISSIONAL
    def _valor_adm(ln: Line) -> bool:
        for w in ln.words:
            cx = (w.x0 + w.x1) / 2
            if abs(cx - centros["admissional"]) < 45 and \
                    _norm(w.text).rstrip(",") in ("todos", "nao", "ghe", "ghes"):
                return True
        return False

    ancoras = [i for i, ln in enumerate(corpo) if _valor_adm(ln)]
    if not ancoras:
        return [], notas

    exames: list[dict] = []
    for n, ia in enumerate(ancoras):
        # faixa da linha: do ponto médio com a âncora anterior até o da próxima
        y_a = _y(corpo[ia])
        y_ant = _y(corpo[ancoras[n - 1]]) if n else None
        y_prox = _y(corpo[ancoras[n + 1]]) if n + 1 < len(ancoras) else None
        lo = (y_ant + y_a) / 2 if y_ant is not None else float("-inf")
        hi = (y_a + y_prox) / 2 if y_prox is not None else float("inf")

        nome_partes: list[str] = []
        cols: dict[str, list[str]] = {k: [] for k in centros}
        for ln in corpo:
            if not (lo <= _y(ln) < hi):
                continue
            for w in ln.words:
                cx = (w.x0 + w.x1) / 2
                if w.x0 < x_nome_max and cx < x_nome_max + 30:
                    nome_partes.append(w.text)
                else:
                    perfil = min(centros, key=lambda k: abs(centros[k] - cx))
                    cols[perfil].append(w.text)

        nome = " ".join(nome_partes)
        marcadores = "".join(re.findall(r"\*+", nome))
        nome = re.sub(r"\s*\*+\s*", " ", nome)
        nome = re.sub(r"(\w)- (\w)", r"\1-\2", nome)  # quebra de linha em hífen
        nome = re.sub(r"\s+", " ", nome).strip()
        if not nome:
            continue
        exames.append({
            "nome": nome,
            "marcadores": marcadores,
            "colunas": {k: " ".join(v) for k, v in cols.items()},
        })
    return exames, notas


def _interpretar_celula(valor: str, codigos: list[str]) -> set[str] | str:
    """célula da grade -> conjunto de códigos de GHE, ou "ver_itens"."""
    v = _norm(valor)
    if "ver" in v and "iten" in v:
        return "ver_itens"
    if "todos" in v:
        return set(codigos)
    achados: set[str] = set()
    for cod in re.findall(r"\d+(?:\.\d+)?", valor):
        achados.update(c for c in codigos if c == cod or c.startswith(cod + "."))
    if achados:
        return achados
    return set()  # vazio ou "NÃO"


# --------------------------------------- 3. atividades críticas (OCR da imagem)

def _ocr_atividades(pdf_path: str, pagina: int) -> list[tuple[str, set[str]]]:
    """OCR da tabela (imagem) de funções x atividades críticas.

    Render em 400dpi apenas do retângulo da imagem, remoção das linhas de
    grade (senão o tesseract fragmenta as células) e leitura em PSM 6.
    Devolve [(nome da função no OCR, {atividades})].
    """
    import numpy as np
    import pdfplumber
    import pytesseract
    from PIL import Image

    with pdfplumber.open(pdf_path) as pdf:
        p = pdf.pages[pagina - 1]
        if not p.images:
            return []
        im = max(p.images, key=lambda i: i["width"] * i["height"])
        bbox = (max(im["x0"] - 2, 0), max(im["top"] - 2, 0),
                min(im["x1"] + 2, p.width), min(im["bottom"] + 2, p.height))
        img = p.crop(bbox).to_image(resolution=400).original.convert("L")

    a = np.array(img)
    tinta = a < 128
    a = a.copy()
    a[tinta.sum(axis=1) > tinta.shape[1] * 0.5, :] = 255   # linhas horizontais
    a[:, tinta.sum(axis=0) > tinta.shape[0] * 0.5] = 255   # linhas verticais

    dados = pytesseract.image_to_data(
        Image.fromarray(a), lang="por", config="--psm 6",
        output_type=pytesseract.Output.DICT,
    )

    palavras = []  # (top, centro_x, esquerda, texto)
    for i, txt in enumerate(dados["text"]):
        txt = txt.strip()
        if txt and float(dados["conf"][i]) > 20:
            cx = dados["left"][i] + dados["width"][i] / 2
            palavras.append((dados["top"][i], cx, dados["left"][i], txt))
    palavras.sort()

    # agrupa em linhas (passo de linha da tabela ~64px em 400dpi)
    linhas: list[list[tuple]] = []
    for w in palavras:
        if linhas and w[0] - linhas[-1][0][0] <= 25:
            linhas[-1].append(w)
        else:
            linhas.append([w])

    # cabeçalho -> centro x de cada coluna de atividade
    chaves = {
        "confinado": "espaco_confinado", "altura": "trabalho_em_altura",
        "eletrecidade": "eletricidade", "eletricidade": "eletricidade",
        "resgate": "resgate", "emergencia": "resposta_emergencia",
    }
    centros: dict[str, float] = {}
    corpo_inicio = 0
    for i, ln in enumerate(linhas):
        for _, cx, _, txt in ln:
            atividade = chaves.get(_norm(txt))
            if atividade:
                centros[atividade] = cx
        if _norm(" ".join(t for _, _, _, t in ln)).startswith("funcao") or \
                any(_norm(t) == "funcao" for _, _, _, t in ln):
            corpo_inicio = i + 1
    if len(centros) < 5:
        return []
    x_min_col = min(centros.values()) - 220

    resultado: list[tuple[str, set[str]]] = []
    for ln in linhas[corpo_inicio:]:
        nome = " ".join(t for _, cx, _, t in sorted(ln, key=lambda w: w[2])
                        if cx < x_min_col)
        marcas: set[str] = set()
        for _, cx, _, txt in ln:
            if re.fullmatch(r"[xX×]", txt) and cx >= x_min_col:
                atividade = min(centros, key=lambda k: abs(centros[k] - cx))
                if abs(centros[atividade] - cx) < 220:
                    marcas.add(atividade)
        nome = re.sub(r"\s+", " ", nome).strip()
        if len(_stem(nome)) >= 4 and marcas:
            resultado.append((nome, marcas))
    return resultado


# ----------------------------------------------------- 4. funções bilíngues

def _carregar_bilingue() -> list[tuple[str, str]]:
    if not _DADOS.is_file():
        return []
    dados = json.loads(_DADOS.read_text(encoding="utf-8"))
    return [(pt.strip(), en.strip()) for pt, en in dados.items()]


def _traduzir(funcao: str, bilingue: list[tuple[str, str]]) -> str | None:
    """PT do PDF -> nome em inglês da planilha do cliente (ou None)."""
    melhor: tuple[int, str, str] | None = None
    for pt, en in bilingue:
        t = _tier(funcao, pt)
        if t and (melhor is None or t > melhor[0]):
            melhor = (t, pt, en)
    if melhor is None:
        return None
    t, pt, en = melhor
    if t == 5:  # grafia exata: usa o inglês como está (níveis inclusos)
        return en
    _, niveis_f = _tokens_sem_nivel(funcao)
    sufixo = funcao.split()[-len(niveis_f):] if niveis_f else []
    _, niveis_p = _tokens_sem_nivel(pt)
    en_toks = en.split()
    for _ in range(len(niveis_p)):  # tira os níveis do inglês também
        if en_toks and (_RE_NIVEL.match(_norm(en_toks[-1]))
                        or _norm(en_toks[-1]) in _NIVEIS_EXTRA):
            en_toks.pop()
    base = " ".join(en_toks).rstrip(".-").strip()
    return " ".join([base] + sufixo) if sufixo else base


# ------------------------------------------------------------------ extração

def extrair(lines: list[Line], pdf_path: str | None = None) -> tuple[list[GHE], dict]:
    avisos_doc: list[str] = []

    empresa = ""
    for ln in lines:
        m = re.match(r"^RAZÃO SOCIAL\s+(.+)$", ln.text.strip())
        if m:
            empresa = m.group(1).strip()
            break

    blocos = _parse_lista_ghes(lines)
    codigos = [b["codigo"] for b in blocos]

    grade, notas = _parse_grade(lines)

    # nota "***" (ou similar) definindo periodicidade diferente do padrão
    meses_por_marcador: dict[str, int] = {}
    for marcador, texto in notas.items():
        m = re.search(r"a cada\s*(\d+)\s*ano", _norm(texto))
        if m:
            meses_por_marcador[marcador] = int(m.group(1)) * 12
        else:
            m = re.search(r"a cada\s*(\d+)\s*mes", _norm(texto))
            if m:
                meses_por_marcador[marcador] = int(m.group(1))

    # tabela de atividades críticas (imagem -> OCR)
    pagina_ac = None
    for ln in lines:
        if _norm(ln.text).startswith("tabela de funcoes para trabalho em altura") \
                and "..." not in ln.text:
            pagina_ac = ln.page
            break

    # exames específicos de atividades críticas: lista textual (com bullets)
    # abaixo da tabela — só vale a ocorrência na página da tabela (o título
    # também aparece no índice do documento)
    especificos: list[str] = []
    coletando = False
    for ln in lines:
        t = ln.text.strip()
        if pagina_ac and ln.page < pagina_ac:
            continue
        if _norm(t).startswith("exames especificos para"):
            coletando = True
            especificos = []
            continue
        if coletando:
            m = re.match(r"^[•·\-\*]\s*(.+)$", t)
            if m:
                especificos.append(m.group(1).strip())
            elif especificos and t and t != "Confidential" \
                    and not _norm(t).startswith("emergencia"):
                break
    atividades_ocr: list[tuple[str, set[str]]] = []
    if pagina_ac and pdf_path:
        atividades_ocr = _ocr_atividades(pdf_path, pagina_ac)
        if atividades_ocr:
            avisos_doc.append(
                f"INFO: tabela de atividades críticas (pág. {pagina_ac}) é imagem "
                f"no PDF — extraída por OCR ({len(atividades_ocr)} funções); "
                f"conferir na tela de conferência."
            )
    if pagina_ac and not atividades_ocr:
        avisos_doc.append(
            f"Tabela de atividades críticas (pág. {pagina_ac}) não pôde ser "
            f"extraída — exames específicos e NRs por atividade NÃO aplicados."
        )

    bilingue = _carregar_bilingue()
    if not bilingue:
        avisos_doc.append(
            "Planilha de funções bilíngues não encontrada — coluna Função "
            "ficará apenas em português."
        )

    avisos_doc.append(
        f"INFO: periodicidade padrão do Perfil Periódico interpretada como "
        f"{_PERIODICO_PADRAO_MESES} meses (notas da grade podem sobrepor, ex.: "
        f"RX Tórax/Espirometria); confirmar — ver pendencias.md."
    )

    ghes: list[GHE] = []
    ocr_usadas: set[int] = set()

    for bloco in blocos:
        cod = bloco["codigo"]
        for funcao in bloco["funcoes"]:
            g = GHE(
                codigo=f"{cod}/{funcao}",
                nome=funcao,
                setor_override=f"GHE {cod}",
                riscos=list(bloco["riscos"]),
                pagina=bloco["pagina"],
            )

            # função bilíngue (regra do cliente: "COMANDANTE / CAPTAIN")
            en = _traduzir(funcao, bilingue) if bilingue else None
            cargo = f"{funcao} / {en}" if en else funcao
            if bilingue and not en:
                g.avisos.append(
                    f"INFO: função {funcao!r} sem correspondência na planilha "
                    f"de funções bilíngues — mantida só em português."
                )
            g.cargos = [cargo]

            # grade base de exames
            exames: list[Exame] = []
            for ex in grade:
                cel = {p: _interpretar_celula(v, codigos)
                       for p, v in ex["colunas"].items()}
                per = cod in cel["periodico"] if isinstance(cel["periodico"], set) else False
                meses = meses_por_marcador.get(
                    ex["marcadores"], _PERIODICO_PADRAO_MESES) if per else None

                def _tem(perfil: str) -> bool:
                    v = cel[perfil]
                    if v == "ver_itens":  # regra do cliente: segue o Periódico
                        return per
                    return cod in v

                e = Exame(
                    nome=ex["nome"],
                    admissao=_tem("admissional"),
                    periodico_meses=meses,
                    ret_trab=_tem("retorno"),
                    mud_riscos=_tem("mudanca"),
                    demissao=_tem("demissional"),
                )
                if any([e.admissao, e.periodico_meses, e.ret_trab,
                        e.mud_riscos, e.demissao]):
                    exames.append(e)

            # atividades críticas da função (OCR): usa a melhor camada de
            # casamento (linhas de nível diferente da mesma função se somam)
            tiers = [(_tier(funcao, nome_ocr), i)
                     for i, (nome_ocr, _) in enumerate(atividades_ocr)]
            melhor_tier = max((t for t, _ in tiers), default=0)
            marcas: set[str] = set()
            achou_ac = melhor_tier > 0
            for t, i in tiers:
                if t > 0:
                    ocr_usadas.add(i)  # variações de nível não viram "sobra"
                if t == melhor_tier and t > 0:
                    marcas |= atividades_ocr[i][1]

            nrs = {"NR30"}  # regra do cliente: NR30 em todos os GHEs
            if achou_ac:
                # as atividades encontradas não viram aviso por GHE (o aviso
                # de documento já manda conferir a tabela OCR; 30 GHEs
                # amarelos = ruído) — elas ficam visíveis nas NRs da PGR
                nrs |= {_ATIVIDADE_NR[a] for a in marcas}
                _aplicar_exames_especificos(exames, especificos)
                exames = [e for e in exames
                          if "eletrocardiograma" not in _stem(e.nome)]
            elif atividades_ocr:
                g.avisos.append(
                    f"INFO: função {funcao!r} não consta na tabela de atividades "
                    f"críticas — mantido Eletrocardiograma; regra etária do "
                    f"documento (45+ anos: teste ergométrico) não é "
                    f"representável na planilha."
                )
            g.nrs = {cargo: sorted(nrs)}
            g.exames = exames
            ghes.append(g)

    sobras = [nome for i, (nome, _) in enumerate(atividades_ocr)
              if i not in ocr_usadas]
    if sobras:
        avisos_doc.append(
            "INFO: funções da tabela de atividades críticas sem função "
            "correspondente na lista de GHEs: " + "; ".join(sobras) + "."
        )

    meta = {
        "empresa": empresa or "EMPRESA",
        "total_ghes": len(ghes),
        "layout": "solstad",
        "avisos_documento": avisos_doc,
    }
    return ghes, meta


def _aplicar_exames_especificos(exames: list[Exame], especificos: list[str]) -> None:
    """Grade de exames específicos p/ atividades críticas: anual, todos os
    perfis exceto demissional. Mescla com o exame equivalente da grade base
    (mesmo exame com grafia diferente) ou cria um novo."""
    for nome in especificos:
        alvo = None
        se = _stem(nome)
        primeiro = _stem(nome.split()[0])
        for e in exames:
            sg = _stem(e.nome)
            if se == sg or sg.startswith(se) or se.startswith(sg) \
                    or SequenceMatcher(None, se, sg).ratio() >= 0.8 \
                    or (len(primeiro) >= 5 and sg.startswith(primeiro)):
                alvo = e
                break
        if alvo is None:
            alvo = Exame(nome=nome)
            exames.append(alvo)
        alvo.admissao = True
        alvo.ret_trab = True
        alvo.mud_riscos = True
        if not alvo.periodico_meses:
            alvo.periodico_meses = 12
