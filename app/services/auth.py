from __future__ import annotations

import hashlib
from typing import Iterable

import streamlit as st

from database.db import fetch_one, record_log


def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


def current_user() -> dict | None:
    return st.session_state.get("user")


def is_authenticated() -> bool:
    return bool(st.session_state.get("authenticated"))


def authenticate_user(username: str, password: str) -> dict | None:
    normalized_username = username.strip().lower()
    if not normalized_username or not password:
        return None

    user = fetch_one(
        """
        SELECT *
        FROM associados
        WHERE usuario = ? AND status = 'ativo'
        LIMIT 1
        """,
        (normalized_username,),
    )
    if not user:
        return None

    if user["senha_hash"] != hash_password(password):
        return None

    user.pop("senha_hash", None)
    return user


def login_user(username: str, password: str) -> tuple[bool, str]:
    user = authenticate_user(username, password)
    if not user:
        return False, "Usuário ou senha inválidos, ou acesso inativo."

    st.session_state["authenticated"] = True
    st.session_state["user"] = user
    record_log(user.get("id"), "Login realizado no sistema")
    return True, "Login realizado com sucesso."


def logout_user() -> None:
    user = current_user()
    if user:
        record_log(user.get("id"), "Logout realizado no sistema")

    st.session_state["authenticated"] = False
    st.session_state["user"] = None


def refresh_user_session(user_id: int) -> dict | None:
    refreshed_user = fetch_one("SELECT * FROM associados WHERE id = ?", (user_id,))
    if not refreshed_user:
        st.session_state["authenticated"] = False
        st.session_state["user"] = None
        return None

    refreshed_user.pop("senha_hash", None)
    st.session_state["user"] = refreshed_user
    return refreshed_user


def require_auth(allowed_types: str | Iterable[str] | None = None) -> dict:
    user = current_user()
    if not is_authenticated() or not user:
        st.warning("Sua sessão expirou ou ainda não foi iniciada.")
        if st.button("Ir para o login", use_container_width=True):
            st.switch_page("pages/login.py")
        st.stop()

    if allowed_types is None:
        return user

    normalized_allowed_types = {allowed_types} if isinstance(allowed_types, str) else set(allowed_types)
    if user.get("tipo") not in normalized_allowed_types:
        st.error("Você não tem permissão para acessar esta página.")
        destination = "pages/dashboard.py" if user.get("tipo") == "admin" else "pages/painel_associado.py"
        if st.button("Voltar para o painel", use_container_width=True):
            st.switch_page(destination)
        st.stop()

    return user
