from flask import Blueprint
from decorators import login_required
from ui import render_page
from db import get_connection
import json as _json

bp = Blueprint("dashboard", __name__, url_prefix="/dashboard")

@bp.route("")
@login_required
def dashboard():
    conn = get_connection()
    cur = conn.cursor(dictionary=True)

    cur.execute("""
        SELECT
          SUM(CASE WHEN status = 'inativo' THEN 1 ELSE 0 END) AS inativos,
          SUM(CASE WHEN status = 'inativo' THEN 0 ELSE 1 END) AS ativos
        FROM pessoas
    """)
    row_total = cur.fetchone() or {"ativos": 0, "inativos": 0}
    total_ativos = row_total["ativos"] or 0
    total_inativos = row_total["inativos"] or 0
    total_pessoas = total_ativos + total_inativos

    cur.execute("""
        SELECT COALESCE(status, 'Não informado') AS status, COUNT(*) AS total
        FROM pessoas
        GROUP BY COALESCE(status, 'Não informado')
        ORDER BY total DESC
    """)
    rows_status = cur.fetchall() or []

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

    conteudo = f"""
    <h2>Dashboard de cadastros</h2>

    <div class="cards-row">
      <div class="card-metric">
        <div class="card-metric-label">Total de cadastros</div>
        <div class="card-metric-value">{total_pessoas}</div>
      </div>
      <div class="card-metric">
        <div class="card-metric-label">Ativos</div>
        <div class="card-metric-value">{total_ativos}</div>
      </div>
      <div class="card-metric">
        <div class="card-metric-label">Inativados</div>
        <div class="card-metric-value">{total_inativos}</div>
      </div>
    </div>

    <div class="charts-row">
      <div class="chart-card">
        <h3>Distribuição por status (ativos e inativos)</h3>
        <canvas id="chartStatus"></canvas>
      </div>
      <div class="chart-card">
        <h3>Pessoas por cidade (Top 5 – ativos)</h3>
        <canvas id="chartCidade"></canvas>
      </div>
    </div>

    <script>
      (function(){{
        const statusLabels = {_json.dumps(status_labels, ensure_ascii=False)};
        const statusValues = {_json.dumps(status_values)};
        const cidadeLabels = {_json.dumps(cidade_labels, ensure_ascii=False)};
        const cidadeValues = {_json.dumps(cidade_values)};

        new Chart(document.getElementById('chartStatus'), {{
          type:'doughnut',
          data:{{labels:statusLabels, datasets:[{{data:statusValues}}]}},
          options:{{plugins:{{legend:{{position:'bottom'}}}}}}
        }});

        new Chart(document.getElementById('chartCidade'), {{
          type:'bar',
          data:{{labels:cidadeLabels, datasets:[{{data:cidadeValues}}]}},
          options:{{plugins:{{legend:{{display:false}}}}, scales:{{y:{{beginAtZero:true, ticks:{{precision:0}}}}}}}}
        }});
      }})();
    </script>
    """
    return render_page("Dashboard", conteudo)
