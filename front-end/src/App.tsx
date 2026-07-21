import { useEffect, useRef, useState } from "react"
import { Toaster, toast } from "sonner"
import { processarPdf, type Resposta } from "./api"
import { AppShell } from "./components/AppShell"
import { ConferenciaModal } from "./components/ConferenciaModal"
import { ProcessingStepper, ETAPAS } from "./components/ProcessingStepper"
import { Resultado } from "./components/Resultado"
import { UploadZone } from "./components/UploadZone"

type PageState = "upload" | "processing" | "completed"

export default function App() {
  const [estado, setEstado] = useState<PageState>("upload")
  const [arquivo, setArquivo] = useState<File | null>(null)
  const [etapa, setEtapa] = useState(0)
  const [dados, setDados] = useState<Resposta | null>(null)
  const [conferindo, setConferindo] = useState(false)
  const timer = useRef<ReturnType<typeof setInterval>>(undefined)

  useEffect(() => () => clearInterval(timer.current), [])

  async function processar() {
    if (!arquivo) return
    setEstado("processing")
    setEtapa(0)
    // as etapas avançam por tempo estimado; a última só completa com a resposta
    timer.current = setInterval(
      () => setEtapa((e) => Math.min(e + 1, ETAPAS.length - 1)),
      7000
    )
    try {
      const resposta = await processarPdf(arquivo)
      setDados(resposta)
      setEstado("completed")
      toast.success(
        `${resposta.resumo.total_ghes} GHEs extraídos de ${resposta.resumo.empresa}`
      )
    } catch (e) {
      toast.error(e instanceof Error ? e.message : String(e))
      setEstado("upload")
    } finally {
      clearInterval(timer.current)
    }
  }

  function novo() {
    setArquivo(null)
    setDados(null)
    setConferindo(false)
    setEstado("upload")
  }

  return (
    <>
      <AppShell titulo="">
        {estado === "upload" && (
          <UploadZone arquivo={arquivo} onSelecionar={setArquivo} onProcessar={processar} />
        )}
        {estado === "processing" && (
          <ProcessingStepper etapaAtual={etapa} nomeArquivo={arquivo?.name ?? ""} />
        )}
        {estado === "completed" && dados && (
          <Resultado dados={dados} onConferir={() => setConferindo(true)} onNovo={novo} />
        )}
      </AppShell>
      {dados && (
        <ConferenciaModal
          open={conferindo}
          jobId={dados.job_id}
          ghes={dados.ghes_detalhe}
          onClose={() => setConferindo(false)}
        />
      )}
      <Toaster position="top-right" richColors />
    </>
  )
}
