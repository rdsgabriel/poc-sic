import { useEffect, type ReactNode } from "react"
import { XIcon } from "lucide-react"
import { cn } from "../../lib/utils"

type Props = {
  open: boolean
  onClose: () => void
  className?: string
  children: ReactNode
}

/** Dialog leve (sem radix): overlay + conteúdo centralizado, fecha no ESC e
 *  no clique do backdrop. Visual equivalente ao Dialog shadcn do ProntuAI. */
export function DialogLite({ open, onClose, className, children }: Props) {
  useEffect(() => {
    if (!open) return
    const escutar = (e: KeyboardEvent) => e.key === "Escape" && onClose()
    document.addEventListener("keydown", escutar)
    document.body.style.overflow = "hidden"
    return () => {
      document.removeEventListener("keydown", escutar)
      document.body.style.overflow = ""
    }
  }, [open, onClose])

  if (!open) return null
  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-2"
      onMouseDown={(e) => e.target === e.currentTarget && onClose()}
    >
      <div
        className={cn(
          "relative bg-card text-card-foreground rounded-2xl border shadow-lg p-4 flex flex-col",
          className
        )}
      >
        <button
          onClick={onClose}
          className="absolute top-4 right-4 rounded-sm opacity-60 hover:opacity-100 cursor-pointer"
          aria-label="Fechar"
        >
          <XIcon className="size-5" />
        </button>
        {children}
      </div>
    </div>
  )
}
