library(jsonlite)
library(igraph)

# Read JSON exported from Python
data <- fromJSON("data/network_data.json")

nodes <- data$nodes
edges <- data$edges

# Build the graph
g <- graph_from_data_frame(edges, vertices = nodes, directed = FALSE)

# Compute a simple centrality
strength_values <- strength(g, weights = E(g)$weight)

# Build JSON output
output <- data.frame(
  symptom = names(strength_values),
  strength = as.numeric(strength_values)
)

write_json(output, "data/r_results.json", pretty = TRUE)

cat("Analyse terminee : resultats ecrits dans data/r_results.json\n")
