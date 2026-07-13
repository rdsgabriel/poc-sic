import { defineConfig } from "vite"
import react from "@vitejs/plugin-react"
import tailwindcss from "@tailwindcss/vite"

// Em dev, o Vite roda em :5173 e proxia a API da POC.
// Alvo padrão: o container do docker compose (porta 8890 do host).
// Se estiver rodando a API local em outra porta, sobrescreva com:
//   VITE_API_TARGET=http://localhost:8000 npm run dev
// (atenção: nesta máquina a porta 8000 é de OUTRO projeto, o bot-quali)
const alvo = process.env.VITE_API_TARGET ?? "http://localhost:8890"

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    host: true, // expõe na rede local (equivale a --host)
    proxy: {
      "/processar": alvo,
      "/pdf": alvo,
      "/download": alvo,
    },
  },
})
