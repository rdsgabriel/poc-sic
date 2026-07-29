"""Cria ou atualiza um usuário do login: python -m app.criar_usuario <nome>

Grava o hash bcrypt em users.json (raiz do projeto, fora do git) e imprime
o JSON completo para colar na env USERS_JSON do Render.
"""

from __future__ import annotations

import getpass
import json
import sys

import bcrypt

from .auth import USERS_FILE


def main() -> None:
    if len(sys.argv) != 2:
        sys.exit("uso: python -m app.criar_usuario <nome>")
    nome = sys.argv[1]
    senha = getpass.getpass("Senha: ")
    if len(senha) < 8:
        sys.exit("Use ao menos 8 caracteres.")
    if senha != getpass.getpass("Confirme: "):
        sys.exit("Senhas não conferem.")

    usuarios = (
        json.loads(USERS_FILE.read_text(encoding="utf-8"))
        if USERS_FILE.is_file()
        else {}
    )
    usuarios[nome] = bcrypt.hashpw(senha.encode(), bcrypt.gensalt()).decode()
    USERS_FILE.write_text(
        json.dumps(usuarios, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(f"Usuário {nome!r} salvo em {USERS_FILE}")
    print("\nPara o Render, cole isto na variável de ambiente USERS_JSON:")
    print(json.dumps(usuarios, ensure_ascii=False))


if __name__ == "__main__":
    main()
