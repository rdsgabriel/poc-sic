export type Risco = { nome: string; grupo: string }

export type FocoDocumento = {
  pagina: number
  top: number
  bottom: number
  funcao?: {
    pagina: number
    top: number
    bottom: number
    left: number
    right: number
  }
}

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
  codigo: string
  setor: string
  pagina: number | null
  foco: FocoDocumento | null
  cargos: string[]
  riscos: Risco[]
  exames: Exame[]
  ausencia_riscos: boolean
  avisos: string[]
  confianca: number
  fatores_confianca?: Array<{ desconto: number; descricao: string }>
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

/** Sessão ausente/expirada: o App volta para a tela de login ao capturar. */
export class SessaoExpirada extends Error {
  constructor() {
    super("Sessão expirada — faça login novamente.")
  }
}

async function lerJson(resp: Response): Promise<unknown> {
  if (resp.status === 401) throw new SessaoExpirada()
  try {
    return await resp.json()
  } catch {
    // corpo vazio/não-JSON: a requisição não chegou na API da POC
    // (proxy apontando para o serviço errado, API fora do ar, etc.)
    throw new Error(
      `resposta inválida do servidor (HTTP ${resp.status}). ` +
      "Verifique se a API da POC está no ar e se o proxy aponta para ela " +
      "(padrão: container na porta 8890)."
    )
  }
}

export async function login(usuario: string, senha: string): Promise<void> {
  const resp = await fetch("/api/login", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ usuario, senha }),
  })
  if (!resp.ok) {
    const dados = (await resp.json().catch(() => null)) as { detail?: string } | null
    throw new Error(dados?.detail ?? `falha no login (HTTP ${resp.status})`)
  }
}

export async function usuarioAtual(): Promise<string | null> {
  const resp = await fetch("/api/me").catch(() => null)
  if (!resp?.ok) return null
  return ((await resp.json()) as { usuario: string }).usuario
}

export async function logout(): Promise<void> {
  await fetch("/api/logout", { method: "POST" }).catch(() => undefined)
}

type StatusJob =
  | { status: "na_fila" | "processando" }
  | { status: "concluido"; resposta: Resposta }
  | { status: "erro"; detail: string }

const POLL_MS = 3000

export async function processarPdf(arquivo: File): Promise<Resposta> {
  const form = new FormData()
  form.append("pdf", arquivo)
  const resp = await fetch("/api/processar", { method: "POST", body: form })
  const inicio = (await lerJson(resp)) as { job_id?: string; detail?: string }
  if (!resp.ok || !inicio.job_id) {
    throw new Error(inicio.detail ?? "falha no processamento")
  }

  // o processamento roda em fila no servidor; acompanha até concluir
  for (;;) {
    await new Promise((r) => setTimeout(r, POLL_MS))
    const respStatus = await fetch(`/api/status/${encodeURIComponent(inicio.job_id)}`)
    const status = (await lerJson(respStatus)) as StatusJob & { detail?: string }
    if (!respStatus.ok) throw new Error(status.detail ?? "falha ao consultar o job")
    if (status.status === "concluido") return status.resposta
    if (status.status === "erro") throw new Error(status.detail)
  }
}
