# %% [markdown]
# # services/audit_service.py
# Serviço de auditoria (log) das ações no cadastro.
# Objetivo: registrar alterações importantes sem depender do front.
# - Ex.: cadastro atualizado, inativado/reativado, inclusão de evento de acompanhamento, etc.
#
# Observação:
# - O app NÃO deve quebrar se o log falhar.
# - Por isso usamos try/except e seguimos o fluxo principal.

from db import get_connection


def registrar_auditoria(pessoa_id: int, usuario_id: int | None, acao: str, descricao: str | None = None):
    """Insere uma linha na tabela `pessoa_auditoria`.

    Espera-se que a tabela exista (você já criou conforme combinado).
    Campos típicos:
      - pessoa_id, usuario_id, acao, descricao, criado_em

    Se ocorrer qualquer erro, a função apenas retorna (não levanta exceção).
    """
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO pessoa_auditoria (pessoa_id, usuario_id, acao, descricao, criado_em)
            VALUES (%s, %s, %s, %s, NOW())
            """,
            (pessoa_id, usuario_id, acao, descricao),
        )
        conn.commit()
        cur.close()
        conn.close()
    except Exception:
        # Não quebrar o fluxo do app por falha de auditoria
        return
