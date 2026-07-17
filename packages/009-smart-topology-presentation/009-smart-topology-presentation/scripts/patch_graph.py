#!/usr/bin/env python3
import re
from pathlib import Path

path = Path("frontend/js/graph.js")
text = path.read_text(encoding="utf-8")

text, count = re.subn(
    r"function resolvedCanvasViewMode\(nodes = canvasManagedNodes\(\)\) \{.*?\n\}",
    """function resolvedCanvasViewMode(nodes = canvasManagedNodes()) {
  if (canvasViewMode !== "auto") {
    return canvasViewMode;
  }

  /*
   * Auto is the clean operational view.
   * Engineering remains the explicit X-ray view.
   */
  return "overview";
}""",
    text,
    count=1,
    flags=re.DOTALL,
)
if count != 1:
    raise SystemExit("Could not patch resolvedCanvasViewMode().")

replacement = """function canvasBuildModel() {
  const allNodes = canvasManagedNodes();
  const mode = resolvedCanvasViewMode(allNodes);

  if (mode === "engineering") {
    return {
      mode,
      nodes: allNodes,
      edges: graph.edges.map(edge => ({ ...edge }))
    };
  }

  /*
   * Overview is asset-centric. Workers and workloads remain available
   * in Engineering, but their live state is folded into matched assets.
   */
  const operationalNodes = allNodes.filter(node => {
    const category = inventoryCategory(node);

    return (
      category !== "worker" &&
      category !== "workload"
    );
  });

  const asicNodes = canvasAsicNodes(operationalNodes);
  const shouldClusterAsics = asicNodes.length > 50;

  if (!shouldClusterAsics) {
    const visibleIds = new Set(
      operationalNodes.map(node => node.id)
    );

    return {
      mode,
      nodes: operationalNodes,
      edges: graph.edges
        .filter(edge =>
          visibleIds.has(edge.source) &&
          visibleIds.has(edge.target)
        )
        .map(edge => ({ ...edge }))
    };
  }

  const visibleNodes = operationalNodes.filter(node =>
    inventoryCategory(node) !== "asic"
  );

  const syntheticEdges = [];

  visibleNodes
    .filter(node => inventoryCategory(node) === "pool")
    .forEach(poolNode => {
      const members = canvasClusterMembers(
        poolNode,
        asicNodes
      );

      if (!members.length) {
        return;
      }

      if (expandedPoolClusters.has(poolNode.id)) {
        visibleNodes.push(...members);

        members.forEach(member => {
          syntheticEdges.push({
            source: member.id,
            target: poolNode.id,
            type: "MINES_ON",
            label: "Mines On"
          });
        });

        return;
      }

      const cluster = canvasBuildPoolCluster(
        poolNode,
        members
      );

      visibleNodes.push(cluster);

      syntheticEdges.push({
        source: cluster.id,
        target: poolNode.id,
        type: "MINES_ON",
        label: "Mines On"
      });
    });

  const visibleIds = new Set(
    visibleNodes.map(node => node.id)
  );

  const retainedEdges = graph.edges.filter(edge =>
    String(edge.type || "").toUpperCase() !== "MINES_ON" &&
    visibleIds.has(edge.source) &&
    visibleIds.has(edge.target)
  );

  return {
    mode,
    nodes: visibleNodes,
    edges: [
      ...retainedEdges,
      ...syntheticEdges
    ]
  };
}

function canvasLayerForNode"""

text, count = re.subn(
    r"function canvasBuildModel\(\) \{.*?\n\}\n\nfunction canvasLayerForNode",
    replacement,
    text,
    count=1,
    flags=re.DOTALL,
)
if count != 1:
    raise SystemExit("Could not patch canvasBuildModel().")

path.write_text(text, encoding="utf-8")
print("Applied smart topology presentation patch.")
