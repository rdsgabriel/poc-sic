"""
De-para do cliente SK (layout Mafra/Taboca) — regra de IMPORTAÇÃO.

`preparar_para_planilha` é aplicado pelo pipeline só na geração dos xlsx;
a extração (e os goldens) mantêm a nomenclatura exata do PDF. Estes testes
não dependem de PDF: exercitam a transformação com dados sintéticos usando
os nomes reais do documento Taboca.
"""

from __future__ import annotations

from app.extractors import mafra
from app.extractors.base import GHE, Exame, Risco


def _ghe(exames: list[Exame], riscos: list[Risco] | None = None) -> GHE:
    return GHE(codigo="CARGO X", nome="CARGO X", cargos=["CARGO X"],
               exames=exames, riscos=riscos or [])


def _nomes(g: GHE) -> list[str]:
    return [e.nome for e in g.exames]


def test_risco_perde_sufixo_esocial() -> None:
    g = _ghe([], [Risco(nome="Radiação Ionizante eSocial 02.01.009", grupo="Físico"),
                  Risco(nome="Óleo mineral eSocial 01.17.001", grupo="Químico"),
                  Risco(nome="Calor", grupo="Físico")])
    (t,) = mafra.preparar_para_planilha([g])
    assert [r.nome for r in t.riscos] == ["Radiação Ionizante", "Óleo mineral", "Calor"]


def test_renomeia_exames_para_catalogo() -> None:
    g = _ghe([Exame(nome="Eletrocardiograma (ECG)", admissao=True),
              Exame(nome="Glicemia jejum", periodico_meses=12)])
    (t,) = mafra.preparar_para_planilha([g])
    assert _nomes(t) == ["ELETROCARDIOGRAMA", "GLICEMIA DE JEJUM"]
    assert t.exames[0].admissao and t.exames[1].periodico_meses == 12


def test_desdobramento_1_para_n_mantem_perfis() -> None:
    g = _ghe([Exame(nome="Função renal (ureia + creatinina)",
                    admissao=True, periodico_meses=12),
              Exame(nome="Função hepática (TGO, TGP, GGT)", demissao=True)])
    (t,) = mafra.preparar_para_planilha([g])
    assert _nomes(t) == ["UREIA", "CREATININA", "TGP (ALT)", "GGT (GAMA-GT)", "TGO (AST)"]
    assert all(e.admissao and e.periodico_meses == 12 for e in t.exames[:2])
    assert all(e.demissao for e in t.exames[2:])


def test_fusao_n_para_1_mescla_perfis() -> None:
    g = _ghe([Exame(nome="Exame clínico", admissao=True),
              Exame(nome="anamnese e exame físico", periodico_meses=12)])
    (t,) = mafra.preparar_para_planilha([g])
    assert _nomes(t) == ["CLÍNICO OCUPACIONAL"]
    assert t.exames[0].admissao and t.exames[0].periodico_meses == 12


def test_fuzzy_absorve_variacoes_de_grafia() -> None:
    # typo "ANAMNSE" da planilha, "Rx"/"Raio-X" e "ou"/"e frações" do PDF
    g = _ghe([Exame(nome="Hemograma completo com contagem de plaquetas ou frações",
                    admissao=True),
              Exame(nome="Rx Tórax (PA) Padrão OIT (o mais recente), com dois "
                         "leitores habilitados (1078)", admissao=True)])
    (t,) = mafra.preparar_para_planilha([g])
    assert _nomes(t) == ["HEMOGRAMA COMPLETO COM PLAQUETAS",
                         "RADIOGRAFIA DE TÓRAX - PADRÃO OIT"]


def test_fora_do_depara_mantem_nomenclatura_do_pdf() -> None:
    g = _ghe([Exame(nome="Acuidade visual", admissao=True),
              Exame(nome="Ácido úrico", admissao=True)])
    (t,) = mafra.preparar_para_planilha([g])
    assert _nomes(t) == ["Acuidade visual", "Ácido úrico"]


def test_nao_altera_os_ghes_originais() -> None:
    g = _ghe([Exame(nome="Exame clínico", admissao=True)],
             [Risco(nome="Óleo mineral eSocial 01.17.001", grupo="Químico")])
    mafra.preparar_para_planilha([g])
    assert g.exames[0].nome == "Exame clínico"
    assert g.riscos[0].nome == "Óleo mineral eSocial 01.17.001"
