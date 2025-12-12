import os
from flask import Flask
from config import Config

from routes.auth import bp as auth_bp
from routes.dashboard import bp as dashboard_bp
from routes.pessoas import bp as pessoas_bp

def create_app():
    app = Flask(__name__, static_folder="static")
    app.secret_key = Config.SECRET_KEY

    # Blueprints
    app.register_blueprint(auth_bp)            # /, /login, /logout, /registrar
    app.register_blueprint(dashboard_bp)       # /dashboard
    app.register_blueprint(pessoas_bp)         # /pessoas

    return app

if __name__ == "__main__":
    app = create_app()
    port = int(os.environ.get("PORT", 5000))
    app.run(debug=True, host="0.0.0.0", port=port)
