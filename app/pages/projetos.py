from pathlib import Path
import sys

APP_DIR = Path(__file__).resolve().parents[1]
if str(APP_DIR) not in sys.path:
    sys.path.append(str(APP_DIR))

import streamlit as st

from database.db import execute, fetch_all, insert, record_log
from services.auth import require_auth
from services.utils import bootstrap_page, format_currency, render_page_header, render_sidebar, status_badge

bootstrap_page("Projetos", "🏗️")
user = require_auth("admin")
render_sidebar(user, "pages/projetos.py")
render_page_header("Projetos da Associação", "Acompanhe iniciativas, arrecadação e evolução financeira de cada projeto.")

projects = fetch_all("SELECT * FROM projetos ORDER BY id DESC")
tabs = st.tabs(["Novo projeto", "Atualizar projeto", "Portfólio"])

with tabs[0]:
    with st.form("create_project_form", clear_on_submit=True):
        project_name = st.text_input("Nome do projeto *")
        description = st.text_area("Descrição", height=140)
        status = st.selectbox("Status", ["planejado", "andamento", "concluido"], index=0)
        estimated_value = st.number_input("Valor previsto", min_value=0.0, step=100.0, format="%.2f")
        raised_value = st.number_input("Valor arrecadado", min_value=0.0, step=100.0, format="%.2f")
        submitted = st.form_submit_button("Cadastrar projeto", type="primary", use_container_width=True)

    if submitted:
        if not project_name.strip():
            st.error("Informe o nome do projeto.")
        else:
            insert(
                """
                INSERT INTO projetos (nome, descricao, status, valor_previsto, valor_arrecadado)
                VALUES (?, ?, ?, ?, ?)
                """,
                (project_name.strip(), description.strip(), status, float(estimated_value), float(raised_value)),
            )
            record_log(user["id"], f"Projeto cadastrado: {project_name.strip()}")
            st.success("Projeto cadastrado com sucesso.")
            st.rerun()

with tabs[1]:
    if not projects:
        st.info("Cadastre projetos para liberar a atualização de progresso.")
    else:
        project_options = {f"{project['nome']} | {project['status']}": project for project in projects}
        selected_label = st.selectbox("Selecione o projeto", options=list(project_options.keys()))
        selected_project = project_options[selected_label]

        with st.form("update_project_form"):
            updated_name = st.text_input("Nome", value=selected_project["nome"])
            updated_description = st.text_area("Descrição", value=selected_project["descricao"] or "", height=140)
            status_index = ["planejado", "andamento", "concluido"].index(selected_project["status"])
            updated_status = st.selectbox("Status", ["planejado", "andamento", "concluido"], index=status_index)
            updated_estimated = st.number_input(
                "Valor previsto",
                min_value=0.0,
                step=100.0,
                format="%.2f",
                value=float(selected_project["valor_previsto"] or 0),
            )
            updated_raised = st.number_input(
                "Valor arrecadado",
                min_value=0.0,
                step=100.0,
                format="%.2f",
                value=float(selected_project["valor_arrecadado"] or 0),
            )
            save_project = st.form_submit_button("Salvar atualizações", type="primary", use_container_width=True)

        if save_project:
            execute(
                """
                UPDATE projetos
                SET nome = ?, descricao = ?, status = ?, valor_previsto = ?, valor_arrecadado = ?
                WHERE id = ?
                """,
                (
                    updated_name.strip(),
                    updated_description.strip(),
                    updated_status,
                    float(updated_estimated),
                    float(updated_raised),
                    selected_project["id"],
                ),
            )
            record_log(user["id"], f"Projeto atualizado: #{selected_project['id']}")
            st.success("Projeto atualizado com sucesso.")
            st.rerun()

with tabs[2]:
    if not projects:
        st.info("Nenhum projeto cadastrado ainda.")
    else:
        total_expected = sum(float(project["valor_previsto"] or 0) for project in projects)
        total_raised = sum(float(project["valor_arrecadado"] or 0) for project in projects)
        active_count = len([project for project in projects if project["status"] == "andamento"])
        c1, c2, c3 = st.columns(3)
        c1.metric("Total previsto", format_currency(total_expected))
        c2.metric("Total arrecadado", format_currency(total_raised))
        c3.metric("Projetos em andamento", active_count)

        for project in projects:
            expected = float(project["valor_previsto"] or 0)
            raised = float(project["valor_arrecadado"] or 0)
            progress = min(raised / expected, 1.0) if expected > 0 else 0.0
            with st.container(border=True):
                st.markdown(f"### {project['nome']} {status_badge(project['status'])}", unsafe_allow_html=True)
                st.write(project["descricao"] or "Sem descrição cadastrada.")
                st.progress(progress)
                st.caption(f"Arrecadado: {format_currency(raised)} de {format_currency(expected)} | Progresso: {progress * 100:.0f}%")
