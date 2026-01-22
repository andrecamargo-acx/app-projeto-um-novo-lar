"""services/photo_service.py

Camada simples para armazenar e recuperar fotos no MySQL.

Motivação:
- No Render/containers, escrever em disco (static/) pode ser frágil.
- Centraliza validação/IO e evita duplicação nas rotas.

Tabela esperada: pessoa_fotos
  - pessoa_id (UNIQUE)
  - filename, mime_type, size_bytes, photo_blob (LONGBLOB)
  - created_at, updated_at
"""

from __future__ import annotations

from typing import Optional, Dict, Any


def upsert_pessoa_foto(
    conn,
    pessoa_id: int,
    filename: str,
    mime_type: str,
    content: bytes,
) -> None:
    """Insere ou atualiza a foto de uma pessoa (1 foto por pessoa)."""
    cur = conn.cursor()
    sql = """
    INSERT INTO pessoa_fotos (pessoa_id, filename, mime_type, size_bytes, photo_blob)
    VALUES (%s, %s, %s, %s, %s)
    ON DUPLICATE KEY UPDATE
        filename   = VALUES(filename),
        mime_type  = VALUES(mime_type),
        size_bytes = VALUES(size_bytes),
        photo_blob = VALUES(photo_blob),
        updated_at = CURRENT_TIMESTAMP
    """
    cur.execute(sql, (pessoa_id, filename, mime_type, len(content), content))
    cur.close()


def get_pessoa_foto(conn, pessoa_id: int) -> Optional[Dict[str, Any]]:
    """Retorna dict com filename/mime_type/photo_blob ou None."""
    cur = conn.cursor(dictionary=True)
    cur.execute(
        "SELECT filename, mime_type, photo_blob FROM pessoa_fotos WHERE pessoa_id = %s",
        (pessoa_id,),
    )
    row = cur.fetchone()
    cur.close()
    return row


def has_pessoa_foto(conn, pessoa_id: int) -> bool:
    cur = conn.cursor()
    cur.execute("SELECT 1 FROM pessoa_fotos WHERE pessoa_id = %s LIMIT 1", (pessoa_id,))
    ok = cur.fetchone() is not None
    cur.close()
    return ok


def delete_pessoa_foto(conn, pessoa_id: int) -> None:
    cur = conn.cursor()
    cur.execute("DELETE FROM pessoa_fotos WHERE pessoa_id = %s", (pessoa_id,))
    cur.close()
