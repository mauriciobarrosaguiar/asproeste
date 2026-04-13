from __future__ import annotations

import re
import secrets
import unicodedata
from datetime import date, datetime
from pathlib import Path

import streamlit as st

APP_DIR = Path(__file__).resolve().parents[1]
ASSETS_DIR = APP_DIR / "assets"
UPLOAD_DIR = ASSETS_DIR / "uploads"
UPLOAD_MAP = {
    "comprovantes": UPLOAD_DIR / "comprovantes",
    "atas": UPLOAD_DIR / "atas",
}


def configure_page(title: str, icon: str = "🏡") -> None:
    st.set_page_config(
        page_title=f"{title} | Gestão Associação",
        page_icon=icon,
        layout="wide",
        initial_sidebar_state="expanded",
    )


def ensure_session_defaults() -> None:
    st.session_state.setdefault("authenticated", False)
    st.session_state.setdefault("user", None)


def bootstrap_app_runtime() -> None:
    ensure_session_defaults()
    ASSETS_DIR.mkdir(parents=True, exist_ok=True)
    for directory in UPLOAD_MAP.values():
        directory.mkdir(parents=True, exist_ok=True)

    from database.db import init_db

    init_db()

    from services.pagamentos import update_overdue_payments

    update_overdue_payments()


def bootstrap_page(title: str, icon: str = "🏡") -> None:
    configure_page(title, icon)
    bootstrap_app_runtime()
    inject_global_styles()


def inject_global_styles() -> None:
    stylesheet = ASSETS_DIR / "styles.css"
    if stylesheet.exists():
        st.markdown(f"<style>{stylesheet.read_text(encoding='utf-8')}</style>", unsafe_allow_html=True)


def normalize_string(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value.strip().lower())
    ascii_only = normalized.encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-z0-9]+", " ", ascii_only).strip()


def generate_username(name: str, lot: str = "") -> str:
    normalized_name = normalize_string(name)
    parts = normalized_name.split()
    if not parts:
        return f"usuario{secrets.randbelow(9999):04d}"

    base = parts[0]
    if len(parts) > 1:
        base = f"{base}.{parts[-1]}"

    normalized_lot = normalize_string(lot).replace(" ", "")
    if normalized_lot:
        base = f"{base}.{normalized_lot}"

    return base[:30]


def format_currency(value: float | int | None) -> str:
    amount = float(value or 0)
    formatted = f"{amount:,.2f}".replace(",", "#").replace(".", ",").replace("#", ".")
    return f"R$ {formatted}"


def format_date(value) -> str:
    if not value:
        return "-"

    if isinstance(value, datetime):
        return value.strftime("%d/%m/%Y %H:%M")
    if isinstance(value, date):
        return value.strftime("%d/%m/%Y")

    value_as_string = str(value)
    try:
        if "T" in value_as_string:
            return datetime.fromisoformat(value_as_string).strftime("%d/%m/%Y %H:%M")
        return datetime.fromisoformat(value_as_string).strftime("%d/%m/%Y")
    except ValueError:
        return value_as_string


def month_label(reference: str) -> str:
    if not reference:
        return "-"

    year, month = reference.split("-")
    month_names = {
        "01": "Jan",
        "02": "Fev",
        "03": "Mar",
        "04": "Abr",
        "05": "Mai",
        "06": "Jun",
        "07": "Jul",
        "08": "Ago",
        "09": "Set",
        "10": "Out",
        "11": "Nov",
        "12": "Dez",
    }
    return f"{month_names.get(month, month)}/{year}"


def clean_digits(value: str) -> str:
    return re.sub(r"\D", "", value or "")


def validate_email(email: str) -> bool:
    if not email:
        return True
    return bool(re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email.strip()))


def validate_phone(phone: str) -> bool:
    if not phone:
        return True
    return len(clean_digits(phone)) >= 10


def validate_cpf(cpf: str) -> bool:
    if not cpf:
        return True

    digits = clean_digits(cpf)
    if len(digits) != 11 or digits == digits[0] * 11:
        return False

    for index in range(9, 11):
        total = sum(int(digit) * weight for digit, weight in zip(digits[:index], range(index + 1, 1, -1)))
        check_digit = (total * 10 % 11) % 10
        if check_digit != int(digits[index]):
            return False

    return True


def status_badge(label: str) -> str:
    theme_map = {
        "pago": "success",
        "ativo": "success",
        "concluido": "success",
        "pix": "success",
        "pendente": "danger",
        "inativo": "danger",
        "alta": "danger",
        "atrasado": "warning",
        "média": "warning",
        "andamento": "info",
        "baixa": "info",
        "usuario": "info",
        "planejado": "neutral",
        "admin": "neutral",
        "dinheiro": "neutral",
        "transferencia": "info",
    }
    css_class = theme_map.get((label or "").strip().lower(), "neutral")
    return f"<span class='status-badge {css_class}'>{label}</span>"


def save_uploaded_file(uploaded_file, category: str) -> str | None:
    if not uploaded_file:
        return None

    target_directory = UPLOAD_MAP.get(category)
    if not target_directory:
        return None

    sanitized_name = re.sub(r"[^A-Za-z0-9._-]", "_", uploaded_file.name)
    unique_name = f"{datetime.now().strftime('%Y%m%d%H%M%S')}_{secrets.token_hex(4)}_{sanitized_name}"
    destination = target_directory / unique_name
    destination.write_bytes(uploaded_file.getbuffer())
    return str(destination)


def render_page_header(title: str, subtitle: str) -> None:
    st.markdown(f"<div class='page-title'>{title}</div>", unsafe_allow_html=True)
    st.caption(subtitle)


def render_sidebar(user: dict, current_page: str) -> None:
    from services.auth import logout_user

    admin_pages = [
        ("Dashboard", "pages/dashboard.py"),
        ("Associados", "pages/associados.py"),
        ("Financeiro", "pages/financeiro.py"),
        ("Reuniões", "pages/reunioes.py"),
        ("Avisos", "pages/avisos.py"),
        ("Projetos", "pages/projetos.py"),
        ("Meu Painel", "pages/painel_associado.py"),
    ]
    user_pages = [("Meu Painel", "pages/painel_associado.py")]
    navigation = admin_pages if user.get("tipo") == "admin" else user_pages

    with st.sidebar:
        st.markdown(
            """
            <div class='brand-card'>
                <div class='brand-kicker'>Sistema profissional</div>
                <div class='brand-title'>Gestão Associação</div>
                <div class='brand-subtitle'>Controle integrado da associação de chácaras.</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.markdown(
            f"""
            <div class='profile-card'>
                <strong>{user.get('nome')}</strong><br>
                <span>{user.get('usuario')}</span><br>
                <span>{status_badge(user.get('tipo', ''))} {status_badge(user.get('status', ''))}</span>
            </div>
            """,
            unsafe_allow_html=True,
        )

        st.markdown("### Navegação")
        for label, destination in navigation:
            button_type = "primary" if current_page == destination else "secondary"
            if st.button(label, use_container_width=True, type=button_type, key=f"nav_{destination}"):
                if current_page != destination:
                    st.switch_page(destination)

        st.divider()
        if st.button("Logout", use_container_width=True):
            logout_user()
            st.switch_page("pages/login.py")
