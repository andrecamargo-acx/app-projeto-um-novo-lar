# %% [markdown]
# # services/auth_service.py
# Funções de autenticação e cadastro de usuários.

from werkzeug.security import generate_password_hash, check_password_hash
from db import get_connection


def criar_usuario(nome: str, email: str, senha: str, perfil: str = "colaborador"):
    # %% [markdown]
    # ## criar_usuario
    # Cria um usuário com senha hasheada.
    conn = get_connection()
    cur = conn.cursor()
    senha_hash = generate_password_hash(senha)
    cur.execute(
        """
        INSERT INTO usuarios (nome, email, senha_hash, perfil, ativo)
        VALUES (%s, %s, %s, %s, 1)
        """,
        (nome, email, senha_hash, perfil),
    )
    conn.commit()
    cur.close()
    conn.close()


def buscar_usuario_por_email(email: str):
    # %% [markdown]
    # ## buscar_usuario_por_email
    # Retorna usuário ativo pelo e-mail (ou None).
    conn = get_connection()
    cur = conn.cursor(dictionary=True)
    cur.execute("SELECT * FROM usuarios WHERE email = %s AND ativo = 1", (email,))
    row = cur.fetchone()
    cur.close()
    conn.close()
    return row


def validar_senha(senha_hash: str, senha: str) -> bool:
    # %% [markdown]
    # ## validar_senha
    # Verifica a senha informada comparando com hash armazenado.
    return check_password_hash(senha_hash, senha)
