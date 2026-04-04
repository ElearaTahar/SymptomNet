import pandas as pd
import streamlit as st

st.set_page_config(page_title="SymptomNet", layout="wide")

st.title("SymptomNet")
st.caption("Prototype V0 - Visualisation simple de réseaux de symptômes")

st.markdown(
    """
Ce prototype permet de :
- saisir des symptômes
- saisir des relations entre symptômes
- visualiser un réseau interactif
- reprérer les symptômes les plus centraux
"""
)

default_symptoms = pd.DataFrame(
    [
        {"label": "Anxiété", "intensity": 7, "category": "Diagnostic"},
        {"label": "Insomnie", "intensity": 5, "category": "Autre"},
        {"label": "Fatigue", "intensity": 6, "category": "Autre"},
        {"label": "Conflit familial", "intensity": 8, "category": "Environnement"},
    ]
)

st.subheader("Symptômes")

symptoms_df = st.data_editor(
    default_symptoms, 
    num_rows="dynamic", 
    use_container_width=True, 
    hide_index=True,
)

st.write("Données actuelles :")
st.dataframe(symptoms_df, use_container_width=True, hide_index=True)