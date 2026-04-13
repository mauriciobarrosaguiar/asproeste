from datetime import datetime
from pathlib import Path
import sys

APP_DIR = Path(__file__).resolve().parents[1]
if str(APP_DIR) not in sys.path:
    sys.path.append(str(APP_DIR))

import pandas as pd
import streamlit as st

from database.db import execute, fetch_all, fetch_one, insert, record_log
from services.auth import hash_password, require_auth
from services.utils import (
    bootstrap_page,
    format_date,
    generate_username,
    render_page_header,
    render_sidebar,
    validate_cpf,
    validate_email,
    validate_phone,
)


def build_unique_username(name: str, lot: str, ignore_id: int | None = None) -> str:
    base_username = generate_username(name, lot)
    candidate = base_username
    counter = 2

    while True:
        existing = fetch_one("SELECT id FROM associados WHERE usuario = ?", (candidate,))
        if not existing or existing["id"] == ignore_id:
            return candidate
        candidate = f"{base_username}.{counter}"
        counter += 1


def list_associates(search_term: str = "", status_filter: str = "todos", type_filter: str = "todos") -> list[dict]:
    query = """
        SELECT id, nome, cpf, telefone, email, lote, endereco, usuario, tipo, status, data_cadastro
        FROM associados
        WHERE 1 = 1
    """
    params: list = []

    if search_term:
        query += " AND (LOWER(nome) LIKE ? OR LOWER(usuario) LIKE ? OR LOWER(COALESCE(lote, '')) LIKE ?)"
        pattern = f"%{search_term.lower()}%"
        params.extend([pattern, pattern, pattern])

    if status_filter != "todos":
        query += " AND status = ?"
        params.append(status_filter)

    if type_filter != "todos":
        query += " AND tipo = ?"
        params.append(type_filter)

    query += " ORDER BY nome"
    return fetch_all(query, tuple(params))


bootstrap_page("Associados", "👥")
user = require_auth("admin")
render_sidebar(user, "pages/associados.py")
render_page_header("Gestão de Associados", "Cadastre, edite, filtre e acompanhe os acessos dos membros da associação.")

all_associates = list_associates()
tabs = st.tabs(["Novo cadastro", "Gerenciar cadastro", "Listagem"])

