import streamlit as st

from views.multi_input import render_multi_input_page
from views.self_study_input import render_self_study_input_page

def render_combined_input_page():
    st.header("📝 授業・自習記録の入力")

    tab1, tab2 = st.tabs(["📖 授業", "📝 自習"])
    
    with tab1:
        render_multi_input_page()
        
    with tab2:
        render_self_study_input_page()