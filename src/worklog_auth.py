"""Вход в админку AXIS: bcrypt и пользователи из кода + ADDITIONAL_USERS."""
from __future__ import annotations

import os

import bcrypt
import streamlit as st
from dotenv import load_dotenv

load_dotenv(override=True)


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode(), hashed.encode())


def load_users() -> dict:
    users = {
        "admin": {
            "hash": "$2b$12$kULF9uKSNlV8Q3OTy02o9.ElMYQytN5tyXvnvmuyXrG.GXsmIy6oe",
            "role": "admin",
        },
    }
    user_list_env = os.getenv("ADDITIONAL_USERS", "")
    if user_list_env:
        for user_spec in user_list_env.split(";"):
            parts = user_spec.strip().split(":")
            if len(parts) == 3:
                uname, uhash, urole = parts
                users[uname] = {"hash": uhash, "role": urole}
    return users


USERS = load_users()


def check_password() -> bool:
    if st.session_state.get("authenticated"):
        return True

    st.markdown("<br><br>", unsafe_allow_html=True)
    _, col2, _ = st.columns([1, 2, 1])

    with col2:
        st.header("🔐 Вход в AXIS")
        with st.form("axis_login", clear_on_submit=False, border=False):
            login = st.text_input("Логин", autocomplete="username")
            pwd = st.text_input("Пароль", type="password", autocomplete="current-password")
            submitted = st.form_submit_button("Войти", width="stretch", type="primary")
        if submitted:
            if login in USERS and verify_password(pwd, USERS[login]["hash"]):
                st.session_state.authenticated = True
                st.session_state.user_role = USERS[login]["role"]
                st.session_state.user_name = login
                st.rerun()
            else:
                st.error("❌ Неверные данные")
    return False
