import {
  AlertTriangleIcon,
  CheckCircle2Icon,
  DownloadIcon,
  FileJsonIcon,
  SearchIcon,
  UploadIcon,
} from "lucide-react"
import { rotuloGhe, type Resposta } from "../api"
import { Button } from "./ui/button"
import { ConfidenceScore } from "./ConfidenceScore"

type Props = {
  dados: Resposta
  onConferir: () => void
  onNovo: () => void
}

export function Resultado({ dados, onConferir, onNovo }: Props) {
  const r = dados.resumo
  const comAtencao = dados.ghes_detalhe.filter((g) => g.pontos_atencao.length > 0).length
  const avisosDoc = r.avisos_documento ?? []
  const totalAtencao = comAtencao + avisosDoc.length

  return (
    <div className="mx-auto flex max-w-5xl flex-col gap-5 animate-in fade-in duration-300">
      <section className="overflow-hidden rounded-lg border bg-white">
        <div className="flex items-start justify-between gap-5 px-6 py-5">
          <div>
            <p className="mb-1 text-xs font-semibold uppercase tracking-[.12em] text-slate-500">
              Processamento concluído
            </p>
            <h2 className="text-xl font-semibold tracking-tight text-slate-900">{r.empresa}</h2>
            <p className="mt-1 text-sm text-slate-500">
              Revise os registros sinalizados antes de usar as planilhas.
            </p>
          </div>
          <div className="flex items-center gap-2 pt-1 text-sm text-slate-600">
            {dados.validacao_ok ? (
              <><CheckCircle2Icon className="size-4 text-emerald-700" /> Leitores concordam</>
            ) : (
              <><AlertTriangleIcon className="size-4 text-amber-700" /> Divergências encontradas</>
            )}
          </div>
        </div>

        <dl className="grid grid-cols-3 border-y bg-slate-50/60">
          <Numero rotulo="GHEs" valor={r.total_ghes} />
          <Numero rotulo="Funções" valor={r.total_funcoes} />
          <Numero rotulo="Para revisar" valor={totalAtencao} destaque={totalAtencao > 0} />
        </dl>

        <div className="flex flex-wrap items-center gap-2 px-6 py-4">
          <Button onClick={onConferir}>
            <SearchIcon /> Conferir extração
          </Button>
          {Object.entries(dados.downloads).map(([rotulo, url]) => (
            <Button key={url} variant="outline"
              onClick={() => window.open(url, "_blank")}>
              {url.endsWith(".json") ? <FileJsonIcon /> : <DownloadIcon />}
              {rotulo}
            </Button>
          ))}
          <Button variant="ghost" onClick={onNovo} className="ml-auto">
            <UploadIcon /> Novo documento
          </Button>
        </div>
      </section>

      {(avisosDoc.length > 0 || dados.divergencias.length > 0) && (
        <section className="rounded-lg border bg-white px-6 py-5">
          <h3 className="text-sm font-semibold text-slate-900">Ocorrências do processamento</h3>
          <div className="mt-3 divide-y border-y">
            {dados.divergencias.map((texto, i) => (
              <Ocorrencia key={`d-${i}`} texto={texto} importante />
            ))}
            {avisosDoc.map((texto, i) => <Ocorrencia key={`a-${i}`} texto={texto} />)}
          </div>
        </section>
      )}

      <section className="rounded-lg border bg-white px-6 py-5">
        <div className="mb-4 flex items-baseline justify-between">
          <div>
            <h3 className="text-sm font-semibold text-slate-900">Registros extraídos</h3>
            <p className="mt-0.5 text-xs text-slate-500">Selecione Conferir extração para comparar com o PDF.</p>
          </div>
          <span className="text-xs tabular-nums text-slate-500">{r.ghes.length} registros</span>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-y bg-slate-50/70 text-left text-[11px] uppercase tracking-[.08em] text-slate-500">
                <th className="px-3 py-2.5 font-semibold">Setor / função</th>
                <th className="px-3 py-2.5 text-right font-semibold">Riscos</th>
                <th className="px-3 py-2.5 text-right font-semibold">Exames</th>
                <th className="px-3 py-2.5 text-right font-semibold">Funções</th>
                <th className="px-3 py-2.5 text-right font-semibold">Confiança</th>
              </tr>
            </thead>
            <tbody className="divide-y">
              {r.ghes.map((g, i) => {
                const detalhe = dados.ghes_detalhe[i]
                return (
                  <tr key={dados.ghes_detalhe[i]?.codigo ?? i} className="text-slate-700 hover:bg-slate-50/70">
                    <td className="px-3 py-2.5 text-slate-800">{rotuloGhe(dados.ghes_detalhe, i)}</td>
                    <td className="px-3 py-2.5 text-right tabular-nums">{g.riscos}</td>
                    <td className="px-3 py-2.5 text-right tabular-nums">{g.exames}</td>
                    <td className="px-3 py-2.5 text-right tabular-nums">{g.funcoes}</td>
                    <td className="px-3 py-2.5 text-right text-xs">
                      {detalhe && <ConfidenceScore ghe={detalhe} />}
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  )
}

function Numero({
  rotulo,
  valor,
  destaque = false,
}: {
  rotulo: string
  valor: number
  destaque?: boolean
}) {
  return (
    <div className={`border-r px-6 py-4 last:border-r-0 ${destaque ? "bg-amber-50/70" : ""}`}>
      <dt className={`text-[11px] font-semibold uppercase tracking-[.1em] ${destaque ? "text-amber-800" : "text-slate-500"}`}>
        {rotulo}
      </dt>
      <dd className={`mt-1 text-2xl font-semibold tabular-nums tracking-tight ${destaque ? "text-amber-700" : "text-slate-900"}`}>
        {valor}
      </dd>
    </div>
  )
}

function Ocorrencia({ texto, importante = false }: { texto: string; importante?: boolean }) {
  return (
    <div className="flex gap-3 py-2.5 text-sm leading-5 text-slate-600">
      <AlertTriangleIcon className={`mt-0.5 size-4 shrink-0 ${importante ? "text-amber-700" : "text-slate-400"}`} />
      <span>{texto.replace(/^INFO:\s*/, "")}</span>
    </div>
  )
}
