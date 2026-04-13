from datetime import date
from pathlib import Path
import sys

APP_DIR = Path(__file__).resolve().parents[1]
if str(APP_DIR) not in sys.path:
    sys.path.append(str(APP_DIR))

import pandas as pd
import streamlit as st

from database.db import fetch_all
from services.auth import require_auth
from services.pagamentos import (
    create_bulk_monthly_payments,
    create_payment,
    get_financial_summary,
    get_monthly_revenue_chart,
    get_open_payments,
    get_status_distribution,
    list_payments,
    mark_payment_as_paid,
)
from services.utils import bootstrap_page, format_currency, format_date, render_page_header, render_sidebar, save_uploaded_file

bootstrap_page("Financeiro", "💰")
user = require_auth("admin")
render_sidebar(user, "pages/financeiro.py")
render_page_header("Gestão Financeira", "Crie cobranças, faça baixas, acompanhe inadimplência e consolide a arrecadação.")

active_associates = fetch_all(
    """
    SELECT id, nome, lote
    FROM associados
    WHERE status = 'ativo' AND tipo = 'usuario'
    ORDER BY nome
    """
)
associate_options = {f"{associate['nome']} - Lote {associate['lote'] or '-'}": associate["id"] for associate in active_associates}

tabs = st.tabs(["Dashboard financeiro", "Cobrança individual", "Cobrança em lote", "Baixa manual", "Histórico"])

with tabs[0]:
    summary = get_financial_summary()
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Recebido no mês", format_currency(summary["recebido_mes"]))
    col2.metric("Em aberto", format_currency(summary["em_aberto"]))
    col3.metric("Inadimplentes", summary["inadimplentes"])
    col4.metric("Títulos quitados", summary["pagamentos_pagos"])

    chart_left, chart_right = st.columns([1.5, 1])
    with chart_left:
        st.subheader("Evolução mensal")
        monthly_rows = get_monthly_revenue_chart()
        monthly_df = pd.DataFrame(monthly_rows)
        if monthly_df.empty:
            st.info("Cadastre cobranças para visualizar a evolução mensal.")
        else:
            monthly_df["Mês"] = monthly_df["referencia"].str.slice(5, 7) + "/" + monthly_df["referencia"].str.slice(0, 4)
            chart_df = monthly_df.set_index("Mês")[["arrecadado", "previsto"]].rename(
                columns={"arrecadado": "Arrecadado", "previsto": "Previsto"}
            )
            st.area_chart(chart_df, use_container_width=True)

    with chart_right:
        st.subheader("Distribuição por status")
        status_df = pd.DataFrame(get_status_distribution())
        if status_df.empty:
            st.info("Sem pagamentos cadastrados.")
        else:
            status_df["status"] = status_df["status"].str.capitalize()
            st.bar_chart(status_df.set_index("status"), use_container_width=True)

with tabs[1]:
    st.subheader("Criar cobrança individual")
    if not associate_options:
        st.warning("Cadastre associados ativos para começar a gerar cobranças.")
    else:
        with st.form("single_charge_form", clear_on_submit=True):
            associate_label = st.selectbox("Associado", list(associate_options.keys()))
            amount = st.number_input("Valor da cobrança", min_value=0.0, step=10.0, format="%.2f")
            due_date = st.date_input("Data de vencimento", value=date.today())
            observation = st.text_area("Observação", value="Mensalidade da associação", height=100)
            submitted = st.form_submit_button("Criar cobrança", use_container_width=True, type="primary")

        if submitted:
            if amount <= 0:
                st.error("Informe um valor válido para a cobrança.")
            else:
                payment_id = create_payment(
                    associado_id=associate_options[associate_label],
                    valor=float(amount),
                    data_vencimento=due_date.isoformat(),
                    observacao=observation,
                    created_by=user["id"],
                )
                st.success(f"Cobrança criada com sucesso. ID do pagamento: {payment_id}")
                st.rerun()

