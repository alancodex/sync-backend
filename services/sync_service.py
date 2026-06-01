from database.connection import get_connection
from datetime import datetime, timedelta, timezone


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
        return "inativo"

    latest = records[0]

    if latest.get("dataErro") is not None:
        return "erro"

    tipo = (latest.get("tipo") or "").lower()

    if "erro" in tipo:
        return "erro"

    if "enviando" in tipo or "recebendo" in tipo or "fim" in tipo or "inicio" in tipo:
        data_inicio = latest.get("dataInicio")
        if data_inicio:
            try:
                dt = datetime.strptime(str(data_inicio)[:19], "%Y-%m-%d %H:%M:%S")
                agora_brasil = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(hours=3)

                # Pega o tempo da loja + 10 minutos de margem
                tempo_loja = 10  # padrão caso não tenha valor
                try:
                    tempo_loja = int(latest.get("tempo") or 10)
                except (ValueError, TypeError):
                    tempo_loja = 10

                tolerancia_segundos = (tempo_loja + 10) * 60

                if (agora_brasil - dt).total_seconds() > tolerancia_segundos:
                    return "inativo"
            except ValueError:
                pass
        return "ok"

    if "open" in tipo:
        return "sincronizando"

    return "inativo"


def _build_group_summary(grupo: str, records: list[dict], lojas: list[str]) -> dict:
    if not records:
        return {}

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
        status = "inativo"

    latest = max(records, key=lambda r: r.get("dataInicio") or "")
    timestamps = [latest.get("dataFim"), latest.get("dataStart"), latest.get("dataInicio")]
    ultima_atualizacao = next((_fmt_dt(t) for t in timestamps if t), None)

    lojas_detalhadas = []
    for nome in sorted(lojas):
        lojas_detalhadas.append({
            "nome":   nome,
            "status": lojas_status.get(nome, "inativo"),
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

    for rec in latest_records:
        for field in ("dataInicio", "dataFim", "dataStart", "dataErro"):
            rec[field] = _fmt_dt(rec.get(field))

    grupos_records: dict[str, list[dict]] = {}
    for rec in latest_records:
        grupo = rec.get("grupoLoja") or "Outros"
        grupos_records.setdefault(grupo, []).append(rec)

    grupos_lojas: dict[str, set] = {}
    for l in all_lojas:
        grupo = l.get("grupoLoja") or "Outros"
        nome  = l.get("nomeFantasia") or ""
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
            if (l.get("grupoLoja") or "Outros") == grupo
        ]

        if not lojas_do_grupo:
            return {"grupo_loja": grupo, "registros": [], "status": "inativo", "lojas": []}

        # Busca TOP 100 por loja individualmente e junta tudo
        records = []
        for loja in lojas_do_grupo:
            cursor.execute("""
                SELECT TOP 4
                    id, idEmpresa, nomeFantasia, tempo, grupoLoja,
                    dataInicio, dataFim, dataStart, dataErro, versaoFL, descricao, tipo
                FROM sincronizacao
                WHERE nomeFantasia = ?
                ORDER BY dataInicio DESC
            """, (loja,))
            rows = cursor.fetchall()
            records += [_row_to_dict(cursor, r) for r in rows]

        # Ordena tudo por data decrescente
        records.sort(key=lambda r: r.get("dataInicio") or "", reverse=True)

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
    elif "ok" in status_records:
        status = "ok"
    else:
        status = "inativo"

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
                if (l.get("grupoLoja") or "Outros") == grupo
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
