from datetime import date
from pathlib import Path
import sys

APP_DIR = Path(__file__).resolve().parents[1]
if str(APP_DIR) not in sys.path:
    sys.path.append(str(APP_DIR))

import streamlit as st

from database.db import execute, fetch_all, insert, record_log
from services.auth import require_auth
from services.utils import bootstrap_page, format_date, render_page_header, render_sidebar, status_badge

bootstrap_page("Avisos", "📣")
user = require_auth("admin")
render_sidebar(user, "pages/avisos.py")
render_page_header("Avisos e Comunicação", "Publique comunicados com prioridade e mantenha todos informados.")

notices = fetch_all("SELECT * FROM avisos ORDER BY data DESC, id DESC")
tabs = st.tabs(["Novo aviso", "Avisos publicados"])

with tabs[0]:
    with st.form("create_notice_form", clear_on_submit=True):
        title = st.text_input("Título do aviso *")
        message = st.text_area("Mensagem *", height=180)
        priority = st.selectbox("Prioridade", ["baixa", "média", "alta"], index=1)
        submitted = st.form_submit_button("Publicar aviso", type="primary", use_container_width=True)

    if submitted:
        if not title.strip() or not message.strip():
            st.error("Título e mensagem são obrigatórios.")
        else:
            insert(
                """
                INSERT INTO avisos (titulo, mensagem, data, prioridade)
                VALUES (?, ?, ?, ?)
                """,
                (title.strip(), message.strip(), date.today().isoformat(), priority),
            )
            record_log(user["id"], f"Aviso publicado: {title.strip()}")
            st.success("Aviso publicado com sucesso.")
            st.rerun()

with tabs[1]:
    filter_col1, filter_col2 = st.columns([1.4, 1])
    search_term = filter_col1.text_input("Buscar aviso")
    priority_filter = filter_col2.selectbox("Prioridade", ["todas", "baixa", "média", "alta"])

    filtered_notices = []
    for notice in notices:
        matches_search = not search_term or search_term.lower() in notice["titulo"].lower() or search_term.lower() in notice["mensagem"].lower()
        matches_priority = priority_filter == "todas" or notice["prioridade"] == priority_filter
        if matches_search and matches_priority:
            filtered_notices.append(notice)

    if not filtered_notices:
        st.info("Nenhum aviso encontrado com os filtros informados.")
    else:
        for notice in filtered_notices:
            with st.container(border=True):
                st.markdown(f"### {notice['titulo']} {status_badge(notice['prioridade'])}", unsafe_allow_html=True)
                st.caption(format_date(notice["data"]))
                st.write(notice["mensagem"])

        notice_options = {f"{notice['titulo']} | {format_date(notice['data'])}": notice["id"] for notice in filtered_notices}
        selected_notice = st.selectbox("Selecionar aviso para exclusão", options=list(notice_options.keys()))
        confirm_delete = st.checkbox("Confirmo a exclusão do aviso selecionado", key="delete_notice_confirmation")
        if st.button("Excluir aviso", use_container_width=True):
            if not confirm_delete:
                st.warning("Marque a confirmação antes de excluir o aviso.")
            else:
                execute("DELETE FROM avisos WHERE id = ?", (notice_options[selected_notice],))
                record_log(user["id"], f"Aviso excluído: {selected_notice}")
                st.success("Aviso excluído com sucesso.")
                st.rerun()
