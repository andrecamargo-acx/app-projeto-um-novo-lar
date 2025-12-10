import os
import json
from datetime import datetime
from pathlib import Path

from flask import (
    Flask,
    request,
    redirect,
    url_for,
    session,
    flash,
    render_template_string,
)
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from functools import wraps
import mysql.connector

# ============================================================
# ⚙️ Configuração do MySQL
# - Em produção (Render): usar variáveis de ambiente
# - Em desenvolvimento local: opcionalmente usar mysql_config.json
# ============================================================

CONFIG_PATH = Path("mysql_config.json")


def carregar_config_mysql() -> dict:
    # Prioriza variáveis de ambiente (ex.: para uso no Render)
    host = os.getenv("DB_HOST")
    if host:
        return {
            "host": host,
            "port": int(os.getenv("DB_PORT", "3306")),
            "user": os.getenv("DB_USER"),
            "password": os.getenv("DB_PASSWORD"),
            "database": os.getenv("DB_NAME"),
        }

    # Fallback: arquivo local mysql_config.json (para rodar no PC)
    if not CONFIG_PATH.exists():
        raise FileNotFoundError(
            f"Arquivo de configuração {CONFIG_PATH} não encontrado.\n"
            "Defina as variáveis de ambiente DB_HOST, DB_USER, DB_PASSWORD, DB_NAME\n"
            "ou gere o mysql_config.json com o 00_mysql_config.ipynb."
        )
    return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))


def get_connection():
    cfg = carregar_config_mysql()
    return mysql.connector.connect(
        host=cfg["host"],
        port=cfg["port"],
        user=cfg["user"],
        password=cfg["password"],
        database=cfg["database"],
    )


# ============================================================
# 📁 Upload de fotos
# ============================================================

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"
FOTOS_DIR = STATIC_DIR / "fotos_pessoas"
FOTOS_DIR.mkdir(parents=True, exist_ok=True)

ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif"}


