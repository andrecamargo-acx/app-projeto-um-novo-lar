# %% [markdown]
# # decorators.py
# Decorators reutilizáveis para rotas.
# Hoje temos: login_required

from functools import wraps
from flask import session, flash, redirect, url_for


def login_required(f):
    # %% [markdown]
    # ## login_required
    # Garante que o usuário esteja logado.
    # Se não estiver, redireciona para /login e mostra mensagem.
    @wraps(f)
    def wrapper(*args, **kwargs):
        if not session.get("usuario_id"):
            flash("Faça login para acessar esta página.", "warning")
            return redirect(url_for("auth.login"))
        return f(*args, **kwargs)

    return wrapper
