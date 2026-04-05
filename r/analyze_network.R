library(jsonlite)
library(igraph)

input_path <- "data/network_data.json"
output_path <- "data/r_results.json"

# --- Read JSON exported from Python ----------------------------------------
data <- fromJSON(input_path)

nodes <- data$nodes
edges <- data$edges

# --- Safety checks ----------------------------------------------------------
if (is.null(nodes) || nrow(nodes) == 0) {
  write_json(data.frame(), output_path, pretty = TRUE, auto_unbox = TRUE)
  cat("Aucun noeud fourni. Resultats vides ecrits dans", output_path, "\n")
  quit(save = "no")
}

if (is.null(edges) || nrow(edges) == 0) {
  output <- data.frame(
    symptom = as.character(nodes$label),
    strength = rep(0, nrow(nodes)),
    closeness = rep(0, nrow(nodes)),
    betweenness = rep(0, nrow(nodes))
  )

  write_json(output, output_path, pretty = TRUE, auto_unbox = TRUE)
  cat("Aucune arete fournie. Resultats vides de centralite ecrits dans", output_path, "\n")
  quit(save = "no")
}

# --- Normalize edge data ----------------------------------------------------
edges$source <- as.character(edges$source)
edges$target <- as.character(edges$target)
edges$weight <- as.numeric(edges$weight)

# Remove invalid rows
edges <- edges[
  !is.na(edges$source) &
    !is.na(edges$target) &
    edges$source != "" &
    edges$target != "" &
    edges$source != edges$target,
]

if (nrow(edges) == 0) {
  output <- data.frame(
    symptom = as.character(nodes$label),
    strength = rep(0, nrow(nodes)),
    closeness = rep(0, nrow(nodes)),
    betweenness = rep(0, nrow(nodes))
  )

  write_json(output, output_path, pretty = TRUE, auto_unbox = TRUE)
  cat("Aucune arete valide apres nettoyage. Resultats ecrits dans", output_path, "\n")
  quit(save = "no")
}

# Ensure weights are valid and positive
edges$weight[is.na(edges$weight)] <- 0.1
edges$weight[edges$weight <= 0] <- 0.1

# igraph closeness/betweenness interpret weights as distances/costs.
# Your UI weight means "strength of relationship", so we invert it to build distances.
edges$distance <- 1 / edges$weight

# --- Build graph ------------------------------------------------------------
g <- graph_from_data_frame(
  d = edges[, c("source", "target", "weight", "distance")],
  vertices = nodes,
  directed = FALSE
)

# --- Compute centralities ---------------------------------------------------
strength_values <- strength(g, weights = E(g)$weight)

closeness_values <- closeness(
  g,
  vids = V(g),
  mode = "all",
  weights = E(g)$distance,
  normalized = TRUE
)

betweenness_values <- betweenness(
  g,
  v = V(g),
  directed = FALSE,
  weights = E(g)$distance,
  normalized = TRUE
)

# Replace NaN/Inf that can appear on disconnected graphs
closeness_values[!is.finite(closeness_values)] <- 0
betweenness_values[!is.finite(betweenness_values)] <- 0

# --- Build output -----------------------------------------------------------
output <- data.frame(
  symptom = V(g)$name,
  strength = round(as.numeric(strength_values), 3),
  closeness = round(as.numeric(closeness_values), 3),
  betweenness = round(as.numeric(betweenness_values), 3),
  stringsAsFactors = FALSE
)

output <- output[order(
  -output$strength,
  -output$closeness,
  -output$betweenness,
  output$symptom
), ]

write_json(output, output_path, pretty = TRUE, auto_unbox = TRUE)

cat("Analyse terminee : resultats ecrits dans", output_path, "\n")