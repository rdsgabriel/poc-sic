# Pendências — decisões de negócio em aberto

Perguntas que o pipeline resolve hoje com uma interpretação padrão sinalizada
(avisos `INFO:` na conferência). Cada resposta é ajuste de poucas linhas no
extrator correspondente. Atualizar este arquivo quando a resposta vier.

## Layout Occupare (SK/Itajui — `app/extractors/occupare.py`)

1. **Periodicidade "Todas as Vezes"** (16 exames no PDF Itajui)
   - Interpretação atual: **12 meses** (ciclo padrão anual do documento).
   - Pergunta: "Todas as Vezes" deve virar 12 meses no Perfil Periódico, ou
     outro valor/tratamento?

2. **Periodicidade "Uma única Vez" com checkbox Periódico marcado**
   (14 exames no PDF Itajui — contradição interna do documento)
   - Interpretação atual: exame **fica fora do Perfil Periódico** (mantém os
     demais perfis marcados).
   - Pergunta: confirmar exclusão do periódico, ou incluir com alguma
     periodicidade?

## Layout VIX (Cenibra — `app/extractors/vix.py`)

3. **Formato da coluna Setor** para GHEs sem o padrão "GHE 01 - NOME"
   - Atual: código puro (`FPC_BLO_OPE_A_03`).
   - Pergunta: o sistema de importação aceita esse formato, ou espera outro
     (ex.: com o setor por extenso)?

## Layout Mafra Ambiental (SK/Taboca — `app/extractors/mafra.py`)

4. **Cargo MESTRE DE OBRAS sem GSE no documento**
   - O PDF não traz a linha "Ambientes: ... (Ambiente Principal)" para esse
     cargo (lacuna do próprio documento).
   - Interpretação atual: coluna Setor recebe o **nome do cargo**, com aviso.
   - Pergunta: qual setor usar? (corrigir na origem do documento, ou definir
     um GSE manualmente?)

## Todos os layouts novos

5. **Spot-check humano dos goldens** (Cenibra, SK/Itajui e SK/Taboca)
   - Os golden tests protegem contra regressão, mas o conteúdo ainda não foi
     validado por humano (2–3 GHEs/funções contra o PDF, como descrito no
     GUIA_MELHORIAS.md). Feito o spot-check, marcar aqui.

## Resolvidas (histórico)

- ~~Valor das colunas NR na PGR~~ → **"X"** confirmado pelo negócio (jul/2026).
- ~~Mudança de função / Retorno ao Trabalho no layout VIX~~ → acordado com o
  cliente: Mudança repete o Admissional; Retorno recebe só "Exame Clínico".
