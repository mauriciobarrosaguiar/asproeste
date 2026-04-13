from pathlib import Path
import sys

APP_DIR = Path(__file__).resolve().parents[1]
if str(APP_DIR) not in sys.path:
    sys.path.append(str(APP_DIR))

import streamlit as st

from services.auth import current_user, is_authenticated, login_user
from services.utils import bootstrap_page

bootstrap_page("Login", "🔐")

if is_authenticated():
    user = current_user()
    destination = "pages/dashboard.py" if user and user.get("tipo") == "admin" else "pages/painel_associado.py"
    st.switch_page(destination)

left, center, right = st.columns([1.1, 1.2, 1.1])
with center:
    st.markdown(
        """
        <div class="login-hero">
            <h1>Gestão Associação</h1>
            <p>Plataforma integrada para financeiro, comunicação, reuniões e gestão dos associados.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.markdown("<div class='login-panel'>", unsafe_allow_html=True)
    with st.form("login_form", clear_on_submit=False):
        username = st.text_input("Usuário", placeholder="Digite seu usuário")
        password = st.text_input("Senha", type="password", placeholder="Digite sua senha")
        submitted = st.form_submit_button("Entrar", use_container_width=True, type="primary")

    if submitted:
        if not username.strip() or not password.strip():
            st.error("Informe usuário e senha para acessar o sistema.")
        else:
            authenticated, message = login_user(username=username, password=password)
            if authenticated:
                st.success(message)
                destination = "pages/dashboard.py" if current_user().get("tipo") == "admin" else "pages/painel_associado.py"
                st.switch_page(destination)
            else:
                st.error(message)

    st.info("Acesso inicial: usuário `admin` e senha `123456`.")
    st.markdown("</div>", unsafe_allow_html=True)
