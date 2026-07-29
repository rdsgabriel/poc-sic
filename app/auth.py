"""Autenticação por sessão (cookie assinado) para expor a POC na internet.

Usuários são criados manualmente (``python -m app.criar_usuario <nome>``) e
vivem em ``users.json`` na raiz do projeto OU na variável de ambiente
``USERS_JSON`` (JSON ``{"usuario": "hash bcrypt"}``) — a env tem precedência
e é o caminho recomendado no Render, que não persiste arquivos fora do disco.

O cookie é assinado com ``SESSION_SECRET`` (env). Sem a env, um segredo
efêmero é gerado e as sessões caem a cada restart — aceitável em dev, nunca
em produção. ``COOKIE_SECURE=0`` desliga o flag Secure para testar o front
via IP da rede local (http).
"""

from __future__ import annotations

import json
import logging
import os
import secrets
import time
from collections import defaultdict, deque
from pathlib import Path

import bcrypt
from fastapi import APIRouter, HTTPException, Request, Response
from itsdangerous import BadSignature, URLSafeTimedSerializer
from pydantic import BaseModel

LOGGER = logging.getLogger("uvicorn.error")

COOKIE = "poc_pcmso_sessao"
SESSAO_MAX_S = 12 * 60 * 60

USERS_FILE = Path(__file__).resolve().parent.parent / "users.json"

_SECRET = os.environ.get("SESSION_SECRET")
if not _SECRET:
    _SECRET = secrets.token_hex(32)
    LOGGER.warning(
        "SESSION_SECRET ausente: segredo efêmero em uso, sessões caem a cada restart."
    )
_serializer = URLSafeTimedSerializer(_SECRET, salt="sessao")

_COOKIE_SECURE = os.environ.get("COOKIE_SECURE", "1") != "0"


def _usuarios() -> dict[str, str]:
    env = os.environ.get("USERS_JSON")
    if env:
        return json.loads(env)
    if USERS_FILE.is_file():
        return json.loads(USERS_FILE.read_text(encoding="utf-8"))
    return {}


# rate-limit em memória (a API roda em 1 processo): 5 tentativas/min por IP
_tentativas: dict[str, deque[float]] = defaultdict(deque)


def _limitar(ip: str) -> None:
    agora = time.monotonic()
    fila = _tentativas[ip]
    while fila and agora - fila[0] > 60:
        fila.popleft()
    if len(fila) >= 5:
        raise HTTPException(429, "Muitas tentativas de login; aguarde um minuto.")
    fila.append(agora)


def usuario_logado(request: Request) -> str:
    token = request.cookies.get(COOKIE)
    if not token:
        raise HTTPException(401, "Não autenticado.")
    try:
        return _serializer.loads(token, max_age=SESSAO_MAX_S)
    except BadSignature as exc:
        raise HTTPException(401, "Sessão inválida ou expirada.") from exc


router = APIRouter(prefix="/api")


class Credenciais(BaseModel):
    usuario: str
    senha: str


@router.post("/login")
def login(cred: Credenciais, request: Request, response: Response) -> dict:
    _limitar(request.client.host if request.client else "?")
    hash_conhecido = _usuarios().get(cred.usuario)
    # sempre roda um checkpw, mesmo para usuário inexistente: o tempo de
    # resposta não denuncia quais logins existem
    alvo = hash_conhecido or bcrypt.hashpw(b"nao-existe", bcrypt.gensalt()).decode()
    valido = bcrypt.checkpw(cred.senha.encode(), alvo.encode())
    if not (hash_conhecido and valido):
        LOGGER.warning("login recusado | usuario=%r", cred.usuario)
        raise HTTPException(401, "Usuário ou senha inválidos.")
    response.set_cookie(
        COOKIE,
        _serializer.dumps(cred.usuario),
        max_age=SESSAO_MAX_S,
        httponly=True,
        secure=_COOKIE_SECURE,
        samesite="lax",
        path="/",
    )
    LOGGER.info("login ok | usuario=%s", cred.usuario)
    return {"usuario": cred.usuario}


@router.post("/logout")
def logout(response: Response) -> dict:
    response.delete_cookie(COOKIE, path="/")
    return {"ok": True}


@router.get("/me")
def me(request: Request) -> dict:
    return {"usuario": usuario_logado(request)}
