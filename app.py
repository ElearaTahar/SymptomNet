import tempfile
from pathlib import Path

import networkx as nx
import pandas as pd
import streamlit as st
from pyvis.network import Network


CATEGORY_OPTIONS = ["Diagnostic", "Environnement", "Autre"]

CATEGORY_COLORS = {
    "Diagnostic": "#ef4444",
    "Environnement": "#3b82f6",
    "Autre": "#10b981",
}

DEFAULT_SYMPTOMS = pd.DataFrame(
    [
        {"label": "Anxiété", "intensity": 7, "category": "Diagnostic"},
        {"label": "Insomnie", "intensity": 5, "category": "Autre"},
        {"label": "Fatigue", "intensity": 6, "category": "Autre"},
        {"label": "Conflit familial", "intensity": 8, "category": "Environnement"},
    ]
)

DEFAULT_SYMPTOMS["category"] = pd.Categorical(
    DEFAULT_SYMPTOMS["category"],
    categories=CATEGORY_OPTIONS,
)

DEFAULT_EDGES = pd.DataFrame(
    [
        {"source": "Anxiété", "target": "Insomnie", "weight": 0.7},
        {"source": "Insomnie", "target": "Fatigue", "weight": 0.8},
        {"source": "Conflit familial", "target": "Anxiété", "weight": 0.6},
    ]
)


# --- Data normalization ----------------------------------------------------
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


# --- Graph building and metrics --------------------------------------------
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


# --- Visualization ---------------------------------------------------------
def color_for_category(category: str) -> str:
    return CATEGORY_COLORS.get(category, "#8b5cf6")


def render_pyvis_graph(graph: nx.Graph) -> str:
    net = Network(
        height="650px",
        width="100%",
        bgcolor="#ffffff",
        font_color="#111827",
    )

    net.barnes_hut()

    for node, attrs in graph.nodes(data=True):
        intensity = float(attrs.get("intensity", 1))
        category = attrs.get("category", "Autre")
        color = color_for_category(category)

        net.add_node(
            node,
            label=node,
            title=f"{node}<br>Catégorie: {category}<br>Intensité: {intensity}",
            color=color,
            size=15 + (intensity * 3),
        )

    for source, target, attrs in graph.edges(data=True):
        weight = float(attrs.get("weight", 0.1))

        net.add_edge(
            source,
            target,
            value=weight * 5,
            title=f"Poids: {weight}",
        )

    net.set_options(
        """
        {
          "interaction": {
            "hover": true,
            "navigationButtons": true,
            "keyboard": true
          },
          "physics": {
            "enabled": true,
            "barnesHut": {
              "gravitationalConstant": -3000,
              "springLength": 180,
              "springConstant": 0.04
            }
          }
        }
        """
    )

    with tempfile.NamedTemporaryFile(delete=False, suffix=".html") as tmp_file:
        net.save_graph(tmp_file.name)
        html = Path(tmp_file.name).read_text(encoding="utf-8")

    return html


# --- Page setup ------------------------------------------------------------
st.set_page_config(page_title="SymptomNet", layout="wide")

st.title("SymptomNet")
st.caption("Prototype V0 - Visualisation simple de réseaux de symptômes")

st.markdown(
    """
Ce prototype permet de :
- saisir des symptômes et leur intensité
- définir des relations entre symptômes
- visualiser un réseau interactif
- repérer les symptômes les plus centraux
"""
)

# --- Editors ---------------------------------------------------------------
left_col, right_col = st.columns(2)

with left_col:
    st.subheader("Symptômes")
    symptoms_df = st.data_editor(
        DEFAULT_SYMPTOMS,
        num_rows="dynamic",
        use_container_width=True,
        hide_index=True,
        column_config={
            "label": st.column_config.TextColumn("Symptôme", required=True),
            "intensity": st.column_config.NumberColumn(
                "Intensité",
                min_value=1,
                max_value=10,
                step=1,
            ),
            "category": st.column_config.SelectboxColumn(
                "Catégorie",
                options=CATEGORY_OPTIONS,
            ),
        },
    )

symptom_options = [
    label.strip()
    for label in symptoms_df["label"].dropna().tolist()
    if str(label).strip() != ""
]

with right_col:
    st.subheader("Relations")
    edges_df = st.data_editor(
        DEFAULT_EDGES,
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
            ),
        },
    )

# --- Data preparation ------------------------------------------------------
symptoms_df = normalize_symptoms_df(pd.DataFrame(symptoms_df))
valid_labels = set(symptoms_df["label"].tolist())
edges_df = normalize_edges_df(pd.DataFrame(edges_df), valid_labels)

graph = build_graph(symptoms_df, edges_df)
metrics_df = compute_metrics(graph)

# --- Results ---------------------------------------------------------------
st.divider()

kpi_col1, kpi_col2, kpi_col3 = st.columns(3)
kpi_col1.metric("Nombre de symptômes", graph.number_of_nodes())
kpi_col2.metric("Nombre de relations", graph.number_of_edges())
kpi_col3.metric(
    "Symptôme le plus central",
    metrics_df.iloc[0]["symptom"] if not metrics_df.empty else "-",
)

legend_cols = st.columns(3)
legend_cols[0].markdown("🔴 **Diagnostic**")
legend_cols[1].markdown("🔵 **Environnement**")
legend_cols[2].markdown("🟢 **Autre**")

graph_col, metrics_col = st.columns([2, 1])

with graph_col:
    st.subheader("Réseau")
    if graph.number_of_nodes() == 0:
        st.info("Ajoutez au moins un symptôme pour afficher le réseau.")
    else:
        html = render_pyvis_graph(graph)
        st.components.v1.html(html, height=700, scrolling=True)

with metrics_col:
    st.subheader("Centralités")
    if metrics_df.empty:
        st.info("Aucune métrique disponible.")
    else:
        st.dataframe(metrics_df, use_container_width=True, hide_index=True)

        top_symptom = metrics_df.iloc[0]["symptom"]
        st.write(f"Le symptôme le plus central actuellement est **{top_symptom}**.")

        if len(metrics_df) >= 3:
            top_3 = ", ".join(metrics_df.head(3)["symptom"].tolist())
            st.write(f"Top 3 actuel : **{top_3}**.")