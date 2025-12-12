from flask import Blueprint, request, redirect, url_for, session, flash
from ui import render_page
from services.auth_service import criar_usuario, buscar_usuario_por_email, validar_senha

bp = Blueprint("auth", __name__)

@bp.route("/")
def index():
    if session.get("usuario_id"):
        return redirect(url_for("dashboard.dashboard"))
    return redirect(url_for("auth.login"))

@bp.route("/login", methods=["GET","POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email","").strip().lower()
        senha = request.form.get("senha","")
        usuario = buscar_usuario_por_email(email)
        if not usuario or not validar_senha(usuario["senha_hash"], senha):
            flash("Usuário ou senha inválidos.", "error")
        else:
            session["usuario_id"] = usuario["id"]
            session["usuario_nome"] = usuario["nome"]
            flash("Login realizado com sucesso.", "success")
            return redirect(url_for("dashboard.dashboard"))

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

@bp.route("/logout")
def logout():
    session.clear()
    flash("Você saiu do sistema.", "success")
    return redirect(url_for("auth.login"))

@bp.route("/registrar", methods=["GET","POST"])
def registrar():
    if request.method == "POST":
        nome = request.form.get("nome","").strip()
        email = request.form.get("email","").strip().lower()
        senha = request.form.get("senha","")
        senha2 = request.form.get("senha2","")

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
                return redirect(url_for("auth.login"))

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
