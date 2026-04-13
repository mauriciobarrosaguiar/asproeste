import streamlit as st

from services.auth import current_user, is_authenticated
from services.utils import bootstrap_page

bootstrap_page("Inicial", "🏡")

if not is_authenticated():
    st.switch_page("pages/login.py")

user = current_user()
if user and user.get("tipo") == "admin":
    st.switch_page("pages/dashboard.py")

st.switch_page("pages/painel_associado.py")
