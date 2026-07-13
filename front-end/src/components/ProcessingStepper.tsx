import { useEffect, useState } from "react"
import { CheckIcon, FileScanIcon, LayersIcon, Loader2Icon, ShieldCheckIcon, TableIcon } from "lucide-react"
import { cn } from "../lib/utils"

export const ETAPAS = [
  { titulo: "Leitura do PDF", descricao: "docling extraindo texto e coordenadas", icone: FileScanIcon },
  { titulo: "Extração de GHEs", descricao: "riscos, exames e funções por GHE", icone: LayersIcon },
  { titulo: "Validação cruzada", descricao: "segundo leitor independente confere a extração", icone: ShieldCheckIcon },
  { titulo: "Planilhas PGR e PCMSO", descricao: "montagem no formato de importação", icone: TableIcon },
] as const

type Props = { etapaAtual: number; nomeArquivo: string }

function useSegundos() {
  const [s, setS] = useState(0)
  useEffect(() => {
    const t = setInterval(() => setS((v) => v + 1), 1000)
    return () => clearInterval(t)
  }, [])
  return s
}

export function ProcessingStepper({ etapaAtual, nomeArquivo }: Props) {
  const segundos = useSegundos()
  const mm = Math.floor(segundos / 60)
  const ss = String(segundos % 60).padStart(2, "0")
  return (
    <div className="max-w-2xl mx-auto animate-in fade-in duration-500 mt-48">
      <div className="rounded-xl bg-card border shadow-sm p-6">
        <div className="flex items-baseline justify-between gap-2">
          <h2 className="font-semibold mb-1">Processando documento</h2>
          <span className="text-sm tabular-nums text-muted-foreground">{mm}:{ss}</span>
        </div>
        <p className="text-sm text-muted-foreground mb-6 truncate">{nomeArquivo}</p>
        <ol className="flex flex-col gap-0">
          {ETAPAS.map((etapa, i) => {
            const concluida = i < etapaAtual
            const ativa = i === etapaAtual
            const Icone = etapa.icone
            return (
              <li key={etapa.titulo} className="flex gap-4">
                <div className="flex flex-col items-center">
                  <div
                    className={cn(
                      "flex size-9 items-center justify-center rounded-full border-2 transition-colors",
                      concluida && "bg-secondary border-secondary text-secondary-foreground",
                      ativa && "border-secondary text-secondary",
                      !concluida && !ativa && "border-border text-muted-foreground"
                    )}
                  >
                    {concluida ? (
                      <CheckIcon className="size-4" />
                    ) : ativa ? (
                      <Loader2Icon className="size-4 animate-spin" />
                    ) : (
                      <Icone className="size-4" />
                    )}
                  </div>
                  {i < ETAPAS.length - 1 && (
                    <div className={cn("w-0.5 flex-1 min-h-8", concluida ? "bg-secondary" : "bg-border")} />
                  )}
                </div>
                <div className="pb-8">
                  <p className={cn("text-sm font-medium", !concluida && !ativa && "text-muted-foreground")}>
                    {etapa.titulo}
                  </p>
                  <p className="text-xs text-muted-foreground">{etapa.descricao}</p>
                </div>
              </li>
            )
          })}
        </ol>
      </div>
    </div>
  )
}
