# %% [markdown]
# # routes/pessoas.py
# Rotas de pessoas:
# - listagem (inclui inativos)
# - detalhes
# - novo cadastro
# - edição
# - inativar
# - IA (resumo e classificação)
# - upload de foto

from datetime import datetime
from pathlib import Path

from flask import Blueprint, request, redirect, url_for, flash, session, send_file, make_response
from werkzeug.utils import secure_filename

from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

from decorators import login_required
from ui import render_page
from db import get_connection
from config import Config
from services.ia_service import gerar_resumo_pessoa_ia, classificar_pessoa_ia
from services.audit_service import registrar_auditoria

bp = Blueprint("pessoas", __name__, url_prefix="/pessoas")

BASE_DIR = Path(__file__).resolve().parents[1]
STATIC_DIR = BASE_DIR / "static"
FOTOS_DIR = STATIC_DIR / "fotos_pessoas"
FOTOS_DIR.mkdir(parents=True, exist_ok=True)


def allowed_file(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in Config.ALLOWED_EXTENSIONS


@bp.route("")
@login_required
def lista_pessoas():
    # %% [markdown]
    # ## lista_pessoas
    # Lista todas as pessoas (ativos primeiro, inativos por último).
    conn = get_connection()
    cur = conn.cursor(dictionary=True)
    cur.execute("""
        SELECT *
        FROM pessoas
        ORDER BY CASE WHEN status = 'inativo' THEN 1 ELSE 0 END, id DESC
    """)
    pessoas = cur.fetchall() or []
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

        raw_status = (p.get("status") or "").strip().lower()
        if raw_status == "inativo":
            status_html = '<span class="status-badge status-badge-inativo">Inativo</span>'
        else:
            status_html = f'<span class="status-badge">{p.get("status") or "Ativo"}</span>'

        detalhes_link = url_for("pessoas.detalhes_pessoa", pessoa_id=p["id"])
        linhas.append(f"""
          <tr>
            <td>{foto_html}</td>
            <td>{p['id']}</td>
            <td>{p.get('nome') or ''}</td>
            <td>{p.get('apelido') or ''}</td>
            <td>{p.get('telefone') or ''}</td>
            <td>{p.get('cidade_origem') or ''}</td>
            <td>{status_html}</td>
            <td><a class="btn btn-secondary" href="{detalhes_link}">Ver detalhes</a></td>
          </tr>
        """)

    conteudo = f"""
    <h2>Pessoas acolhidas</h2>
    <p><a class="btn btn-primary" href="{url_for('pessoas.nova_pessoa')}">Novo cadastro</a></p>
    <table>
      <thead>
        <tr>
          <th>Foto</th><th>ID</th><th>Nome</th><th>Apelido</th><th>Telefone</th><th>Cidade</th><th>Status</th><th></th>
        </tr>
      </thead>
      <tbody>
        {''.join(linhas)}
      </tbody>
    </table>
    """
    return render_page("Pessoas", conteudo)


@bp.route("/<int:pessoa_id>")
@login_required
def detalhes_pessoa(pessoa_id: int):
    # %% [markdown]
    # ## detalhes_pessoa
    # Mostra todas as informações disponíveis do cadastro + ações (editar, inativar, IA).
    conn = get_connection()
    cur = conn.cursor(dictionary=True)
    cur.execute("SELECT * FROM pessoas WHERE id = %s", (pessoa_id,))
    pessoa = cur.fetchone()
    cur.close()

    # Eventos de acompanhamento (timeline)
    cur_e = conn.cursor(dictionary=True)
    cur_e.execute(
        "SELECT * FROM pessoa_eventos WHERE pessoa_id = %s ORDER BY data_evento DESC, id DESC",
        (pessoa_id,)
    )
    eventos = cur_e.fetchall() or []
    cur_e.close()

    # Auditoria (histórico técnico)
    cur_a = conn.cursor(dictionary=True)
    cur_a.execute(
        "SELECT * FROM pessoa_auditoria WHERE pessoa_id = %s ORDER BY criado_em DESC, id DESC LIMIT 50",
        (pessoa_id,)
    )
    auditoria = cur_a.fetchall() or []
    cur_a.close()

    conn.close()

    if not pessoa:
        flash("Pessoa não encontrada.", "error")
        return redirect(url_for("pessoas.lista_pessoas"))

    foto_arquivo = pessoa.get("foto_arquivo")
    if foto_arquivo:
        foto_html = f'<img src="{url_for("static", filename="fotos_pessoas/" + foto_arquivo)}" class="photo-large" alt="Foto">'
    else:
        foto_html = '<div class="photo-large-placeholder">Sem foto cadastrada</div>'

    resumo_ia = session.pop("resumo_ia", None)
    sugestao_ia = session.pop("sugestao_ia", None)
    perguntas_ia = session.pop("perguntas_ia", None)

    resumo_ia_html = f"""<div class="details-block" style="border-left: 4px solid #1c75ff;">
      <h3>Resumo com IA</h3><p style="white-space: pre-line; font-size:13px;">{resumo_ia}</p></div>""" if resumo_ia else ""

    perguntas_ia_html = f"""<div class="details-block" style="border-left: 4px solid #7c3aed;">
      <h3>Perguntas sugeridas (IA)</h3><p style="white-space: pre-line; font-size:13px;">{perguntas_ia}</p></div>""" if perguntas_ia else ""

    sugestao_ia_html = f"""<div class="details-block" style="border-left: 4px solid #00b894;">
      <h3>Sugestões de próximos passos (IA)</h3><p style="white-space: pre-line; font-size:13px;">{sugestao_ia}</p></div>""" if sugestao_ia else ""

    def _fmt(v): return v or ""

    # Monta HTML dos eventos de acompanhamento
    eventos_linhas = []
    for ev in eventos:
        dt = ev.get('data_evento') or ''
        tipo = ev.get('tipo_evento') or 'Evento'
        desc = (ev.get('descricao') or '').replace('\n','<br>')
        eventos_linhas.append(f"""<div class='details-block'>
          <div style='display:flex; justify-content:space-between; gap:10px; flex-wrap:wrap;'>
            <div><b>{tipo}</b></div>
            <div style='color:#6b7280; font-size:12px;'>{dt}</div>
          </div>
          <div style='margin-top:6px; font-size:13px; color:#111827;'>{desc}</div>
        </div>""")
    eventos_html = "".join(eventos_linhas) if eventos_linhas else "<div style='color:#6b7280;'>Sem eventos de acompanhamento ainda.</div>"

    # Monta HTML da auditoria
    aud_linhas = []
    for au in auditoria:
        dt = au.get('criado_em') or ''
        acao = au.get('acao') or ''
        desc = (au.get('descricao') or '').replace('\n','<br>')
        aud_linhas.append(f"""<div class='details-block'>
          <div style='display:flex; justify-content:space-between; gap:10px; flex-wrap:wrap;'>
            <div><b>{acao}</b></div>
            <div style='color:#6b7280; font-size:12px;'>{dt}</div>
          </div>
          <div style='margin-top:6px; font-size:13px; color:#111827;'>{desc}</div>
        </div>""")
    auditoria_html = "".join(aud_linhas) if aud_linhas else "<div style='color:#6b7280;'>Sem registros de auditoria.</div>"

    conteudo = f"""
    <h2>Detalhes da pessoa acolhida</h2>

    <div style="display:flex; gap:8px; margin-bottom:10px; flex-wrap:wrap;">
      <a href="{url_for('pessoas.exportar_pdf', pessoa_id=pessoa_id)}" class="btn btn-secondary">Exportar PDF</a>
      <a href="{url_for('pessoas.exportar_csv')}" class="btn btn-secondary">Exportar CSV (todas)</a>

      <form method="post" action="{url_for('pessoas.resumo_pessoa_ia', pessoa_id=pessoa_id)}">
        <button type="submit" class="btn btn-primary">Gerar resumo com IA</button>
      </form>
      <form method="post" action="{url_for('pessoas.classificar_pessoa_ia_route', pessoa_id=pessoa_id)}">
        <button type="submit" class="btn btn-secondary">Classificar e sugerir próximos passos (IA)</button>
      </form>
      <a href="{url_for('pessoas.editar_pessoa', pessoa_id=pessoa_id)}" class="btn btn-secondary">Editar cadastro</a>
    </div>

    {resumo_ia_html}
    {sugestao_ia_html}
    {perguntas_ia_html}

    
    <div style="display:flex; gap:8px; flex-wrap:wrap; margin: 10px 0 14px 0;">
      <button type="button" class="btn btn-secondary" onclick="showTab('tab_cadastro')">Cadastro</button>
      <button type="button" class="btn btn-secondary" onclick="showTab('tab_saude')">Saúde & Avaliações</button>
      <button type="button" class="btn btn-secondary" onclick="showTab('tab_acomp')">Acompanhamento</button>
      <button type="button" class="btn btn-secondary" onclick="showTab('tab_auditoria')">Histórico técnico</button>
    </div>

    <script>
      function showTab(id){
        const tabs = ['tab_cadastro','tab_saude','tab_acomp','tab_auditoria'];
        tabs.forEach(t => {
          const el = document.getElementById(t);
          if(el) el.style.display = (t===id ? 'block' : 'none');
        });
        window.scrollTo({top: 0, behavior: 'smooth'});
      }
      // padrão: cadastro
      document.addEventListener('DOMContentLoaded', () => showTab('tab_cadastro'));
    </script>

    <div class="details-layout">
      <div>
        <div id="tab_cadastro">
        <div class="details-block">
          <h3>Informações gerais</h3>
          <div class="details-grid">
            <div><div class="details-item-label">Nome completo</div><div class="details-item-value">{_fmt(pessoa.get('nome'))}</div></div>
            <div><div class="details-item-label">Apelido</div><div class="details-item-value">{_fmt(pessoa.get('apelido'))}</div></div>
            <div><div class="details-item-label">Gênero</div><div class="details-item-value">{_fmt(pessoa.get('genero'))}</div></div>
            <div><div class="details-item-label">Estado civil</div><div class="details-item-value">{_fmt(pessoa.get('estado_civil'))}</div></div>
            <div><div class="details-item-label">Escolaridade</div><div class="details-item-value">{_fmt(pessoa.get('escolaridade'))}</div></div>
            <div><div class="details-item-label">Quantidade de filhos</div><div class="details-item-value">{_fmt(pessoa.get('qtd_filhos'))}</div></div>
            <div><div class="details-item-label">Nascimento</div><div class="details-item-value">{_fmt(pessoa.get('data_nascimento'))}</div></div>
            <div><div class="details-item-label">Documento principal</div><div class="details-item-value">{_fmt(pessoa.get('documento_principal'))}</div></div>
            <div><div class="details-item-label">Possui documentos básicos</div><div class="details-item-value">{"Sim" if pessoa.get("tem_documentos") else "Não"}</div></div>
            <div><div class="details-item-label">Telefone</div><div class="details-item-value">{_fmt(pessoa.get('telefone'))}</div></div>
            <div><div class="details-item-label">Contato de emergência</div><div class="details-item-value">{_fmt(pessoa.get('contato_emergencia'))}</div></div>
            <div><div class="details-item-label">Cidade de origem</div><div class="details-item-value">{_fmt(pessoa.get('cidade_origem'))}</div></div>
            <div><div class="details-item-label">Status</div><div class="details-item-value">{_fmt(pessoa.get('status'))}</div></div>
            <div><div class="details-item-label">Data de cadastro</div><div class="details-item-value">{_fmt(pessoa.get('data_cadastro'))}</div></div>
            <div><div class="details-item-label">Prioridade (IA)</div><div class="details-item-value">{_fmt(pessoa.get('prioridade_ia'))}</div></div>
            <div><div class="details-item-label">Tags (IA)</div><div class="details-item-value">{_fmt(pessoa.get('tags_ia'))}</div></div>
          </div>
        </div>

        <div class="details-block">
          <h3>Contexto familiar e trabalho</h3>
          <div class="details-item-label">Profissão anterior</div>
          <div class="details-item-value">{_fmt(pessoa.get('profissao_anterior'))}</div><br>
          <div class="details-item-label">Renda mensal aproximada</div>
          <div class="details-item-value">{_fmt(pessoa.get('renda_mensal_aprox'))}</div><br>
          <div class="details-item-label">Rede de apoio</div>
          <div class="details-item-value">{_fmt(pessoa.get('rede_apoio'))}</div>
        </div>
      </div>

      <div id="tab_saude" style="display:none;">
        <div class="details-block">
          <h3>Histórico, saúde e avaliações</h3>
          <div class="details-item-label">Situação de rua desde</div>
          <div class="details-item-value">{_fmt(pessoa.get('situacao_rua_desde'))}</div><br>
          <div class="details-item-label">Resumo de saúde</div>
          <div class="details-item-value">{_fmt(pessoa.get('saude_resumo'))}</div><br>
          <div class="details-item-label">Dependências químicas</div>
          <div class="details-item-value">{_fmt(pessoa.get('dependencias_quimicas'))}</div><br>
          <div class="details-item-label">Observações gerais</div>
          <div class="details-item-value">{_fmt(pessoa.get('observacoes'))}</div><br>
          <div class="details-item-label">Avaliação médica</div>
          <div class="details-item-value">{_fmt(pessoa.get('avaliacao_medica'))}</div><br>
          <div class="details-item-label">Avaliação do psicólogo</div>
          <div class="details-item-value">{_fmt(pessoa.get('avaliacao_psicologica'))}</div>
        </div>

        </div>
      </div>

      <div id="tab_acomp" style="display:none;">
        <div class="details-block">
          <h3>Novo evento de acompanhamento</h3>
          <form method="post" action="{url_for('pessoas.adicionar_evento', pessoa_id=pessoa_id)}">
            <div class="field-group">
              <div class="field"><label>Tipo</label><input type="text" name="tipo_evento" placeholder="Ex: avaliação_medica, avaliacao_psicologica, encaminhamento"></div>
              <div class="field"><label>Data do evento</label><input type="date" name="data_evento"></div>
            </div>
            <div class="field"><label>Descrição</label><textarea name="descricao" required></textarea></div>
            <button type="submit" class="btn btn-primary">Adicionar evento</button>
          </form>
        </div>
        <h3 style="margin-top:14px;">Linha do tempo</h3>
        {eventos_html}
      </div>

      <div id="tab_auditoria" style="display:none;">
        <h3>Auditoria</h3>
        {auditoria_html}
      </div>

      <div style="margin-top: 10px; display:flex; gap: 8px; flex-wrap:wrap;">
          <a href="{url_for('pessoas.lista_pessoas')}" class="btn btn-secondary">Voltar para lista</a>
          {('' if (pessoa.get('status') or '').strip().lower()=='inativo' else f'''<form method="post" action="{url_for('pessoas.inativar_pessoa', pessoa_id=pessoa_id)}" onsubmit="return confirm('Tem certeza que deseja marcar este cadastro como inativo?');">
            <button type="submit" class="btn btn-danger">Marcar como inativo</button>
          </form>''')}
          {('' if (pessoa.get('status') or '').strip().lower()!='inativo' else f'''<form method="post" action="{url_for('pessoas.ativar_pessoa', pessoa_id=pessoa_id)}" onsubmit="return confirm('Tem certeza que deseja reativar este cadastro?');">
            <button type="submit" class="btn btn-primary">Reativar cadastro</button>
          </form>''')}
        </div>
      </div>

      <div>
        <div class="details-block" style="text-align:center;">
          {foto_html}
          <div style="font-size:11px; color:#6b7280; margin-top:6px;">Foto registrada no cadastro</div>
        </div>
      </div>
    </div>
    """
    return render_page("Detalhes", conteudo)


@bp.route("/<int:pessoa_id>/inativar", methods=["POST"])
@login_required
def inativar_pessoa(pessoa_id: int):
    # %% [markdown]
    # ## inativar_pessoa
    # Não apaga o registro. Marca como status='inativo' para histórico.
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("UPDATE pessoas SET status = %s WHERE id = %s", ("inativo", pessoa_id))
    conn.commit()
    cur.close()
    conn.close()
    registrar_auditoria(pessoa_id, session.get("usuario_id"), "status_inativado", "Cadastro marcado como inativo")
    flash("Cadastro marcado como inativo.", "success")
    return redirect(url_for("pessoas.lista_pessoas"))

# %% [markdown]
# ## (Rota) Ativar registro
# Permite reativar um cadastro que foi marcado como inativo.
@bp.route("/<int:pessoa_id>/ativar", methods=["POST"])
@login_required
def ativar_pessoa(pessoa_id: int):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("UPDATE pessoas SET status = %s WHERE id = %s", ("ativo", pessoa_id))
    conn.commit()
    cur.close()
    conn.close()
    registrar_auditoria(pessoa_id, session.get("usuario_id"), "status_reativado", "Cadastro reativado")
    flash("Cadastro reativado com sucesso.", "success")
    return redirect(url_for("pessoas.lista_pessoas"))


@bp.route("/<int:pessoa_id>/resumo_ia", methods=["POST"])
@login_required
def resumo_pessoa_ia(pessoa_id: int):
    # %% [markdown]
    # ## resumo_pessoa_ia
    # Chama Gemini para gerar resumo e guarda em session para exibir na tela de detalhes.
    conn = get_connection()
    cur = conn.cursor(dictionary=True)
    cur.execute("SELECT * FROM pessoas WHERE id = %s", (pessoa_id,))
    pessoa = cur.fetchone()
    cur.close()

    # Eventos de acompanhamento (timeline)
    cur_e = conn.cursor(dictionary=True)
    cur_e.execute(
        "SELECT * FROM pessoa_eventos WHERE pessoa_id = %s ORDER BY data_evento DESC, id DESC",
        (pessoa_id,)
    )
    eventos = cur_e.fetchall() or []
    cur_e.close()

    # Auditoria (histórico técnico)
    cur_a = conn.cursor(dictionary=True)
    cur_a.execute(
        "SELECT * FROM pessoa_auditoria WHERE pessoa_id = %s ORDER BY criado_em DESC, id DESC LIMIT 50",
        (pessoa_id,)
    )
    auditoria = cur_a.fetchall() or []
    cur_a.close()

    conn.close()

    if not pessoa:
        flash("Pessoa não encontrada para gerar resumo.", "error")
        return redirect(url_for("pessoas.lista_pessoas"))

    try:
        resumo = gerar_resumo_pessoa_ia(pessoa)
        flash("Resumo gerado com IA.", "success")
    except Exception as e:
        resumo = f"Erro ao chamar IA: {e}"
        flash("Não foi possível gerar o resumo com IA.", "error")

    session["resumo_ia"] = resumo
    registrar_auditoria(pessoa_id, session.get("usuario_id"), "resumo_ia", "Resumo gerado/atualizado pela IA")
    return redirect(url_for("pessoas.detalhes_pessoa", pessoa_id=pessoa_id))


@bp.route("/<int:pessoa_id>/classificar_ia", methods=["POST"])
@login_required
def classificar_pessoa_ia_route(pessoa_id: int):
    # %% [markdown]
    # ## classificar_pessoa_ia_route
    # Chama Gemini para:
    # - prioridade (alta/média/baixa)
    # - tags (salvas no banco)
    # - sugestões de próximos passos (mostradas na tela)
    conn = get_connection()
    cur = conn.cursor(dictionary=True)
    cur.execute("SELECT * FROM pessoas WHERE id = %s", (pessoa_id,))
    pessoa = cur.fetchone()
    cur.close()

    if not pessoa:
        conn.close()
        flash("Pessoa não encontrada para classificação IA.", "error")
        return redirect(url_for("pessoas.lista_pessoas"))

    try:
        resultado = classificar_pessoa_ia(pessoa)
        prioridade = resultado.get("prioridade", "desconhecida")
        tags = resultado.get("tags", "")
        proximos_passos = resultado.get("proximos_passos", "")
    except Exception as e:
        conn.close()
        session["sugestao_ia"] = f"Erro ao chamar IA: {e}"
        flash("Não foi possível classificar com IA.", "error")
        return redirect(url_for("pessoas.detalhes_pessoa", pessoa_id=pessoa_id))

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
    session["perguntas_ia"] = (resultado.get("perguntas") or "").strip()
    registrar_auditoria(pessoa_id, session.get("usuario_id"), "classificacao_ia", f"prioridade={prioridade} tags={tags}")
    return redirect(url_for("pessoas.detalhes_pessoa", pessoa_id=pessoa_id))


@bp.route("/nova", methods=["GET","POST"])
@login_required
def nova_pessoa():
    # %% [markdown]
    # ## nova_pessoa
    # Tela de cadastro inicial (com upload opcional de foto).
    if request.method == "POST":
        nome = request.form.get("nome","").strip()
        apelido = request.form.get("apelido","").strip() or None
        data_nascimento = request.form.get("data_nascimento") or None

        genero = request.form.get("genero","").strip() or None
        estado_civil = request.form.get("estado_civil","").strip() or None
        escolaridade = request.form.get("escolaridade","").strip() or None
        qtd_filhos_str = request.form.get("qtd_filhos","").strip()
        qtd_filhos = int(qtd_filhos_str) if qtd_filhos_str else None

        documento_principal = request.form.get("documento_principal","").strip() or None
        tem_documentos = (request.form.get("tem_documentos") == "on")
        telefone = request.form.get("telefone","").strip() or None
        contato_emergencia = request.form.get("contato_emergencia","").strip() or None
        cidade_origem = request.form.get("cidade_origem","").strip() or None

        profissao_anterior = request.form.get("profissao_anterior","").strip() or None
        renda_mensal_aprox = request.form.get("renda_mensal_aprox","").strip() or None
        rede_apoio = request.form.get("rede_apoio","").strip() or None

        situacao_rua_desde = request.form.get("situacao_rua_desde","").strip() or None
        saude_resumo = request.form.get("saude_resumo","").strip() or None
        dependencias_quimicas = request.form.get("dependencias_quimicas","").strip() or None
        observacoes = request.form.get("observacoes","").strip() or None

        avaliacao_medica = request.form.get("avaliacao_medica","").strip() or None
        avaliacao_psicologica = request.form.get("avaliacao_psicologica","").strip() or None

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
                nome, apelido, data_nascimento, genero, estado_civil, escolaridade, qtd_filhos,
                documento_principal, tem_documentos, telefone, contato_emergencia, cidade_origem,
                profissao_anterior, renda_mensal_aprox, rede_apoio, situacao_rua_desde, saude_resumo,
                dependencias_quimicas, observacoes, avaliacao_medica, avaliacao_psicologica,
                status, data_cadastro, foto_arquivo
            )
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            """
            tem_docs_int = 1 if tem_documentos else 0
            valores = (
                nome, apelido, data_nascimento or None, genero, estado_civil, escolaridade, qtd_filhos,
                documento_principal, tem_docs_int, telefone, contato_emergencia, cidade_origem,
                profissao_anterior, renda_mensal_aprox, rede_apoio, situacao_rua_desde, saude_resumo,
                dependencias_quimicas, observacoes, avaliacao_medica, avaliacao_psicologica,
                "ativo", datetime.now().strftime("%Y-%m-%d %H:%M:%S"), foto_arquivo
            )
            cur.execute(insert_sql, valores)
            pessoa_id = cur.lastrowid
            conn.commit()
            cur.close()
            conn.close()
            registrar_auditoria(pessoa_id, session.get("usuario_id"), "cadastro_criado", "Novo cadastro criado")
            flash("Pessoa cadastrada com sucesso.", "success")
            return redirect(url_for("pessoas.lista_pessoas"))

    conteudo = f"""
    <h2>Novo cadastro de pessoa acolhida</h2>
    <form method="post" enctype="multipart/form-data">
      <div class="field-group">
        <div class="field"><label>Nome completo *</label><input type="text" name="nome" required></div>
        <div class="field"><label>Apelido</label><input type="text" name="apelido"></div>
        <div class="field"><label>Data de nascimento</label><input type="date" name="data_nascimento"></div>
        <div class="field"><label>Gênero</label><input type="text" name="genero"></div>
        <div class="field"><label>Estado civil</label><input type="text" name="estado_civil"></div>
        <div class="field"><label>Escolaridade</label><input type="text" name="escolaridade"></div>
        <div class="field"><label>Quantidade de filhos</label><input type="number" name="qtd_filhos" min="0"></div>
        <div class="field"><label>Documento principal (RG/CPF ou outro)</label><input type="text" name="documento_principal"></div>
      </div>

      <div class="field-group">
        <div class="field"><label><input type="checkbox" name="tem_documentos"> Possui documentos básicos</label></div>
        <div class="field"><label>Telefone</label><input type="text" name="telefone"></div>
        <div class="field"><label>Contato de emergência</label><input type="text" name="contato_emergencia"></div>
        <div class="field"><label>Cidade de origem</label><input type="text" name="cidade_origem"></div>
      </div>

      <div class="field-group">
        <div class="field"><label>Profissão anterior</label><input type="text" name="profissao_anterior"></div>
        <div class="field"><label>Renda mensal aproximada</label><input type="text" name="renda_mensal_aprox"></div>
        <div class="field"><label>Rede de apoio</label><textarea name="rede_apoio"></textarea></div>
      </div>

      <div class="field-group">
        <div class="field"><label>Situação de rua desde quando?</label><textarea name="situacao_rua_desde"></textarea></div>
        <div class="field"><label>Resumo de saúde</label><textarea name="saude_resumo"></textarea></div>
      </div>

      <div class="field-group">
        <div class="field"><label>Dependências químicas</label><textarea name="dependencias_quimicas"></textarea></div>
        <div class="field"><label>Observações gerais</label><textarea name="observacoes"></textarea></div>
      </div>

      <div class="field-group">
        <div class="field"><label>Avaliação médica (opcional)</label><textarea name="avaliacao_medica"></textarea></div>
        <div class="field"><label>Avaliação do psicólogo (opcional)</label><textarea name="avaliacao_psicologica"></textarea></div>
      </div>

      <div class="field-group">
        <div class="field"><label>Foto da pessoa (opcional)</label><input type="file" name="foto" accept="image/*"></div>
      </div>

      </div>
      </div>

      <div id="tab_acomp" style="display:none;">
        <div class="details-block">
          <h3>Novo evento de acompanhamento</h3>
          <form method="post" action="{url_for('pessoas.adicionar_evento', pessoa_id=pessoa_id)}">
            <div class="field-group">
              <div class="field"><label>Tipo</label><input type="text" name="tipo_evento" placeholder="Ex: avaliação_medica, avaliacao_psicologica, encaminhamento"></div>
              <div class="field"><label>Data do evento</label><input type="date" name="data_evento"></div>
            </div>
            <div class="field"><label>Descrição</label><textarea name="descricao" required></textarea></div>
            <button type="submit" class="btn btn-primary">Adicionar evento</button>
          </form>
        </div>
        <h3 style="margin-top:14px;">Linha do tempo</h3>
        {eventos_html}
      </div>

      <div id="tab_auditoria" style="display:none;">
        <h3>Auditoria</h3>
        {auditoria_html}
      </div>

      <div style="margin-top: 10px; display:flex; gap: 8px; flex-wrap:wrap;">
        <button type="submit" class="btn btn-primary">Salvar cadastro</button>
        <a href="{url_for('pessoas.lista_pessoas')}" class="btn btn-secondary">Voltar para lista</a>
      </div>
    </form>
    """
    return render_page("Novo cadastro", conteudo)


@bp.route("/<int:pessoa_id>/editar", methods=["GET","POST"])
@login_required
def editar_pessoa(pessoa_id: int):
    # %% [markdown]
    # ## editar_pessoa
    # Permite inserir informações adicionais no perfil após o cadastro inicial
    # (ex: avaliação médica, psicológica, etc.) e atualizar foto.
    conn = get_connection()
    cur = conn.cursor(dictionary=True)
    cur.execute("SELECT * FROM pessoas WHERE id = %s", (pessoa_id,))
    pessoa = cur.fetchone()

    if not pessoa:
        cur.close(); conn.close()
        flash("Pessoa não encontrada para edição.", "error")
        return redirect(url_for("pessoas.lista_pessoas"))

    if request.method == "POST":
        nome = request.form.get("nome","").strip()
        apelido = request.form.get("apelido","").strip() or None
        data_nascimento = request.form.get("data_nascimento") or None

        genero = request.form.get("genero","").strip() or None
        estado_civil = request.form.get("estado_civil","").strip() or None
        escolaridade = request.form.get("escolaridade","").strip() or None
        qtd_filhos_str = request.form.get("qtd_filhos","").strip()
        qtd_filhos = int(qtd_filhos_str) if qtd_filhos_str else None

        documento_principal = request.form.get("documento_principal","").strip() or None
        tem_documentos = (request.form.get("tem_documentos") == "on")
        telefone = request.form.get("telefone","").strip() or None
        contato_emergencia = request.form.get("contato_emergencia","").strip() or None
        cidade_origem = request.form.get("cidade_origem","").strip() or None

        profissao_anterior = request.form.get("profissao_anterior","").strip() or None
        renda_mensal_aprox = request.form.get("renda_mensal_aprox","").strip() or None
        rede_apoio = request.form.get("rede_apoio","").strip() or None

        situacao_rua_desde = request.form.get("situacao_rua_desde","").strip() or None
        saude_resumo = request.form.get("saude_resumo","").strip() or None
        dependencias_quimicas = request.form.get("dependencias_quimicas","").strip() or None
        observacoes = request.form.get("observacoes","").strip() or None

        avaliacao_medica = request.form.get("avaliacao_medica","").strip() or None
        avaliacao_psicologica = request.form.get("avaliacao_psicologica","").strip() or None

        foto_arquivo = pessoa.get("foto_arquivo")
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
            tem_docs_int = 1 if tem_documentos else 0
            update_sql = """
            UPDATE pessoas SET
                nome=%s, apelido=%s, data_nascimento=%s, genero=%s, estado_civil=%s, escolaridade=%s, qtd_filhos=%s,
                documento_principal=%s, tem_documentos=%s, telefone=%s, contato_emergencia=%s, cidade_origem=%s,
                profissao_anterior=%s, renda_mensal_aprox=%s, rede_apoio=%s, situacao_rua_desde=%s, saude_resumo=%s,
                dependencias_quimicas=%s, observacoes=%s, avaliacao_medica=%s, avaliacao_psicologica=%s, foto_arquivo=%s
            WHERE id=%s
            """
            valores = (
                nome, apelido, data_nascimento or None, genero, estado_civil, escolaridade, qtd_filhos,
                documento_principal, tem_docs_int, telefone, contato_emergencia, cidade_origem,
                profissao_anterior, renda_mensal_aprox, rede_apoio, situacao_rua_desde, saude_resumo,
                dependencias_quimicas, observacoes, avaliacao_medica, avaliacao_psicologica, foto_arquivo,
                pessoa_id
            )
            cur2 = conn.cursor()
            cur2.execute(update_sql, valores)
            conn.commit()
            cur2.close()
            cur.close()
            conn.close()
            registrar_auditoria(pessoa_id, session.get("usuario_id"), "cadastro_atualizado", "Campos do cadastro foram atualizados")
            flash("Cadastro atualizado com sucesso.", "success")
            return redirect(url_for("pessoas.detalhes_pessoa", pessoa_id=pessoa_id))

    def _f(v): return v or ""
    tem_docs_checked = "checked" if pessoa.get("tem_documentos") else ""

    conteudo = f"""
    <h2>Editar cadastro da pessoa acolhida</h2>
    <form method="post" enctype="multipart/form-data">
      <div class="field-group">
        <div class="field"><label>Nome completo *</label><input type="text" name="nome" value="{_f(pessoa.get('nome'))}" required></div>
        <div class="field"><label>Apelido</label><input type="text" name="apelido" value="{_f(pessoa.get('apelido'))}"></div>
        <div class="field"><label>Data de nascimento</label><input type="date" name="data_nascimento" value="{_f(pessoa.get('data_nascimento'))}"></div>
        <div class="field"><label>Gênero</label><input type="text" name="genero" value="{_f(pessoa.get('genero'))}"></div>
        <div class="field"><label>Estado civil</label><input type="text" name="estado_civil" value="{_f(pessoa.get('estado_civil'))}"></div>
        <div class="field"><label>Escolaridade</label><input type="text" name="escolaridade" value="{_f(pessoa.get('escolaridade'))}"></div>
        <div class="field"><label>Quantidade de filhos</label><input type="number" name="qtd_filhos" min="0" value="{_f(pessoa.get('qtd_filhos'))}"></div>
        <div class="field"><label>Documento principal</label><input type="text" name="documento_principal" value="{_f(pessoa.get('documento_principal'))}"></div>
      </div>

      <div class="field-group">
        <div class="field"><label><input type="checkbox" name="tem_documentos" {tem_docs_checked}> Possui documentos básicos</label></div>
        <div class="field"><label>Telefone</label><input type="text" name="telefone" value="{_f(pessoa.get('telefone'))}"></div>
        <div class="field"><label>Contato de emergência</label><input type="text" name="contato_emergencia" value="{_f(pessoa.get('contato_emergencia'))}"></div>
        <div class="field"><label>Cidade de origem</label><input type="text" name="cidade_origem" value="{_f(pessoa.get('cidade_origem'))}"></div>
      </div>

      <div class="field-group">
        <div class="field"><label>Profissão anterior</label><input type="text" name="profissao_anterior" value="{_f(pessoa.get('profissao_anterior'))}"></div>
        <div class="field"><label>Renda mensal aproximada</label><input type="text" name="renda_mensal_aprox" value="{_f(pessoa.get('renda_mensal_aprox'))}"></div>
        <div class="field"><label>Rede de apoio</label><textarea name="rede_apoio">{_f(pessoa.get('rede_apoio'))}</textarea></div>
      </div>

      <div class="field-group">
        <div class="field"><label>Situação de rua desde quando?</label><textarea name="situacao_rua_desde">{_f(pessoa.get('situacao_rua_desde'))}</textarea></div>
        <div class="field"><label>Resumo de saúde</label><textarea name="saude_resumo">{_f(pessoa.get('saude_resumo'))}</textarea></div>
      </div>

      <div class="field-group">
        <div class="field"><label>Dependências químicas</label><textarea name="dependencias_quimicas">{_f(pessoa.get('dependencias_quimicas'))}</textarea></div>
        <div class="field"><label>Observações gerais</label><textarea name="observacoes">{_f(pessoa.get('observacoes'))}</textarea></div>
      </div>

      <div class="field-group">
        <div class="field"><label>Avaliação médica</label><textarea name="avaliacao_medica">{_f(pessoa.get('avaliacao_medica'))}</textarea></div>
        <div class="field"><label>Avaliação do psicólogo</label><textarea name="avaliacao_psicologica">{_f(pessoa.get('avaliacao_psicologica'))}</textarea></div>
      </div>

      <div class="field-group">
        <div class="field"><label>Foto (envie uma nova para substituir)</label><input type="file" name="foto" accept="image/*"></div>
      </div>

      </div>
      </div>

      <div id="tab_acomp" style="display:none;">
        <div class="details-block">
          <h3>Novo evento de acompanhamento</h3>
          <form method="post" action="{url_for('pessoas.adicionar_evento', pessoa_id=pessoa_id)}">
            <div class="field-group">
              <div class="field"><label>Tipo</label><input type="text" name="tipo_evento" placeholder="Ex: avaliação_medica, avaliacao_psicologica, encaminhamento"></div>
              <div class="field"><label>Data do evento</label><input type="date" name="data_evento"></div>
            </div>
            <div class="field"><label>Descrição</label><textarea name="descricao" required></textarea></div>
            <button type="submit" class="btn btn-primary">Adicionar evento</button>
          </form>
        </div>
        <h3 style="margin-top:14px;">Linha do tempo</h3>
        {eventos_html}
      </div>

      <div id="tab_auditoria" style="display:none;">
        <h3>Auditoria</h3>
        {auditoria_html}
      </div>

      <div style="margin-top: 10px; display:flex; gap: 8px; flex-wrap:wrap;">
        <button type="submit" class="btn btn-primary">Salvar alterações</button>
        <a href="{url_for('pessoas.detalhes_pessoa', pessoa_id=pessoa_id)}" class="btn btn-secondary">Cancelar</a>
      </div>
    </form>
    """
    cur.close(); conn.close()
    return render_page("Editar cadastro", conteudo)


# %% [markdown]
# ## (Rota) Adicionar evento de acompanhamento
# Cria um evento na tabela `pessoa_eventos` para compor a linha do tempo.
@bp.route("/<int:pessoa_id>/eventos/adicionar", methods=["POST"])
@login_required
def adicionar_evento(pessoa_id: int):
    tipo = (request.form.get("tipo_evento") or "").strip() or "evento"
    data_evento = request.form.get("data_evento") or None
    descricao = (request.form.get("descricao") or "").strip()

    if not descricao:
        flash("Descrição do evento é obrigatória.", "warning")
        return redirect(url_for("pessoas.detalhes_pessoa", pessoa_id=pessoa_id))

    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO pessoa_eventos (pessoa_id, tipo_evento, descricao, data_evento, criado_em, criado_por_usuario_id)
        VALUES (%s, %s, %s, %s, NOW(), %s)
        """,
        (pessoa_id, tipo, descricao, data_evento, session.get("usuario_id")),
    )
    conn.commit()
    cur.close()
    conn.close()

    registrar_auditoria(pessoa_id, session.get("usuario_id"), "evento_adicionado", f"{tipo} em {data_evento or 'sem data'}")
    flash("Evento adicionado com sucesso.", "success")
    return redirect(url_for("pessoas.detalhes_pessoa", pessoa_id=pessoa_id))


