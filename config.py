import os
import json
from pathlib import Path

CONFIG_PATH = Path("mysql_config.json")

class Config:
    # Flask
    SECRET_KEY = os.environ.get("SECRET_KEY", "mude-esta-chave-para-uma-string-bem-grande-e-secreta")

    # MySQL (Render via env; local via mysql_config.json)
    DB_HOST = os.getenv("DB_HOST")
    DB_PORT = int(os.getenv("DB_PORT", "3306"))
    DB_USER = os.getenv("DB_USER")
    DB_PASSWORD = os.getenv("DB_PASSWORD")
    DB_NAME = os.getenv("DB_NAME")

    # Gemini (MVP: key fixa permitida, mas ainda aceita env)
    GEMINI_API_KEY = os.getenv(
        "GEMINI_API_KEY",
        "AIzaSyBzGnwcfhIQT_ix-uD756HuTkEj58FmXKc",
    )
    GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

    # Uploads
    ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif"}

    @staticmethod
    def load_mysql_config() -> dict:
        # Em produção: variáveis de ambiente
        if Config.DB_HOST:
            return {
                "host": Config.DB_HOST,
                "port": Config.DB_PORT,
                "user": Config.DB_USER,
                "password": Config.DB_PASSWORD,
                "database": Config.DB_NAME,
            }

        # Desenvolvimento local: mysql_config.json
        if not CONFIG_PATH.exists():
            raise FileNotFoundError(
                f"Arquivo de configuração {CONFIG_PATH} não encontrado. "
                "Defina DB_HOST/DB_USER/DB_PASSWORD/DB_NAME ou gere o mysql_config.json."
            )

        return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
