import streamlit as st

from views.multi_input import render_multi_input_page
from views.self_study_input import render_self_study_input_page
from views.edit_input import render_edit_input_page
from views.group_input import render_group_input_page

def render_combined_input_page():
    st.header("📝 授業・自習記録の入力")

    record_type = st.radio(
        "✍️ 記録の種類を選択してください", 
        ["📖 授業記録（新規）", "🧑‍🤝‍🧑 授業記録（集団）", "📝 自習記録", "🛠️ 授業記録の修正"], 
        horizontal=True, 
        key="record_type_combined"
    )
    st.divider()

    if record_type == "📖 授業記録（新規）":
        render_multi_input_page()
    elif record_type == "🧑‍🤝‍🧑 授業記録（集団）":
        render_group_input_page()    
    elif record_type == "📝 自習記録":
        render_self_study_input_page()
    elif record_type == "🛠️ 授業記録の修正":
        render_edit_input_page()