# %% [markdown]
# ## (Rota) Exportar CSV
# Exporta todos os cadastros em CSV (útil para relatórios e prestação de contas).
@bp.route("/exportar_csv")
@login_required
def exportar_csv():
    conn = get_connection()
    cur = conn.cursor(dictionary=True)
    cur.execute("SELECT * FROM pessoas ORDER BY id DESC")
    rows = cur.fetchall() or []
    cur.close()
    conn.close()

    output = io.StringIO()
    if rows:
        fieldnames = list(rows[0].keys())
    else:
        fieldnames = ["id", "nome"]

    writer = csv.DictWriter(output, fieldnames=fieldnames)
    writer.writeheader()
    for r in rows:
        writer.writerow(r)

    resp = make_response(output.getvalue())
    resp.headers["Content-Type"] = "text/csv; charset=utf-8"
    resp.headers["Content-Disposition"] = "attachment; filename=pessoas_um_novo_lar.csv"
    return resp


# %% [markdown]
# ## (Rota) Exportar PDF
# Gera um PDF simples com a ficha da pessoa (dados principais + saúde + observações + IA).
@bp.route("/<int:pessoa_id>/exportar_pdf")
@login_required
def exportar_pdf(pessoa_id: int):
    conn = get_connection()
    cur = conn.cursor(dictionary=True)
    cur.execute("SELECT * FROM pessoas WHERE id = %s", (pessoa_id,))
    pessoa = cur.fetchone() or {}
    cur.close()
    conn.close()

    if not pessoa:
        flash("Pessoa não encontrada para exportar PDF.", "error")
        return redirect(url_for("pessoas.lista_pessoas"))

    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4

    y = height - 50
    c.setFont("Helvetica-Bold", 16)
    c.drawString(40, y, "Um Novo Lar - Ficha do Acolhido")
    y -= 20

    c.setFont("Helvetica", 10)
    c.drawString(40, y, f"Gerado em: {datetime.datetime.now().strftime('%d/%m/%Y %H:%M')}")
    y -= 25

    def draw_label_value(label, value):
        nonlocal y
        if y < 80:
            c.showPage()
            y = height - 50
        c.setFont("Helvetica-Bold", 10)
        c.drawString(40, y, f"{label}:")
        c.setFont("Helvetica", 10)
        c.drawString(160, y, str(value or ""))
        y -= 14

    draw_label_value("ID", pessoa.get("id"))
    draw_label_value("Nome", pessoa.get("nome"))
    draw_label_value("Apelido", pessoa.get("apelido"))
    draw_label_value("Nascimento", pessoa.get("data_nascimento"))
    draw_label_value("Telefone", pessoa.get("telefone"))
    draw_label_value("Cidade de origem", pessoa.get("cidade_origem"))
    draw_label_value("Documentos básicos", "Sim" if pessoa.get("tem_documentos") else "Não")
    draw_label_value("Status", pessoa.get("status"))
    draw_label_value("Prioridade (IA)", pessoa.get("prioridade_ia"))
    draw_label_value("Tags (IA)", pessoa.get("tags_ia"))

    y -= 10
    c.setFont("Helvetica-Bold", 12)
    c.drawString(40, y, "Saúde & Avaliações")
    y -= 18
    draw_label_value("Resumo de saúde", pessoa.get("saude_resumo"))
    draw_label_value("Dependências químicas", pessoa.get("dependencias_quimicas"))
    draw_label_value("Avaliação médica", pessoa.get("avaliacao_medica"))
    draw_label_value("Avaliação psicológica", pessoa.get("avaliacao_psicologica"))

    y -= 10
    c.setFont("Helvetica-Bold", 12)
    c.drawString(40, y, "Observações")
    y -= 16
    c.setFont("Helvetica", 10)
    obs = (pessoa.get("observacoes") or "").strip()
    for line in (obs.splitlines() or [""]):
        if y < 80:
            c.showPage()
            y = height - 50
            c.setFont("Helvetica", 10)
        c.drawString(40, y, line[:120])
        y -= 12

    c.showPage()
    c.save()
    buffer.seek(0)

    filename = f"ficha_pessoa_{pessoa_id}.pdf"
    return send_file(buffer, as_attachment=True, download_name=filename, mimetype="application/pdf")

