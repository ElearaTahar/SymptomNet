library(jsonlite)
library(igraph)
library(qgraph)

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
    layout = list(),
    metadata = list(
      layout_engine = NA,
      layout_fallback_used = FALSE,
      layout_warning = NA
    )
  )

  write_json(result, output_path, pretty = TRUE, auto_unbox = TRUE, null = "null")
  cat(message_text, "\n")
}

# --- Safety checks ----------------------------------------------------------
if (is.null(nodes) || nrow(nodes) == 0) {
  result <- list(
    metrics = list(),
    layout = list(),
    metadata = list(
      layout_engine = NA,
      layout_fallback_used = FALSE,
      layout_warning = NA
    )
  )

  write_json(result, output_path, pretty = TRUE, auto_unbox = TRUE, null = "null")
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

edges_for_paths <- edges[
  !is.na(edges$distance),
  c("source", "target", "weight", "distance")
]

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

# --- Prepare layout inputs --------------------------------------------------
node_names <- as.character(nodes$label)

layout_matrix_input <- matrix(
  0,
  nrow = length(node_names),
  ncol = length(node_names),
  dimnames = list(node_names, node_names)
)

edges_for_layout <- edges[edges$abs_weight > 0, c("source", "target", "abs_weight")]

if (nrow(edges_for_layout) > 0) {
  for (i in seq_len(nrow(edges_for_layout))) {
    source_name <- as.character(edges_for_layout$source[i])
    target_name <- as.character(edges_for_layout$target[i])
    weight_value <- as.numeric(edges_for_layout$abs_weight[i])

    layout_matrix_input[source_name, target_name] <- weight_value
    layout_matrix_input[target_name, source_name] <- weight_value
  }
}

# --- Build layout output ----------------------------------------------------
layout_engine <- NA_character_
layout_fallback_used <- FALSE
layout_warning <- NA_character_

if (vcount(g_signed) == 1) {
  layout <- data.frame(
    symptom = V(g_signed)$name,
    x = 0,
    y = 0,
    stringsAsFactors = FALSE
  )
  layout_engine <- "trivial"
} else if (sum(layout_matrix_input) == 0) {
  layout <- data.frame(
    symptom = V(g_signed)$name,
    x = 0,
    y = 0,
    stringsAsFactors = FALSE
  )
  layout_engine <- "empty"
} else {
  qgraph_result <- tryCatch(
    {
      qgraph_object <- qgraph(
        layout_matrix_input,
        layout = "spring",
        DoNotPlot = TRUE
      )

      layout_matrix <- qgraph_object$layout

      if (is.null(layout_matrix) || nrow(layout_matrix) != length(node_names)) {
        stop("qgraph returned an invalid layout matrix.")
      }

      list(
        success = TRUE,
        layout_matrix = layout_matrix,
        warning = NA_character_
      )
    },
    error = function(e) {
      list(
        success = FALSE,
        layout_matrix = NULL,
        warning = conditionMessage(e)
      )
    }
  )

  if (isTRUE(qgraph_result$success)) {
    layout_matrix <- qgraph_result$layout_matrix
    layout_engine <- "qgraph"
  } else {
    edges_for_igraph_layout <- edges[
      edges$abs_weight > 0,
      c("source", "target", "abs_weight")
    ]
    colnames(edges_for_igraph_layout) <- c("source", "target", "weight")

    g_layout <- graph_from_data_frame(
      d = edges_for_igraph_layout,
      vertices = nodes,
      directed = FALSE
    )

    layout_matrix <- layout_with_fr(
      g_layout,
      weights = E(g_layout)$weight
    )

    if (is.null(layout_matrix) || nrow(layout_matrix) != length(node_names)) {
      stop("igraph fallback returned an invalid layout matrix.")
    }

    layout_engine <- "igraph"
    layout_fallback_used <- TRUE
    layout_warning <- qgraph_result$warning
  }

  layout <- data.frame(
    symptom = node_names,
    x = round(layout_matrix[, 1], 6),
    y = round(layout_matrix[, 2], 6),
    stringsAsFactors = FALSE
  )
}

# --- Build structured result ------------------------------------------------
result <- list(
  metrics = metrics,
  layout = layout,
  metadata = list(
    layout_engine = layout_engine,
    layout_fallback_used = layout_fallback_used,
    layout_warning = layout_warning
  )
)

write_json(result, output_path, pretty = TRUE, auto_unbox = TRUE, null = "null")

cat("Network analysis complete. Structured JSON results with layout written.\n")