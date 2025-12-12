# %% [markdown]
# # db.py
# Módulo responsável por abrir conexão com o MySQL.
# Mantemos isso separado para evitar repetição.

import mysql.connector
from config import Config


def get_connection():
    cfg = Config.load_mysql_config()
    return mysql.connector.connect(
        host=cfg["host"],
        port=cfg["port"],
        user=cfg["user"],
        password=cfg["password"],
        database=cfg["database"],
    )
