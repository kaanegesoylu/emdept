"""Yeşil Alan Kuyruk Paneli — FENG 497.

Çalıştırma:  streamlit run app.py
"""
import streamlit as st

st.set_page_config(page_title="Yeşil Alan Kuyruk Paneli", page_icon=":material/local_hospital:", layout="wide")

from views import canli, karar, veri, yogunluk, yontem  # noqa: E402
from views.common import init_state, source_badge  # noqa: E402

st.markdown("""<style>
.block-container {padding-top: 2.2rem; max-width: 1180px;}
[data-testid="stMetricValue"] {font-size: 1.7rem;}
h1 {font-size: 1.9rem !important;}
</style>""", unsafe_allow_html=True)

init_state()

nav = st.navigation([
    st.Page(veri.render, title="Veri", icon=":material/database:", url_path="veri", default=True),
    st.Page(yogunluk.render, title="Yoğunluk", icon=":material/bar_chart:", url_path="yogunluk"),
    st.Page(karar.render, title="Karar", icon=":material/groups:", url_path="karar"),
    st.Page(canli.render, title="Canlı durum", icon=":material/sensors:", url_path="canli"),
    st.Page(yontem.render, title="Yöntem", icon=":material/menu_book:", url_path="yontem"),
])
st.sidebar.markdown("**Yeşil Alan Kuyruk Paneli**  \nFENG 497 · v0.1")
source_badge()
nav.run()
