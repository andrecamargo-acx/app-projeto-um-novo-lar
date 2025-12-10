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
import google.generativeai as genai
import json as pyjson

# ============================================================
# ⚙️ Configuração do MySQL
# ============================================================

CONFIG_PATH = Path("mysql_config.json")


def carregar_config_mysql() -> dict:
    # Em produção (Render): variáveis de ambiente
    host = os.getenv("DB_HOST")
    if host:
        return {
            "host": host,
            "port": int(os.getenv("DB_PORT", "3306")),
            "user": os.getenv("DB_USER"),
            "password": os.getenv("DB_PASSWORD"),
            "database": os.getenv("DB_NAME"),
        }

    # Desenvolvimento local: mysql_config.json
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
# 🤖 Configuração do GEMINI
# ============================================================

GEMINI_API_KEY = os.getenv(
    "GEMINI_API_KEY",
    "AIzaSyBzGnwcfhIQT_ix-uD756HuTkEj58FmXKc",  # MVP: key fixa
)

if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)
    gemini_model = genai.GenerativeModel("gemini-2.5-flash")
else:
    gemini_model = None


def gerar_resumo_pessoa_ia(pessoa: dict) -> str:
    """
    Gera um resumo textual da situação da pessoa usando GEMINI.
    """
    if not gemini_model:
        return "IA não configurada (GEMINI_API_KEY ausente)."

    contexto = f"""
Nome: {pessoa.get('nome') or 'Não informado'}
Gênero: {pessoa.get('genero') or 'Não informado'}
Data de nascimento: {pessoa.get('data_nascimento') or 'Não informada'}
Cidade de origem: {pessoa.get('cidade_origem') or 'Não informada'}
Situação de rua desde: {pessoa.get('situacao_rua_desde') or 'Não informada'}
Resumo de saúde: {pessoa.get('saude_resumo') or 'Não informado'}
Dependências químicas: {pessoa.get('dependencias_quimicas') or 'Não informado'}
Rede de apoio: {pessoa.get('rede_apoio') or 'Não informada'}
Profissão anterior: {pessoa.get('profissao_anterior') or 'Não informado'}
Observações gerais: {pessoa.get('observacoes') or 'Sem observações'}
"""

    prompt = f"""
Você é um assistente social que escreve resumos de forma empática e objetiva.

Abaixo estão informações estruturadas sobre uma pessoa acolhida.
Gere um resumo em português, claro e humano, em até 2 parágrafos, destacando:
- contexto geral da pessoa
- pontos de atenção (saúde, documentos, dependência, rede de apoio)
- sem fazer diagnósticos médicos, apenas descrevendo a situação.

Texto para analisar:
{contexto}
"""

    resp = gemini_model.generate_content(prompt)
    return (resp.text or "").strip()


def classificar_pessoa_ia(pessoa: dict) -> dict:
    """
    Classifica prioridade e temas principais a partir dos dados da pessoa,
    retornando um dicionário com:
      - prioridade: 'alta' | 'media' | 'baixa'
      - tags: string separada por ponto e vírgula
      - proximos_passos: texto explicativo
    """
    if not gemini_model:
        return {
            "prioridade": "desconhecida",
            "tags": "",
            "proximos_passos": "IA não configurada (GEMINI_API_KEY ausente).",
        }

    contexto = f"""
Gênero: {pessoa.get('genero') or 'Não informado'}
Idade/Data de nascimento: {pessoa.get('data_nascimento') or 'Não informada'}
Cidade de origem: {pessoa.get('cidade_origem') or 'Não informada'}
Situação de rua desde: {pessoa.get('situacao_rua_desde') or 'Não informada'}
Resumo de saúde: {pessoa.get('saude_resumo') or 'Não informado'}
Dependências químicas: {pessoa.get('dependencias_quimicas') or 'Não informado'}
Possui documentos básicos: {"Sim" if pessoa.get("tem_documentos") else "Não"}
Rede de apoio: {pessoa.get('rede_apoio') or 'Não informada'}
Profissão anterior: {pessoa.get('profissao_anterior') or 'Não informado'}
Observações gerais: {pessoa.get('observacoes') or 'Sem observações'}
"""

    prompt = f"""
Você é um profissional de assistência social que analisa casos de pessoas em situação de vulnerabilidade.

Analise as informações abaixo e responda ESTRITAMENTE em JSON, sem texto fora do JSON, no seguinte formato:

{{
  "prioridade": "alta" | "media" | "baixa",
  "tags": ["tag1", "tag2", ...],
  "proximos_passos": "texto em português com sugestões de próximos passos"
}}

As tags devem ser palavras curtas em snake_case, por exemplo:
["saude_mental", "dependencia_quimica", "sem_documentos", "sem_rede_apoio"]

Informações da pessoa:
{contexto}
"""

    resp = gemini_model.generate_content(prompt)
    texto = (resp.text or "").strip()

    # Tentativa de remover possíveis delimitadores de código
    if texto.startswith("```"):
        texto = texto.strip("`")
        if "\n" in texto:
            texto = "\n".join(texto.split("\n")[1:])

    try:
        data = pyjson.loads(texto)
    except Exception:
        return {
            "prioridade": "desconhecida",
            "tags": "",
            "proximos_passos": "Não foi possível interpretar a resposta da IA.",
        }

    prioridade = data.get("prioridade", "desconhecida")
    tags_list = data.get("tags", [])
    if isinstance(tags_list, list):
        tags_str = ";".join(str(t) for t in tags_list)
    else:
        tags_str = str(tags_list)

    proximos_passos = data.get("proximos_passos", "")

    return {
        "prioridade": prioridade,
        "tags": tags_str,
        "proximos_passos": proximos_passos,
    }


