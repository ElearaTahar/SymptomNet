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

default_symptoms["category"] = pd.Categorical(
    default_symptoms["category"],
    categories=["Diagnostic", "Environnement", "Autre"]
)

default_edges = pd.DataFrame(
    [
        {"source": "Anxiété", "target": "Insomnie", "weight": 0.7},
        {"source": "Insomnie", "target": "Fatigue", "weight": 0.8},
        {"source": "Conflit familial", "target": "Anxiété", "weight": 0.6},
    ]
)

left_col, right_col = st.columns(2)

with left_col:
    st.subheader("Symptômes")

    symptoms_df = st.data_editor(
        default_symptoms, 
        num_rows="dynamic", 
        use_container_width=True, 
        hide_index=True,
        column_config={
            "label": st.column_config.TextColumn(
                "Symptôme",
                required=True,
            ),
            "intensity": st.column_config.NumberColumn(
                "Intensité",
                min_value=1,
                max_value=10,
                step=1,
            ),
            "ccategory": st.column_config.SelectboxColumn(
                "Catégorie",
                options=["Diagnostic", "Environnement", "Autre"],
            )
        }
    )

symptom_options = [
    label.strip()
    for label in symptoms_df["label"].dropna().tolist()
    if str(label).strip() != ""
]

with right_col:
    st.subheader("Relations")

    edges_df = st.data_editor(
        default_edges,
        num_rows="dynamic",
        use_container_width=True,
        hide_index=True,
        column_config={
            "source": st.column_config.SelectboxColumn(
                "Source",
                options=symptom_options,
                required=True,
            ),
            "target": st.column_config.SelectboxColumn(
                "Cible",
                options=symptom_options,
                required=True,
            ),
            "weight": st.column_config.NumberColumn(
                "Poids",
                min_value=0.1,
                max_value=1.0,
                step=0.1,
            )
        }
    )

st.divider()

preview_left, preview_right = st.columns(2)

with preview_left:
    st.write("Symptômes actuels")
    st.dataframe(symptoms_df, use_container_width=True, hide_index=True)

with preview_right:
    st.write("Relations actuelles")
    st.dataframe(edges_df, use_container_width=True, hide_index=True)