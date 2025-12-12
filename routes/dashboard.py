# %% [markdown]
# # routes/dashboard.py
# Dashboard com métricas e gráficos (Chart.js).

from flask import Blueprint
from decorators import login_required
from ui import render_page
from db import get_connection
import json as _json
import json

bp = Blueprint("dashboard", __name__, url_prefix="/dashboard")

@bp.route("")
@login_required
def dashboard():
    # %% [markdown]
    # ## Dashboard avançado
    # Mostra:
    # - Total (ativos/inativos)
    # - Cadastros por mês (base: data_cadastro)
    # - Pendências (sem documentos / sem avaliação médica / sem avaliação psicológica)
    # - Distribuição por status
    # - Top 5 cidades (ativos)

    conn = get_connection()
    cur = conn.cursor(dictionary=True)

    # Totais (ativos e inativos)
    cur.execute("""
        SELECT
          SUM(CASE WHEN status = 'inativo' THEN 1 ELSE 0 END) AS inativos,
          SUM(CASE WHEN status = 'inativo' THEN 0 ELSE 1 END) AS ativos
        FROM pessoas
    """)
    row_total = cur.fetchone() or {"ativos": 0, "inativos": 0}
    total_ativos = int(row_total.get("ativos") or 0)
    total_inativos = int(row_total.get("inativos") or 0)
    total_pessoas = total_ativos + total_inativos

    # Pendências (visão para acompanhamento)
    cur.execute("""
        SELECT
          SUM(CASE WHEN COALESCE(tem_documentos,0) = 0 THEN 1 ELSE 0 END) AS sem_documentos,
          SUM(CASE WHEN avaliacao_medica IS NULL OR TRIM(avaliacao_medica) = '' THEN 1 ELSE 0 END) AS sem_avaliacao_medica,
          SUM(CASE WHEN avaliacao_psicologica IS NULL OR TRIM(avaliacao_psicologica) = '' THEN 1 ELSE 0 END) AS sem_avaliacao_psicologica
        FROM pessoas
        WHERE status <> 'inativo' OR status IS NULL
    """)
    pend = cur.fetchone() or {"sem_documentos": 0, "sem_avaliacao_medica": 0, "sem_avaliacao_psicologica": 0}
    sem_documentos = int(pend.get("sem_documentos") or 0)
    sem_avaliacao_medica = int(pend.get("sem_avaliacao_medica") or 0)
    sem_avaliacao_psicologica = int(pend.get("sem_avaliacao_psicologica") or 0)

    # Distribuição por status
    cur.execute("""
        SELECT COALESCE(status, 'Não informado') AS status, COUNT(*) AS total
        FROM pessoas
        GROUP BY COALESCE(status, 'Não informado')
        ORDER BY total DESC
    """)
    rows_status = cur.fetchall() or []

    # Top 5 cidades (ativos)
    cur.execute("""
        SELECT COALESCE(cidade_origem, 'Não informada') AS cidade, COUNT(*) AS total
        FROM pessoas
        WHERE status <> 'inativo' OR status IS NULL
        GROUP BY COALESCE(cidade_origem, 'Não informada')
        ORDER BY total DESC
        LIMIT 5
    """)
    rows_cidade = cur.fetchall() or []

    # Cadastros por mês (últimos 12 meses, baseado em data_cadastro)
    # Observação: data_cadastro pode ser DATE ou DATETIME. Usamos DATE_FORMAT.
    cur.execute("""
        SELECT DATE_FORMAT(data_cadastro, '%Y-%m') AS ym, COUNT(*) AS total
        FROM pessoas
        WHERE data_cadastro IS NOT NULL
        GROUP BY DATE_FORMAT(data_cadastro, '%Y-%m')
        ORDER BY ym DESC
        LIMIT 12
    """)
    rows_mes = cur.fetchall() or []
    rows_mes = list(reversed(rows_mes))  # para plotar em ordem crescente

    cur.close()
    conn.close()

    status_labels = [r["status"] for r in rows_status]
    status_values = [int(r["total"]) for r in rows_status]

    cidade_labels = [r["cidade"] for r in rows_cidade]
    cidade_values = [int(r["total"]) for r in rows_cidade]

    mes_labels = [r["ym"] for r in rows_mes]
    mes_values = [int(r["total"]) for r in rows_mes]

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
      <div class="card-metric">
        <div class="card-metric-label">Pendência: sem documentos</div>
        <div class="card-metric-value">{sem_documentos}</div>
      </div>
      <div class="card-metric">
        <div class="card-metric-label">Pendência: sem avaliação médica</div>
        <div class="card-metric-value">{sem_avaliacao_medica}</div>
      </div>
      <div class="card-metric">
        <div class="card-metric-label">Pendência: sem avaliação psicológica</div>
        <div class="card-metric-value">{sem_avaliacao_psicologica}</div>
      </div>
    </div>

    <div class="charts-row">
      <div class="chart-card">
        <h3>Cadastros por mês (últimos 12)</h3>
        <canvas id="chartCadMes"></canvas>
      </div>
      <div class="chart-card">
        <h3>Distribuição por status</h3>
        <canvas id="chartStatus"></canvas>
      </div>
    </div>

    <div class="charts-row">
      <div class="chart-card">
        <h3>Pessoas por cidade (Top 5 – ativos)</h3>
        <canvas id="chartCidade"></canvas>
      </div>
      <div class="chart-card">
        <h3>Pendências (ativos)</h3>
        <canvas id="chartPendencias"></canvas>
      </div>
    </div>

    <script>
      (function(){{
        const mesLabels = {json.dumps(mes_labels, ensure_ascii=False)};
        const mesValues = {json.dumps(mes_values)};

        const statusLabels = {json.dumps(status_labels, ensure_ascii=False)};
        const statusValues = {json.dumps(status_values)};

        const cidadeLabels = {json.dumps(cidade_labels, ensure_ascii=False)};
        const cidadeValues = {json.dumps(cidade_values)};

        const pendLabels = ["Sem documentos","Sem avaliação médica","Sem avaliação psicológica"];
        const pendValues = [{sem_documentos},{sem_avaliacao_medica},{sem_avaliacao_psicologica}];

        new Chart(document.getElementById('chartCadMes'), {{
          type:'line',
          data:{{labels:mesLabels, datasets:[{{data:mesValues}}]}},
          options:{{plugins:{{legend:{{display:false}}}}, scales:{{y:{{beginAtZero:true, ticks:{{precision:0}}}}}}}}
        }});

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

        new Chart(document.getElementById('chartPendencias'), {{
          type:'bar',
          data:{{labels:pendLabels, datasets:[{{data:pendValues}}]}},
          options:{{plugins:{{legend:{{display:false}}}}, scales:{{y:{{beginAtZero:true, ticks:{{precision:0}}}}}}}}
        }});
      }})();
    </script>
    """

    return render_page("Dashboard", conteudo)