def allowed_file(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


# ============================================================
# 🌐 App Flask
# ============================================================

app = Flask(__name__, static_folder="static")
app.secret_key = os.environ.get(
    "SECRET_KEY",
    "mude-esta-chave-para-uma-string-bem-grande-e-secreta",
)


# ============================================================
# 👥 Funções auxiliares de usuário (tabela usuarios)
# ============================================================

def criar_usuario(nome: str, email: str, senha: str, perfil: str = "colaborador"):
    conn = get_connection()
    cur = conn.cursor()

    senha_hash = generate_password_hash(senha)

    sql = """
    INSERT INTO usuarios (nome, email, senha_hash, perfil, ativo)
    VALUES (%s, %s, %s, %s, 1)
    """
    cur.execute(sql, (nome, email, senha_hash, perfil))
    conn.commit()

    cur.close()
    conn.close()


def buscar_usuario_por_email(email: str):
    conn = get_connection()
    cur = conn.cursor(dictionary=True)

    sql = "SELECT * FROM usuarios WHERE email = %s AND ativo = 1"
    cur.execute(sql, (email,))
    row = cur.fetchone()

    cur.close()
    conn.close()
    return row


# ============================================================
# 🔐 Decorator para rotas que exigem login
# ============================================================

def login_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if not session.get("usuario_id"):
            flash("Faça login para acessar esta página.", "warning")
            return redirect(url_for("login"))
        return f(*args, **kwargs)

    return wrapper


# ============================================================
# 🎨 Layout base (v2) – com logo, topbar e estilo mais profissional
# ============================================================

layout_base = """
<!doctype html>
<html lang="pt-br">
<head>
    <meta charset="utf-8">
    <title>{{ titulo or "Um novo lar" }}</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">

    <!-- Chart.js para gráficos do dashboard -->
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>

    <style>
        :root {
            --bg-gradient-start: #e6f0ff;
            --bg-gradient-end: #ffffff;
            --primary: #1c75ff;
            --primary-light: #92b9ff;
            --primary-dark: #165fcc;
            --accent: #00b894;
            --text-main: #1f2933;
            --text-muted: #6b7280;
            --border-subtle: #dde2eb;
            --danger: #e74c3c;
            --warning: #f1c40f;
            --success: #2ecc71;
        }

        * {
            box-sizing: border-box;
        }

        body {
            margin: 0;
            padding: 24px;
            font-family: system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
            background: linear-gradient(135deg, var(--bg-gradient-start), var(--bg-gradient-end));
            color: var(--text-main);
        }

        .app-shell {
            max-width: 1100px;
            margin: 0 auto;
            background: #ffffff;
            border-radius: 18px;
            padding: 20px 24px 28px;
            box-shadow:
                0 18px 35px rgba(15, 35, 95, 0.08),
                0 0 0 1px rgba(15, 23, 42, 0.04);
            border: 1px solid rgba(148, 163, 184, 0.3);
        }

        .topbar {
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 16px;
            margin-bottom: 18px;
            padding-bottom: 14px;
            border-bottom: 1px solid var(--border-subtle);
        }

        .brand {
            display: flex;
            align-items: center;
            gap: 12px;
        }

        .brand-logo {
            width: 40px;
            height: 40px;
            border-radius: 12px;
            background: radial-gradient(circle at 30% 20%, #ffffff, var(--primary));
            display: flex;
            align-items: center;
            justify-content: center;
            overflow: hidden;
        }

        .brand-logo img {
            width: 100%;
            height: 100%;
            object-fit: contain;
        }

        .brand-text-title {
            font-size: 18px;
            font-weight: 700;
            letter-spacing: 0.04em;
            text-transform: uppercase;
        }

        .brand-text-subtitle {
            font-size: 12px;
            color: var(--text-muted);
        }

        .user-info {
            font-size: 13px;
            color: var(--text-muted);
            margin-bottom: 4px;
            text-align: right;
        }

        .menu {
            display: flex;
            gap: 8px;
            flex-wrap: wrap;
            justify-content: flex-end;
        }

        .menu a {
            font-size: 13px;
            padding: 6px 12px;
            border-radius: 999px;
            border: 1px solid transparent;
            text-decoration: none;
            color: var(--text-main);
            background: #f3f4ff;
            transition: all 0.15s ease;
        }

        .menu a:hover {
            background: #e0e7ff;
            border-color: var(--primary-light);
        }

        .menu a.menu-primary {
            background: var(--primary);
            color: #ffffff;
            border-color: var(--primary-dark);
            box-shadow: 0 6px 14px rgba(37, 99, 235, 0.4);
        }

        .menu a.menu-primary:hover {
            background: var(--primary-dark);
        }

        .flash-container {
            margin-bottom: 12px;
        }

        .flash {
            padding: 10px 12px;
            margin-bottom: 8px;
            border-radius: 10px;
            font-size: 13px;
            display: flex;
            align-items: flex-start;
            gap: 8px;
            border: 1px solid transparent;
        }

        .flash-success {
            background: #ecfdf3;
            border-color: #bbf7d0;
            color: #166534;
        }

        .flash-warning {
            background: #fffbeb;
            border-color: #facc15;
            color: #92400e;
        }

        .flash-error {
            background: #fef2f2;
            border-color: #fecaca;
            color: #b91c1c;
        }

        .content-card {
            margin-top: 6px;
            padding: 16px 18px 20px;
            border-radius: 16px;
            background: #f9fafb;
            border: 1px solid #e5e7eb;
        }

        h1, h2, h3 {
            margin-top: 0;
            color: var(--text-main);
        }

        h2 {
            font-size: 20px;
            margin-bottom: 14px;
        }

        .btn {
            padding: 7px 13px;
            border-radius: 999px;
            border: none;
            cursor: pointer;
            text-decoration: none;
            font-size: 13px;
            display: inline-flex;
            align-items: center;
            gap: 6px;
            transition: all 0.15s ease;
        }

        .btn-primary {
            background: linear-gradient(135deg, var(--primary), var(--primary-dark));
            color: #ffffff;
            box-shadow: 0 8px 16px rgba(37, 99, 235, 0.4);
        }

        .btn-primary:hover {
            transform: translateY(-1px);
            box-shadow: 0 10px 22px rgba(37, 99, 235, 0.5);
        }

        .btn-secondary {
            background: #e5e7eb;
            color: #111827;
        }

        .btn-secondary:hover {
            background: #d1d5db;
        }

        .field-group {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
            gap: 12px 16px;
            margin-bottom: 12px;
        }

        .field {
            display: flex;
            flex-direction: column;
            gap: 4px;
        }

        label {
            font-weight: 600;
            font-size: 13px;
            color: var(--text-main);
        }

        input[type=text],
        input[type=password],
        input[type=date],
        textarea,
        select {
            width: 100%;
            padding: 7px 9px;
            border-radius: 9px;
            border: 1px solid #d1d5db;
            font-size: 13px;
            outline: none;
            transition: all 0.15s ease;
            background: #ffffff;
        }

        input:focus,
        textarea:focus,
        select:focus {
            border-color: var(--primary);
            box-shadow: 0 0 0 2px rgba(37, 99, 235, 0.25);
        }

        textarea {
            min-height: 70px;
            resize: vertical;
        }

        table {
            width: 100%;
            border-collapse: collapse;
            margin-top: 8px;
            font-size: 13px;
            background: #ffffff;
            border-radius: 12px;
            overflow: hidden;
            border: 1px solid #e5e7eb;
        }

        th, td {
            padding: 8px 10px;
            border-bottom: 1px solid #e5e7eb;
        }

        thead {
            background: linear-gradient(135deg, #eff6ff, #e0f2fe);
        }

        tbody tr:nth-child(even) {
            background: #f9fafb;
        }

        tbody tr:hover {
            background: #e5f1ff;
        }

        .photo-thumb {
            width: 40px;
            height: 40px;
            border-radius: 999px;
            object-fit: cover;
            border: 2px solid #e5e7eb;
        }

        .photo-thumb-placeholder {
            width: 40px;
            height: 40px;
            border-radius: 999px;
            border: 2px dashed #cbd5e1;
            display: inline-flex;
            align-items: center;
            justify-content: center;
            font-size: 9px;
            color: #9ca3af;
        }

        .details-layout {
            display: grid;
            grid-template-columns: minmax(0, 2fr) minmax(0, 1fr);
            gap: 18px;
        }

        .details-block {
            background: #ffffff;
            border-radius: 12px;
            padding: 12px 14px;
            border: 1px solid #e5e7eb;
            margin-bottom: 8px;
        }

        .details-block h3 {
            font-size: 14px;
            margin-bottom: 6px;
        }

        .details-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
            gap: 8px 16px;
        }

        .details-item-label {
            font-size: 11px;
            text-transform: uppercase;
            letter-spacing: 0.06em;
            color: var(--text-muted);
        }

        .details-item-value {
            font-size: 13px;
            font-weight: 500;
        }

        .photo-large-wrapper {
            text-align: center;
        }

        .photo-large {
            width: 160px;
            height: 160px;
            border-radius: 24px;
            object-fit: cover;
            border: 3px solid #e5e7eb;
            box-shadow:
                0 15px 30px rgba(15, 35, 95, 0.25),
                0 0 0 1px rgba(148, 163, 184, 0.4);
            margin-bottom: 8px;
        }

        .photo-large-placeholder {
            width: 160px;
            height: 160px;
            border-radius: 24px;
            border: 2px dashed #cbd5e1;
            display: inline-flex;
            align-items: center;
            justify-content: center;
            font-size: 11px;
            color: #9ca3af;
            margin-bottom: 8px;
        }

        .photo-caption {
            font-size: 11px;
            color: var(--text-muted);
        }

        .cards-row {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
            gap: 12px;
            margin-bottom: 16px;
        }

        .card-metric {
            padding: 10px 12px;
            border-radius: 14px;
            border: 1px solid #e5e7eb;
            background: #ffffff;
        }

        .card-metric-label {
            font-size: 11px;
            text-transform: uppercase;
            letter-spacing: 0.08em;
            color: var(--text-muted);
        }

        .card-metric-value {
            font-size: 20px;
            font-weight: 700;
            margin-top: 4px;
        }

        .card-metric-sub {
            font-size: 11px;
            color: var(--text-muted);
        }

        .charts-row {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
            gap: 16px;
            margin-top: 8px;
        }

        .chart-card {
            background: #ffffff;
            border-radius: 14px;
            padding: 10px 12px;
            border: 1px solid #e5e7eb;
        }

        .chart-card h3 {
            font-size: 13px;
            margin-bottom: 6px;
        }

        @media (max-width: 720px) {
            body {
                padding: 10px;
            }
            .app-shell {
                padding: 14px 14px 18px;
            }
            .topbar {
                flex-direction: column;
                align-items: flex-start;
            }
            .user-info {
                text-align: left;
            }
            .details-layout {
                grid-template-columns: 1fr;
            }
        }
    </style>
</head>
<body>
<div class="app-shell">
    <div class="topbar">
        <div class="brand">
            <div class="brand-logo">
                <img src="{{ url_for('static', filename='logo_um_novo_lar.png') }}" alt="Um novo lar">
            </div>
            <div>
                <div class="brand-text-title">UM NOVO LAR</div>
                <div class="brand-text-subtitle">Sistema de acolhimento e cadastro</div>
            </div>
        </div>
        <div>
            {% if session.get('usuario_id') %}
                <div class="user-info">
                    Olá, {{ session.get('usuario_nome') }}
                </div>
            {% endif %}
            <div class="menu">
                {% if session.get('usuario_id') %}
                    <a href="{{ url_for('dashboard') }}" class="menu-primary">Dashboard</a>
                    <a href="{{ url_for('lista_pessoas') }}">Pessoas acolhidas</a>
                    <a href="{{ url_for('nova_pessoa') }}">Novo cadastro</a>
                    <a href="{{ url_for('logout') }}">Sair</a>
                {% else %}
                    <a href="{{ url_for('login') }}" class="menu-primary">Login</a>
                    <a href="{{ url_for('registrar') }}">Criar acesso</a>
                {% endif %}
            </div>
        </div>
    </div>

    <div class="flash-container">
        {% with messages = get_flashed_messages(with_categories=True) %}
          {% if messages %}
            {% for cat, msg in messages %}
              <div class="flash flash-{{ cat }}">{{ msg }}</div>
            {% endfor %}
          {% endif %}
        {% endwith %}
    </div>

    <div class="content-card">
        {{ conteudo|safe }}
    </div>
</div>
</body>
</html>
"""


def render_page(titulo: str, conteudo_html: str):
    return render_template_string(layout_base, titulo=titulo, conteudo=conteudo_html)


# ============================================================
# 🧭 Rotas
# ============================================================

@app.route("/")
def index():
    if "usuario_id" in session:
        return redirect(url_for("dashboard"))
    return redirect(url_for("login"))


# ---------- Login ----------
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        senha = request.form.get("senha", "")

        usuario = buscar_usuario_por_email(email)
        if not usuario or not check_password_hash(usuario["senha_hash"], senha):
            flash("Usuário ou senha inválidos.", "error")
        else:
            session["usuario_id"] = usuario["id"]
            session["usuario_nome"] = usuario["nome"]
            flash("Login realizado com sucesso.", "success")
            return redirect(url_for("dashboard"))

    conteudo = """
    <h2>Login</h2>
    <form method="post">
        <div class="field">
            <label>E-mail</label>
            <input type="text" name="email" required>
        </div>
        <div class="field">
            <label>Senha</label>
            <input type="password" name="senha" required>
        </div>
        <button type="submit" class="btn btn-primary">Entrar</button>
    </form>
    """
    return render_page("Login", conteudo)


# ---------- Logout ----------
@app.route("/logout")
def logout():
    session.clear()
    flash("Você saiu do sistema.", "success")
    return redirect(url_for("login"))


# ---------- Cadastro de usuário ----------
@app.route("/registrar", methods=["GET", "POST"])
def registrar():
    if request.method == "POST":
        nome = request.form.get("nome", "").strip()
        email = request.form.get("email", "").strip().lower()
        senha = request.form.get("senha", "")
        senha2 = request.form.get("senha2", "")

        if not nome or not email or not senha:
            flash("Preencha nome, e-mail e senha.", "warning")
        elif senha != senha2:
            flash("As senhas não conferem.", "warning")
        else:
            existente = buscar_usuario_por_email(email)
            if existente:
                flash("Já existe um usuário ativo com esse e-mail.", "warning")
            else:
                criar_usuario(nome, email, senha, perfil="colaborador")
                flash("Usuário criado com sucesso. Agora você pode fazer login.", "success")
                return redirect(url_for("login"))

    conteudo = """
    <h2>Criar usuário</h2>
    <form method="post">
        <div class="field">
            <label>Nome</label>
            <input type="text" name="nome" required>
        </div>
        <div class="field">
            <label>E-mail</label>
            <input type="text" name="email" required>
        </div>
        <div class="field">
            <label>Senha</label>
            <input type="password" name="senha" required>
        </div>
        <div class="field">
            <label>Confirme a senha</label>
            <input type="password" name="senha2" required>
        </div>
        <button type="submit" class="btn btn-primary">Salvar</button>
    </form>
    """
    return render_page("Cadastro de usuário", conteudo)


# ---------- Dashboard ----------
@app.route("/dashboard")
@login_required
def dashboard():
    conn = get_connection()
    cur = conn.cursor(dictionary=True)

    # Total de pessoas
    cur.execute("SELECT COUNT(*) AS total FROM pessoas")
    row_total = cur.fetchone() or {"total": 0}
    total_pessoas = row_total["total"]

    # Pessoas por status
    cur.execute("""
        SELECT COALESCE(status, 'Não informado') AS status, COUNT(*) AS total
        FROM pessoas
        GROUP BY COALESCE(status, 'Não informado')
        ORDER BY total DESC
    """)
    rows_status = cur.fetchall() or []

    # Pessoas por cidade (top 5)
    cur.execute("""
        SELECT COALESCE(cidade_origem, 'Não informada') AS cidade, COUNT(*) AS total
        FROM pessoas
        GROUP BY COALESCE(cidade_origem, 'Não informada')
        ORDER BY total DESC
        LIMIT 5
    """)
    rows_cidade = cur.fetchall() or []

    cur.close()
    conn.close()

    import json as _json

    status_labels = [r["status"] for r in rows_status]
    status_values = [r["total"] for r in rows_status]

    cidade_labels = [r["cidade"] for r in rows_cidade]
    cidade_values = [r["total"] for r in rows_cidade]

    conteudo = f"""
    <h2>Dashboard de cadastros</h2>

    <div class="cards-row">
        <div class="card-metric">
            <div class="card-metric-label">Total de pessoas acolhidas</div>
            <div class="card-metric-value">{total_pessoas}</div>
            <div class="card-metric-sub">Registros ativos na base</div>
        </div>
        <div class="card-metric">
            <div class="card-metric-label">Situações cadastradas</div>
            <div class="card-metric-value">{len(status_labels)}</div>
            <div class="card-metric-sub">Estados diferentes de acompanhamento</div>
        </div>
        <div class="card-metric">
            <div class="card-metric-label">Cidades de origem</div>
            <div class="card-metric-value">{len(cidade_labels)}</div>
            <div class="card-metric-sub">Top 5 mais recorrentes</div>
        </div>
    </div>

    <div class="charts-row">
        <div class="chart-card">
            <h3>Distribuição por status</h3>
            <canvas id="chartStatus"></canvas>
        </div>
        <div class="chart-card">
            <h3>Pessoas por cidade (Top 5)</h3>
            <canvas id="chartCidade"></canvas>
        </div>
    </div>

    <script>
        (function() {{
            const statusLabels = {_json.dumps(status_labels, ensure_ascii=False)};
            const statusValues = {_json.dumps(status_values)};
            const cidadeLabels = {_json.dumps(cidade_labels, ensure_ascii=False)};
            const cidadeValues = {_json.dumps(cidade_values)};

            const chartStatusCtx = document.getElementById('chartStatus').getContext('2d');
            new Chart(chartStatusCtx, {{
                type: 'doughnut',
                data: {{
                    labels: statusLabels,
                    datasets: [{{
                        data: statusValues
                    }}]
                }},
                options: {{
                    plugins: {{
                        legend: {{
                            position: 'bottom'
                        }}
                    }}
                }}
            }});

            const chartCidadeCtx = document.getElementById('chartCidade').getContext('2d');
            new Chart(chartCidadeCtx, {{
                type: 'bar',
                data: {{
                    labels: cidadeLabels,
                    datasets: [{{
                        data: cidadeValues
                    }}]
                }},
                options: {{
                    plugins: {{
                        legend: {{ display: false }}
                    }},
                    scales: {{
                        y: {{
                            beginAtZero: true,
                            ticks: {{
                                precision: 0
                            }}
                        }}
                    }}
                }}
            }});
        }})();
    </script>
    """
    return render_page("Dashboard", conteudo)


# ---------- Lista de pessoas ----------
@app.route("/pessoas")
@login_required
def lista_pessoas():
    conn = get_connection()
    cur = conn.cursor(dictionary=True)

    cur.execute("SELECT * FROM pessoas ORDER BY id DESC")
    pessoas = cur.fetchall()
    cur.close()
    conn.close()

    linhas = []
    for p in pessoas:
        foto_arquivo = p.get("foto_arquivo")
        if foto_arquivo:
            foto_html = f'<img src="{url_for("static", filename="fotos_pessoas/" + foto_arquivo)}" class="photo-thumb" alt="Foto">'
        else:
            foto_html = '<div class="photo-thumb-placeholder">sem foto</div>'

        detalhes_link = url_for("detalhes_pessoa", pessoa_id=p["id"])

        linhas.append(f"""
            <tr>
                <td>{foto_html}</td>
                <td>{p['id']}</td>
                <td>{p.get('nome') or ''}</td>
                <td>{p.get('apelido') or ''}</td>
                <td>{p.get('telefone') or ''}</td>
                <td>{p.get('cidade_origem') or ''}</td>
                <td>{p.get('status') or ''}</td>
                <td><a class="btn btn-secondary" href="{detalhes_link}">Ver detalhes</a></td>
            </tr>
        """)

    rows_html = "".join(linhas)
    link_nova_pessoa = url_for("nova_pessoa")

    conteudo = f"""
    <h2>Pessoas acolhidas</h2>
    <p>
        <a class="btn btn-primary" href="{link_nova_pessoa}">Novo cadastro</a>
    </p>
    <table>
        <thead>
            <tr>
                <th>Foto</th>
                <th>ID</th>
                <th>Nome</th>
                <th>Apelido</th>
                <th>Telefone</th>
                <th>Cidade de origem</th>
                <th>Status</th>
                <th></th>
            </tr>
        </thead>
        <tbody>
            {rows_html}
        </tbody>
    </table>
    """
    return render_page("Pessoas", conteudo)


# ---------- Detalhes da pessoa ----------
@app.route("/pessoas/<int:pessoa_id>")
@login_required
def detalhes_pessoa(pessoa_id: int):
    conn = get_connection()
    cur = conn.cursor(dictionary=True)

    cur.execute("SELECT * FROM pessoas WHERE id = %s", (pessoa_id,))
    pessoa = cur.fetchone()

    cur.close()
    conn.close()

    if not pessoa:
        flash("Pessoa não encontrada.", "error")
        return redirect(url_for("lista_pessoas"))

    foto_arquivo = pessoa.get("foto_arquivo")
    if foto_arquivo:
        foto_html = f'<img src="{url_for("static", filename="fotos_pessoas/" + foto_arquivo)}" class="photo-large" alt="Foto">'
    else:
        foto_html = '<div class="photo-large-placeholder">Sem foto cadastrada</div>'

    def _fmt(value):
        return value or ""

    conteudo = f"""
    <h2>Detalhes da pessoa acolhida</h2>
    <div class="details-layout">
        <div>
            <div class="details-block">
                <h3>Informações gerais</h3>
                <div class="details-grid">
                    <div>
                        <div class="details-item-label">Nome completo</div>
                        <div class="details-item-value">{_fmt(pessoa.get("nome"))}</div>
                    </div>
                    <div>
                        <div class="details-item-label">Apelido</div>
                        <div class="details-item-value">{_fmt(pessoa.get("apelido"))}</div>
                    </div>
                    <div>
                        <div class="details-item-label">Data de nascimento</div>
                        <div class="details-item-value">{_fmt(pessoa.get("data_nascimento"))}</div>
                    </div>
                    <div>
                        <div class="details-item-label">Documento principal</div>
                        <div class="details-item-value">{_fmt(pessoa.get("documento_principal"))}</div>
                    </div>
                    <div>
                        <div class="details-item-label">Possui documentos básicos</div>
                        <div class="details-item-value">{"Sim" if pessoa.get("tem_documentos") else "Não"}</div>
                    </div>
                    <div>
                        <div class="details-item-label">Telefone</div>
                        <div class="details-item-value">{_fmt(pessoa.get("telefone"))}</div>
                    </div>
                    <div>
                        <div class="details-item-label">Contato de emergência</div>
                        <div class="details-item-value">{_fmt(pessoa.get("contato_emergencia"))}</div>
                    </div>
                    <div>
                        <div class="details-item-label">Cidade de origem</div>
                        <div class="details-item-value">{_fmt(pessoa.get("cidade_origem"))}</div>
                    </div>
                    <div>
                        <div class="details-item-label">Status</div>
                        <div class="details-item-value">{_fmt(pessoa.get("status"))}</div>
                    </div>
                    <div>
                        <div class="details-item-label">Data de cadastro</div>
                        <div class="details-item-value">{_fmt(pessoa.get("data_cadastro"))}</div>
                    </div>
                </div>
            </div>

            <div class="details-block">
                <h3>Histórico e saúde</h3>
                <div class="details-item-label">Situação de rua desde</div>
                <div class="details-item-value">{_fmt(pessoa.get("situacao_rua_desde"))}</div>
                <br>
                <div class="details-item-label">Resumo de saúde</div>
                <div class="details-item-value">{_fmt(pessoa.get("saude_resumo"))}</div>
                <br>
                <div class="details-item-label">Dependências químicas</div>
                <div class="details-item-value">{_fmt(pessoa.get("dependencias_quimicas"))}</div>
                <br>
                <div class="details-item-label">Observações gerais</div>
                <div class="details-item-value">{_fmt(pessoa.get("observacoes"))}</div>
            </div>
        </div>

        <div>
            <div class="details-block photo-large-wrapper">
                {foto_html}
                <div class="photo-caption">Foto registrada no cadastro</div>
            </div>
        </div>
    </div>
    """
    return render_page("Detalhes da pessoa", conteudo)


# ---------- Nova pessoa ----------
@app.route("/pessoas/nova", methods=["GET", "POST"])
@login_required
def nova_pessoa():
    if request.method == "POST":
        nome = request.form.get("nome", "").strip()
        apelido = request.form.get("apelido", "").strip() or None
        data_nascimento = request.form.get("data_nascimento") or None
        documento_principal = request.form.get("documento_principal", "").strip() or None
        tem_documentos = request.form.get("tem_documentos") == "on"
        telefone = request.form.get("telefone", "").strip() or None
        contato_emergencia = request.form.get("contato_emergencia", "").strip() or None
        cidade_origem = request.form.get("cidade_origem", "").strip() or None
        situacao_rua_desde = request.form.get("situacao_rua_desde", "").strip() or None
        saude_resumo = request.form.get("saude_resumo", "").strip() or None
        dependencias_quimicas = request.form.get("dependencias_quimicas", "").strip() or None
        observacoes = request.form.get("observacoes", "").strip() or None

        foto_arquivo = None
        file = request.files.get("foto")
        if file and file.filename and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            prefix = datetime.now().strftime("%Y%m%d%H%M%S")
            filename = f"{prefix}_{filename}"
            file.save(FOTOS_DIR / filename)
            foto_arquivo = filename

        if not nome:
            flash("Nome é obrigatório.", "warning")
        else:
            conn = get_connection()
            cur = conn.cursor()

            insert_sql = """
            INSERT INTO pessoas (
                nome,
                apelido,
                data_nascimento,
                documento_principal,
                tem_documentos,
                telefone,
                contato_emergencia,
                cidade_origem,
                situacao_rua_desde,
                saude_resumo,
                dependencias_quimicas,
                observacoes,
                status,
                data_cadastro,
                foto_arquivo
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """
            tem_docs_int = 1 if tem_documentos else 0
            valores = (
                nome,
                apelido,
                data_nascimento or None,
                documento_principal,
                tem_docs_int,
                telefone,
                contato_emergencia,
                cidade_origem,
                situacao_rua_desde,
                saude_resumo,
                dependencias_quimicas,
                observacoes,
                "ativo",
                datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                foto_arquivo,
            )

            cur.execute(insert_sql, valores)
            conn.commit()
            cur.close()
            conn.close()

            flash("Pessoa cadastrada com sucesso.", "success")
            return redirect(url_for("lista_pessoas"))

    link_lista = url_for("lista_pessoas")

    conteudo = f"""
    <h2>Novo cadastro de pessoa acolhida</h2>
    <form method="post" enctype="multipart/form-data">
        <div class="field-group">
            <div class="field">
                <label>Nome completo *</label>
                <input type="text" name="nome" required>
            </div>
            <div class="field">
                <label>Apelido</label>
                <input type="text" name="apelido">
            </div>
            <div class="field">
                <label>Data de nascimento</label>
                <input type="date" name="data_nascimento">
            </div>
            <div class="field">
                <label>Documento principal (RG/CPF ou outro)</label>
                <input type="text" name="documento_principal">
            </div>
        </div>

        <div class="field-group">
            <div class="field">
                <label><input type="checkbox" name="tem_documentos"> Possui documentos básicos</label>
            </div>
            <div class="field">
                <label>Telefone</label>
                <input type="text" name="telefone">
            </div>
            <div class="field">
                <label>Contato de emergência</label>
                <input type="text" name="contato_emergencia">
            </div>
            <div class="field">
                <label>Cidade de origem</label>
                <input type="text" name="cidade_origem">
            </div>
        </div>

        <div class="field-group">
            <div class="field">
                <label>Situação de rua desde quando?</label>
                <textarea name="situacao_rua_desde"></textarea>
            </div>
            <div class="field">
                <label>Resumo de saúde (doenças, medicações, etc.)</label>
                <textarea name="saude_resumo"></textarea>
            </div>
        </div>

        <div class="field-group">
            <div class="field">
                <label>Dependências químicas</label>
                <textarea name="dependencias_quimicas"></textarea>
            </div>
            <div class="field">
                <label>Observações gerais</label>
                <textarea name="observacoes"></textarea>
            </div>
        </div>

        <div class="field-group">
            <div class="field">
                <label>Foto da pessoa (opcional)</label>
                <input type="file" name="foto" accept="image/*">
            </div>
        </div>

        <div style="margin-top: 10px; display:flex; gap: 8px;">
            <button type="submit" class="btn btn-primary">Salvar cadastro</button>
            <a href="{link_lista}" class="btn btn-secondary">Voltar para lista</a>
        </div>
    </form>
    """
    return render_page("Novo cadastro", conteudo)


# ============================================================
# ▶️ Rodar app (para desenvolvimento local)
# ============================================================

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(
        debug=True,
        host="0.0.0.0",
        port=port,
    )
