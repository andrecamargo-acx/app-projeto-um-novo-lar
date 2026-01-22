# Um Novo Lar — versão com Blueprints

## Rodar local
```bash
pip install -r requirements.txt
python app.py
```

## Render
- **Build Command:** `pip install -r requirements.txt`
- **Start Command:** `gunicorn app:app`

## Arquivos
- Coloque o logo em: `static/logo_um_novo_lar.png`
- Fotos: **armazenadas no MySQL** (tabela `pessoa_fotos`).
  - Migração: `migrations/001_add_pessoa_fotos.sql`
  - Fallback (legado): ainda consegue servir fotos antigas de `static/fotos_pessoas/`
- MySQL:
  - Local: `mysql_config.json`
  - Render: configure `DB_HOST/DB_PORT/DB_USER/DB_PASSWORD/DB_NAME`

## Upload de foto
- Limite padrão: **5MB** (ajuste via env `MAX_PHOTO_MB`)
