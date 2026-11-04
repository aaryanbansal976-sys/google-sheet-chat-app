import streamlit as st

from support_insights.config import Settings
from support_insights.dashboard import render
from support_insights.models import AppError

try:
    try:
        values = st.secrets.to_dict()
    except FileNotFoundError:
        values = {}
    render(Settings.from_mapping(values))
except AppError as error:
    st.error("Configuration unavailable: " + error.code)