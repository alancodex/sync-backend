"""
services/sync_service.py
Colunas reais: id, idEmpresa, nomeFantasia, tempo, grupoLoja,
               dataInicio, dataFim, dataStart, dataErro, versaoFL, descricao, tipo
"""

from database.connection import get_connection
from datetime import datetime, timezone, timedelta

MINUTOS_SINCRONIZANDO = 15 

QUERY_ALL_STORES = """
    SELECT
        id, idEmpresa, nomeFantasia, tempo, grupoLoja,
        dataInicio, dataFim, dataStart, dataErro, versaoFL, descricao, tipo
    FROM sincronizacao
    ORDER BY grupoLoja, dataInicio DESC
"""

QUERY_STORE_DETAIL = """
    SELECT
        id, idEmpresa, nomeFantasia, tempo, grupoLoja,
        dataInicio, dataFim, dataStart, dataErro, versaoFL, descricao, tipo
    FROM sincronizacao
    WHERE grupoLoja = ?
    ORDER BY dataInicio DESC
"""

QUERY_SUMMARY_STATS = """
    SELECT
        COUNT(DISTINCT grupoLoja) AS total_lojas,
        SUM(CASE WHEN dataErro IS NOT NULL THEN 1 ELSE 0 END) AS total_erros,
        MAX(dataFim) AS ultima_sincronizacao
    FROM sincronizacao
"""


def _row_to_dict(cursor, row) -> dict:
    columns = [col[0] for col in cursor.description]
    return dict(zip(columns, row))


def _fmt_dt(value) -> str | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%d %H:%M:%S")
    return str(value)



def _classify_status(records: list[dict]) -> str:
    if not records:
        return "desconhecido"

    latest = records[0]

    # Erro explícito
    if latest.get("dataErro") is not None:
        return "erro"

    tipo = (latest.get("tipo") or "").lower()
    if "erro" in tipo:
        return "erro"

    # Pega o dataInicio do registro mais recente
    data_inicio = latest.get("dataInicio")
    if data_inicio is None:
        return "desconhecido"

    # Converte para datetime se vier como string
    if isinstance(data_inicio, str):
        try:
            data_inicio = datetime.strptime(data_inicio[:19], "%Y-%m-%d %H:%M:%S")
        except ValueError:
            return "desconhecido"

    agora = datetime.now()
    diferenca = agora - data_inicio

    # Se o último evento foi há menos de 15 minutos → ainda sincronizando
    if diferenca <= timedelta(minutes=MINUTOS_SINCRONIZANDO):
        return "sincronizando"

    # Último evento foi há mais de 15 minutos → sincronização concluída
    return "ok"


def _build_store_summary(grupo_loja: str, records: list[dict]) -> dict:
    if not records:
        return {}

    latest = records[0]
    status = _classify_status(records)

    timestamps = [latest.get("dataFim"), latest.get("dataStart"), latest.get("dataInicio")]
    ultima_atualizacao = next((_fmt_dt(t) for t in timestamps if t), None)

    return {
        "grupo_loja":         grupo_loja,
        "empresa":            latest.get("idEmpresa", ""),
        "nome_fantasia":      latest.get("nomeFantasia", ""),
        "status":             status,
        "mensagem":           latest.get("tipo", ""),
        "erro":               _fmt_dt(latest.get("dataErro")),
        "versao":             latest.get("versaoFL", ""),
        "tipo":               latest.get("tipo", ""),
        "ultima_atualizacao": ultima_atualizacao,
        "total_registros":    len(records),
    }


def get_all_stores_status() -> list[dict]:
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(QUERY_ALL_STORES)
        rows = cursor.fetchall()
        all_records = [_row_to_dict(cursor, r) for r in rows]
    finally:
        conn.close()

    # grupoLoja é texto — agrupa normalmente
    stores: dict[str, list[dict]] = {}
    for rec in all_records:
        grp = rec["grupoLoja"]
        stores.setdefault(grp, []).append(rec)

    return [_build_store_summary(grp, recs) for grp, recs in stores.items()]


def get_store_detail(grupo_loja: str) -> dict:
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(QUERY_STORE_DETAIL, (grupo_loja,))
        rows = cursor.fetchall()
        records = [_row_to_dict(cursor, r) for r in rows]
    finally:
        conn.close()

    if not records:
        return {"grupo_loja": grupo_loja, "registros": [], "status": "desconhecido"}

    for rec in records:
        for field in ("dataInicio", "dataFim", "dataStart", "dataErro"):
            rec[field] = _fmt_dt(rec.get(field))

    status = _classify_status(records)
    summary = _build_store_summary(grupo_loja, records)

    return {**summary, "status": status, "registros": records}


def get_dashboard_stats() -> dict:
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(QUERY_SUMMARY_STATS)
        row = cursor.fetchone()
        stats = _row_to_dict(cursor, row) if row else {}
    finally:
        conn.close()

    return {
        "total_lojas":          stats.get("total_lojas", 0),
        "total_erros":          stats.get("total_erros", 0),
        "ultima_sincronizacao": _fmt_dt(stats.get("ultima_sincronizacao")),
    }


def get_chart_data(grupo_loja: str | None = None) -> list[dict]:
    base_query = """
        SELECT
            grupoLoja,
            nomeFantasia,
            CAST(dataInicio AS DATE) AS data,
            COUNT(*) AS total_sincronizacoes,
            SUM(CASE WHEN dataErro IS NOT NULL THEN 1 ELSE 0 END) AS total_erros
        FROM sincronizacao
        WHERE dataInicio IS NOT NULL
        {where}
        GROUP BY grupoLoja, nomeFantasia, CAST(dataInicio AS DATE)
        ORDER BY data DESC
    """
    where = "AND grupoLoja = ?" if grupo_loja else ""
    query = base_query.format(where=where)

    conn = get_connection()
    try:
        cursor = conn.cursor()
        if grupo_loja:
            cursor.execute(query, (grupo_loja,))
        else:
            cursor.execute(query)
        rows = cursor.fetchall()
        records = [_row_to_dict(cursor, r) for r in rows]
    finally:
        conn.close()

    for rec in records:
        rec["data"] = str(rec["data"]) if rec.get("data") else None

    return records