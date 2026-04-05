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
  cat("No nodes provided. Empty results written.\n")
  quit(save = "no")
}

if (is.null(edges) || nrow(edges) == 0) {
  output <- data.frame(
    symptom = as.character(nodes$label),
    strength = rep(0, nrow(nodes)),
    closeness = rep(0, nrow(nodes)),
    betweenness = rep(0, nrow(nodes)),
    expected_influence = rep(0, nrow(nodes))
  )

  write_json(output, output_path, pretty = TRUE, auto_unbox = TRUE)
  cat("No edges provided. Empty centrality results written.\n")
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
  output <- data.frame(
    symptom = as.character(nodes$label),
    strength = rep(0, nrow(nodes)),
    closeness = rep(0, nrow(nodes)),
    betweenness = rep(0, nrow(nodes)),
    expected_influence = rep(0, nrow(nodes))
  )

  write_json(output, output_path, pretty = TRUE, auto_unbox = TRUE)
  cat("No valid edges after cleaning.\n")
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

# Signed weighted sum
expected_influence_values <- strength(g_signed, weights = E(g_signed)$weight)

# Absolute weighted sum
strength_values <- strength(g_signed, weights = abs(E(g_signed)$weight))

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

# --- Build output -----------------------------------------------------------
output <- data.frame(
  symptom = V(g_signed)$name,
  strength = round(as.numeric(strength_values[V(g_signed)$name]), 3),
  closeness = round(as.numeric(closeness_values[V(g_signed)$name]), 3),
  betweenness = round(as.numeric(betweenness_values[V(g_signed)$name]), 3),
  expected_influence = round(as.numeric(expected_influence_values[V(g_signed)$name]), 3),
  stringsAsFactors = FALSE
)

output[is.na(output)] <- 0

output <- output[order(
  -output$expected_influence,
  -output$strength,
  -output$closeness,
  -output$betweenness,
  output$symptom
), ]

write_json(output, output_path, pretty = TRUE, auto_unbox = TRUE)

cat("Network analysis complete. Results written to JSON.\n")