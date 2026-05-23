from database.connection import get_connection
from datetime import datetime, timedelta

# ─── Mapeamento grupo → palavras-chave ───────────────────────────────────────
GRUPOS_KEYWORDS = {
    "Graciosa":         ["GRACIOSA"],
    "To Rica":          ["TO RICA"],
    "Pupilentes":       ["PUPILENTES"],
    "Papaleguas":       ["PPL", "PAPALEGUAS"],
    "Destak":           ["DESTAK"],
    "Empório HD":       ["EMPORIO"],
    "Sementeira":       ["SEMENT"],
    "Sigillo":          ["SIGILL", "SIGILO"],
    "Vibe Praia":       ["VIBE"],
    "Recyclo":          ["RECYCLO"],
    "Bombas":           ["BOMBAS"],
    "Cimento Mello":    ["MELO", "CIMENTO"],
    "La Donna":         ["DONNA"],
    "Lojão Conforto":   ["CONFORTO"],
    "Central":          ["CENTRAL"],
    "V+ Virtual":       ["V+"],
    "Rossini":          ["ROSSINI"],
    "Oticas Economica": ["OTICAS ECONOMICA", "OTICA ECONOMICA"],
    "Credcardo":        ["CREDCARDO"],
    "CIAO":             ["CIAO"],
    "Automaq":          ["AUTOMAQ"],
}


def _detectar_grupo(nome_fantasia: str) -> str:
    if not nome_fantasia:
        return "Outros"
    nome_upper = nome_fantasia.upper()
    for grupo, keywords in GRUPOS_KEYWORDS.items():
        for kw in keywords:
            if kw.upper() in nome_upper:
                return grupo
    return nome_fantasia


QUERY_ALL_STORES = """
    SELECT s.id, s.idEmpresa, s.nomeFantasia, s.tempo, s.grupoLoja,
           s.dataInicio, s.dataFim, s.dataStart, s.dataErro,
           s.versaoFL, s.descricao, s.tipo
    FROM sincronizacao s
    INNER JOIN (
        SELECT nomeFantasia, MAX(dataInicio) AS ultima
        FROM sincronizacao
        WHERE nomeFantasia IS NOT NULL AND nomeFantasia <> ''
        GROUP BY nomeFantasia
    ) t ON s.nomeFantasia = t.nomeFantasia AND s.dataInicio = t.ultima
"""

