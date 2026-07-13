import { useRef, useState } from "react"
import { FileTextIcon, FileUpIcon, XIcon } from "lucide-react"
import { Button } from "./ui/button"
import { cn } from "../lib/utils"

type Props = {
  arquivo: File | null
  onSelecionar: (f: File | null) => void
  onProcessar: () => void
}

function formatBytes(n: number) {
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(0)} KB`
  return `${(n / 1024 / 1024).toFixed(1)} MB`
}

/** Dropzone no padrão do document-upload-zone.tsx do ProntuAI. */
export function UploadZone({ arquivo, onSelecionar, onProcessar }: Props) {
  const input = useRef<HTMLInputElement>(null)
  const [arrastando, setArrastando] = useState(false)
  const [erro, setErro] = useState<string | null>(null)

  function receber(f: File | undefined) {
    if (!f) return
    if (!f.name.toLowerCase().endsWith(".pdf")) {
      setErro("Apenas arquivos PDF são aceitos.")
      return
    }
    setErro(null)
    onSelecionar(f)
  }

  return (
    <div className="flex flex-col gap-4 max-w-4xl mx-auto mt-56">
      <div
        role="button"
        data-dragging={arrastando || undefined}
        onClick={() => input.current?.click()}
        onDragOver={(e) => { e.preventDefault(); setArrastando(true) }}
        onDragLeave={() => setArrastando(false)}
        onDrop={(e) => {
          e.preventDefault()
          setArrastando(false)
          receber(e.dataTransfer.files[0])
        }}
        className={cn(
          "flex min-h-64 flex-col items-center justify-center rounded-xl border-2 border-dashed border-primary p-8 cursor-pointer",
          "transition-colors hover:bg-accent/10 data-[dragging=true]:bg-accent/20 data-[dragging=true]:border-secondary"
        )}
      >
        <input
          ref={input}
          type="file"
          accept="application/pdf"
          className="sr-only"
          onChange={(e) => receber(e.target.files?.[0])}
        />
        <div className="mb-4 flex size-16 items-center justify-center rounded-full border-2 bg-card shadow-sm">
          <FileUpIcon className="size-8 opacity-60" />
        </div>
        <p className="mb-2 text-lg font-semibold">Enviar PCMSO</p>
        <p className="mb-3 text-sm text-muted-foreground">
          Arraste e solte ou clique para selecionar
        </p>
        <div className="flex flex-wrap justify-center gap-2 text-xs text-muted-foreground/70">
          <span>PDF do PCMSO</span>
          <span>•</span>
          <span>1 arquivo por vez</span>
        </div>
      </div>

      {erro && (
        <div className="rounded-lg border border-destructive/50 bg-destructive/10 px-4 py-2 text-sm text-destructive">
          {erro}
        </div>
      )}

      {arquivo && (
        <div className="flex items-center justify-between gap-3 rounded-lg border bg-card p-3">
          <div className="flex items-center gap-3 min-w-0">
            <FileTextIcon className="size-5 shrink-0 opacity-60" />
            <div className="min-w-0">
              <p className="truncate text-sm font-medium">{arquivo.name}</p>
              <p className="text-xs text-muted-foreground">{formatBytes(arquivo.size)}</p>
            </div>
          </div>
          <Button variant="ghost" size="icon" onClick={() => onSelecionar(null)} aria-label="Remover">
            <XIcon />
          </Button>
        </div>
      )}

      <Button size="lg" className="w-full" disabled={!arquivo} onClick={onProcessar}>
        Processar documento
      </Button>
    </div>
  )
}
