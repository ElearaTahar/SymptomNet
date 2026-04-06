import json
import subprocess
import tempfile
from pathlib import Path

import networkx as nx
import pandas as pd
import streamlit as st
from pyvis.network import Network


CATEGORY_OPTIONS = ["Diagnostic", "Environnement", "Autre"]

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

    df["weight"] = pd.to_numeric(df["weight"], errors="coerce").fillna(0.0)
    df["weight"] = df["weight"].clip(lower=-1.0, upper=1.0)

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
            columns=[
                "symptom",
                "degree",
                "strength_abs",
                "expected_influence",
                "betweenness",
            ]
        )

    degree = dict(graph.degree())

    strength_abs = {
        node: round(
            sum(
                abs(float(data.get("weight", 0.0)))
                for _, _, data in graph.edges(node, data=True)
            ),
            3,
        )
        for node in graph.nodes()
    }

    expected_influence = {
        node: round(
            sum(
                float(data.get("weight", 0.0))
                for _, _, data in graph.edges(node, data=True)
            ),
            3,
        )
        for node in graph.nodes()
    }

    distance_graph = nx.Graph()
    for node, attrs in graph.nodes(data=True):
        distance_graph.add_node(node, **attrs)

    for source, target, attrs in graph.edges(data=True):
        weight = float(attrs.get("weight", 0.0))
        abs_weight = abs(weight)

        if abs_weight == 0:
            continue

        distance_graph.add_edge(
            source,
            target,
            weight=weight,
            distance=1 / abs_weight,
        )

    betweenness = (
        nx.betweenness_centrality(
            distance_graph,
            weight="distance",
            normalized=True,
        )
        if distance_graph.number_of_edges() > 0
        else {node: 0.0 for node in graph.nodes()}
    )

    rows = []
    for node in graph.nodes():
        rows.append(
            {
                "symptom": node,
                "degree": degree.get(node, 0),
                "strength_abs": strength_abs.get(node, 0.0),
                "expected_influence": expected_influence.get(node, 0.0),
                "betweenness": round(betweenness.get(node, 0.0), 3),
            }
        )

    metrics_df = pd.DataFrame(rows)
    metrics_df = metrics_df.sort_values(
        by=["expected_influence", "strength_abs", "betweenness", "degree", "symptom"],
        ascending=[False, False, False, False, True],
    ).reset_index(drop=True)

    return metrics_df


# --- Visualization ---------------------------------------------------------
def shape_for_category(category: str) -> str:
    return {
        "Diagnostic": "dot",
        "Environnement": "square",
        "Autre": "triangle",
    }.get(category, "dot")


def edge_width_for_weight(weight: float) -> float:
    abs_weight = abs(weight)
    return 1.5 + (abs_weight * 6.0)


def edge_opacity_for_weight(weight: float) -> float:
    abs_weight = abs(weight)
    return 0.3 + (abs_weight * 0.7)


def rgba_from_gray(gray_value: int, alpha: float) -> str:
    gray_value = max(0, min(255, gray_value))
    return f"rgba({gray_value},{gray_value},{gray_value},{alpha:.3f})"


def build_layout_map(layout_df: pd.DataFrame | None) -> dict[str, tuple[float, float]]:
    if layout_df is None or layout_df.empty:
        return {}

    required_columns = {"symptom", "x", "y"}
    if not required_columns.issubset(layout_df.columns):
        return {}

    df = layout_df.copy()
    df["symptom"] = df["symptom"].fillna("").astype(str).str.strip()
    df = df[df["symptom"] != ""].reset_index(drop=True)

    if df.empty:
        return {}

    df["x"] = pd.to_numeric(df["x"], errors="coerce").fillna(0.0)
    df["y"] = pd.to_numeric(df["y"], errors="coerce").fillna(0.0)

    df["x"] = df["x"] - df["x"].mean()
    df["y"] = df["y"] - df["y"].mean()

    max_abs = max(df["x"].abs().max(), df["y"].abs().max(), 1.0)
    target_radius = 250.0

    df["x"] = (df["x"] / max_abs) * target_radius
    df["y"] = (df["y"] / max_abs) * target_radius

    return {
        row.symptom: (float(row.x), float(row.y))
        for row in df.itertuples(index=False)
    }


