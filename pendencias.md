# Pendências — decisões de negócio em aberto

Perguntas que o pipeline resolve hoje com uma interpretação padrão sinalizada
(avisos `INFO:` na conferência). Cada resposta é ajuste de poucas linhas no
extrator correspondente. Atualizar este arquivo quando a resposta vier.

## Layout VIX (Cenibra — `app/extractors/vix.py`)

1. **Formato da coluna Setor** para GHEs sem o padrão "GHE 01 - NOME"
   - Atual: código puro (`FPC_BLO_OPE_A_03`).
   - Pergunta: o sistema de importação aceita esse formato, ou espera outro
     (ex.: com o setor por extenso)?

## Layout Mafra Ambiental (SK/Taboca — `app/extractors/mafra.py`)

2. **Cargo MESTRE DE OBRAS sem GSE no documento**
   - O PDF não traz a linha "Ambientes: ... (Ambiente Principal)" para esse
     cargo (lacuna do próprio documento).
   - Interpretação atual: coluna Setor recebe o **nome do cargo**, com aviso.
   - Pergunta: qual setor usar? (corrigir na origem do documento, ou definir
     um GSE manualmente?)

## Layout International SOS / Solstad (`app/extractors/solstad.py`)

3. **Periodicidade padrão do Perfil Periódico**
   - A grade do documento não traz meses; o texto do PCMSO cita a regra da
     NR7 (anual para expostos / bienal para os demais).
   - Interpretação atual: **12 meses** para todos (embarcação, grau de risco
     3/4 e todos os GHEs expostos), exceto RX Tórax/Espirometria = **24
     meses** (nota "***" da própria grade). Confirmar.

4. **Formato da coluna Setor**: o documento não dá NOME aos GHEs, só número.
   - Atual: `GHE 2`, `GHE 3.1`... (sem " - NOME"). O sistema aceita?

5. **Função COMISSÁRIO (GHE 8.1)**
   - Não existe na planilha de funções bilíngues (ficou só em português) nem
     na tabela de atividades críticas (manteve Eletrocardiograma; sem NRs de
     atividade). Confirmar se é lacuna do documento/planilha ou função
     desativada.

6. **Funções da tabela de atividades críticas fora da lista de GHEs**
   - SUPERVISOR DE ANCORAGEM e MOÇO DE CONVÉS têm atividades críticas mas
     não pertencem a nenhum GHE → não geram linha nas planilhas. Confirmar.

7. **CAMAREIRO OFFSHORE I**: a planilha bilíngue só tem CAMAREIRO OFFSHORE e
   CAMAREIRO OFFSHORE II. O nome em inglês foi derivado ("HOUSEKEEPER
   OFFSHORE I"). Confirmar grafia.

8. **Regra etária ECG/Teste Ergométrico** (funções SEM atividade crítica):
   "até 44 anos ECG, 45+ teste ergométrico" não é representável na planilha
   (não há dimensão idade). Atual: mantém só o ECG na grade + aviso INFO.

## Todos os layouts novos

9. **Spot-check humano dos goldens** (Cenibra, SK/Itajui, SK/Taboca e
   Solstad/NORMAND POSEIDON)
   - Os golden tests protegem contra regressão, mas o conteúdo ainda não foi
     validado por humano (2–3 GHEs/funções contra o PDF, como descrito no
     GUIA_MELHORIAS.md). O golden do Solstad merece atenção especial: a
     tabela de atividades críticas veio de OCR. Feito o spot-check, marcar
     aqui.

## Resolvidas (histórico)

- ~~Valor das colunas NR na PGR~~ → **"X"** confirmado pelo negócio (jul/2026).
- ~~Mudança de função / Retorno ao Trabalho no layout VIX~~ → acordado com o
  cliente: Mudança repete o Admissional; Retorno recebe só "Exame Clínico".
- ~~Occupare: periodicidade "Todas as Vezes"~~ → **12 meses**, confirmado
  pelo negócio (jul/2026).
- ~~Occupare: "Uma única Vez" com checkbox Periódico marcado~~ → **entra no
  Perfil Periódico com 12 meses**, confirmado pelo negócio (jul/2026).
  (Obs.: eram 9 exames "Avaliação Psicológica" no PDF Itajui, não 14 como
  anotado antes.)
- ~~Solstad: Retorno/Mudança "VER ITENS 3 e 4 NAS PAGS. 5 e 6"~~ → seguem a
  grade do **Periódico** (regra passada pelo negócio, jul/2026).
