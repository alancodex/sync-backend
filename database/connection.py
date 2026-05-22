"""
database/connection.py
Módulo de conexão com SQL Server via pyodbc.
"""

import pyodbc
import os
from dotenv import load_dotenv

load_dotenv()

DB_CONFIG = {
    "server":   os.getenv("DB_SERVER",   "186.227.202.150"),
    "port":     os.getenv("DB_PORT",     "4505"),
    "database": os.getenv("DB_NAME",     "CDSSINC"),
    "username": os.getenv("DB_USER",     "troubleshoot"),
    "password": os.getenv("DB_PASSWORD", "CDS123dificil!@#"),
}


def get_connection():
    """
    Retorna uma conexão ativa com o SQL Server.
    Driver preferencial: ODBC Driver 17 for SQL Server.
    Fallback: FreeTDS / SQL Server (Linux).
    """
    drivers = [
        "ODBC Driver 17 for SQL Server",
        "ODBC Driver 18 for SQL Server",
        "FreeTDS",
        "SQL Server",
    ]

    driver = _get_available_driver(drivers)
    if not driver:
        raise RuntimeError(
            "Nenhum driver ODBC compatível encontrado. "
            "Instale o 'ODBC Driver 17 for SQL Server' ou 'FreeTDS'."
        )

    conn_str = (
        f"DRIVER={{{driver}}};"
        f"SERVER={DB_CONFIG['server']},{DB_CONFIG['port']};"
        f"DATABASE={DB_CONFIG['database']};"
        f"UID={DB_CONFIG['username']};"
        f"PWD={DB_CONFIG['password']};"
        "TrustServerCertificate=yes;"
        "Connection Timeout=10;"
    )

    return pyodbc.connect(conn_str)


def _get_available_driver(drivers: list[str]) -> str | None:
    """Retorna o primeiro driver ODBC instalado da lista."""
    installed = [d for d in pyodbc.drivers()]
    for driver in drivers:
        if driver in installed:
            return driver
    # Se nenhum bater exatamente, retorna o primeiro instalado que mencione SQL
    for d in installed:
        if "SQL" in d or "FreeTDS" in d:
            return d
    return None


def test_connection() -> dict:
    """Testa a conexão e retorna status."""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT @@VERSION")
        version = cursor.fetchone()[0].split("\n")[0]
        conn.close()
        return {"status": "ok", "server_version": version}
    except Exception as exc:
        return {"status": "error", "message": str(exc)}
