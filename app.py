# %% [markdown]
# 
# # 🌐 03 - Aplicação Web (Flask) com Login
# 
# Esta aplicação web permite:
# 
# - Login e logout de usuários cadastrados na tabela `usuarios`
# - Cadastro de novas pessoas acolhidas (tabela `pessoas`)
# - Listagem básica das pessoas cadastradas
# 
# ## Ordem recomendada de uso
# 
# 1. `00_mysql_config.ipynb` → salva a configuração do MySQL.
# 2. `01_config_db.ipynb` → cria as tabelas `pessoas` e `usuarios`.
# 3. `02_funcoes_cadastro.ipynb` → funções de apoio para `pessoas` (opcional).
# 4. Este notebook → sobe o servidor Flask.
# 
# > Antes de rodar, instale as dependências (no terminal do ambiente Python):
# >
# > ```bash
# > pip install flask mysql-connector-python
# > ```
# 

# %%
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
from functools import wraps
import mysql.connector
from pathlib import Path
import json
from datetime import datetime



# %%
# ============================================================
# 🔧 Carrega configuração do MySQL a partir do mysql_config.json
# (gerado pelo 00_mysql_config.ipynb)


# %%
# ============================================================

CONFIG_PATH = Path("mysql_config.json")


def carregar_config_mysql() -> dict:
    if not CONFIG_PATH.exists():
        raise FileNotFoundError(
            f"Arquivo de configuração {CONFIG_PATH} não encontrado.\n"
            "Execute antes o notebook 00_mysql_config.ipynb para gerar o mysql_config.json."
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




# %%
# ============================================================
# 🌐 App Flask


# %%
# ============================================================

app = Flask(__name__)
# IMPORTANTE: troque essa chave depois por algo forte e secreto
app.secret_key = "mude-esta-chave-para-uma-string-bem-grande-e-secreta"




# %%
# ============================================================
# 👥 Funções auxiliares de usuário (tabela usuarios)


# %%
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




# %%
# ============================================================
# 🔐 Decorator para rotas que exigem login


# %%
# ============================================================

def login_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if "usuario_id" not in session:
            flash("Faça login para acessar essa página.", "warning")
            return redirect(url_for("login"))
        return f(*args, **kwargs)

    return wrapper




# %%
# ============================================================
# 🧱 Layout base (template HTML)


# %%
# ============================================================

layout_base = """
<!doctype html>
<html lang=\"pt-br\">
<head>
    <meta charset=\"utf-8\">
    <title>{{ titulo or \"Um novo lar\" }}</title>
    <style>
        :root {
            --primary: #0d6efd;
            --primary-light: #e7f1ff;
            --primary-dark: #0b5ed7;
            --bg-body: #f0f4f8;
            --card-bg: #ffffff;
            --border-soft: #dde2eb;
            --text-main: #1f2933;
            --text-muted: #6b7280;
            --danger: #dc3545;
            --success: #198754;
            --warning: #ffc107;
        }

        * {
            box-sizing: border-box;
            margin: 0;
            padding: 0;
        }

        body {
            font-family: system-ui, -apple-system, BlinkMacSystemFont, \"Segoe UI\", sans-serif;
            background: radial-gradient(circle at top left, #e0f2fe, #f9fafb 45%, #e5e7eb);
            color: var(--text-main);
            padding: 24px;
        }

        .app-shell {
            max-width: 1080px;
            margin: 0 auto;
            background: linear-gradient(135deg, rgba(255,255,255,0.98), rgba(241,245,249,0.98));
            border-radius: 18px;
            box-shadow:
                0 22px 45px rgba(15, 23, 42, 0.15),
                0 0 0 1px rgba(148, 163, 184, 0.15);
            border: 1px solid rgba(226, 232, 240, 0.9);
            padding: 22px 26px 26px;
        }

        .topbar {
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 16px;
            margin-bottom: 18px;
        }

        .brand {
            display: flex;
            align-items: center;
            gap: 14px;
        }

        .brand-logo {
            width: 52px;
            height: 52px;
            border-radius: 14px;
            padding: 6px;
            background: radial-gradient(circle at 30% 0, #ffffff, #dbeafe);
            box-shadow:
                0 10px 25px rgba(37, 99, 235, 0.25),
                0 0 0 1px rgba(191, 219, 254, 0.9);
            display: flex;
            align-items: center;
            justify-content: center;
            overflow: hidden;
        }

        .brand-logo img {
            max-width: 100%;
            max-height: 100%;
            object-fit: contain;
        }

        .brand-text {
            display: flex;
            flex-direction: column;
            gap: 2px;
        }

        .brand-title {
            font-size: 1.05rem;
            font-weight: 700;
            letter-spacing: 0.04em;
            text-transform: uppercase;
            color: var(--primary-dark);
        }

        .brand-subtitle {
            font-size: 0.88rem;
            color: var(--text-muted);
        }

        .nav-area {
            display: flex;
            flex-direction: column;
            align-items: flex-end;
            gap: 6px;
        }

        .user-greeting {
            font-size: 0.85rem;
            color: var(--text-muted);
        }

        .nav-links {
            display: flex;
            flex-wrap: wrap;
            gap: 6px;
        }

        .nav-pill {
            font-size: 0.82rem;
            padding: 6px 11px;
            border-radius: 999px;
            border: 1px solid transparent;
            text-decoration: none;
            color: var(--primary-dark);
            background: rgba(219, 234, 254, 0.9);
            font-weight: 500;
            transition: all 0.16s ease-out;
        }

        .nav-pill:hover {
            background: #ffffff;
            border-color: rgba(37, 99, 235, 0.3);
            box-shadow: 0 4px 12px rgba(15, 23, 42, 0.12);
            transform: translateY(-1px);
        }

        .nav-pill--secondary {
            background: #f3f4f6;
            color: #374151;
        }

        hr.soft-separator {
            border: none;
            border-top: 1px solid rgba(209, 213, 219, 0.7);
            margin: 4px 0 14px;
        }

        .content-card {
            background: var(--card-bg);
            border-radius: 14px;
            padding: 18px 18px 20px;
            border: 1px solid rgba(226, 232, 240, 0.9);
            box-shadow: 0 10px 25px rgba(15, 23, 42, 0.06);
        }

        h1, h2, h3 {
            color: var(--text-main);
        }

        h2 {
            font-size: 1.1rem;
            margin-bottom: 10px;
        }

        p {
            margin-bottom: 10px;
            font-size: 0.94rem;
        }

        /* Flash messages */
        .flash {
            padding: 8px 10px;
            margin-bottom: 10px;
            border-radius: 10px;
            border: 1px solid transparent;
            font-size: 0.9rem;
        }

        .flash-success {
            background: #ecfdf5;
            color: var(--success);
            border-color: rgba(16, 185, 129, 0.6);
        }

        .flash-warning {
            background: #fffbeb;
            color: #92400e;
            border-color: rgba(251, 191, 36, 0.7);
        }

        .flash-error {
            background: #fef2f2;
            color: var(--danger);
            border-color: rgba(248, 113, 113, 0.7);
        }

        /* Tabelas */
        table {
            width: 100%;
            border-collapse: collapse;
            margin-top: 8px;
            font-size: 0.9rem;
        }

        thead tr {
            background: linear-gradient(90deg, #e5edff, #f1f5f9);
        }

        th, td {
            padding: 8px 9px;
            border-bottom: 1px solid #e5e7eb;
            text-align: left;
        }

        th {
            font-weight: 600;
            color: #374151;
        }

        tbody tr:nth-child(even) {
            background: #f9fafb;
        }

        tbody tr:hover {
            background: #eff6ff;
        }

        /* Formulários */
        .field {
            margin-bottom: 10px;
        }

        label {
            display: block;
            font-weight: 600;
            margin-bottom: 4px;
            font-size: 0.86rem;
            color: #374151;
        }

        input[type=text],
        input[type=password],
        input[type=date],
        textarea {
            width: 100%;
            padding: 7px 8px;
            border-radius: 8px;
            border: 1px solid #d1d5db;
            font-size: 0.92rem;
            transition: border-color 0.15s ease-out, box-shadow 0.15s ease-out;
        }

        input:focus,
        textarea:focus {
            outline: none;
            border-color: var(--primary);
            box-shadow: 0 0 0 2px rgba(59, 130, 246, 0.35);
        }

        textarea {
            min-height: 80px;
            resize: vertical;
        }

        /* Botões */
        .btn {
            display: inline-flex;
            align-items: center;
            justify-content: center;
            gap: 6px;
            padding: 7px 14px;
            border-radius: 999px;
            border: none;
            cursor: pointer;
            text-decoration: none;
            font-size: 0.88rem;
            font-weight: 500;
            transition: all 0.15s ease-out;
        }

        .btn-primary {
            background: linear-gradient(135deg, var(--primary), var(--primary-dark));
            color: #ffffff;
            box-shadow: 0 10px 25px rgba(37, 99, 235, 0.35);
        }

        .btn-primary:hover {
            filter: brightness(1.05);
            transform: translateY(-1px);
            box-shadow: 0 14px 30px rgba(37, 99, 235, 0.45);
        }

        .btn-secondary {
            background: #f3f4f6;
            color: #374151;
            border: 1px solid #d1d5db;
        }

        .btn-secondary:hover {
            background: #e5e7eb;
        }

        .btn-danger {
            background: #fee2e2;
            color: #b91c1c;
            border: 1px solid #fecaca;
        }

        .btn-danger:hover {
            background: #fecaca;
        }

        .actions-row {
            margin-top: 12px;
            display: flex;
            gap: 8px;
            flex-wrap: wrap;
        }

        /* Grids de formulário */
        .field-group {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
            gap: 12px;
            margin-bottom: 6px;
        }

        /* Responsividade */
        @media (max-width: 768px) {
            body {
                padding: 10px;
            }
            .app-shell {
                padding: 16px 14px 18px;
            }
            .topbar {
                flex-direction: column;
                align-items: flex-start;
            }
            .nav-area {
                width: 100%;
                align-items: flex-start;
            }
            .nav-links {
                width: 100%;
            }
        }
    </style>
</head>
<body>
<div class=\"app-shell\">
    <div class=\"topbar\">
        <div class=\"brand\">
            <div class=\"brand-logo\">
                <img src=\"{{ url_for('static', filename='logo_um_novo_lar.png') }}\" alt=\"Logo Um novo lar\">
            </div>
            <div class=\"brand-text\">
                <div class=\"brand-title\">UM NOVO LAR</div>
                <div class=\"brand-subtitle\">Sistema de acolhimento e acompanhamento</div>
            </div>
        </div>
        <div class=\"nav-area\">
            {% if session.get('usuario_id') %}
                <div class=\"user-greeting\">
                    Olá, <strong>{{ session.get('usuario_nome') }}</strong>
                </div>
                <div class=\"nav-links\">
                    <a class=\"nav-pill\" href=\"{{ url_for('lista_pessoas') }}\">Pessoas acolhidas</a>
                    <a class=\"nav-pill\" href=\"{{ url_for('nova_pessoa') }}\">Novo cadastro</a>
                    <a class=\"nav-pill nav-pill--secondary\" href=\"{{ url_for('logout') }}\">Sair</a>
                </div>
            {% else %}
                <div class=\"nav-links\">
                    <a class=\"nav-pill\" href=\"{{ url_for('login') }}\">Login</a>
                    <a class=\"nav-pill nav-pill--secondary\" href=\"{{ url_for('registrar') }}\">Criar acesso</a>
                </div>
            {% endif %}
        </div>
    </div>

    <hr class=\"soft-separator\">

    {% with messages = get_flashed_messages(with_categories=True) %}
      {% if messages %}
        {% for cat, msg in messages %}
          <div class=\"flash flash-{{ cat }}\">{{ msg }}</div>
        {% endfor %}
      {% endif %}
    {% endwith %}

    <div class=\"content-card\">
        {{ conteudo|safe }}
    </div>
</div>
</body>
</html>
"""



def render_page(titulo: str, conteudo_html: str):
    return render_template_string(layout_base, titulo=titulo, conteudo=conteudo_html)




# %%
# ============================================================
# 🧭 Rotas


# %%
# ============================================================

@app.route("/")
def index():
    if "usuario_id" in session:
        return redirect(url_for("lista_pessoas"))
    return redirect(url_for("login"))


# ---------- Login ----------
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        senha = request.form.get("senha", "")

        usuario = buscar_usuario_por_email(email)
        if not usuario or not check_password_hash(usuario["senha_hash"], senha):
            flash("E-mail ou senha inválidos.", "error")
        else:
            session["usuario_id"] = usuario["id"]
            session["usuario_nome"] = usuario["nome"]
            flash("Login realizado com sucesso.", "success")
            return redirect(url_for("lista_pessoas"))

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


# ---------- Cadastro de usuário (registro) ----------
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
        linhas.append(f"""
            <tr>
                <td>{p['id']}</td>
                <td>{p.get('nome') or ''}</td>
                <td>{p.get('apelido') or ''}</td>
                <td>{p.get('telefone') or ''}</td>
                <td>{p.get('status') or ''}</td>
            </tr>
        """)

    rows_html = "".join(linhas)

    link_nova_pessoa = url_for("nova_pessoa")

    conteudo = f"""
    <h2>Pessoas acolhidas</h2>
    <p><a class="btn btn-primary" href="{link_nova_pessoa}">Novo cadastro</a></p>
    <table>
        <thead>
            <tr>
                <th>ID</th>
                <th>Nome</th>
                <th>Apelido</th>
                <th>Telefone</th>
                <th>Status</th>
            </tr>
        </thead>
        <tbody>
            {rows_html}
        </tbody>
    </table>
    """
    return render_page("Pessoas", conteudo)


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
                data_cadastro
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
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
    <form method="post">
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
        <div class="field">
            <label>Em situação de rua desde quando?</label>
            <textarea name="situacao_rua_desde" rows="2"></textarea>
        </div>
        <div class="field">
            <label>Resumo da situação de saúde</label>
            <textarea name="saude_resumo" rows="3"></textarea>
        </div>
        <div class="field">
            <label>Dependências químicas</label>
            <textarea name="dependencias_quimicas" rows="2"></textarea>
        </div>
        <div class="field">
            <label>Observações gerais</label>
            <textarea name="observacoes" rows="3"></textarea>
        </div>
        <button type="submit" class="btn btn-primary">Salvar</button>
        <a href="{link_lista}" class="btn btn-secondary">Voltar</a>
    </form>
    """
    return render_page("Nova pessoa", conteudo)




# %%
# ============================================================
# ▶️ Rodar app


# %%
# ============================================================

if __name__ == "__main__":
    # Em notebook, é melhor sem reloader
    app.run(
        debug=True,
        host="0.0.0.0",
        port=5000,
        use_reloader=False,
    )



