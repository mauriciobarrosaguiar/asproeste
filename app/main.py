import streamlit as st
from services.auth import current_user, is_authenticated
from services.utils import bootstrap_page

bootstrap_page("Inicial", "🏡")

# 🔥 COLOCA O CSS AQUI (DEPOIS DO bootstrap)
st.markdown("""
<style>

/* SIDEBAR FUNDO */
section[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #1b4332, #2d6a4f);
}

/* BOTÕES DO MENU */
button[kind="secondary"] {
    background-color: #2f855a !important;
    color: white !important;
    border-radius: 10px;
    height: 50px;
    font-weight: bold;
}

/* HOVER */
button[kind="secondary"]:hover {
    background-color: #276749 !important;
    color: white !important;
}

/* TEXTO SEMPRE VISÍVEL */
button {
    color: white !important;
}

</style>
""", unsafe_allow_html=True)

if not is_authenticated():
    st.switch_page("pages/login.py")

user = current_user()
if user and user.get("tipo") == "admin":
    st.switch_page("pages/dashboard.py")

st.switch_page("pages/painel_associado.py")
