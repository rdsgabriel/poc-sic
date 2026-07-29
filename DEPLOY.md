# Deploy — Render (API) + Vercel (front)

Arquitetura: o front na Vercel fala com a API pelo rewrite `/api/*` do
`front-end/vercel.json` (mesma origem no browser → cookies de sessão simples,
sem CORS). A API no Render processa os PDFs em fila, um por vez.

## 1. Criar os usuários do login

Com o container local no ar:

```bash
docker exec -it poc_sicolos_interno-poc-pcmso-1 python -m app.criar_usuario <nome>
```

Repita por usuário. O comando imprime ao final o JSON completo
(`{"usuario": "hash bcrypt", ...}`) — copie-o: é o valor da env `USERS_JSON`
no Render. Senhas nunca são armazenadas, só hashes.

## 2. Render (API)

1. Workspace no plano **Pro** (Settings → Billing) — decisão de 2026-07:
   vários projetos no mesmo workspace + audit logs/SOC 2 (dado sensível).
2. **New → Blueprint** → conectar o repo `rdsgabriel/poc-sic`. O
   [render.yaml](render.yaml) cria o Web Service `poc-pcmso-api`
   (instância `pro`, 2 CPU/4 GB — validado por benchmark: mesma velocidade
   do ambiente local; disco de 10 GB para os jobs; `SESSION_SECRET` gerado).
3. Quando pedir `USERS_JSON`, cole o JSON do passo 1.
4. Primeiro deploy leva alguns minutos (imagem ~2,7 GB). Ao final, anote a
   URL pública (ex.: `https://poc-pcmso-api.onrender.com`).
5. Teste: `curl https://<url>/api/me` deve responder 401 (auth ativa).

## 3. Vercel (front)

1. Confira se o `destination` em [front-end/vercel.json](front-end/vercel.json)
   bate com a URL real do Render (ajustar → commit → push, se mudou).
2. **Add New → Project** → repo `poc-sic` → **Root Directory: `front-end`**
   (framework Vite é detectado; build `npm run build`, saída `dist`).
3. Deploy. A URL da Vercel é a que os usuários acessam.

## 4. Validar em produção

- Abrir a URL da Vercel → tela de login → entrar → subir um PDF conhecido.
- O processamento roda em fila (status a cada 3 s); um PDF grande leva ~2 min.
- Downloads e o PDF da conferência exigem a sessão (cookie httpOnly, 12 h).

## Operação

- **Novo usuário**: rodar o passo 1 de novo e atualizar `USERS_JSON` no
  dashboard do Render (Environment) — o serviço reinicia sozinho.
- **Jobs** (PDF do cliente + planilhas) expiram em 7 dias
  (`JOBS_RETENCAO_DIAS`).
- **PDF maior que os conhecidos estourando memória?** Subir `plan:` no
  render.yaml (pico atual: 2,3 GB no maior PDF testado).
- **Dev local**: nada mudou — `docker compose up -d` (porta 8890) e, para o
  front, `cd front-end && npm run dev`. O login local usa `users.json` na
  raiz (fora do git); recrie-o após recriar o container.
