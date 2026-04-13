from __future__ import annotations

from datetime import date

from database.db import execute, execute_many, fetch_all, fetch_one, insert, record_log
from services.utils import save_uploaded_file


def update_overdue_payments() -> int:
    overdue_rows = fetch_all(
        """
        SELECT id
        FROM pagamentos
        WHERE status = 'pendente'
          AND data_pagamento IS NULL
          AND date(data_vencimento) < date('now', 'localtime')
        """
    )
    if not overdue_rows:
        return 0

    execute_many("UPDATE pagamentos SET status = 'atrasado' WHERE id = ?", [(row["id"],) for row in overdue_rows])
    return len(overdue_rows)


def create_payment(
    associado_id: int,
    valor: float,
    data_vencimento: str,
    observacao: str = "",
    created_by: int | None = None,
) -> int:
    payment_id = insert(
        """
        INSERT INTO pagamentos (
            associado_id,
            valor,
            data_vencimento,
            status,
            observacao
        )
        VALUES (?, ?, ?, 'pendente', ?)
        """,
        (associado_id, valor, data_vencimento, observacao.strip()),
    )
    if created_by:
        record_log(created_by, f"Cobrança individual criada para associado #{associado_id}")
    return payment_id


def create_bulk_monthly_payments(
    associado_ids: list[int],
    valor: float,
    data_vencimento: str,
    observacao: str,
    created_by: int | None = None,
) -> dict[str, int]:
    if not associado_ids:
        return {"criados": 0, "ignorados": 0}

    month_reference = data_vencimento[:7]
    created_count = 0
    skipped_count = 0

    for associado_id in associado_ids:
        existing_payment = fetch_one(
            """
            SELECT id
            FROM pagamentos
            WHERE associado_id = ?
              AND strftime('%Y-%m', data_vencimento) = ?
            LIMIT 1
            """,
            (associado_id, month_reference),
        )
        if existing_payment:
            skipped_count += 1
            continue

        create_payment(
            associado_id=associado_id,
            valor=valor,
            data_vencimento=data_vencimento,
            observacao=observacao,
            created_by=created_by,
        )
        created_count += 1

    if created_by and created_count:
        record_log(created_by, f"Geração em lote concluída: {created_count} cobranças criadas")

    return {"criados": created_count, "ignorados": skipped_count}


def mark_payment_as_paid(
    payment_id: int,
    payment_date: str,
    payment_method: str,
    observation: str = "",
    receipt_path: str | None = None,
    user_id: int | None = None,
) -> int:
    updated_rows = execute(
        """
        UPDATE pagamentos
        SET data_pagamento = ?,
            status = 'pago',
            forma_pagamento = ?,
            observacao = ?,
            comprovante_path = COALESCE(?, comprovante_path)
        WHERE id = ?
        """,
        (payment_date, payment_method, observation.strip(), receipt_path, payment_id),
    )
    if user_id and updated_rows:
        record_log(user_id, f"Pagamento #{payment_id} baixado manualmente")
    return updated_rows


def attach_receipt(payment_id: int, uploaded_file, user_id: int | None = None) -> str | None:
    receipt_path = save_uploaded_file(uploaded_file, "comprovantes")
    if not receipt_path:
        return None

    execute(
        "UPDATE pagamentos SET comprovante_path = ? WHERE id = ?",
        (receipt_path, payment_id),
    )
    if user_id:
        record_log(user_id, f"Comprovante anexado ao pagamento #{payment_id}")
    return receipt_path


def get_financial_summary() -> dict:
    received_month = fetch_one(
        """
        SELECT COALESCE(SUM(valor), 0) AS total
        FROM pagamentos
        WHERE status = 'pago'
          AND strftime('%Y-%m', data_pagamento) = strftime('%Y-%m', 'now', 'localtime')
        """
    )
    pending_total = fetch_one(
        """
        SELECT COALESCE(SUM(valor), 0) AS total
        FROM pagamentos
        WHERE status IN ('pendente', 'atrasado')
        """
    )
    overdue_count = fetch_one(
        """
        SELECT COUNT(DISTINCT associado_id) AS total
        FROM pagamentos
        WHERE status = 'atrasado'
        """
    )
    paid_count = fetch_one("SELECT COUNT(*) AS total FROM pagamentos WHERE status = 'pago'")
    open_count = fetch_one("SELECT COUNT(*) AS total FROM pagamentos WHERE status IN ('pendente', 'atrasado')")

    return {
        "recebido_mes": float((received_month or {}).get("total", 0) or 0),
        "em_aberto": float((pending_total or {}).get("total", 0) or 0),
        "inadimplentes": int((overdue_count or {}).get("total", 0) or 0),
        "pagamentos_pagos": int((paid_count or {}).get("total", 0) or 0),
        "pagamentos_abertos": int((open_count or {}).get("total", 0) or 0),
    }


