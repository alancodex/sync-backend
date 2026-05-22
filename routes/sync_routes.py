"""
routes/sync_routes.py
"""

from flask import Blueprint, jsonify, request
from services import (
    get_all_stores_status,
    get_store_detail,
    get_dashboard_stats,
    get_chart_data,
)
from database import test_connection

sync_bp = Blueprint("sync", __name__, url_prefix="/api")


def _error_response(message: str, status_code: int = 500):
    return jsonify({"error": True, "message": message}), status_code


@sync_bp.route("/health", methods=["GET"])
def health():
    db_status = test_connection()
    return jsonify({"api": "ok", "database": db_status})


@sync_bp.route("/status", methods=["GET"])
def get_status():
    try:
        data = get_all_stores_status()
        return jsonify({"success": True, "total": len(data), "lojas": data})
    except Exception as exc:
        return _error_response(str(exc))


@sync_bp.route("/stats", methods=["GET"])
def get_stats():
    try:
        stats = get_dashboard_stats()
        return jsonify({"success": True, **stats})
    except Exception as exc:
        return _error_response(str(exc))


#grupoLoja é string, não int
@sync_bp.route("/loja/<string:grupo_loja>", methods=["GET"])
def get_loja(grupo_loja: str):
    try:
        data = get_store_detail(grupo_loja)
        if not data.get("registros"):
            return _error_response(f"Loja {grupo_loja} não encontrada.", 404)
        return jsonify({"success": True, **data})
    except Exception as exc:
        return _error_response(str(exc))


@sync_bp.route("/charts", methods=["GET"])
def get_charts():
    try:
        grupo_loja = request.args.get("grupo_loja", type=str)
        data = get_chart_data(grupo_loja)
        return jsonify({"success": True, "series": data})
    except Exception as exc:
        return _error_response(str(exc))


@sync_bp.route("/amostra", methods=["GET"])
def get_amostra():
    from database import get_connection
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT TOP 3 * FROM sincronizacao ORDER BY dataInicio DESC")
    cols = [col[0] for col in cursor.description]
    rows = []
    for row in cursor.fetchall():
        r = {}
        for k, v in zip(cols, row):
            r[k] = str(v) if v is not None else None
        rows.append(r)
    conn.close()
    return jsonify(rows)