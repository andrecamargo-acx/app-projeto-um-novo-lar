# %% [markdown]
# # config.py
# Este módulo centraliza as configurações do projeto.
# - Lê credenciais do MySQL via **variáveis de ambiente** (produção/Render)
# - Ou usa o arquivo **mysql_config.json** (desenvolvimento local)
# - Armazena também configurações do Gemini (IA) e upload de arquivos

import os
import json
from pathlib import Path

CONFIG_PATH = Path("mysql_config.json")


class Config:
    # %% [markdown]
    # ## Flask
    # SECRET_KEY é usada para assinar cookies de sessão.
    SECRET_KEY = os.environ.get(
        "SECRET_KEY",
        "mude-esta-chave-para-uma-string-bem-grande-e-secreta",
    )

    # %% [markdown]
    # ## MySQL
    # No Render, configure no painel:
    # DB_HOST, DB_PORT, DB_USER, DB_PASSWORD, DB_NAME
    DB_HOST = os.getenv("DB_HOST")
    DB_PORT = int(os.getenv("DB_PORT", "3306"))
    DB_USER = os.getenv("DB_USER")
    DB_PASSWORD = os.getenv("DB_PASSWORD")
    DB_NAME = os.getenv("DB_NAME")

    # %% [markdown]
    # ## Gemini (IA)
    # MVP: chave fixa permitida (como você autorizou), mas ainda aceita env.
    GEMINI_API_KEY = os.getenv(
        "GEMINI_API_KEY",
        "AIzaSyBzGnwcfhIQT_ix-uD756HuTkEj58FmXKc",
    )
    GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

    # %% [markdown]
    # ## Upload de imagens
    # Tipos de imagem aceitos no upload da foto.
    ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif"}

    @staticmethod
    def load_mysql_config() -> dict:
        # %% [markdown]
        # ### load_mysql_config()
        # Retorna um dicionário com host/port/user/password/database.
        # Prioriza ENV (produção) e cai para mysql_config.json (local).
        if Config.DB_HOST:
            return {
                "host": Config.DB_HOST,
                "port": Config.DB_PORT,
                "user": Config.DB_USER,
                "password": Config.DB_PASSWORD,
                "database": Config.DB_NAME,
            }

        if not CONFIG_PATH.exists():
            raise FileNotFoundError(
                f"Arquivo de configuração {CONFIG_PATH} não encontrado. "
                "Defina DB_HOST/DB_USER/DB_PASSWORD/DB_NAME ou gere o mysql_config.json."
            )

        return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
