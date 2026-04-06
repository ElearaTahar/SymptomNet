library(jsonlite)
library(igraph)

input_path <- "data/network_data.json"
output_path <- "data/r_results.json"

# --- Read JSON exported from Python ----------------------------------------
data <- fromJSON(input_path)

nodes <- data$nodes
edges <- data$edges

write_empty_result <- function(nodes, output_path, message_text) {
  metrics <- data.frame(
    symptom = as.character(nodes$label),
    strength = rep(0, nrow(nodes)),
    closeness = rep(0, nrow(nodes)),
    betweenness = rep(0, nrow(nodes)),
    expected_influence = rep(0, nrow(nodes)),
    stringsAsFactors = FALSE
  )

  result <- list(
    metrics = metrics,
    layout = list()
  )

  write_json(result, output_path, pretty = TRUE, auto_unbox = TRUE)
  cat(message_text, "\n")
}

# --- Safety checks ----------------------------------------------------------
if (is.null(nodes) || nrow(nodes) == 0) {
  result <- list(
    metrics = list(),
    layout = list()
  )

  write_json(result, output_path, pretty = TRUE, auto_unbox = TRUE)
  cat("No nodes provided. Empty results written.\n")
  quit(save = "no")
}

if (is.null(edges) || nrow(edges) == 0) {
  write_empty_result(
    nodes,
    output_path,
    "No edges provided. Empty centrality results written."
  )
  quit(save = "no")
}

# --- Normalize edge data ----------------------------------------------------
edges$source <- as.character(edges$source)
edges$target <- as.character(edges$target)
edges$weight <- as.numeric(edges$weight)

edges <- edges[
  !is.na(edges$source) &
    !is.na(edges$target) &
    edges$source != "" &
    edges$target != "" &
    edges$source != edges$target,
]

if (nrow(edges) == 0) {
  write_empty_result(
    nodes,
    output_path,
    "No valid edges after cleaning."
  )
  quit(save = "no")
}

# Keep signed weights for influence metrics
edges$weight[is.na(edges$weight)] <- 0

# Remove exact zero-weight edges from shortest-path computation
edges$abs_weight <- abs(edges$weight)

# Positive distance is required for closeness/betweenness
edges$distance <- NA_real_
edges$distance[edges$abs_weight > 0] <- 1 / edges$abs_weight[edges$abs_weight > 0]

# --- Build graphs -----------------------------------------------------------
g_signed <- graph_from_data_frame(
  d = edges[, c("source", "target", "weight")],
  vertices = nodes,
  directed = FALSE
)

edges_for_paths <- edges[!is.na(edges$distance), c("source", "target", "weight", "distance")]

g_paths <- graph_from_data_frame(
  d = edges_for_paths,
  vertices = nodes,
  directed = FALSE
)

# --- Compute centralities ---------------------------------------------------
expected_influence_values <- strength(g_signed, weights = E(g_signed)$weight)

abs_weights <- abs(E(g_signed)$weight)
strength_values <- strength(g_signed, weights = abs_weights)

if (ecount(g_paths) > 0) {
  closeness_values <- closeness(
    g_paths,
    vids = V(g_paths),
    mode = "all",
    weights = E(g_paths)$distance,
    normalized = TRUE
  )

  betweenness_values <- betweenness(
    g_paths,
    v = V(g_paths),
    directed = FALSE,
    weights = E(g_paths)$distance,
    normalized = TRUE
  )
} else {
  closeness_values <- rep(0, vcount(g_signed))
  names(closeness_values) <- V(g_signed)$name

  betweenness_values <- rep(0, vcount(g_signed))
  names(betweenness_values) <- V(g_signed)$name
}

closeness_values[!is.finite(closeness_values)] <- 0
betweenness_values[!is.finite(betweenness_values)] <- 0

# --- Build metrics output ---------------------------------------------------
metrics <- data.frame(
  symptom = V(g_signed)$name,
  strength = round(as.numeric(strength_values[V(g_signed)$name]), 3),
  closeness = round(as.numeric(closeness_values[V(g_signed)$name]), 3),
  betweenness = round(as.numeric(betweenness_values[V(g_signed)$name]), 3),
  expected_influence = round(as.numeric(expected_influence_values[V(g_signed)$name]), 3),
  stringsAsFactors = FALSE
)

metrics[is.na(metrics)] <- 0

metrics <- metrics[order(
  -metrics$expected_influence,
  -metrics$strength,
  -metrics$closeness,
  -metrics$betweenness,
  metrics$symptom
), ]

edges_for_layout <- edges[edges$abs_weight > 0, c("source", "target", "abs_weight")]
colnames(edges_for_layout) <- c("source", "target", "weight")

g_layout <- graph_from_data_frame(
  d = edges_for_layout,
  vertices = nodes,
  directed = FALSE
)

# --- Build layout output ----------------------------------------------------
if (vcount(g_signed) == 1) {
  layout <- data.frame(
    symptom = V(g_signed)$name,
    x = 0,
    y = 0,
    stringsAsFactors = FALSE
  )
} else if (ecount(g_layout) == 0) {
  layout <- data.frame(
    symptom = V(g_signed)$name,
    x = 0,
    y = 0,
    stringsAsFactors = FALSE
  )
} else {
  layout_matrix <- layout_with_fr(
    g_layout,
    weights = E(g_layout)$weight
  )

  layout <- data.frame(
    symptom = V(g_layout)$name,
    x = round(layout_matrix[, 1], 6),
    y = round(layout_matrix[, 2], 6),
    stringsAsFactors = FALSE
  )
}

# --- Build structured result ------------------------------------------------
result <- list(
  metrics = metrics,
  layout = layout
)

write_json(result, output_path, pretty = TRUE, auto_unbox = TRUE)

cat("Network analysis complete. Structured JSON results with layout written.\n")