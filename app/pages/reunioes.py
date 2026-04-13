from datetime import date
from pathlib import Path
import sys

APP_DIR = Path(__file__).resolve().parents[1]
if str(APP_DIR) not in sys.path:
    sys.path.append(str(APP_DIR))

import streamlit as st

from database.db import execute, fetch_all, insert, record_log
from services.auth import require_auth
from services.utils import bootstrap_page, format_date, render_page_header, render_sidebar, save_uploaded_file

bootstrap_page("Reuniões", "📝")
user = require_auth("admin")
render_sidebar(user, "pages/reunioes.py")
render_page_header("Gestão de Reuniões", "Registre pautas, atas e presença das assembleias com rastreabilidade.")

meetings = fetch_all("SELECT * FROM reunioes ORDER BY data DESC, id DESC")
associate_rows = fetch_all("SELECT nome, lote FROM associados WHERE tipo = 'usuario' AND status = 'ativo' ORDER BY nome")
associate_names = [f"{row['nome']} - Lote {row['lote'] or '-'}" for row in associate_rows]

tabs = st.tabs(["Nova reunião", "Gestão da reunião", "Histórico"])

with tabs[0]:
    with st.form("create_meeting_form", clear_on_submit=True):
        title = st.text_input("Título da reunião *")
        meeting_date = st.date_input("Data", value=date.today())
        description = st.text_area("Descrição / pauta", height=140)
        submitted = st.form_submit_button("Criar reunião", use_container_width=True, type="primary")

    if submitted:
        if not title.strip():
            st.error("Informe o título da reunião.")
        else:
            insert(
                """
                INSERT INTO reunioes (titulo, data, descricao, ata, presenca)
                VALUES (?, ?, ?, '', '')
                """,
                (title.strip(), meeting_date.isoformat(), description.strip()),
            )
            record_log(user["id"], f"Reunião criada: {title.strip()}")
            st.success("Reunião cadastrada com sucesso.")
            st.rerun()

with tabs[1]:
    if not meetings:
        st.info("Nenhuma reunião cadastrada ainda.")
    else:
        meeting_options = {f"{meeting['titulo']} | {format_date(meeting['data'])}": meeting for meeting in meetings}
        selected_label = st.selectbox("Selecione a reunião", list(meeting_options.keys()))
        selected_meeting = meeting_options[selected_label]
        current_presence = [item.strip() for item in (selected_meeting["presenca"] or "").split(",") if item.strip()]

        with st.form("manage_meeting_form"):
            managed_title = st.text_input("Título", value=selected_meeting["titulo"])
            managed_date = st.date_input("Data", value=date.fromisoformat(selected_meeting["data"]))
            managed_description = st.text_area("Descrição / pauta", value=selected_meeting["descricao"] or "", height=120)
            managed_minutes = st.text_area("Ata", value=selected_meeting["ata"] or "", height=180)
            managed_presence = st.multiselect("Registro de presença", options=associate_names, default=current_presence)
            minutes_file = st.file_uploader("Anexar arquivo da ata (opcional)", type=["pdf", "doc", "docx", "png", "jpg", "jpeg"])
            save_meeting = st.form_submit_button("Salvar reunião", type="primary", use_container_width=True)

        if save_meeting:
            attachment_path = save_uploaded_file(minutes_file, "atas") if minutes_file else None
            final_minutes = managed_minutes.strip()
            if attachment_path:
                final_minutes = f"{final_minutes}\n\nArquivo da ata: {attachment_path}".strip()

            execute(
                """
                UPDATE reunioes
                SET titulo = ?, data = ?, descricao = ?, ata = ?, presenca = ?
                WHERE id = ?
                """,
                (
                    managed_title.strip(),
                    managed_date.isoformat(),
                    managed_description.strip(),
                    final_minutes,
                    ", ".join(managed_presence),
                    selected_meeting["id"],
                ),
            )
            record_log(user["id"], f"Reunião atualizada: #{selected_meeting['id']}")
            st.success("Dados da reunião atualizados com sucesso.")
            st.rerun()

with tabs[2]:
    if not meetings:
        st.info("Ainda não existem reuniões para listar.")
    else:
        for meeting in meetings:
            with st.expander(f"{meeting['titulo']} | {format_date(meeting['data'])}", expanded=False):
                st.write(f"**Descrição:** {meeting['descricao'] or 'Sem descrição cadastrada.'}")
                st.write(f"**Presença:** {meeting['presenca'] or 'Sem presença registrada.'}")
                st.write(f"**Ata:** {meeting['ata'] or 'Ata ainda não preenchida.'}")
