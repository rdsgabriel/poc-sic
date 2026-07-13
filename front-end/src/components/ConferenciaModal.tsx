import { useEffect, useMemo, useState } from "react"
import {
  AlertTriangleIcon, ChevronDownIcon, ChevronUpIcon, ExternalLinkIcon,
} from "lucide-react"
import { nivelConfianca, rotuloGhe, type Exame, type GheDetalhe } from "../api"
import { usePdfPreview } from "../hooks/use-pdf-preview"
import { Badge } from "./ui/badge"
import { Button } from "./ui/button"
import { DialogLite } from "./ui/dialog-lite"
import { cn } from "../lib/utils"

type Props = {
  open: boolean
  jobId: string
  ghes: GheDetalhe[]
  onClose: () => void
}

function varianteConfianca(g: GheDetalhe) {
  const nivel = nivelConfianca(g)
  return nivel === "alta" ? "ok" : nivel === "media" ? "pendente" : "erro"
}

const COR_GRUPO: Record<string, string> = {
  "Físico": "bg-sky-100 text-sky-700 border-sky-300",
  "Químico": "bg-yellow-100 text-yellow-700 border-yellow-300",
  "Biológico": "bg-emerald-100 text-emerald-700 border-emerald-300",
  "Ergonômicos": "bg-cyan-100 text-cyan-700 border-cyan-300",
  "Acidente": "bg-orange-100 text-orange-700 border-orange-300",
}

function perfisDoExame(e: Exame): string[] {
  const p: string[] = []
  if (e.admissao) p.push("Admissional")
  if (e.periodico_meses) p.push(`Periódico ${e.periodico_meses}m`)
  if (e.demissao) p.push("Demissional")
  if (e.ret_trab) p.push("Ret. Trabalho")
  if (e.mud_riscos) p.push("Mud. Função")
  if (e.apos_adm || e.apos_adm_meses) p.push("Após Adm.")
  return p
}

/** Conferência em split view (padrão document-details-modal-checagem do
 *  ProntuAI): rail de GHEs à esquerda, dados no centro, PDF à direita. */
