import os
from flask import Flask
from config import Config

from routes.auth import bp as auth_bp
from routes.dashboard import bp as dashboard_bp
from routes.pessoas import bp as pessoas_bp

def create_app():
    app = Flask(__name__, static_folder="static")
    app.secret_key = Config.SECRET_KEY

    app.register_blueprint(auth_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(pessoas_bp)

    return app

# ✅ ISSO AQUI RESOLVE NO RENDER (gunicorn app:app)
app = create_app()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(debug=True, host="0.0.0.0", port=port)
