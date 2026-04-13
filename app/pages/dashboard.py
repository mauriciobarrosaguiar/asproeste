from pathlib import Path
import sys

APP_DIR = Path(__file__).resolve().parents[1]
if str(APP_DIR) not in sys.path:
    sys.path.append(str(APP_DIR))

import pandas as pd
import streamlit as st

from database.db import fetch_all, fetch_one
from services.auth import require_auth
from services.notificacoes import gerar_fila_notificacoes_financeiras
from services.pagamentos import get_financial_summary, get_monthly_revenue_chart, get_recent_financial_activity, get_status_distribution
from services.utils import bootstrap_page, format_currency, format_date, month_label, render_page_header, render_sidebar

bootstrap_page("Dashboard", "📊")
user = require_auth("admin")
render_sidebar(user, "pages/dashboard.py")
render_page_header("Dashboard Administrativo", "Visão consolidada da operação financeira, social e administrativa da associação.")

summary = get_financial_summary()
total_associates = fetch_one("SELECT COUNT(*) AS total FROM associados WHERE tipo = 'usuario'") or {"total": 0}
active_projects = fetch_one("SELECT COUNT(*) AS total FROM projetos WHERE status = 'andamento'") or {"total": 0}
recent_logs = fetch_all(
    """
    SELECT logs.data, logs.acao, COALESCE(associados.nome, 'Sistema') AS usuario_nome
    FROM logs
    LEFT JOIN associados ON associados.id = logs.usuario_id
    ORDER BY logs.id DESC
    LIMIT 8
    """
)
recent_payments = get_recent_financial_activity(8)
notification_queue = gerar_fila_notificacoes_financeiras()

metric_columns = st.columns(4)
metric_columns[0].metric("Total de associados", int(total_associates["total"]))
metric_columns[1].metric("Arrecadado no mês", format_currency(summary["recebido_mes"]))
metric_columns[2].metric("Inadimplentes", summary["inadimplentes"])
metric_columns[3].metric("Projetos ativos", int(active_projects["total"]))

chart_left, chart_right = st.columns([1.6, 1])
with chart_left:
    st.subheader("Receita mensal")
    monthly_rows = get_monthly_revenue_chart()
    monthly_df = pd.DataFrame(monthly_rows)
    if monthly_df.empty:
        st.info("Os gráficos serão exibidos assim que houver cobranças registradas.")
    else:
        monthly_df["Mês"] = monthly_df["referencia"].apply(month_label)
        chart_df = monthly_df.set_index("Mês")[["arrecadado", "previsto"]].rename(
            columns={"arrecadado": "Arrecadado", "previsto": "Previsto"}
        )
        st.line_chart(chart_df, use_container_width=True)

with chart_right:
    st.subheader("Situação dos pagamentos")
    status_rows = get_status_distribution()
    status_df = pd.DataFrame(status_rows)
    if status_df.empty:
        st.info("Sem pagamentos cadastrados no momento.")
    else:
        status_df["status"] = status_df["status"].str.capitalize()
        st.bar_chart(status_df.set_index("status"), use_container_width=True)

alert_left, alert_right = st.columns([1.1, 1.3])
with alert_left:
    st.subheader("Monitoramento rápido")
    st.info(f"Fila preparada para futuras automações: {len(notification_queue)} notificações financeiras potenciais.")
    st.warning(f"Pagamentos em aberto: {format_currency(summary['em_aberto'])}")
    st.success(f"Pagamentos quitados registrados: {summary['pagamentos_pagos']}")

with alert_right:
    st.subheader("Resumo recente")
    quick_table = pd.DataFrame(recent_payments)
    if quick_table.empty:
        st.info("Nenhuma movimentação financeira recente.")
    else:
        quick_table["valor"] = quick_table["valor"].apply(format_currency)
        quick_table["data_vencimento"] = quick_table["data_vencimento"].apply(format_date)
        quick_table["data_pagamento"] = quick_table["data_pagamento"].apply(format_date)
        quick_table = quick_table.rename(
            columns={
                "id": "ID",
                "associado_nome": "Associado",
                "valor": "Valor",
                "status": "Status",
                "data_vencimento": "Vencimento",
                "data_pagamento": "Pagamento",
            }
        )
        st.dataframe(quick_table, use_container_width=True, hide_index=True)

tab_logs, tab_financial = st.tabs(["Atividades do sistema", "Financeiro recente"])
with tab_logs:
    logs_df = pd.DataFrame(recent_logs)
    if logs_df.empty:
        st.info("Nenhum log registrado até o momento.")
    else:
        logs_df["data"] = logs_df["data"].apply(format_date)
        logs_df = logs_df.rename(columns={"data": "Data", "acao": "Ação", "usuario_nome": "Usuário"})
        st.dataframe(logs_df, use_container_width=True, hide_index=True)

with tab_financial:
    detailed_df = pd.DataFrame(recent_payments)
    if detailed_df.empty:
        st.info("Sem pagamentos para exibir.")
    else:
        detailed_df["valor"] = detailed_df["valor"].apply(format_currency)
        detailed_df["data_vencimento"] = detailed_df["data_vencimento"].apply(format_date)
        detailed_df["data_pagamento"] = detailed_df["data_pagamento"].apply(format_date)
        detailed_df = detailed_df.rename(
            columns={
                "id": "ID",
                "associado_nome": "Associado",
                "valor": "Valor",
                "status": "Status",
                "data_vencimento": "Vencimento",
                "data_pagamento": "Pagamento",
            }
        )
        st.dataframe(detailed_df, use_container_width=True, hide_index=True)
