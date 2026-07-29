import { useState, type FormEvent } from "react"
import { Loader2Icon } from "lucide-react"
import { login } from "../api"
import marca from "../assets/marca-principal.png"

/** Login minimalista: logo e inputs direto sobre o fundo escuro da sidebar. */
export function Login({ onEntrar }: { onEntrar: (usuario: string) => void }) {
  const [usuario, setUsuario] = useState("")
  const [senha, setSenha] = useState("")
  const [enviando, setEnviando] = useState(false)
  const [erro, setErro] = useState<string | null>(null)

  async function entrar(e: FormEvent) {
    e.preventDefault()
    setEnviando(true)
    setErro(null)
    try {
      await login(usuario.trim(), senha)
      onEntrar(usuario.trim())
    } catch (err) {
      setErro(err instanceof Error ? err.message : String(err))
    } finally {
      setEnviando(false)
    }
  }

  const campo =
    "h-11 w-full rounded-md border border-white/15 bg-white/5 px-3 text-sm " +
    "text-sidebar-foreground placeholder:text-sidebar-foreground/40 " +
    "outline-none transition-colors focus:border-sidebar-primary"

  return (
    <div className="flex min-h-svh items-center justify-center bg-sidebar p-4">
      <form onSubmit={entrar} className="w-full max-w-xs">
        <img src={marca} alt="BR MED" className="mx-auto mb-10 h-12 w-auto" />

        <div className="flex flex-col gap-3">
          <input
            className={campo}
            placeholder="Usuário"
            value={usuario}
            onChange={(e) => setUsuario(e.target.value)}
            autoComplete="username"
            autoFocus
            required
          />
          <input
            className={campo}
            type="password"
            placeholder="Senha"
            value={senha}
            onChange={(e) => setSenha(e.target.value)}
            autoComplete="current-password"
            required
          />
        </div>

        {erro && <p className="mt-4 text-center text-sm text-red-300">{erro}</p>}

        <button
          type="submit"
          disabled={enviando}
          className="mt-6 flex h-11 w-full items-center justify-center gap-2 rounded-md bg-sidebar-primary text-sm font-medium text-sidebar-primary-foreground transition-opacity hover:opacity-90 disabled:opacity-50"
        >
          {enviando && <Loader2Icon className="size-4 animate-spin" />}
          Entrar
        </button>
      </form>
    </div>
  )
}