QUERY_ALL_LOJAS = """
    SELECT DISTINCT grupoLoja, nomeFantasia
    FROM sincronizacao
    WHERE nomeFantasia IS NOT NULL AND nomeFantasia <> ''
    ORDER BY nomeFantasia
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

    if latest.get("dataErro") is not None:
        return "erro"

    tipo = (latest.get("tipo") or "").lower()

    if "erro" in tipo:
        return "erro"

    if "enviando" in tipo or "recebendo" in tipo or "fim" in tipo or "inicio" in tipo:
        # Verifica se o evento é recente (últimas 2 horas)
        data_inicio = latest.get("dataInicio")
        if isinstance(data_inicio, str):
            try:
                data_inicio = datetime.strptime(data_inicio[:19], "%Y-%m-%d %H:%M:%S")
            except ValueError:
                return "desconhecido"
        if data_inicio:
            diferenca = datetime.now() - data_inicio
            if diferenca.total_seconds() > 7200:  # mais de 2 horas sem atualizar
                return "desconhecido"
        return "ok"

    if "open" in tipo:
        return "sincronizando"

    return "desconhecido"


def _build_group_summary(grupo: str, records: list[dict], lojas: list[str]) -> dict:
    if not records:
        return {}

    # Status individual por loja
    lojas_status = {}
    for rec in records:
        nome = rec.get("nomeFantasia") or ""
        lojas_status[nome] = _classify_status([rec])

    statuses = list(lojas_status.values())
    if "erro" in statuses:
        status = "erro"
    elif "sincronizando" in statuses:
        status = "sincronizando"
    elif "ok" in statuses:
        status = "ok"
    else:
        status = "desconhecido"

    latest = max(records, key=lambda r: r.get("dataInicio") or "")
    timestamps = [latest.get("dataFim"), latest.get("dataStart"), latest.get("dataInicio")]
    ultima_atualizacao = next((_fmt_dt(t) for t in timestamps if t), None)

    # Monta lista de lojas com status individual
    lojas_detalhadas = []
    for nome in sorted(lojas):
        lojas_detalhadas.append({
            "nome":   nome,
            "status": lojas_status.get(nome, "desconhecido"),
        })

    return {
        "grupo_loja":         grupo,
        "nome_fantasia":      grupo,
        "lojas":              lojas_detalhadas,
        "status":             status,
        "mensagem":           latest.get("tipo", ""),
        "erro":               _fmt_dt(latest.get("dataErro")),
        "versao":             latest.get("versaoFL", ""),
        "ultima_atualizacao": ultima_atualizacao,
    }


def get_all_stores_status() -> list[dict]:
    conn = get_connection()
    try:
        cursor = conn.cursor()

        cursor.execute(QUERY_ALL_STORES)
        rows = cursor.fetchall()
        latest_records = [_row_to_dict(cursor, r) for r in rows]

        cursor.execute(QUERY_ALL_LOJAS)
        rows2 = cursor.fetchall()
        cols2 = [col[0] for col in cursor.description]
        all_lojas = [dict(zip(cols2, r)) for r in rows2]
    finally:
        conn.close()

    grupos_records: dict[str, list[dict]] = {}
    for rec in latest_records:
        nome = rec.get("nomeFantasia") or ""
        grupo = _detectar_grupo(nome)
        grupos_records.setdefault(grupo, []).append(rec)

    grupos_lojas: dict[str, set] = {}
    for l in all_lojas:
        nome = l.get("nomeFantasia") or ""
        grupo = _detectar_grupo(nome)
        grupos_lojas.setdefault(grupo, set()).add(nome)

    result = []
    for grupo, records in grupos_records.items():
        lojas = list(grupos_lojas.get(grupo, set()))
        result.append(_build_group_summary(grupo, records, lojas))

    result.sort(key=lambda x: x["grupo_loja"])
    return result


def get_store_detail(grupo: str) -> dict:
    conn = get_connection()
    try:
        cursor = conn.cursor()

        cursor.execute(QUERY_ALL_LOJAS)
        rows = cursor.fetchall()
        cols = [col[0] for col in cursor.description]
        all_lojas = [dict(zip(cols, r)) for r in rows]

        lojas_do_grupo = [
            l["nomeFantasia"] for l in all_lojas
            if _detectar_grupo(l.get("nomeFantasia") or "") == grupo
        ]

        if not lojas_do_grupo:
            return {"grupo_loja": grupo, "registros": [], "status": "desconhecido", "lojas": []}

        placeholders = ", ".join(["?" for _ in lojas_do_grupo])
        query = f"""
            SELECT TOP 200
                id, idEmpresa, nomeFantasia, tempo, grupoLoja,
                dataInicio, dataFim, dataStart, dataErro, versaoFL, descricao, tipo
            FROM sincronizacao
            WHERE nomeFantasia IN ({placeholders})
            ORDER BY dataInicio DESC
        """
        cursor.execute(query, lojas_do_grupo)
        rows = cursor.fetchall()
        records = [_row_to_dict(cursor, r) for r in rows]
    finally:
        conn.close()

    for rec in records:
        for field in ("dataInicio", "dataFim", "dataStart", "dataErro"):
            rec[field] = _fmt_dt(rec.get(field))

    status_records = [_classify_status([r]) for r in records[:len(lojas_do_grupo)]]
    if "erro" in status_records:
        status = "erro"
    elif "sincronizando" in status_records:
        status = "sincronizando"
    else:
        status = "ok"

    latest = records[0] if records else {}
    timestamps = [latest.get("dataFim"), latest.get("dataStart"), latest.get("dataInicio")]
    ultima_atualizacao = next((_fmt_dt(t) for t in timestamps if t), None)

    return {
        "grupo_loja":         grupo,
        "nome_fantasia":      grupo,
        "lojas":              sorted(lojas_do_grupo),
        "status":             status,
        "mensagem":           latest.get("tipo", ""),
        "erro":               _fmt_dt(latest.get("dataErro")),
        "versao":             latest.get("versaoFL", ""),
        "ultima_atualizacao": ultima_atualizacao,
        "registros":          records,
    }


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


def get_chart_data(grupo: str | None = None) -> list[dict]:
    conn = get_connection()
    try:
        cursor = conn.cursor()

        if grupo:
            cursor.execute(QUERY_ALL_LOJAS)
            rows = cursor.fetchall()
            cols = [col[0] for col in cursor.description]
            all_lojas = [dict(zip(cols, r)) for r in rows]
            lojas_do_grupo = [
                l["nomeFantasia"] for l in all_lojas
                if _detectar_grupo(l.get("nomeFantasia") or "") == grupo
            ]
            if not lojas_do_grupo:
                return []
            placeholders = ", ".join(["?" for _ in lojas_do_grupo])
            query = f"""
                SELECT nomeFantasia, CAST(dataInicio AS DATE) AS data,
                       COUNT(*) AS total_sincronizacoes,
                       SUM(CASE WHEN dataErro IS NOT NULL THEN 1 ELSE 0 END) AS total_erros
                FROM sincronizacao
                WHERE nomeFantasia IN ({placeholders}) AND dataInicio IS NOT NULL
                GROUP BY nomeFantasia, CAST(dataInicio AS DATE)
                ORDER BY data DESC
            """
            cursor.execute(query, lojas_do_grupo)
        else:
            query = """
                SELECT nomeFantasia, CAST(dataInicio AS DATE) AS data,
                       COUNT(*) AS total_sincronizacoes,
                       SUM(CASE WHEN dataErro IS NOT NULL THEN 1 ELSE 0 END) AS total_erros
                FROM sincronizacao
                WHERE dataInicio IS NOT NULL
                GROUP BY nomeFantasia, CAST(dataInicio AS DATE)
                ORDER BY data DESC
            """
            cursor.execute(query)

        rows = cursor.fetchall()
        records = [_row_to_dict(cursor, r) for r in rows]
    finally:
        conn.close()

    for rec in records:
        rec["data"] = str(rec["data"]) if rec.get("data") else None

    return records