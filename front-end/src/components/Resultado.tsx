import { AlertTriangleIcon, DownloadIcon, FileJsonIcon, SearchCheckIcon, UploadIcon } from "lucide-react"
import { nivelConfianca, rotuloGhe, type Resposta } from "../api"
import { Badge } from "./ui/badge"
import { Button } from "./ui/button"

type Props = {
  dados: Resposta
  onConferir: () => void
  onNovo: () => void
}

export function Resultado({ dados, onConferir, onNovo }: Props) {
  const r = dados.resumo
  const comAtencao = dados.ghes_detalhe.filter((g) => g.confianca < 100).length
  const avisosDoc = r.avisos_documento ?? []

  return (
    <div className="max-w-4xl mx-auto flex flex-col gap-4 animate-in fade-in duration-500">
      {/* cards de sumário (padrão checagem ProntuAI) */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <CardSumario
          rotulo="GHEs extraídos" valor={r.total_ghes}
          classes="from-sky-50 to-sky-100 border-sky-200" texto="text-sky-700" numero="text-sky-600" bola="bg-sky-200"
        />
        <CardSumario
          rotulo="Funções" valor={r.total_funcoes}
          classes="from-emerald-50 to-emerald-100 border-emerald-200" texto="text-emerald-700" numero="text-emerald-600" bola="bg-emerald-200"
        />
        <CardSumario
          rotulo="Pontos de atenção" valor={comAtencao + avisosDoc.length}
          classes={comAtencao + avisosDoc.length ? "from-yellow-50 to-yellow-100 border-yellow-200" : "from-slate-50 to-slate-100 border-slate-200"}
          texto={comAtencao + avisosDoc.length ? "text-yellow-700" : "text-slate-500"}
          numero={comAtencao + avisosDoc.length ? "text-yellow-600" : "text-slate-400"}
          bola={comAtencao + avisosDoc.length ? "bg-yellow-200" : "bg-slate-200"}
        />
      </div>

      <div className="rounded-xl bg-card border shadow-sm p-6">
        <div className="flex items-start justify-between gap-4 flex-wrap">
          <div>
            <h2 className="font-semibold">{r.empresa}</h2>
            <p className="text-sm text-muted-foreground">
              Extração concluída e conferida por dois leitores independentes.
            </p>
          </div>
          {dados.validacao_ok ? (
            <Badge variant="ok">✓ Validação cruzada OK</Badge>
          ) : (
            <Badge variant="atencao">Divergências entre leitores</Badge>
          )}
        </div>

        <div className="flex flex-wrap gap-2 mt-5">
          {Object.entries(dados.downloads).map(([rotulo, url]) => (
            <Button key={url} variant={url.endsWith(".json") ? "outline" : "secondary"}
              onClick={() => window.open(url, "_blank")}>
              {url.endsWith(".json") ? <FileJsonIcon /> : <DownloadIcon />}
              {rotulo}
            </Button>
          ))}
          <Button onClick={onConferir}>
            <SearchCheckIcon />
            Conferir extração
          </Button>
          <Button variant="ghost" onClick={onNovo}>
            <UploadIcon />
            Novo documento
          </Button>
        </div>

        {avisosDoc.length > 0 && (
          <div className="mt-4">
            <h3 className="text-sm font-semibold mb-2">Avisos do documento ({avisosDoc.length})</h3>
            <div className="space-y-1.5">
              {avisosDoc.map((a, i) => (
                <div key={i} className="flex items-start gap-2 rounded border bg-card px-3 py-2">
                  <AlertTriangleIcon className="size-4 shrink-0 text-amber-500 mt-0.5" />
                  <span className="text-sm text-muted-foreground">{a}</span>
                </div>
              ))}
            </div>
          </div>
        )}

        {dados.divergencias.length > 0 && (
          <div className="mt-4 rounded-lg border border-orange-300 bg-orange-50 p-3 text-sm text-orange-700">
            <p className="font-medium mb-1">Divergências entre leitores:</p>
            <ul className="list-disc pl-5">
              {dados.divergencias.map((d, i) => <li key={i}>{d}</li>)}
            </ul>
          </div>
        )}
      </div>

      <div className="rounded-xl bg-card border shadow-sm p-6">
        <h3 className="font-semibold mb-3">Detalhe por GHE</h3>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b text-left text-muted-foreground">
                <th className="py-2 pr-3 font-medium">Setor</th>
                <th className="py-2 px-3 font-medium text-right">Riscos</th>
                <th className="py-2 px-3 font-medium text-right">Exames</th>
                <th className="py-2 px-3 font-medium text-right">Funções</th>
                <th className="py-2 pl-3 font-medium text-right">Confiança</th>
              </tr>
            </thead>
            <tbody>
              {r.ghes.map((g, i) => {
                const conf = dados.ghes_detalhe[i]?.confianca ?? 100
                return (
                  <tr key={i} className="border-b last:border-0">
                    <td className="py-2 pr-3">{rotuloGhe(dados.ghes_detalhe, i)}</td>
                    <td className="py-2 px-3 text-right tabular-nums">{g.riscos}</td>
                    <td className="py-2 px-3 text-right tabular-nums">{g.exames}</td>
                    <td className="py-2 px-3 text-right tabular-nums">{g.funcoes}</td>
                    <td className="py-2 pl-3 text-right">
                      <Badge variant={
                        dados.ghes_detalhe[i]
                          ? { alta: "ok", media: "pendente", baixa: "erro" }[nivelConfianca(dados.ghes_detalhe[i])] as "ok" | "pendente" | "erro"
                          : "ok"
                      }>
                        {conf}%
                      </Badge>
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}

function CardSumario({
  rotulo, valor, classes, texto, numero, bola,
}: {
  rotulo: string; valor: number; classes: string; texto: string; numero: string; bola: string
}) {
  return (
    <div className={`bg-gradient-to-br border rounded-lg p-4 shadow-sm ${classes}`}>
      <div className="flex items-center justify-between">
        <div>
          <div className={`text-xs font-medium uppercase tracking-wide ${texto}`}>{rotulo}</div>
          <div className={`text-3xl font-bold mt-1 ${numero}`}>{valor}</div>
        </div>
        <div className={`size-12 rounded-full flex items-center justify-center text-lg font-bold ${bola} ${texto}`}>
          {valor}
        </div>
      </div>
    </div>
  )
}