# ============================================================
# 🌐 App Flask
# ============================================================

app = Flask(__name__, static_folder="static")
app.secret_key = os.environ.get(
    "SECRET_KEY",
    "mude-esta-chave-para-uma-string-bem-grande-e-secreta",
)


# ============================================================
# 👥 Funções auxiliares de usuário
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
# 🔐 Decorator de login
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
# 🎨 Layout base (logo maior, fundo branco)
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
            width: 64px;
            height: 64px;
            border-radius: 14px;
            background: #ffffff;
            display: flex;
            align-items: center;
            justify-content: center;
            overflow: hidden;
            border: 1px solid #e5e7eb;
            box-shadow: 0 4px 10px rgba(15, 23, 42, 0.15);
        }

        .brand-logo img {
            width: 90%;
            height: 90%;
            object-fit: contain;
        }

        .brand-text-title {
            font-size: 20px;
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

        .btn-danger {
            background: #fee2e2;
            color: #b91c1c;
        }

        .btn-danger:hover {
            background: #fecaca;
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
        input[type=number],
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
            color: #6b7280;
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

    # Total de pessoas ativas (status != 'inativo')
    cur.execute("""
        SELECT COUNT(*) AS total
        FROM pessoas
        WHERE status <> 'inativo' OR status IS NULL
    """)
    row_total = cur.fetchone() or {"total": 0}
    total_pessoas = row_total["total"]

    # Pessoas por status (apenas ativos)
    cur.execute("""
        SELECT COALESCE(status, 'Não informado') AS status, COUNT(*) AS total
        FROM pessoas
        WHERE status <> 'inativo' OR status IS NULL
        GROUP BY COALESCE(status, 'Não informado')
        ORDER BY total DESC
    """)
    rows_status = cur.fetchall() or []

    # Pessoas por cidade (top 5) – apenas ativos
    cur.execute("""
        SELECT COALESCE(cidade_origem, 'Não informada') AS cidade, COUNT(*) AS total
        FROM pessoas
        WHERE status <> 'inativo' OR status IS NULL
        GROUP BY COALESCE(cidade_origem, 'Não informada')
        ORDER BY total DESC
        LIMIT 5
    """)
    rows_cidade = cur.fetchall() or []

    cur.close()
    conn.close()

    status_labels = [r["status"] for r in rows_status]
    status_values = [r["total"] for r in rows_status]
    cidade_labels = [r["cidade"] for r in rows_cidade]
    cidade_values = [r["total"] for r in rows_cidade]

    import json as _json

    conteudo = f"""
    <h2>Dashboard de cadastros</h2>

    <div class="cards-row">
        <div class="card-metric">
            <div class="card-metric-label">Total de pessoas acolhidas (ativas)</div>
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
            <h3>Distribuição por status (ativos)</h3>
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

    # Só mostra quem não está inativo
    cur.execute("""
        SELECT *
        FROM pessoas
        WHERE status <> 'inativo' OR status IS NULL
        ORDER BY id DESC
    """)
    pessoas = cur.fetchall()
    cur.close()
    conn.close()

    linhas = []
    for p in pessoas:
        foto_arquivo = p.get("foto_arquivo")
        if foto_arquivo:
            foto_url = url_for("static", filename="fotos_pessoas/" + foto_arquivo)
            foto_html = f'<img src="{foto_url}" class="photo-thumb" alt="Foto">'
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

    resumo_ia = session.pop("resumo_ia", None)
    sugestao_ia = session.pop("sugestao_ia", None)

    resumo_ia_html = ""
    if resumo_ia:
        resumo_ia_html = f"""
        <div class="details-block" style="border-left: 4px solid #1c75ff;">
            <h3>Resumo com IA</h3>
            <p style="white-space: pre-line; font-size:13px;">{resumo_ia}</p>
        </div>
        """

    sugestao_ia_html = ""
    if sugestao_ia:
        sugestao_ia_html = f"""
        <div class="details-block" style="border-left: 4px solid #00b894;">
            <h3>Sugestões de próximos passos (IA)</h3>
            <p style="white-space: pre-line; font-size:13px;">{sugestao_ia}</p>
        </div>
        """

    inativar_link = url_for("inativar_pessoa", pessoa_id=pessoa_id)
    voltar_link = url_for("lista_pessoas")
    resumo_ia_link = url_for("resumo_pessoa_ia", pessoa_id=pessoa_id)
    classificar_ia_link = url_for("classificar_pessoa_ia_route", pessoa_id=pessoa_id)

    conteudo = f"""
    <h2>Detalhes da pessoa acolhida</h2>

    <div style="display:flex; gap:8px; margin-bottom:10px; flex-wrap:wrap;">
        <form method="post" action="{resumo_ia_link}">
            <button type="submit" class="btn btn-primary">Gerar resumo com IA</button>
        </form>
        <form method="post" action="{classificar_ia_link}">
            <button type="submit" class="btn btn-secondary">Classificar e sugerir próximos passos (IA)</button>
        </form>
    </div>

    {resumo_ia_html}
    {sugestao_ia_html}

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
                        <div class="details-item-label">Gênero</div>
                        <div class="details-item-value">{_fmt(pessoa.get("genero"))}</div>
                    </div>
                    <div>
                        <div class="details-item-label">Estado civil</div>
                        <div class="details-item-value">{_fmt(pessoa.get("estado_civil"))}</div>
                    </div>
                    <div>
                        <div class="details-item-label">Escolaridade</div>
                        <div class="details-item-value">{_fmt(pessoa.get("escolaridade"))}</div>
                    </div>
                    <div>
                        <div class="details-item-label">Quantidade de filhos</div>
                        <div class="details-item-value">{_fmt(pessoa.get("qtd_filhos"))}</div>
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
                    <div>
                        <div class="details-item-label">Prioridade (IA)</div>
                        <div class="details-item-value">{_fmt(pessoa.get("prioridade_ia"))}</div>
                    </div>
                    <div>
                        <div class="details-item-label">Tags (IA)</div>
                        <div class="details-item-value">{_fmt(pessoa.get("tags_ia"))}</div>
                    </div>
                </div>
            </div>

            <div class="details-block">
                <h3>Contexto familiar e trabalho</h3>
                <div class="details-item-label">Profissão anterior</div>
                <div class="details-item-value">{_fmt(pessoa.get("profissao_anterior"))}</div>
                <br>
                <div class="details-item-label">Renda mensal aproximada</div>
                <div class="details-item-value">{_fmt(pessoa.get("renda_mensal_aprox"))}</div>
                <br>
                <div class="details-item-label">Rede de apoio (família, amigos, instituições)</div>
                <div class="details-item-value">{_fmt(pessoa.get("rede_apoio"))}</div>
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

            <div style="margin-top: 10px; display:flex; gap: 8px;">
                <a href="{voltar_link}" class="btn btn-secondary">Voltar para lista</a>
                <form method="post" action="{inativar_link}" onsubmit="return confirm('Tem certeza que deseja marcar este cadastro como inativo?');">
                    <button type="submit" class="btn btn-danger">Marcar como inativo</button>
                </form>
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


# ---------- Marcar como inativo (soft delete) ----------
@app.route("/pessoas/<int:pessoa_id>/inativar", methods=["POST"])
@login_required
def inativar_pessoa(pessoa_id: int):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("UPDATE pessoas SET status = %s WHERE id = %s", ("inativo", pessoa_id))
    conn.commit()
    cur.close()
    conn.close()

    flash("Cadastro marcado como inativo.", "success")
    return redirect(url_for("lista_pessoas"))


# ---------- Gerar resumo IA ----------
@app.route("/pessoas/<int:pessoa_id>/resumo_ia", methods=["POST"])
@login_required
def resumo_pessoa_ia(pessoa_id: int):
    conn = get_connection()
    cur = conn.cursor(dictionary=True)
    cur.execute("SELECT * FROM pessoas WHERE id = %s", (pessoa_id,))
    pessoa = cur.fetchone()
    cur.close()
    conn.close()

    if not pessoa:
        flash("Pessoa não encontrada para gerar resumo.", "error")
        return redirect(url_for("lista_pessoas"))

    try:
        resumo = gerar_resumo_pessoa_ia(pessoa)
        flash("Resumo gerado com IA.", "success")
    except Exception as e:
        resumo = f"Erro ao chamar IA: {e}"
        flash("Não foi possível gerar o resumo com IA.", "error")

    session["resumo_ia"] = resumo
    return redirect(url_for("detalhes_pessoa", pessoa_id=pessoa_id))


# ---------- Classificar IA ----------
@app.route("/pessoas/<int:pessoa_id>/classificar_ia", methods=["POST"])
@login_required
def classificar_pessoa_ia_route(pessoa_id: int):
    conn = get_connection()
    cur = conn.cursor(dictionary=True)
    cur.execute("SELECT * FROM pessoas WHERE id = %s", (pessoa_id,))
    pessoa = cur.fetchone()
    cur.close()

    if not pessoa:
        conn.close()
        flash("Pessoa não encontrada para classificação IA.", "error")
        return redirect(url_for("lista_pessoas"))

    try:
        resultado = classificar_pessoa_ia(pessoa)
        prioridade = resultado.get("prioridade", "desconhecida")
        tags = resultado.get("tags", "")
        proximos_passos = resultado.get("proximos_passos", "")
    except Exception as e:
        conn.close()
        session["sugestao_ia"] = f"Erro ao chamar IA: {e}"
        flash("Não foi possível classificar com IA.", "error")
        return redirect(url_for("detalhes_pessoa", pessoa_id=pessoa_id))

    # Atualiza na tabela
    cur2 = conn.cursor()
    try:
        cur2.execute(
            "UPDATE pessoas SET prioridade_ia = %s, tags_ia = %s WHERE id = %s",
            (prioridade, tags, pessoa_id),
        )
        conn.commit()
        flash("Classificação IA atualizada no cadastro.", "success")
    except Exception as e:
        conn.rollback()
        flash(f"Erro ao salvar classificação IA no banco: {e}", "error")
    finally:
        cur2.close()
        conn.close()

    session["sugestao_ia"] = proximos_passos or "Classificação IA realizada."
    return redirect(url_for("detalhes_pessoa", pessoa_id=pessoa_id))


# ---------- Nova pessoa ----------
@app.route("/pessoas/nova", methods=["GET", "POST"])
@login_required
def nova_pessoa():
    if request.method == "POST":
        nome = request.form.get("nome", "").strip()
        apelido = request.form.get("apelido", "").strip() or None
        data_nascimento = request.form.get("data_nascimento") or None

        genero = request.form.get("genero", "").strip() or None
        estado_civil = request.form.get("estado_civil", "").strip() or None
        escolaridade = request.form.get("escolaridade", "").strip() or None
        qtd_filhos_str = request.form.get("qtd_filhos", "").strip()
        qtd_filhos = int(qtd_filhos_str) if qtd_filhos_str else None

        documento_principal = request.form.get("documento_principal", "").strip() or None
        tem_documentos = request.form.get("tem_documentos") == "on"
        telefone = request.form.get("telefone", "").strip() or None
        contato_emergencia = request.form.get("contato_emergencia", "").strip() or None
        cidade_origem = request.form.get("cidade_origem", "").strip() or None

        profissao_anterior = request.form.get("profissao_anterior", "").strip() or None
        renda_mensal_aprox = request.form.get("renda_mensal_aprox", "").strip() or None
        rede_apoio = request.form.get("rede_apoio", "").strip() or None

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
                genero,
                estado_civil,
                escolaridade,
                qtd_filhos,
                documento_principal,
                tem_documentos,
                telefone,
                contato_emergencia,
                cidade_origem,
                profissao_anterior,
                renda_mensal_aprox,
                rede_apoio,
                situacao_rua_desde,
                saude_resumo,
                dependencias_quimicas,
                observacoes,
                status,
                data_cadastro,
                foto_arquivo
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """
            tem_docs_int = 1 if tem_documentos else 0
            valores = (
                nome,
                apelido,
                data_nascimento or None,
                genero,
                estado_civil,
                escolaridade,
                qtd_filhos,
                documento_principal,
                tem_docs_int,
                telefone,
                contato_emergencia,
                cidade_origem,
                profissao_anterior,
                renda_mensal_aprox,
                rede_apoio,
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
                <label>Gênero</label>
                <input type="text" name="genero" placeholder="Masculino, feminino, não-binário, etc.">
            </div>
            <div class="field">
                <label>Estado civil</label>
                <input type="text" name="estado_civil">
            </div>
            <div class="field">
                <label>Escolaridade</label>
                <input type="text" name="escolaridade" placeholder="Fundamental, médio, superior, etc.">
            </div>
            <div class="field">
                <label>Quantidade de filhos</label>
                <input type="number" name="qtd_filhos" min="0">
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
                <label>Profissão anterior</label>
                <input type="text" name="profissao_anterior" placeholder="Última ocupação/trabalho">
            </div>
            <div class="field">
                <label>Renda mensal aproximada</label>
                <input type="text" name="renda_mensal_aprox" placeholder="Valor ou faixa">
            </div>
            <div class="field">
                <label>Rede de apoio (família, amigos, instituições)</label>
                <textarea name="rede_apoio"></textarea>
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
# ▶️ Main
# ============================================================

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(
        debug=True,
        host="0.0.0.0",
        port=port,
    )
