# %% [markdown]
# # ui.py
# Este módulo contém o **layout base** (HTML+CSS) e um helper para renderizar páginas.
# Mantemos aqui para:
# - reaproveitar o mesmo cabeçalho/menu em todas as telas
# - controlar estilo de forma centralizada

from flask import render_template_string

layout_base = """<!doctype html>
<html lang="pt-br">
<head>
  <meta charset="utf-8">
  <title>{{ titulo or "Um novo lar" }}</title>
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>

  <style>
    :root{
      --bg1:#e6f0ff; --bg2:#ffffff;
      --primary:#1c75ff; --primaryDark:#165fcc; --primaryLight:#92b9ff;
      --text:#1f2933; --muted:#6b7280; --border:#dde2eb;
    }
    *{box-sizing:border-box}
    body{
      margin:0; padding:24px;
      font-family:system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;
      background:linear-gradient(135deg,var(--bg1),var(--bg2));
      color:var(--text);
    }
    .app-shell{
      max-width:1100px; margin:0 auto;
      background:#fff; border-radius:18px;
      padding:20px 24px 28px;
      box-shadow:0 18px 35px rgba(15,35,95,.08),0 0 0 1px rgba(15,23,42,.04);
      border:1px solid rgba(148,163,184,.3);
    }
    .topbar{
      display:flex; align-items:center; justify-content:space-between;
      gap:16px; margin-bottom:18px; padding-bottom:14px;
      border-bottom:1px solid var(--border);
    }
    .brand{display:flex; align-items:center; gap:12px;}
    /* ✅ Logo maior + fundo branco (sem degradê) */
    .brand-logo{
      width:96px; height:96px; border-radius:18px;
      background:#ffffff;
      display:flex; align-items:center; justify-content:center;
      overflow:hidden;
      border:1px solid #e5e7eb;
      box-shadow:0 10px 22px rgba(15,23,42,.18);
    }
    .brand-logo img{width:92%; height:92%; object-fit:contain;}
    .brand-text-title{font-size:20px; font-weight:800; letter-spacing:.06em; text-transform:uppercase;}
    .brand-text-subtitle{font-size:12px; color:var(--muted);}
    .user-info{font-size:13px; color:var(--muted); text-align:right; margin-bottom:4px;}
    .menu{display:flex; gap:8px; flex-wrap:wrap; justify-content:flex-end;}
    .menu a{
      font-size:13px; padding:7px 12px; border-radius:999px;
      text-decoration:none; color:var(--text);
      background:#f3f4ff; border:1px solid transparent;
      transition:.15s;
    }
    .menu a:hover{background:#e0e7ff; border-color:var(--primaryLight);}
    .menu a.menu-primary{
      background:var(--primary); color:#fff; border-color:var(--primaryDark);
      box-shadow:0 8px 16px rgba(37,99,235,.35);
    }
    .menu a.menu-primary:hover{background:var(--primaryDark);}
    .flash-container{margin-bottom:12px;}
    .flash{
      padding:10px 12px; margin-bottom:8px; border-radius:10px; font-size:13px;
      border:1px solid transparent;
    }
    .flash-success{background:#ecfdf3; border-color:#bbf7d0; color:#166534;}
    .flash-warning{background:#fffbeb; border-color:#facc15; color:#92400e;}
    .flash-error{background:#fef2f2; border-color:#fecaca; color:#b91c1c;}
    .content-card{
      margin-top:6px; padding:16px 18px 20px;
      border-radius:16px; background:#f9fafb; border:1px solid #e5e7eb;
    }
    h2{margin:0 0 14px 0; font-size:20px;}
    .btn{
      padding:7px 13px; border-radius:999px; border:none; cursor:pointer;
      text-decoration:none; font-size:13px; display:inline-flex; align-items:center; gap:6px;
      transition:.15s;
    }
    .btn-primary{background:linear-gradient(135deg,var(--primary),var(--primaryDark)); color:#fff; box-shadow:0 8px 16px rgba(37,99,235,.35);}
    .btn-secondary{background:#e5e7eb; color:#111827;}
    .btn-danger{background:#fee2e2; color:#b91c1c;}
    .field-group{display:grid; grid-template-columns:repeat(auto-fit,minmax(220px,1fr)); gap:12px 16px; margin-bottom:12px;}
    .field{display:flex; flex-direction:column; gap:4px;}
    label{font-weight:700; font-size:13px;}
    input[type=text],input[type=password],input[type=date],input[type=number],textarea{
      width:100%; padding:7px 9px; border-radius:9px; border:1px solid #d1d5db; font-size:13px; outline:none;
      background:#fff;
    }
    textarea{min-height:70px; resize:vertical;}
    table{width:100%; border-collapse:collapse; margin-top:8px; font-size:13px; background:#fff; border-radius:12px; overflow:hidden; border:1px solid #e5e7eb;}
    th,td{padding:8px 10px; border-bottom:1px solid #e5e7eb;}
    thead{background:linear-gradient(135deg,#eff6ff,#e0f2fe);}
    tbody tr:nth-child(even){background:#f9fafb;}
    tbody tr:hover{background:#e5f1ff;}
    .photo-thumb{width:40px; height:40px; border-radius:999px; object-fit:cover; border:2px solid #e5e7eb;}
    .photo-thumb-placeholder{width:40px; height:40px; border-radius:999px; border:2px dashed #cbd5e1; display:inline-flex; align-items:center; justify-content:center; font-size:9px; color:#9ca3af;}
    .status-badge{display:inline-block; padding:2px 8px; border-radius:999px; font-size:11px; background:#e5f4ff; color:#1e40af;}
    .status-badge-inativo{background:#fee2e2; color:#991b1b;}
    .cards-row{display:grid; grid-template-columns:repeat(auto-fit,minmax(180px,1fr)); gap:12px; margin-bottom:16px;}
    .card-metric{padding:10px 12px; border-radius:14px; border:1px solid #e5e7eb; background:#fff;}
    .card-metric-label{font-size:11px; text-transform:uppercase; letter-spacing:.08em; color:var(--muted);}
    .card-metric-value{font-size:20px; font-weight:800; margin-top:4px;}
    .charts-row{display:grid; grid-template-columns:repeat(auto-fit,minmax(260px,1fr)); gap:16px; margin-top:8px;}
    .chart-card{background:#fff; border-radius:14px; padding:10px 12px; border:1px solid #e5e7eb;}
    .details-layout{display:grid; grid-template-columns:minmax(0,2fr) minmax(0,1fr); gap:18px;}
    .details-block{background:#fff; border-radius:12px; padding:12px 14px; border:1px solid #e5e7eb; margin-bottom:8px;}
    .details-grid{display:grid; grid-template-columns:repeat(auto-fit,minmax(180px,1fr)); gap:8px 16px;}
    .details-item-label{font-size:11px; text-transform:uppercase; letter-spacing:.06em; color:var(--muted);}
    .details-item-value{font-size:13px; font-weight:600;}

    /* ===== TAGS (IA) - chips (corrigido) ===== */
    .details-item.tags-full{ grid-column: 1 / -1; }

    .tags-wrap{
      display:flex;
      flex-wrap:wrap;
      gap:8px;
      margin-top:6px;
    }
    .tag-chip{
      display:inline-flex;
      align-items:center;
      padding:5px 12px;
      border-radius:999px;
      font-size:12px;
      font-weight:600;
      line-height:1.1;
      background:#eef2ff;
      color:#1e40af;
      border:1px solid #c7d2fe;
      white-space:nowrap;
    }

    .photo-large{width:160px; height:160px; border-radius:24px; object-fit:cover; border:3px solid #e5e7eb; box-shadow:0 15px 30px rgba(15,35,95,.25);}
    .photo-large-placeholder{width:160px; height:160px; border-radius:24px; border:2px dashed #cbd5e1; display:inline-flex; align-items:center; justify-content:center; font-size:11px; color:#9ca3af;}
    @media (max-width:720px){body{padding:10px}.topbar{flex-direction:column; align-items:flex-start}.user-info{text-align:left}.details-layout{grid-template-columns:1fr}.brand-logo{width:90px;height:90px}}

    /* Rodapé com marca ACX (detalhe) */
    .footer-acx{
      margin-top: 28px;
      padding: 14px 0 6px 0;
      border-top: 1px solid rgba(17,24,39,0.08);
      display:flex;
      align-items:center;
      justify-content:center;
      gap:10px;
      color:#6b7280;
      font-size:12px;
    }
    .footer-acx img{
      height: 60px;          /* tamanho ideal */
      width: auto;
      opacity: 0.85;
      filter: grayscale(20%);
    }
    .footer-acx img:hover{
      opacity: 0.9;
      filter: grayscale(20%);
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
        <div class="user-info">Olá, {{ session.get('usuario_nome') }}</div>
      {% endif %}
      <div class="menu">
        {% if session.get('usuario_id') %}
          <a href="{{ url_for('dashboard.dashboard') }}" class="menu-primary">Dashboard</a>
          <a href="{{ url_for('pessoas.lista_pessoas') }}">Pessoas</a>
          <a href="{{ url_for('pessoas.nova_pessoa') }}">Novo cadastro</a>
          <a href="{{ url_for('auth.logout') }}">Sair</a>
        {% else %}
          <a href="{{ url_for('auth.login') }}" class="menu-primary">Login</a>
          <a href="{{ url_for('auth.registrar') }}">Criar acesso</a>
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

<footer class="footer-acx">
  <span>Desenvolvido por</span>
  <img src="/static/logo_acx.png" alt="ACX Developing Beyond" loading="lazy">
</footer>

</body>
</html>
"""


def render_page(titulo: str, conteudo_html: str):
    # %% [markdown]
    # ## render_page
    # Renderiza o `layout_base` e injeta o HTML específico da página no bloco `conteudo`.
    return render_template_string(layout_base, titulo=titulo, conteudo=conteudo_html)