def render_pyvis_graph(
    graph: nx.Graph,
    layout_df: pd.DataFrame | None = None,
) -> str:
    layout_map = build_layout_map(layout_df)
    has_fixed_layout = len(layout_map) > 0

    net = Network(
        height="650px",
        width="100%",
        bgcolor="#ffffff",
        font_color="#111827",
    )

    if not has_fixed_layout:
        net.barnes_hut()

    for node, attrs in graph.nodes(data=True):
        intensity = float(attrs.get("intensity", 1))
        category = attrs.get("category", "Autre")

        node_kwargs = {
            "label": node,
            "title": (
                f"{node}"
                f"<br>Catégorie : {category}"
                f"<br>Intensité : {intensity}"
            ),
            "shape": shape_for_category(category),
            "size": 15 + (intensity * 3),
            "color": {
                "background": "#ffffff",
                "border": "#111827",
                "highlight": {
                    "background": "#f3f4f6",
                    "border": "#111827",
                },
                "hover": {
                    "background": "#f9fafb",
                    "border": "#111827",
                },
            },
            "borderWidth": 2,
            "font": {
                "size": 18,
                "face": "arial",
                "color": "#111827",
                "strokeWidth": 4,
                "strokeColor": "#ffffff",
                "vadjust": -10,
            },
        }

        if node in layout_map:
            x, y = layout_map[node]
            node_kwargs["x"] = x
            node_kwargs["y"] = y
            node_kwargs["physics"] = False

        net.add_node(node, **node_kwargs)

    for source, target, attrs in graph.edges(data=True):
        weight = float(attrs.get("weight", 0.0))
        abs_weight = abs(weight)
        relation_label = "Positive" if weight >= 0 else "Négative"

        net.add_edge(
            source,
            target,
            value=max(abs_weight, 0.05) * 5,
            width=edge_width_for_weight(weight),
            color=rgba_from_gray(80, edge_opacity_for_weight(weight)),
            dashes=(weight < 0),
            title=(
                f"Relation {relation_label.lower()}"
                f"<br>Poids : {weight:.2f}"
                f"<br>Force absolue : {abs_weight:.2f}"
                f"<br>Style : {'pointillé' if weight < 0 else 'continu'}"
            ),
            physics=not has_fixed_layout,
            smooth=False,
        )

    if has_fixed_layout:
        net.set_options(
            """
            {
              "interaction": {
                "hover": true,
                "navigationButtons": true,
                "keyboard": true
              },
              "physics": {
                "enabled": false
              }
            }
            """
        )
    else:
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


# --- R analysis ------------------------------------------------------------
def export_network_to_json(
    symptoms_df: pd.DataFrame,
    edges_df: pd.DataFrame,
    path: str = "data/network_data.json",
) -> str:
    Path(path).parent.mkdir(parents=True, exist_ok=True)

    data = {
        "nodes": symptoms_df.to_dict(orient="records"),
        "edges": edges_df.to_dict(orient="records"),
    }

    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    return path


def load_r_analysis_results(
    path: str = "data/r_results.json",
) -> tuple[pd.DataFrame | None, pd.DataFrame | None, dict | None]:
    try:
        with open(path, "r", encoding="utf-8") as f:
            payload = json.load(f)

        if isinstance(payload, list):
            metrics_df = pd.DataFrame(payload)
            layout_df = None
            metadata = None
        elif isinstance(payload, dict):
            metrics_df = pd.DataFrame(payload.get("metrics", []))
            layout_df = pd.DataFrame(payload.get("layout", []))
            metadata = payload.get("metadata")
        else:
            return None, None, None

        if metrics_df is not None and not metrics_df.empty:
            numeric_columns = [
                "strength",
                "closeness",
                "betweenness",
                "expected_influence",
            ]
            for col in numeric_columns:
                if col in metrics_df.columns:
                    metrics_df[col] = pd.to_numeric(
                        metrics_df[col], errors="coerce"
                    ).fillna(0.0)

            sort_columns = [
                col
                for col in [
                    "expected_influence",
                    "strength",
                    "closeness",
                    "betweenness",
                    "symptom",
                ]
                if col in metrics_df.columns
            ]
            ascending = [False, False, False, False, True][: len(sort_columns)]

            if sort_columns:
                metrics_df = metrics_df.sort_values(
                    by=sort_columns,
                    ascending=ascending,
                ).reset_index(drop=True)

        if layout_df is not None and not layout_df.empty:
            for col in ["x", "y"]:
                if col in layout_df.columns:
                    layout_df[col] = pd.to_numeric(
                        layout_df[col], errors="coerce"
                    ).fillna(0.0)

            if "symptom" in layout_df.columns:
                layout_df["symptom"] = (
                    layout_df["symptom"].fillna("").astype(str).str.strip()
                )
                layout_df = layout_df[layout_df["symptom"] != ""].reset_index(drop=True)

        return metrics_df, layout_df, metadata

    except FileNotFoundError:
        return None, None, None
    except json.JSONDecodeError:
        return None, None, None


def run_r_analysis() -> bool:
    try:
        result = subprocess.run(
            ["Rscript", "r/analyze_network.R"],
            check=True,
            capture_output=True,
            text=True,
        )

        if result.stdout:
            st.info(result.stdout)

        return True

    except subprocess.CalledProcessError as e:
        st.error("Erreur pendant l'exécution du script R.")
        if e.stdout:
            st.code(e.stdout)
        if e.stderr:
            st.code(e.stderr)
        return False


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
        width="stretch",
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
        width="stretch",
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
                min_value=-1.0,
                max_value=1.0,
                step=0.1,
            ),
        },
    )
    st.caption(
        "Poids négatif = relation protectrice / inhibitrice. "
        "Poids positif = relation activante / aggravante."
    )

