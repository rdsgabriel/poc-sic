export type Risco = { nome: string; grupo: string }

export type Exame = {
  nome: string
  admissao: boolean
  apos_adm_meses: number | null
  apos_adm: boolean
  periodico_meses: number | null
  ret_trab: boolean
  mud_riscos: boolean
  demissao: boolean
}

export type GheDetalhe = {
  setor: string
  pagina: number | null
  cargos: string[]
  riscos: Risco[]
  exames: Exame[]
  ausencia_riscos: boolean
  avisos: string[]
  confianca: number
  pontos_atencao: string[]
}

export type GheResumo = {
  setor: string
  riscos: number
  exames: number
  funcoes: number
}

export type Resposta = {
  job_id: string
  resumo: {
    empresa: string
    total_ghes: number
    total_funcoes: number
    ghes: GheResumo[]
    avisos: string[]
    avisos_documento?: string[]
  }
  validacao_ok: boolean
  divergencias: string[]
  downloads: Record<string, string>
  ghes_detalhe: GheDetalhe[]
}

/** Nível visual de confiança: um GHE com QUALQUER ponto de atenção nunca é
 *  "alta" (verde), mesmo com score alto — verde significa "nada a conferir". */
export function nivelConfianca(g: GheDetalhe): "alta" | "media" | "baixa" {
  if (g.confianca < 60) return "baixa"
  if (g.confianca < 90 || g.pontos_atencao.length > 0) return "media"
  return "alta"
}

/** Rótulo do GHE para listas: quando o mesmo setor aparece em vários GHEs
 *  (layouts com 1 GHE por função), acrescenta a função para desambiguar. */
export function rotuloGhe(ghes: GheDetalhe[], i: number): string {
  const g = ghes[i]
  const repetido = ghes.some((outro, j) => j !== i && outro.setor === g.setor)
  if (repetido && g.cargos.length === 1) return `${g.setor} — ${g.cargos[0]}`
  return g.setor
}

export async function processarPdf(arquivo: File): Promise<Resposta> {
  const form = new FormData()
  form.append("pdf", arquivo)
  const resp = await fetch("/processar", { method: "POST", body: form })
  let dados: unknown
  try {
    dados = await resp.json()
  } catch {
    // corpo vazio/não-JSON: a requisição não chegou na API da POC
    // (proxy apontando para o serviço errado, API fora do ar, etc.)
    throw new Error(
      `resposta inválida do servidor (HTTP ${resp.status}). ` +
      "Verifique se a API da POC está no ar e se o proxy aponta para ela " +
      "(padrão: container na porta 8890)."
    )
  }
  if (!resp.ok) {
    const detail = (dados as { detail?: string }).detail
    throw new Error(detail ?? "falha no processamento")
  }
  return dados as Resposta
}
