# SymptomNet

SymptomNet is a Streamlit prototype for building and visualising symptom networks.

It allows users to:
- define symptoms and their intensity
- specify relationships between symptoms
- explore an interactive network graph
- compute centrality metrics using R
- generate a reproducible network layout

This project is an early prototype intended for experimentation and research exploration.

---

## Tech stack

- Python
- Streamlit
- pandas
- networkx
- pyvis
- R
- R packages: `jsonlite`, `igraph`, `qgraph`

---

## Run locally

### 1. Clone the repository

```bash
git clone https://github.com/ElearaTahar/SymptomNet.git
cd SymptomNet
```

### 2. Create a virtual environment

```bash
python -m venv .venv
```

Activate it:
```bash
.venv\Scripts\activate    # Windows
source .venv/bin/activate # macOS/Linux
```

### 3. Install Python dependencies

```bash
pip install streamlit pandas networkx pyvis
```

### 4. Install R

Make sure `Rscript` is available:

```bash
Rscript --version
```

### 5. Install required R packages

Run inside R:

```bash
install.packages(c("jsonlite", "igraph", "qgraph"))
```

### 6. Launch the app

```bash
streamlit run app.py
```

## How it works

- Symptoms and relationships are edited directly in the interface
- Clicking 'Analyze network with R' exports the network to JSON
- The script `r/analyze_network.R` computes centrality metrics and layout
- Results are written to the `data/` folder and reloaded automatically

## Project structure

```bash
.
├── app.py
├── r/
│   └── analyze_network.R
└── data/
```

## Notes 

- The app runs without R, but network analysis requires it
- This is a V0 research prototype, not a production-ready application