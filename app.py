# %% [markdown]
# # app.py
# Ponto de entrada do Flask.
# - Cria a instância Flask
# - Registra os Blueprints
# - Expõe a variável global `app` para o Gunicorn (Render)

import os
from flask import Flask
from config import Config

from routes.auth import bp as auth_bp
from routes.dashboard import bp as dashboard_bp
from routes.pessoas import bp as pessoas_bp


def create_app():
    # %% [markdown]
    # ## create_app()
    # App factory: concentra a montagem da aplicação.
    app = Flask(__name__, static_folder="static", static_url_path="/static")
    app.secret_key = Config.SECRET_KEY

    # Blueprints
    app.register_blueprint(auth_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(pessoas_bp)

    return app


# ✅ Necessário para o Render/Gunicorn: "gunicorn app:app"
app = create_app()


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
