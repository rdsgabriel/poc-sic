import { useCallback, useEffect, useRef, useState } from "react"

type UsePdfPreviewOptions = {
  /** Permite substituir o fetch padrão (ex.: authFetch que renova sessão). */
  fetcher?: typeof fetch
  /** Callback opcional para exibir toast/alert ou registrar erro. */
  onError?: (error: unknown) => void
}

/** Carrega um PDF como blob e expõe uma URL temporária para iframe.
 *  Padrão reutilizado do ProntuAI (ver component.md na raiz do projeto).
 *
 *  As opções ficam num ref: `open`/`close` têm identidade ESTÁVEL entre
 *  renders e podem entrar em deps de useEffect sem causar loop — mesmo que o
 *  chamador passe `onError` inline. */
export function usePdfPreview(options: UsePdfPreviewOptions = {}) {
  const [url, setUrl] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  const optionsRef = useRef(options)
  optionsRef.current = options

  const close = useCallback(() => {
    setUrl((previousUrl) => {
      // Sempre libere a URL temporária para evitar vazamento de memória.
      if (previousUrl) URL.revokeObjectURL(previousUrl)
      return null
    })
  }, [])

  const open = useCallback(async (pdfEndpoint: string) => {
    setLoading(true)
    try {
      const response = await (optionsRef.current.fetcher ?? fetch)(pdfEndpoint)
      if (!response.ok) {
        throw new Error("Não foi possível carregar o documento.")
      }
      const blob = await response.blob()
      const objectUrl = URL.createObjectURL(blob)
      setUrl((previousUrl) => {
        if (previousUrl) URL.revokeObjectURL(previousUrl)
        return objectUrl
      })
    } catch (error) {
      optionsRef.current.onError?.(error)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => close, [close])

  return { url, loading, open, close }
}