with tabs[0]:
    st.subheader("Cadastro completo")
    with st.form("create_associate_form", clear_on_submit=True):
        col1, col2 = st.columns(2)
        name = col1.text_input("Nome completo *")
        cpf = col2.text_input("CPF")
        phone = col1.text_input("Telefone")
        email = col2.text_input("Email")
        lot = col1.text_input("Lote")
        address = col2.text_area("Endereço", height=96)
        access_type = col1.selectbox("Tipo de acesso", ["usuario", "admin"], index=0)
        status = col2.selectbox("Status", ["ativo", "inativo"], index=0)
        password = st.text_input("Senha inicial", type="password", placeholder="Deixe em branco para usar 123456")
        submitted = st.form_submit_button("Cadastrar associado", type="primary", use_container_width=True)

    if submitted:
        if not name.strip():
            st.error("Informe o nome do associado.")
        elif not validate_cpf(cpf):
            st.error("CPF inválido.")
        elif not validate_email(email):
            st.error("Email inválido.")
        elif not validate_phone(phone):
            st.error("Telefone inválido.")
        else:
            generated_username = build_unique_username(name, lot)
            password_hash = hash_password(password or "123456")
            insert(
                """
                INSERT INTO associados (
                    nome, cpf, telefone, email, lote, endereco,
                    usuario, senha_hash, tipo, status, data_cadastro
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    name.strip(),
                    cpf.strip(),
                    phone.strip(),
                    email.strip().lower(),
                    lot.strip(),
                    address.strip(),
                    generated_username,
                    password_hash,
                    access_type,
                    status,
                    datetime.now().date().isoformat(),
                ),
            )
            record_log(user["id"], f"Associado cadastrado: {name.strip()} ({generated_username})")
            st.success(f"Cadastro concluído com sucesso. Usuário gerado: {generated_username}")
            st.rerun()

with tabs[1]:
    st.subheader("Edição, senha e exclusão")
    if not all_associates:
        st.info("Nenhum associado cadastrado ainda.")
    else:
        associate_options = {f"{associate['nome']} | {associate['usuario']} | #{associate['id']}": associate for associate in all_associates}
        selected_label = st.selectbox("Selecione o cadastro", options=list(associate_options.keys()))
        selected_associate = associate_options[selected_label]

        with st.form("edit_associate_form"):
            col1, col2 = st.columns(2)
            edit_name = col1.text_input("Nome completo *", value=selected_associate["nome"])
            edit_cpf = col2.text_input("CPF", value=selected_associate["cpf"])
            edit_phone = col1.text_input("Telefone", value=selected_associate["telefone"])
            edit_email = col2.text_input("Email", value=selected_associate["email"])
            edit_lot = col1.text_input("Lote", value=selected_associate["lote"])
            edit_username = col2.text_input("Usuário", value=selected_associate["usuario"])
            edit_address = st.text_area("Endereço", value=selected_associate["endereco"], height=100)
            col3, col4 = st.columns(2)
            edit_type = col3.selectbox("Tipo de acesso", ["usuario", "admin"], index=0 if selected_associate["tipo"] == "usuario" else 1)
            edit_status = col4.selectbox("Status", ["ativo", "inativo"], index=0 if selected_associate["status"] == "ativo" else 1)
            save_changes = st.form_submit_button("Salvar alterações", type="primary", use_container_width=True)

        if save_changes:
            if not edit_name.strip():
                st.error("Informe o nome do associado.")
            elif not validate_cpf(edit_cpf):
                st.error("CPF inválido.")
            elif not validate_email(edit_email):
                st.error("Email inválido.")
            elif not validate_phone(edit_phone):
                st.error("Telefone inválido.")
            else:
                existing_user = fetch_one("SELECT id FROM associados WHERE usuario = ? AND id != ?", (edit_username.strip().lower(), selected_associate["id"]))
                if existing_user:
                    st.error("Já existe outro cadastro com esse usuário.")
                else:
                    execute(
                        """
                        UPDATE associados
                        SET nome = ?, cpf = ?, telefone = ?, email = ?, lote = ?, endereco = ?, usuario = ?, tipo = ?, status = ?
                        WHERE id = ?
                        """,
                        (
                            edit_name.strip(),
                            edit_cpf.strip(),
                            edit_phone.strip(),
                            edit_email.strip().lower(),
                            edit_lot.strip(),
                            edit_address.strip(),
                            edit_username.strip().lower(),
                            edit_type,
                            edit_status,
                            selected_associate["id"],
                        ),
                    )
                    record_log(user["id"], f"Cadastro atualizado: {edit_name.strip()} (#{selected_associate['id']})")
                    st.success("Cadastro atualizado com sucesso.")
                    st.rerun()

        reset_col, delete_col = st.columns(2)
        with reset_col:
            st.markdown("#### Reset de senha")
            new_password = st.text_input("Nova senha", type="password", key=f"reset_pwd_{selected_associate['id']}")
            if st.button("Redefinir senha", use_container_width=True, key=f"reset_btn_{selected_associate['id']}"):
                target_password = new_password or "123456"
                execute(
                    "UPDATE associados SET senha_hash = ? WHERE id = ?",
                    (hash_password(target_password), selected_associate["id"]),
                )
                record_log(user["id"], f"Senha redefinida para o usuário #{selected_associate['id']}")
                st.success(f"Senha redefinida com sucesso. Senha aplicada: {target_password}")

        with delete_col:
            st.markdown("#### Exclusão")
            confirm_delete = st.checkbox("Confirmo que desejo excluir este cadastro", key=f"confirm_delete_{selected_associate['id']}")
            if st.button("Excluir cadastro", use_container_width=True, key=f"delete_btn_{selected_associate['id']}"):
                if selected_associate["id"] == user["id"]:
                    st.error("Não é permitido excluir o usuário atualmente autenticado.")
                elif not confirm_delete:
                    st.warning("Marque a confirmação para concluir a exclusão.")
                else:
                    linked_payments = fetch_one("SELECT COUNT(*) AS total FROM pagamentos WHERE associado_id = ?", (selected_associate["id"],))
                    if linked_payments and linked_payments["total"] > 0:
                        st.warning("Este cadastro possui pagamentos vinculados. Altere o status para inativo em vez de excluir.")
                    else:
                        execute("DELETE FROM associados WHERE id = ?", (selected_associate["id"],))
                        record_log(user["id"], f"Cadastro excluído: #{selected_associate['id']}")
                        st.success("Cadastro removido com sucesso.")
                        st.rerun()

with tabs[2]:
    st.subheader("Busca e filtros")
    filter_col1, filter_col2, filter_col3 = st.columns([1.4, 1, 1])
    search_term = filter_col1.text_input("Buscar por nome, usuário ou lote")
    status_filter = filter_col2.selectbox("Status", ["todos", "ativo", "inativo"])
    type_filter = filter_col3.selectbox("Tipo", ["todos", "usuario", "admin"])
    filtered_associates = list_associates(search_term, status_filter, type_filter)

    if not filtered_associates:
        st.info("Nenhum associado encontrado com os filtros informados.")
    else:
        dataframe = pd.DataFrame(filtered_associates)
        dataframe["data_cadastro"] = dataframe["data_cadastro"].apply(format_date)
        dataframe = dataframe.rename(
            columns={
                "id": "ID",
                "nome": "Nome",
                "cpf": "CPF",
                "telefone": "Telefone",
                "email": "Email",
                "lote": "Lote",
                "endereco": "Endereço",
                "usuario": "Usuário",
                "tipo": "Tipo",
                "status": "Status",
                "data_cadastro": "Cadastro",
            }
        )
        st.dataframe(dataframe, use_container_width=True, hide_index=True)
