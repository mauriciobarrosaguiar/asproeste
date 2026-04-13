from pathlib import Path
import sys

APP_DIR = Path(__file__).resolve().parents[1]
if str(APP_DIR) not in sys.path:
    sys.path.append(str(APP_DIR))

import streamlit as st

from database.db import execute, fetch_all, fetch_one, record_log
from services.auth import refresh_user_session, require_auth
from services.pagamentos import attach_receipt, get_associate_payments
from services.utils import (
    bootstrap_page,
    format_currency,
    format_date,
    render_page_header,
    render_sidebar,
    status_badge,
    validate_email,
    validate_phone,
)

bootstrap_page("Painel do Associado", "🏡")
user = require_auth({"admin", "usuario"})
render_sidebar(user, "pages/painel_associado.py")
profile = fetch_one("SELECT * FROM associados WHERE id = ?", (user["id"],))
payments = get_associate_payments(user["id"])
notices = fetch_all("SELECT * FROM avisos ORDER BY data DESC, id DESC")
meetings = fetch_all("SELECT * FROM reunioes ORDER BY data DESC, id DESC")
projects = fetch_all("SELECT * FROM projetos ORDER BY id DESC")

paid_count = len([payment for payment in payments if payment["status"] == "pago"])
pending_count = len([payment for payment in payments if payment["status"] == "pendente"])
overdue_count = len([payment for payment in payments if payment["status"] == "atrasado"])

render_page_header("Painel do Associado", "Acompanhe sua situação financeira, comunicados e reuniões sem acessar dados de outros membros.")

summary_col1, summary_col2, summary_col3 = st.columns(3)
summary_col1.metric("Pagamentos quitados", paid_count)
summary_col2.metric("Pendentes", pending_count)
summary_col3.metric("Atrasados", overdue_count)

profile_col, details_col = st.columns([1.1, 1.6])
with profile_col:
    with st.container(border=True):
        st.subheader("Dados pessoais")
        st.write(f"**Nome:** {profile['nome']}")
        st.write(f"**Usuário:** {profile['usuario']}")
        st.write(f"**Lote:** {profile['lote'] or '-'}")
        st.write(f"**CPF:** {profile['cpf'] or '-'}")
        st.write(f"**Status:** {profile['status']}")
        st.write(f"**Cadastro:** {format_date(profile['data_cadastro'])}")

with details_col:
    with st.form("update_profile_form"):
        st.subheader("Atualizar dados básicos")
        update_name = st.text_input("Nome", value=profile["nome"])
        update_phone = st.text_input("Telefone", value=profile["telefone"])
        update_email = st.text_input("Email", value=profile["email"])
        update_address = st.text_area("Endereço", value=profile["endereco"] or "", height=96)
        save_profile = st.form_submit_button("Salvar meus dados", type="primary", use_container_width=True)

    if save_profile:
        if not update_name.strip():
            st.error("O nome não pode ficar em branco.")
        elif not validate_phone(update_phone):
            st.error("Telefone inválido.")
        elif not validate_email(update_email):
            st.error("Email inválido.")
        else:
            execute(
                """
                UPDATE associados
                SET nome = ?, telefone = ?, email = ?, endereco = ?
                WHERE id = ?
                """,
                (
                    update_name.strip(),
                    update_phone.strip(),
                    update_email.strip().lower(),
                    update_address.strip(),
                    profile["id"],
                ),
            )
            record_log(profile["id"], "Dados básicos atualizados pelo associado")
            refresh_user_session(profile["id"])
            st.success("Dados atualizados com sucesso.")
            st.rerun()

tabs = st.tabs(["Pagamentos", "Avisos", "Reuniões", "Projetos"])

with tabs[0]:
    st.subheader("Histórico financeiro")
    if not payments:
        st.info("Nenhum pagamento lançado para seu cadastro.")
    else:
        for payment in payments:
            st.markdown(
                f"""
                <div class="payment-card">
                    <strong>Vencimento:</strong> {format_date(payment['data_vencimento'])}<br>
                    <strong>Valor:</strong> {format_currency(payment['valor'])}<br>
                    <strong>Status:</strong> {status_badge(payment['status'])}<br>
                    <strong>Pagamento:</strong> {format_date(payment['data_pagamento'])}<br>
                    <strong>Forma:</strong> {payment['forma_pagamento'] or '-'}<br>
                    <strong>Observação:</strong> {payment['observacao'] or 'Sem observações'}<br>
                    <strong>Comprovante:</strong> {payment['comprovante_path'] or 'Não anexado'}
                </div>
                """,
                unsafe_allow_html=True,
            )

        uploadable_payments = {
            f"#{payment['id']} | Venc. {format_date(payment['data_vencimento'])} | {format_currency(payment['valor'])}": payment["id"]
            for payment in payments
            if payment["status"] in {"pendente", "atrasado"}
        }
        st.markdown("#### Anexar comprovante")
        if not uploadable_payments:
            st.info("Não há pagamentos pendentes ou atrasados para anexar comprovantes.")
        else:
            selected_payment = st.selectbox("Pagamento", options=list(uploadable_payments.keys()))
            uploaded_receipt = st.file_uploader("Selecionar comprovante", type=["pdf", "png", "jpg", "jpeg"], key="associate_receipt")
            if st.button("Enviar comprovante", type="primary", use_container_width=True):
                if not uploaded_receipt:
                    st.error("Selecione um arquivo antes de enviar.")
                else:
                    saved_path = attach_receipt(uploadable_payments[selected_payment], uploaded_receipt, user_id=profile["id"])
                    if saved_path:
                        st.success("Comprovante anexado com sucesso. A administração poderá validar o pagamento.")
                        st.rerun()
                    else:
                        st.error("Não foi possível anexar o comprovante.")

with tabs[1]:
    if not notices:
        st.info("Nenhum aviso disponível no momento.")
    else:
        for notice in notices:
            with st.container(border=True):
                st.markdown(f"### {notice['titulo']} {status_badge(notice['prioridade'])}", unsafe_allow_html=True)
                st.caption(format_date(notice["data"]))
                st.write(notice["mensagem"])

with tabs[2]:
    if not meetings:
        st.info("Nenhuma reunião registrada ainda.")
    else:
        for meeting in meetings:
            with st.expander(f"{meeting['titulo']} | {format_date(meeting['data'])}"):
                st.write(f"**Descrição:** {meeting['descricao'] or 'Sem descrição.'}")
                st.write(f"**Ata:** {meeting['ata'] or 'Ata ainda não disponível.'}")
                st.write(f"**Presença:** {meeting['presenca'] or 'Presença não registrada.'}")

with tabs[3]:
    if not projects:
        st.info("Nenhum projeto cadastrado no momento.")
    else:
        for project in projects:
            expected = float(project["valor_previsto"] or 0)
            raised = float(project["valor_arrecadado"] or 0)
            progress = min(raised / expected, 1.0) if expected > 0 else 0.0
            with st.container(border=True):
                st.markdown(f"### {project['nome']} {status_badge(project['status'])}", unsafe_allow_html=True)
                st.write(project["descricao"] or "Sem descrição cadastrada.")
                st.progress(progress)
                st.caption(f"Arrecadado: {format_currency(raised)} de {format_currency(expected)}")