with tabs[2]:
    st.subheader("Gerar mensalidades em lote")
    if not active_associates:
        st.warning("Não existem associados ativos para a geração em lote.")
    else:
        default_selection = list(associate_options.keys())
        with st.form("bulk_charge_form"):
            selected_labels = st.multiselect("Associados contemplados", options=list(associate_options.keys()), default=default_selection)
            bulk_amount = st.number_input("Valor padrão da mensalidade", min_value=0.0, step=10.0, format="%.2f", key="bulk_amount")
            bulk_due_date = st.date_input("Vencimento da mensalidade", value=date.today(), key="bulk_due_date")
            bulk_observation = st.text_input("Descrição", value="Mensalidade automática da associação")
            bulk_submit = st.form_submit_button("Gerar cobranças em lote", type="primary", use_container_width=True)

        if bulk_submit:
            if bulk_amount <= 0:
                st.error("Informe um valor válido para a mensalidade.")
            elif not selected_labels:
                st.error("Selecione ao menos um associado.")
            else:
                result = create_bulk_monthly_payments(
                    associado_ids=[associate_options[label] for label in selected_labels],
                    valor=float(bulk_amount),
                    data_vencimento=bulk_due_date.isoformat(),
                    observacao=bulk_observation,
                    created_by=user["id"],
                )
                st.success(
                    f"Geração concluída: {result['criados']} cobranças criadas e {result['ignorados']} ignoradas por já existirem no mês."
                )
                st.rerun()

with tabs[3]:
    st.subheader("Baixa manual de pagamento")
    open_payments = get_open_payments()
    if not open_payments:
        st.success("Não há pagamentos pendentes ou atrasados neste momento.")
    else:
        payment_options = {
            (
                f"#{payment['id']} | {payment['associado_nome']} | "
                f"Venc.: {format_date(payment['data_vencimento'])} | {format_currency(payment['valor'])}"
            ): payment
            for payment in open_payments
        }
        selected_payment_label = st.selectbox("Selecione o pagamento", options=list(payment_options.keys()))
        selected_payment = payment_options[selected_payment_label]

        with st.form("manual_payment_form", clear_on_submit=True):
            payment_date = st.date_input("Data do pagamento", value=date.today())
            payment_method = st.selectbox("Forma de pagamento", ["pix", "dinheiro", "transferencia"])
            payment_observation = st.text_area("Observação da baixa", height=100)
            receipt_file = st.file_uploader("Comprovante (opcional)", type=["pdf", "png", "jpg", "jpeg"], key="manual_receipt")
            confirm_payment = st.form_submit_button("Registrar pagamento", type="primary", use_container_width=True)

        if confirm_payment:
            receipt_path = save_uploaded_file(receipt_file, "comprovantes") if receipt_file else None
            updated = mark_payment_as_paid(
                payment_id=selected_payment["id"],
                payment_date=payment_date.isoformat(),
                payment_method=payment_method,
                observation=payment_observation,
                receipt_path=receipt_path,
                user_id=user["id"],
            )
            if updated:
                st.success("Baixa manual registrada com sucesso.")
                st.rerun()
            else:
                st.error("Não foi possível atualizar o pagamento selecionado.")

with tabs[4]:
    st.subheader("Histórico financeiro")
    history_col1, history_col2, history_col3 = st.columns([1.2, 1, 1.1])
    search_term = history_col1.text_input("Buscar por associado ou observação")
    status_filter = history_col2.selectbox("Status", ["todos", "pendente", "pago", "atrasado"])
    associate_filter = history_col3.selectbox("Associado", ["todos"] + list(associate_options.keys()))

    selected_associate_id = None if associate_filter == "todos" else associate_options[associate_filter]
    payments = list_payments(status=status_filter, associado_id=selected_associate_id, search_term=search_term)
    if not payments:
        st.info("Nenhum pagamento encontrado com os filtros aplicados.")
    else:
        history_df = pd.DataFrame(payments)
        history_df["valor"] = history_df["valor"].apply(format_currency)
        history_df["data_vencimento"] = history_df["data_vencimento"].apply(format_date)
        history_df["data_pagamento"] = history_df["data_pagamento"].apply(format_date)
        history_df = history_df[
            ["id", "associado_nome", "associado_lote", "valor", "status", "data_vencimento", "data_pagamento", "forma_pagamento", "observacao"]
        ].rename(
            columns={
                "id": "ID",
                "associado_nome": "Associado",
                "associado_lote": "Lote",
                "valor": "Valor",
                "status": "Status",
                "data_vencimento": "Vencimento",
                "data_pagamento": "Pagamento",
                "forma_pagamento": "Forma",
                "observacao": "Observação",
            }
        )
        st.dataframe(history_df, use_container_width=True, hide_index=True)
