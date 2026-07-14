"""
Auditoria da extração: nível de confiança por GHE + onde o humano deve olhar.

Camada determinística (sem LLM): combina sinais objetivos do pipeline —
divergência entre leitores, avisos de parse, formas anômalas (GHE sem risco
sem declaração de ausência, exame sem perfil, nomes suspeitos) — num score
0-100 e numa lista de pontos de atenção priorizada.

Opera sobre os dicts do JSON de auditoria (formato `asdict(GHE)`), então
funciona tanto no fluxo web quanto sobre um JSON já salvo.

Um auditor LLM opcional pode ser plugado depois (mesma interface): ele
receberia o texto da seção + o JSON extraído e apontaria divergências que as
heurísticas não veem. Ver GUIA_MELHORIAS.md.
"""

from __future__ import annotations

import re


def auditar_ghe(ghe: dict, divergencias_do_ghe: list[str]) -> dict:
    """Pontua um GHE: 100 = nada a conferir; quanto menor, mais atenção."""
    pontos: list[tuple[int, str]] = []  # (penalidade, descrição)

    for d in divergencias_do_ghe:
        pontos.append((40, f"Leitores divergem: {d}"))

    if not ghe["riscos"] and not ghe.get("ausencia_riscos"):
        pontos.append((40, "Nenhum risco extraído e o documento não declara ausência"))
    if not ghe["exames"]:
        pontos.append((40, "Nenhum exame extraído"))
    if not ghe["cargos"]:
        pontos.append((40, "Nenhuma função extraída"))

    for a in ghe["avisos"]:
        if a.startswith("INFO:"):
            pontos.append((10, a[5:].strip()))
        else:
            pontos.append((25, a))

    for e in ghe["exames"]:
        tem_perfil = any([
            e["admissao"], e["periodico_meses"], e["apos_adm"],
            e["apos_adm_meses"], e["ret_trab"], e["mud_riscos"], e["demissao"],
        ])
        if not tem_perfil:
            pontos.append((20, f"Exame {e['nome']!r} sem nenhum perfil marcado"))
        # nomes legítimos chegam a ~80 chars (ex.: "Rx Tórax (PA) Padrão OIT
        # (o mais recente), com dois leitores habilitados"); colagem de células
        # produz nomes bem maiores
        if len(e["nome"]) > 100:
            pontos.append(
                (15, f"Nome de exame suspeito de célula mesclada: {e['nome']!r}")
            )

    for c in ghe["cargos"]:
        if len(c) <= 3 or re.fullmatch(r"[IVX]+", c):
            pontos.append((20, f"Função com nome suspeito de fragmento: {c!r}"))

    for r in ghe["riscos"]:
        # < 4 e não < 5: "FRIO" é risco legítimo (glossário do próprio
        # PCMSO Solstad); fragmentos de parsing são conectivos de 1-3 letras
        if len(r["nome"]) < 4:
            pontos.append((15, f"Risco com nome muito curto: {r['nome']!r}"))

    confianca = max(0, 100 - sum(p for p, _ in pontos))
    return {
        "confianca": confianca,
        "pontos_atencao": [d for _, d in sorted(pontos, reverse=True)],
    }


def auditar(ghes: list[dict], divergencias: list[str]) -> list[dict]:
    """Auditoria de todos os GHEs; divergências são atribuídas pelo código."""
    resultado = []
    for g in ghes:
        do_ghe = [d for d in divergencias if f"[{g['codigo']}]" in d]
        resultado.append(auditar_ghe(g, do_ghe))
    return resultado