export function ConferenciaModal({ open, jobId, ghes, onClose }: Props) {
  const [selecionado, setSelecionado] = useState(0)
  const [soAtencao, setSoAtencao] = useState(false)
  const [erroPdf, setErroPdf] = useState<string | null>(null)

  const preview = usePdfPreview({
    onError: () =>
      setErroPdf(
        "O documento deste processamento não está mais disponível (sessão antiga). " +
        "Processe o PDF novamente para conferir."
      ),
  })
  const { open: abrirPdf, close: fecharPdf } = preview

  useEffect(() => {
    if (open) {
      setErroPdf(null)
      setSelecionado(0)
      setSoAtencao(false)
      abrirPdf(`/pdf/${jobId}`)
    } else {
      fecharPdf()
    }
  }, [open, jobId, abrirPdf, fecharPdf])

  const visiveis = useMemo(
    () =>
      ghes
        .map((ghe, i) => ({ ghe, i }))
        .filter((x) => !soAtencao || x.ghe.confianca < 100),
    [ghes, soAtencao]
  )
  const comAtencao = ghes.filter((g) => g.confianca < 100).length
  const g = ghes[selecionado]

  const posicao = visiveis.findIndex((x) => x.i === selecionado)
  const irPara = (delta: number) => {
    const alvo = visiveis[posicao + delta]
    if (alvo) setSelecionado(alvo.i)
  }

  const previewSrc = preview.url
    ? `${preview.url}#page=${g?.pagina ?? 1}&toolbar=0&navpanes=0&scrollbar=0`
    : ""

  return (
    <DialogLite
      open={open}
      onClose={onClose}
      className="w-[96vw] h-[94svh] max-w-[96vw] max-h-[94svh]"
    >
      <div className="pr-10 mb-3 flex items-baseline gap-3 flex-wrap">
        <h2 className="text-xl font-semibold leading-none">Conferência da extração</h2>
        <p className="text-sm text-muted-foreground">
          {ghes.length} GHEs · {comAtencao > 0
            ? `${comAtencao} com pontos de atenção`
            : "nenhum ponto de atenção"}
        </p>
      </div>

      <div className="flex-1 min-h-0 grid grid-cols-1 lg:grid-cols-[230px_minmax(0,1.1fr)_minmax(0,1fr)] gap-4">
        {/* rail de GHEs */}
        <div className="flex flex-col min-h-0 rounded-lg border bg-muted/20">
          <div className="flex items-center justify-between px-3 py-2 border-b">
            <span className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
              GHEs
            </span>
            {comAtencao > 0 && (
              <button
                onClick={() => setSoAtencao((v) => !v)}
                className={cn(
                  "text-xs rounded-full px-2 py-0.5 border cursor-pointer transition-colors",
                  soAtencao
                    ? "bg-amber-100 text-amber-800 border-amber-300"
                    : "text-muted-foreground hover:bg-accent/10"
                )}
              >
                ⚠ com atenção ({comAtencao})
              </button>
            )}
          </div>
          <div className="flex-1 min-h-0 overflow-y-auto p-1.5">
            {visiveis.map(({ ghe, i }) => (
              <button
                key={i}
                onClick={() => setSelecionado(i)}
                className={cn(
                  "w-full text-left rounded-md px-2.5 py-2 text-sm flex items-center gap-2 cursor-pointer transition-colors",
                  i === selecionado
                    ? "bg-secondary text-secondary-foreground"
                    : "hover:bg-accent/10"
                )}
              >
                <span
                  className={cn(
                    "size-2 rounded-full shrink-0",
                    nivelConfianca(ghe) === "alta"
                      ? "bg-emerald-500"
                      : nivelConfianca(ghe) === "media"
                        ? "bg-amber-500"
                        : "bg-red-500"
                  )}
                />
                <span className="truncate flex-1" title={rotuloGhe(ghes, i)}>
                  {rotuloGhe(ghes, i)}
                </span>
                {ghe.confianca < 100 && (
                  <AlertTriangleIcon
                    className={cn(
                      "size-3.5 shrink-0",
                      i === selecionado ? "text-secondary-foreground" : "text-amber-500"
                    )}
                  />
                )}
              </button>
            ))}
          </div>
        </div>

        {/* dados extraídos */}
        <div className="flex flex-col min-h-0">
          <div className="flex items-center gap-2 mb-2">
            <div className="flex items-center gap-2 flex-wrap flex-1 min-w-0">
              <h3 className="font-semibold truncate">
                {g ? rotuloGhe(ghes, selecionado) : ""}
              </h3>
              {g?.pagina && <Badge variant="secondary">pág. {g.pagina}</Badge>}
              {g && (
                <Badge variant={varianteConfianca(g)}>
                  confiança {g.confianca}%
                </Badge>
              )}
            </div>
            <Button variant="outline" size="icon" onClick={() => irPara(-1)}
              disabled={posicao <= 0} aria-label="GHE anterior">
              <ChevronUpIcon />
            </Button>
            <Button variant="outline" size="icon" onClick={() => irPara(1)}
              disabled={posicao < 0 || posicao >= visiveis.length - 1} aria-label="Próximo GHE">
              <ChevronDownIcon />
            </Button>
          </div>

          <div className="flex-1 min-h-0 overflow-y-auto pr-2 space-y-5">
            {g && (
              <>
                {g.pontos_atencao.length > 0 && (
                  <section>
                    <h4 className="font-semibold mb-2 text-sm">
                      Pontos de atenção ({g.pontos_atencao.length})
                    </h4>
                    <div className="space-y-1.5">
                      {g.pontos_atencao.map((p, i) => (
                        <div key={i} className="flex items-start gap-2 rounded border bg-card px-3 py-2">
                          <AlertTriangleIcon className="size-4 shrink-0 text-amber-500 mt-0.5" />
                          <span className="text-sm text-muted-foreground">{p}</span>
                        </div>
                      ))}
                    </div>
                  </section>
                )}

                <section>
                  <h4 className="font-semibold mb-2 text-sm">Riscos ({g.riscos.length})</h4>
                  {g.ausencia_riscos ? (
                    <Badge variant="secondary">Ausência de Riscos (declarado no documento)</Badge>
                  ) : (
                    <div className="space-y-1.5">
                      {g.riscos.map((r, i) => (
                        <div key={i} className="flex items-center justify-between gap-2 rounded border bg-card px-3 py-2">
                          <span className="text-sm">{r.nome}</span>
                          <Badge className={COR_GRUPO[r.grupo] ?? ""}>{r.grupo}</Badge>
                        </div>
                      ))}
                    </div>
                  )}
                </section>

                <section>
                  <h4 className="font-semibold mb-2 text-sm">Exames ({g.exames.length})</h4>
                  <div className="space-y-1.5">
                    {g.exames.map((e, i) => (
                      <div key={i} className="flex items-center justify-between gap-2 rounded border bg-card px-3 py-2 flex-wrap">
                        <span className="text-sm">{e.nome}</span>
                        <span className="flex gap-1 flex-wrap">
                          {perfisDoExame(e).map((p) => (
                            <Badge key={p} variant="secondary" className="text-[11px]">{p}</Badge>
                          ))}
                        </span>
                      </div>
                    ))}
                  </div>
                </section>

                <section className="pb-4">
                  <h4 className="font-semibold mb-2 text-sm">Funções ({g.cargos.length})</h4>
                  <div className="grid grid-cols-1 xl:grid-cols-2 gap-1.5">
                    {g.cargos.map((c) => (
                      <div key={c} className="rounded border bg-card px-3 py-2 text-sm">{c}</div>
                    ))}
                  </div>
                </section>
              </>
            )}
          </div>
        </div>

        {/* PDF */}
        <div className="flex flex-col gap-2 min-h-0">
          <div className="flex items-center justify-between">
            <h4 className="font-semibold text-sm">Documento</h4>
            {preview.url && (
              <Button variant="ghost" size="sm"
                onClick={() => window.open(preview.url!, "_blank", "noopener,noreferrer")}>
                <ExternalLinkIcon /> Abrir em nova aba
              </Button>
            )}
          </div>
          <div className="flex-1 min-h-0 rounded-lg border bg-muted/20 overflow-hidden">
            {erroPdf ? (
              <div className="flex h-full items-center justify-center p-6 text-center text-sm text-destructive">
                {erroPdf}
              </div>
            ) : preview.url ? (
              <iframe key={previewSrc} title="PCMSO" src={previewSrc} className="h-full w-full" />
            ) : (
              <div className="flex h-full items-center justify-center text-sm text-muted-foreground">
                Carregando documento…
              </div>
            )}
          </div>
        </div>
      </div>
    </DialogLite>
  )
}
