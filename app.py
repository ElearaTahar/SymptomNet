import networkx as nx
import pandas as pd
import streamlit as st

def normalize_symptoms_df(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    df["label"] = df["label"].fillna("").astype(str).str.strip()
    df["category"] = df["category"].fillna("Autre").astype(str).str.strip()
    df["category"] = df["category"].replace("", "Autre")

    df["intensity"] = pd.to_numeric(df["intensity"], errors="coerce").fillna(1)
    df["intensity"] = df["intensity"].clip(lower=1, upper=10)

    df = df[df["label"] != ""]
    df = df.drop_duplicates(subset=["label"], keep="first")

    return df.reset_index(drop=True)

def normalize_edges_df(df: pd.DataFrame, valid_labels: set[str]) -> pd.DataFrame:
    df = df.copy()

    df["source"] = df["source"].fillna("").astype(str).str.strip()
    df["target"] = df["target"].fillna("").astype(str).str.strip()

    df["weight"] = pd.to_numeric(df["weight"], errors="coerce").fillna(0.1)
    df["weight"] = df["weight"].clip(lower=0.1, upper=1.0)

    df = df[
        (df["source"] != "")
        & (df["target"] != "")
        & (df["source"].isin(valid_labels))
        & (df["target"].isin(valid_labels))
        & (df["source"] != df["target"])
    ]

    return df.reset_index(drop=True)

def build_graph(symptoms_df: pd.DataFrame, edges_df: pd.DataFrame) -> nx.Graph:
    graph = nx.Graph()

    for row in symptoms_df.itertuples(index=False):
        graph.add_node(
            row.label,
            intensity=float(row.intensity),
            category=row.category,
        )

    for row in edges_df.itertuples(index=False):
        graph.add_edge(
            row.source,
            row.target,
            weight=float(row.weight),
        )

    return graph

def compute_metrics(graph: nx.Graph) -> pd.DataFrame:
    if graph.number_of_nodes() == 0:
        return pd.DataFrame(
            columns=["symptom", "degree", "weighted_degree", "betweenness"]
        )

    degree = dict(graph.degree())
    weighted_degree = dict(graph.degree(weight="weight"))
    betweenness = nx.betweenness_centrality(graph, weight="weight", normalized=True)

    rows = []

    for node in graph.nodes():
        rows.append(
            {
                "symptom": node,
                "degree": degree.get(node, 0),
                "weighted_degree": round(weighted_degree.get(node, 0.0), 3),
                "betweenness": round(betweenness.get(node, 0.0), 3),
            }
        )

    metrics_df = pd.DataFrame(rows)

    metrics_df = metrics_df.sort_values(
        by=["weighted_degree", "betweenness", "degree", "symptom"],
        ascending=[False, False, False, True],
    ).reset_index(drop=True)

    return metrics_df

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
            "category": st.column_config.SelectboxColumn(
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

symptoms_df = normalize_symptoms_df(pd.DataFrame(symptoms_df))
valid_labels = set(symptoms_df["label"].tolist())
edges_df = normalize_edges_df(pd.DataFrame(edges_df), valid_labels)

graph = build_graph(symptoms_df, edges_df)
metrics_df = compute_metrics(graph)

st.divider()

st.subheader("Résumé du réseau")
st.write(f"Nombre de symptômes : {graph.number_of_nodes()}")
st.write(f"Nombre de relations : {graph.number_of_edges()}")
st.write(f"Noeuds du graphe : {list(graph.nodes())}")

st.subheader("Centralités")

if metrics_df.empty:
    st.info("Aucune métrique disponible.")
else:
    st.dataframe(metrics_df, use_container_width=True, hide_index=True)

    top_symptom = metrics_df.iloc[0]["symptom"]

    st.write(f"Symptôme le plus central actuellement : **{top_symptom}**")

preview_left, preview_right = st.columns(2)

with preview_left:
    st.write("Symptômes actuels")
    st.dataframe(symptoms_df, use_container_width=True, hide_index=True)

with preview_right:
    st.write("Relations actuelles")
    st.dataframe(edges_df, use_container_width=True, hide_index=True)