def get_monthly_revenue_chart(limit: int = 6) -> list[dict]:
    rows = fetch_all(
        """
        SELECT
            strftime('%Y-%m', COALESCE(data_pagamento, data_vencimento)) AS referencia,
            COALESCE(SUM(CASE WHEN status = 'pago' THEN valor ELSE 0 END), 0) AS arrecadado,
            COALESCE(SUM(valor), 0) AS previsto
        FROM pagamentos
        GROUP BY referencia
        ORDER BY referencia DESC
        LIMIT ?
        """,
        (limit,),
    )
    return list(reversed(rows))


def get_status_distribution() -> list[dict]:
    return fetch_all(
        """
        SELECT status, COUNT(*) AS total
        FROM pagamentos
        GROUP BY status
        ORDER BY status
        """
    )


def list_payments(
    status: str | None = None,
    associado_id: int | None = None,
    search_term: str = "",
) -> list[dict]:
    query = """
        SELECT
            pagamentos.*,
            associados.nome AS associado_nome,
            associados.lote AS associado_lote
        FROM pagamentos
        INNER JOIN associados ON associados.id = pagamentos.associado_id
        WHERE 1 = 1
    """
    params: list = []

    if status and status != "todos":
        query += " AND pagamentos.status = ?"
        params.append(status)

    if associado_id:
        query += " AND pagamentos.associado_id = ?"
        params.append(associado_id)

    if search_term:
        query += " AND (LOWER(associados.nome) LIKE ? OR LOWER(COALESCE(pagamentos.observacao, '')) LIKE ?)"
        pattern = f"%{search_term.lower()}%"
        params.extend([pattern, pattern])

    query += " ORDER BY pagamentos.data_vencimento DESC, pagamentos.id DESC"
    return fetch_all(query, tuple(params))


def get_associate_payments(associado_id: int) -> list[dict]:
    return fetch_all(
        """
        SELECT *
        FROM pagamentos
        WHERE associado_id = ?
        ORDER BY data_vencimento DESC, id DESC
        """,
        (associado_id,),
    )


def get_recent_financial_activity(limit: int = 10) -> list[dict]:
    return fetch_all(
        """
        SELECT
            pagamentos.id,
            associados.nome AS associado_nome,
            pagamentos.valor,
            pagamentos.status,
            pagamentos.data_vencimento,
            pagamentos.data_pagamento
        FROM pagamentos
        INNER JOIN associados ON associados.id = pagamentos.associado_id
        ORDER BY pagamentos.id DESC
        LIMIT ?
        """,
        (limit,),
    )


def get_open_payments() -> list[dict]:
    return fetch_all(
        """
        SELECT
            pagamentos.id,
            pagamentos.valor,
            pagamentos.status,
            pagamentos.data_vencimento,
            associados.nome AS associado_nome,
            associados.lote AS associado_lote
        FROM pagamentos
        INNER JOIN associados ON associados.id = pagamentos.associado_id
        WHERE pagamentos.status IN ('pendente', 'atrasado')
        ORDER BY pagamentos.data_vencimento ASC
        """
    )


def get_overdue_candidates_for_notifications() -> list[dict]:
    update_overdue_payments()
    return fetch_all(
        """
        SELECT
            pagamentos.id,
            pagamentos.valor,
            pagamentos.data_vencimento,
            associados.nome,
            associados.telefone,
            associados.email
        FROM pagamentos
        INNER JOIN associados ON associados.id = pagamentos.associado_id
        WHERE pagamentos.status = 'atrasado'
        ORDER BY pagamentos.data_vencimento ASC
        """
    )
