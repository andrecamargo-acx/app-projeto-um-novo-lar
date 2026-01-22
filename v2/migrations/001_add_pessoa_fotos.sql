-- Cria tabela para armazenar fotos no MySQL (1 foto por pessoa)
-- Execute no mesmo schema do app.

CREATE TABLE IF NOT EXISTS pessoa_fotos (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  pessoa_id INT NOT NULL,
  filename VARCHAR(255) NULL,
  mime_type VARCHAR(100) NOT NULL,
  size_bytes INT UNSIGNED NOT NULL,
  photo_blob LONGBLOB NOT NULL,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP NULL DEFAULT NULL ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  UNIQUE KEY uq_pessoa_fotos_pessoa_id (pessoa_id),
  KEY ix_pessoa_fotos_pessoa_id (pessoa_id),
  CONSTRAINT fk_pessoa_fotos_pessoa_id FOREIGN KEY (pessoa_id)
    REFERENCES pessoas (id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