# --- Data preparation ------------------------------------------------------
symptoms_df = normalize_symptoms_df(pd.DataFrame(symptoms_df))
valid_labels = set(symptoms_df["label"].tolist())
edges_df = normalize_edges_df(pd.DataFrame(edges_df), valid_labels)

graph = build_graph(symptoms_df, edges_df)
metrics_df = compute_metrics(graph)

if "r_metrics_df" not in st.session_state:
    st.session_state["r_metrics_df"] = None

if "r_layout_df" not in st.session_state:
    st.session_state["r_layout_df"] = None

if "r_layout_metadata" not in st.session_state:
    st.session_state["r_layout_metadata"] = None

# --- Results ---------------------------------------------------------------
st.divider()

kpi_col1, kpi_col2, kpi_col3 = st.columns(3)
kpi_col1.metric("Nombre de symptômes", graph.number_of_nodes())
kpi_col2.metric("Nombre de relations", graph.number_of_edges())
kpi_col3.metric(
    "Symptôme le plus central",
    metrics_df.iloc[0]["symptom"] if not metrics_df.empty else "-",
)

action_col1, action_col2 = st.columns([1, 1])

with action_col1:
    if st.button("Analyser le réseau avec R"):
        export_network_to_json(symptoms_df, edges_df)

        success = run_r_analysis()

        if success:
            r_metrics_df, r_layout_df, r_layout_metadata = load_r_analysis_results()

            if r_metrics_df is not None:
                st.session_state["r_metrics_df"] = r_metrics_df
                st.session_state["r_layout_df"] = r_layout_df
                st.session_state["r_layout_metadata"] = r_layout_metadata
                st.success("Analyse R terminée avec succès.")
            else:
                st.error("Le fichier de résultats R est introuvable ou vide.")

with action_col2:
    if st.button("Réinitialiser les résultats R"):
        st.session_state["r_metrics_df"] = None
        st.session_state["r_layout_df"] = None
        st.session_state["r_layout_metadata"] = None
        st.success("Résultats R réinitialisés.")

graph_col, metrics_col = st.columns([2, 1])

with graph_col:
    st.subheader("Réseau")
    st.caption(
        "La forme des nœuds représente la catégorie. "
        "La taille des nœuds représente l’intensité. "
        "L’épaisseur des arêtes représente la force absolue. "
        "Les arêtes continues sont positives ; les arêtes pointillées sont négatives."
    )

    legend_cols = st.columns(4)
    legend_cols[0].markdown("● **Diagnostic**")
    legend_cols[1].markdown("■ **Environnement**")
    legend_cols[2].markdown("▲ **Autre**")
    legend_cols[3].markdown("━ / ┄ **Continu = positif, pointillé = négatif**")

    if graph.number_of_nodes() == 0:
        st.info("Ajoutez au moins un symptôme pour afficher le réseau.")
    else:
        r_layout_df = st.session_state.get("r_layout_df")
        html = render_pyvis_graph(graph, layout_df=r_layout_df)

        r_layout_metadata = st.session_state.get("r_layout_metadata")
        if isinstance(r_layout_metadata, dict):
            layout_engine = r_layout_metadata.get("layout_engine")
            fallback_used = r_layout_metadata.get("layout_fallback_used")
            layout_warning = r_layout_metadata.get("layout_warning")

            if layout_engine:
                layout_label = f"Layout utilisé : {layout_engine}"
                if fallback_used:
                    layout_label += " (fallback)"
                st.caption(layout_label)

            if layout_warning:
                st.caption(
                    "Information de rendu : "
                    f"{layout_warning}"
                )

        tmp_path = Path("data/network_preview.html")
        tmp_path.write_text(html, encoding="utf-8")

        st.iframe(str(tmp_path), height=700)

with metrics_col:
    st.subheader("Centralités")

    r_metrics_df = st.session_state.get("r_metrics_df")

    if r_metrics_df is not None and not r_metrics_df.empty:
        st.caption("Résultats calculés par R")
        st.dataframe(r_metrics_df, width="stretch", hide_index=True)

        top_symptom = r_metrics_df.iloc[0]["symptom"]
        st.write(f"Le symptôme le plus central selon R est **{top_symptom}**.")
    elif metrics_df.empty:
        st.info("Aucune métrique disponible.")
    else:
        st.caption("Aperçu local calculé en Python")
        st.dataframe(metrics_df, width="stretch", hide_index=True)

        top_symptom = metrics_df.iloc[0]["symptom"]
        st.write(f"Le symptôme le plus central actuellement est **{top_symptom}**.")

        if len(metrics_df) >= 3:
            top_3 = ", ".join(metrics_df.head(3)["symptom"].tolist())
            st.write(f"Top 3 actuel : **{top_3}**.")