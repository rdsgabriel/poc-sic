import { useCallback, useEffect, useId, useRef, useState } from "react"
import { createPortal } from "react-dom"
import { InfoIcon } from "lucide-react"
import { nivelConfianca, type GheDetalhe } from "../api"
import { cn } from "../lib/utils"

type Props = {
  ghe: GheDetalhe
  mostrarRotulo?: boolean
  alinhamento?: "inicio" | "fim"
}

export function ConfidenceScore({
  ghe,
  mostrarRotulo = false,
  alinhamento = "fim",
}: Props) {
  const [aberto, setAberto] = useState(false)
  const [posicao, setPosicao] = useState({ top: 0, left: 0, acima: false })
  const ancoraRef = useRef<HTMLButtonElement>(null)
  const tooltipId = useId()
  const nivel = nivelConfianca(ghe)

  const atualizarPosicao = useCallback(() => {
    const ancora = ancoraRef.current
    if (!ancora) return
    const rect = ancora.getBoundingClientRect()
    const largura = Math.min(336, window.innerWidth - 24)
    const esquerdaDesejada = alinhamento === "fim" ? rect.right - largura : rect.left
    setPosicao({
      top: rect.bottom + 8,
      left: Math.max(12, Math.min(esquerdaDesejada, window.innerWidth - largura - 12)),
      acima: rect.bottom + 230 > window.innerHeight,
    })
  }, [alinhamento])

  useEffect(() => {
    if (!aberto) return
    atualizarPosicao()
    const fecharAoRolar = () => setAberto(false)
    window.addEventListener("resize", atualizarPosicao)
    window.addEventListener("scroll", fecharAoRolar, true)
    return () => {
      window.removeEventListener("resize", atualizarPosicao)
      window.removeEventListener("scroll", fecharAoRolar, true)
    }
  }, [aberto, atualizarPosicao])

  const fatores = ghe.fatores_confianca ?? ghe.pontos_atencao.map((descricao) => ({
    desconto: 0,
    descricao,
  }))

  return (
    <>
      <button
        ref={ancoraRef}
        type="button"
        aria-describedby={aberto ? tooltipId : undefined}
        aria-label={`Confiança da extração: ${ghe.confianca}%`}
        onMouseEnter={() => setAberto(true)}
        onMouseLeave={() => setAberto(false)}
        onFocus={() => setAberto(true)}
        onBlur={() => setAberto(false)}
        onClick={() => setAberto(true)}
        className={cn(
          "inline-flex items-center gap-1.5 whitespace-nowrap border-b border-dotted pb-0.5 text-xs font-semibold tabular-nums outline-none transition-colors focus-visible:ring-2 focus-visible:ring-ring/40",
          nivel === "alta" && "border-emerald-500 text-emerald-700",
          nivel === "media" && "border-amber-500 text-amber-700",
          nivel === "baixa" && "border-rose-500 text-rose-700"
        )}
      >
        <span
          className={cn(
            "size-1.5 rounded-full",
            nivel === "alta" && "bg-emerald-600",
            nivel === "media" && "bg-amber-600",
            nivel === "baixa" && "bg-rose-600"
          )}
        />
        {mostrarRotulo && <span className="font-medium text-slate-500">Confiança</span>}
        <span>{ghe.confianca}%</span>
        <InfoIcon className="size-3.5 opacity-65" aria-hidden="true" />
      </button>

      {aberto && createPortal(
        <div
          id={tooltipId}
          role="tooltip"
          className="fixed z-[100] w-[min(336px,calc(100vw-24px))] rounded-md border border-slate-700 bg-slate-900 px-3.5 py-3 text-left text-xs font-normal leading-5 text-slate-100 shadow-xl"
          style={{
            top: posicao.top,
            left: posicao.left,
            transform: posicao.acima ? "translateY(calc(-100% - 16px))" : undefined,
          }}
        >
          <div className="flex items-baseline justify-between gap-4">
            <strong className="text-[13px] font-semibold text-white">Como o score foi calculado</strong>
            <span className="font-semibold tabular-nums text-white">{ghe.confianca}/100</span>
          </div>
          {fatores.length > 0 ? (
            <ul className="mt-2 space-y-1.5 border-t border-slate-700 pt-2">
              {fatores.map((fator, indice) => (
                <li key={`${fator.descricao}-${indice}`} className="grid grid-cols-[32px_1fr] gap-2">
                  <span className="font-semibold tabular-nums text-amber-300">
                    {fator.desconto ? `−${fator.desconto}` : "−"}
                  </span>
                  <span className="text-slate-200">{fator.descricao}</span>
                </li>
              ))}
            </ul>
          ) : (
            <p className="mt-2 border-t border-slate-700 pt-2 text-slate-200">
              Nenhum sinal automático reduziu o score deste registro.
            </p>
          )}
          <p className="mt-2 border-t border-slate-700 pt-2 text-[11px] leading-4 text-slate-400">
            Divergências entre leitores, campos ausentes, avisos do parser e nomes ou perfis suspeitos reduzem a confiança. O indicador orienta a revisão; não substitui a conferência humana.
          </p>
        </div>,
        document.body
      )}
    </>
  )
}
