from __future__ import annotations

from database.db import fetch_all
from services.pagamentos import get_overdue_candidates_for_notifications


def gerar_fila_notificacoes_financeiras() -> list[dict]:
    queue: list[dict] = []
    for row in get_overdue_candidates_for_notifications():
        queue.append(
            {
                "destinatario": row.get("nome"),
                "telefone": row.get("telefone"),
                "email": row.get("email"),
                "mensagem": (
                    f"Olá, {row.get('nome')}. Identificamos um pagamento vencido "
                    f"em {row.get('data_vencimento')} no valor de R$ {row.get('valor'):.2f}."
                ),
                "canal_sugerido": "whatsapp/email",
                "status": "pendente_integracao",
            }
        )
    return queue


def listar_comunicacoes_recentes(limit: int = 10) -> list[dict]:
    return fetch_all(
        """
        SELECT id, titulo, mensagem, data, prioridade
        FROM avisos
        ORDER BY data DESC, id DESC
        LIMIT ?
        """,
        (limit,),
    )


def enviar_notificacao_futura(destinatario: str, canal: str, mensagem: str) -> dict:
    return {
        "destinatario": destinatario,
        "canal": canal,
        "mensagem": mensagem,
        "status": "estrutura_pronta_para_integracao",
    }
