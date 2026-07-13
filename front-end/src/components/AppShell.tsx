import type { ReactNode } from "react"
import { FileSearchIcon, HistoryIcon } from "lucide-react"
import { cn } from "../lib/utils"
import marca from "../assets/marca-principal.png"

/** Shell no padrão ProntuAI: sidebar escura fixa (logo, MENU PRINCIPAL,
 *  item ativo teal) + header h-16 + conteúdo claro com canto arredondado. */
export function AppShell({ titulo, children }: { titulo: string; children: ReactNode }) {
  return (
    <div className="flex min-h-svh bg-sidebar">
      {/* sidebar */}
      <aside className="hidden md:flex w-64 shrink-0 flex-col bg-sidebar text-sidebar-foreground">
        <div className="flex h-16 items-center px-5 ml-1 mt-5 mb-5">
          <img src={marca} alt="BR MED" className="h-11 w-auto" />
        </div>
        <div className="px-5 pt-4 pb-2 text-[11px] font-medium uppercase tracking-wider opacity-60">
          Menu principal
        </div>
        <nav className="flex flex-col gap-1 px-3">
          <SidebarItem ativo icone={<FileSearchIcon className="size-4" />}>
            Extração de PCMSO
          </SidebarItem>
        </nav>
        <div className="mt-auto px-5 py-4 text-xs opacity-50">
          POC · extração determinística
        </div>
      </aside>

      {/* inset */}
      <div className="flex-1 flex flex-col min-w-0">
        <header className="flex h-16 shrink-0 items-center gap-2 px-4 md:px-6 lg:px-8 bg-sidebar text-sidebar-foreground">
          <h1 className="text-lg font-semibold">{titulo}</h1>
        </header>
        <div className="flex flex-col flex-1 bg-background md:rounded-ss-3xl transition-all duration-300">
          <div className="flex-1 min-h-0 p-4 md:p-6 lg:p-8">{children}</div>
        </div>
      </div>
    </div>
  )
}

function SidebarItem({
  children, icone, ativo, desabilitado,
}: {
  children: ReactNode
  icone: ReactNode
  ativo?: boolean
  desabilitado?: boolean
}) {
  return (
    <div
      className={cn(
        "flex h-9 items-center gap-3 rounded-md px-3 text-sm font-medium",
        ativo && "bg-sidebar-primary text-sidebar-primary-foreground shadow-sm",
        desabilitado && "opacity-40"
      )}
    >
      {icone}
      {children}
    </div>
  )
}
