import { lazy, Suspense, useEffect, useMemo, useState } from "react"
import {
  AlertTriangleIcon,
  ChevronDownIcon,
  ChevronUpIcon,
  ExternalLinkIcon,
} from "lucide-react"
import { nivelConfianca, rotuloGhe, type Exame, type GheDetalhe } from "../api"
import { cn } from "../lib/utils"
import { Button } from "./ui/button"
import { DialogLite } from "./ui/dialog-lite"
import { ConfidenceScore } from "./ConfidenceScore"

type Props = {
  open: boolean
  jobId: string
  ghes: GheDetalhe[]
  onClose: () => void
}

const PdfSpotlight = lazy(() =>
  import("./PdfSpotlight").then((modulo) => ({ default: modulo.PdfSpotlight }))
)

function perfisDoExame(e: Exame): string[] {
  const p: string[] = []
  if (e.admissao) p.push("Admissional")
  if (e.periodico_meses) p.push(`Periódico ${e.periodico_meses} meses`)
  if (e.demissao) p.push("Demissional")
  if (e.ret_trab) p.push("Retorno")
  if (e.mud_riscos) p.push("Mudança de função")
  if (e.apos_adm || e.apos_adm_meses) p.push("Após admissão")
  return p
}

export function ConferenciaModal({ open, jobId, ghes, onClose }: Props) {
  const [selecionado, setSelecionado] = useState(0)
  const [soAtencao, setSoAtencao] = useState(false)
  const pdfUrl = jobId ? `/pdf/${encodeURIComponent(jobId)}` : null

  useEffect(() => {
    if (open) {
      setSelecionado(0)
      setSoAtencao(false)
    }
  }, [open, jobId])

  const visiveis = useMemo(
    () =>
      ghes
        .map((ghe, i) => ({ ghe, i }))
        .filter((x) => !soAtencao || x.ghe.pontos_atencao.length > 0),
    [ghes, soAtencao]
  )
  const comAtencao = ghes.filter((g) => g.pontos_atencao.length > 0).length
  const g = ghes[selecionado]
  const posicao = visiveis.findIndex((x) => x.i === selecionado)

  function irPara(delta: number) {
    const alvo = visiveis[posicao + delta]
    if (alvo) setSelecionado(alvo.i)
  }

  return (
    <DialogLite
      open={open}
      onClose={onClose}
      className="h-[95svh] max-h-[95svh] w-[98vw] max-w-[98vw] rounded-xl p-0 overflow-hidden"
    >
      <header className="flex h-14 shrink-0 items-center gap-3 border-b px-5 pr-14">
        <h2 className="text-base font-semibold tracking-tight">Conferência da extração</h2>
        <span className="text-sm text-slate-500">
          {ghes.length} registros{comAtencao ? ` · ${comAtencao} para revisar` : " · sem alertas"}
        </span>
      </header>

      <div className="grid min-h-0 flex-1 grid-cols-1 lg:grid-cols-[250px_minmax(360px,.95fr)_minmax(440px,1.15fr)]">
        <aside className="flex min-h-0 flex-col border-r bg-slate-50/70">
          <div className="flex h-11 items-center justify-between border-b px-3">
            <span className="text-[11px] font-semibold uppercase tracking-[.12em] text-slate-500">
              Registros
            </span>
            {comAtencao > 0 && (
              <button
                onClick={() => setSoAtencao((v) => !v)}
                className={cn(
                  "text-xs text-slate-500 underline-offset-4 hover:underline",
                  soAtencao && "font-medium text-slate-900"
                )}
              >
                {soAtencao ? "Mostrar todos" : `Só revisar (${comAtencao})`}
              </button>
            )}
          </div>
          <div className="min-h-0 flex-1 overflow-y-auto py-1">
            {visiveis.map(({ ghe, i }) => {
              const requerRevisao = ghe.pontos_atencao.length > 0
              return (
                <button
                  key={ghe.codigo || i}
                  onClick={() => setSelecionado(i)}
                  className={cn(
                    "group flex w-full items-center gap-2 border-l-2 px-3 py-2 text-left text-[13px] transition-colors",
                    i === selecionado
                      ? "border-primary bg-cyan-50/70 font-medium text-primary"
                      : "border-transparent text-slate-600 hover:bg-white hover:text-slate-900"
                  )}
                >
                  <span className="min-w-0 flex-1 truncate" title={rotuloGhe(ghes, i)}>
                    {rotuloGhe(ghes, i)}
                  </span>
                  {requerRevisao && (
                    <span className="shrink-0 text-[10px] font-semibold uppercase tracking-wide text-amber-700">
                      revisar
                    </span>
                  )}
                </button>
              )
            })}
          </div>
        </aside>

        <main className="flex min-h-0 flex-col border-r bg-white">
          <div className="flex min-h-14 items-center gap-3 border-b px-4">
            <div className="min-w-0 flex-1">
              <h3 className="truncate text-sm font-semibold text-slate-900">
                {g ? rotuloGhe(ghes, selecionado) : ""}
              </h3>
              {g && (
                <div className="mt-0.5 flex items-center gap-2 text-xs text-slate-500">
                  <span>
                    {g.pagina ? `Página ${g.pagina}` : "Página não identificada"}
                    {nivelConfianca(g) === "alta"
                      ? " · sem alertas automáticos"
                      : ` · ${g.pontos_atencao.length} ponto(s) para revisar`}
                  </span>
                  <span aria-hidden="true">·</span>
                  <ConfidenceScore ghe={g} mostrarRotulo alinhamento="inicio" />
                </div>
              )}
            </div>
            <div className="flex gap-1">
              <Button variant="ghost" size="icon" onClick={() => irPara(-1)}
                disabled={posicao <= 0} aria-label="Registro anterior">
                <ChevronUpIcon />
              </Button>
              <Button variant="ghost" size="icon" onClick={() => irPara(1)}
                disabled={posicao < 0 || posicao >= visiveis.length - 1} aria-label="Próximo registro">
                <ChevronDownIcon />
              </Button>
            </div>
          </div>

          <div className="min-h-0 flex-1 overflow-y-auto px-4 py-5">
            {g && (
              <div className="space-y-7">
                {g.pontos_atencao.length > 0 && (
                  <section className="rounded-r-md border-l-2 border-amber-500 bg-amber-50/60 px-3 py-3">
                    <h4 className="mb-2 text-xs font-semibold uppercase tracking-wider text-slate-600">
                      Revisar
                    </h4>
                    <ul className="space-y-1.5">
                      {g.pontos_atencao.map((p, i) => (
                        <li key={i} className="flex gap-2 text-sm leading-5 text-slate-700">
                          <AlertTriangleIcon className="mt-0.5 size-4 shrink-0 text-amber-600" />
                          {p}
                        </li>
                      ))}
                    </ul>
                  </section>
                )}

                <Secao titulo="Riscos" quantidade={g.riscos.length}>
                  {g.ausencia_riscos ? (
                    <p className="text-sm text-slate-600">Ausência de riscos declarada no documento.</p>
                  ) : (
                    <div className="divide-y border-y">
                      {g.riscos.map((r, i) => (
                        <div key={i} className="grid grid-cols-[1fr_118px] gap-3 py-2.5 text-sm">
                          <span className="leading-5 text-slate-800">{r.nome}</span>
                          <span className="pt-0.5 text-right text-[10px] font-semibold uppercase tracking-[.08em] text-slate-500">
                            {r.grupo}
                          </span>
                        </div>
                      ))}
                    </div>
                  )}
                </Secao>

                <Secao titulo="Exames" quantidade={g.exames.length}>
                  <div className="divide-y border-y">
                    {g.exames.map((e, i) => (
                      <div key={i} className="py-2.5">
                        <div className="text-sm leading-5 text-slate-800">{e.nome}</div>
                        <div className="mt-0.5 text-xs text-slate-500">
                          {perfisDoExame(e).join(" · ")}
                        </div>
                      </div>
                    ))}
                  </div>
                </Secao>

                <Secao titulo="Funções" quantidade={g.cargos.length}>
                  <ul className="divide-y border-y text-sm text-slate-800">
                    {g.cargos.map((c) => <li key={c} className="py-2.5">{c}</li>)}
                  </ul>
                </Secao>
              </div>
            )}
          </div>
        </main>

        <section className="flex min-h-0 flex-col bg-slate-100">
          <div className="flex h-14 shrink-0 items-center justify-between border-b bg-white px-4">
            <div>
              <h4 className="text-sm font-semibold text-slate-900">Documento</h4>
              <p className="text-xs text-slate-500">
                {g?.foco?.funcao
                  ? "GHE em foco · função destacada"
                  : g?.foco
                    ? "A região do GHE está em foco"
                    : "Visualização da página de origem"}
              </p>
            </div>
            {pdfUrl && (
              <Button variant="ghost" size="sm"
                onClick={() => window.open(pdfUrl, "_blank", "noopener,noreferrer")}>
                <ExternalLinkIcon /> Abrir PDF
              </Button>
            )}
          </div>
          <div className="min-h-0 flex-1">
            {pdfUrl && g ? (
              <Suspense fallback={
                <div className="grid h-full place-items-center text-sm text-slate-500">
                  Preparando visualizador…
                </div>
              }>
                <PdfSpotlight url={pdfUrl} pagina={g.foco?.pagina ?? g.pagina ?? 1} foco={g.foco} />
              </Suspense>
            ) : (
              <div className="grid h-full place-items-center text-sm text-slate-500">
                Carregando documento…
              </div>
            )}
          </div>
        </section>
      </div>
    </DialogLite>
  )
}

function Secao({
  titulo,
  quantidade,
  children,
}: {
  titulo: string
  quantidade: number
  children: React.ReactNode
}) {
  return (
    <section>
      <div className="mb-2 flex items-baseline justify-between">
        <h4 className="text-xs font-semibold uppercase tracking-[.1em] text-slate-600">{titulo}</h4>
        <span className="text-xs tabular-nums text-slate-400">{quantidade}</span>
      </div>
      {children}
    </section>
  )
}
