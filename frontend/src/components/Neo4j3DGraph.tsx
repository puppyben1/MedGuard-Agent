import { useEffect, useMemo, useRef, useState } from "react";
import ForceGraph3D, { type ForceGraphMethods, type LinkObject, type NodeObject } from "react-force-graph-3d";
import type { Neo4jGraphPreview, Neo4jNode, Neo4jRelationship } from "../types";

type Graph3DNode = NodeObject<{
  id: string;
  label: string;
  labels: string[];
  properties: Neo4jNode["properties"];
  color: string;
  val: number;
}>;

type Graph3DLink = LinkObject<Graph3DNode, {
  source: string;
  target: string;
  type: string;
  properties: Neo4jRelationship["properties"];
  color: string;
  width: number;
}>;

interface Props {
  graph: Neo4jGraphPreview;
  selectedNodeId?: string | null;
  onNodeClick?: (nodeId: string) => void;
  onLinkClick?: (relationship: Neo4jRelationship) => void;
  compact?: boolean;
}

export default function Neo4j3DGraph({
  graph,
  selectedNodeId = null,
  onNodeClick,
  onLinkClick,
  compact = false,
}: Props) {
  const fgRef = useRef<ForceGraphMethods<Graph3DNode, Graph3DLink>>();
  const [hoveredNodeId, setHoveredNodeId] = useState<string | null>(null);
  const [reducedMotion, setReducedMotion] = useState(false);
  const height = compact ? 288 : 430;
  const renderLimit = compact ? 90 : 160;

  const graphData = useMemo(() => {
    const sampled = sampleGraph(graph, renderLimit);
    const nodes: Graph3DNode[] = sampled.nodes.map((node) => ({
      id: node.id,
      label: nodeLabel(node),
      labels: node.labels,
      properties: node.properties,
      color: nodeColor(node),
      val: node.labels.includes("Drug") ? 8 : node.labels.includes("SideEffect") ? 6 : 4,
    }));
    const links: Graph3DLink[] = sampled.relationships.map((rel) => ({
      source: rel.source,
      target: rel.target,
      type: rel.type,
      properties: rel.properties,
      color: relationshipColor(rel),
      width: rel.type === "HAS_SIDE_EFFECT" ? 1.8 : 1.2,
    }));
    return { nodes, links };
  }, [graph, renderLimit]);

  useEffect(() => {
    const query = window.matchMedia("(prefers-reduced-motion: reduce), (pointer: coarse)");
    const update = () => setReducedMotion(query.matches);
    update();
    query.addEventListener("change", update);
    return () => query.removeEventListener("change", update);
  }, []);

  useEffect(() => {
    const graphRef = fgRef.current;
    if (!graphRef || graphData.nodes.length === 0) return;
    const timeout = window.setTimeout(() => {
      graphRef.zoomToFit(650, 70);
    }, 250);
    return () => window.clearTimeout(timeout);
  }, [graphData]);

  if (graph.nodes.length === 0) {
    return (
      <div
        className="flex items-center justify-center rounded-md border border-slate-800 bg-slate-950 text-sm text-slate-500"
        style={{ minHeight: height }}
      >
        暂无可渲染图谱节点
      </div>
    );
  }

  return (
    <div className="relative overflow-hidden rounded-md border border-slate-800 bg-[#050b14]" style={{ height }}>
      <div className="absolute inset-0 adr-grid-bg" />
      <ForceGraph3D<Graph3DNode, Graph3DLink>
        ref={fgRef}
        graphData={graphData}
        width={undefined}
        height={height}
        backgroundColor="rgba(5, 11, 20, 0)"
        showNavInfo={false}
        nodeLabel={(node) => `${node.label}\n${node.labels.join(" / ")}`}
        nodeColor={(node) => (node.id === selectedNodeId || node.id === hoveredNodeId ? "#fef3c7" : node.color)}
        nodeVal={(node) => (node.id === selectedNodeId ? node.val + 4 : node.val)}
        nodeResolution={reducedMotion ? 12 : 20}
        linkLabel={(link) => link.type}
        linkColor={(link) => link.color}
        linkWidth={(link) => link.width}
        linkOpacity={0.72}
        linkDirectionalParticles={(link) => (reducedMotion ? 0 : link.type === "HAS_SIDE_EFFECT" ? 2 : 1)}
        linkDirectionalParticleWidth={1.6}
        linkDirectionalParticleSpeed={0.006}
        cooldownTicks={reducedMotion ? 35 : 70}
        warmupTicks={reducedMotion ? 8 : 16}
        enableNodeDrag
        enableNavigationControls
        onNodeHover={(node) => setHoveredNodeId(node?.id ? String(node.id) : null)}
        onNodeClick={(node) => {
          if (node.id) onNodeClick?.(String(node.id));
          if (node.x !== undefined && node.y !== undefined && node.z !== undefined) {
            const distance = 80;
            const distRatio = 1 + distance / Math.hypot(node.x, node.y, node.z);
            fgRef.current?.cameraPosition(
              { x: node.x * distRatio, y: node.y * distRatio, z: node.z * distRatio },
              { x: node.x, y: node.y, z: node.z },
              650,
            );
          }
        }}
        onLinkClick={(link) => {
          const source = endpointId(link.source);
          const target = endpointId(link.target);
          onLinkClick?.({ source, target, type: link.type, properties: link.properties });
        }}
      />
      <div className="pointer-events-none absolute left-3 top-3 rounded border border-slate-800 bg-slate-950/80 px-2 py-1 text-[11px] text-cyan-100">
        WebGL 3D · {graph.nodes.length} nodes · {graph.relationships.length} edges
      </div>
    </div>
  );
}

function sampleGraph(graph: Neo4jGraphPreview, limit: number): Neo4jGraphPreview {
  if (graph.nodes.length <= limit) return graph;
  const priority = new Map<string, number>();
  graph.nodes.forEach((node) => {
    const score =
      (node.labels.includes("Drug") ? 100 : 0) +
      (node.labels.includes("SideEffect") || node.labels.includes("MedDRATerm") ? 80 : 0) +
      (node.labels.includes("Mechanism") ? 70 : 0) +
      (node.labels.includes("Evidence") ? 40 : 0);
    priority.set(node.id, score);
  });
  graph.relationships.forEach((rel) => {
    priority.set(rel.source, (priority.get(rel.source) ?? 0) + 1);
    priority.set(rel.target, (priority.get(rel.target) ?? 0) + 1);
  });
  const selected = new Set(
    [...graph.nodes]
      .sort((left, right) => (priority.get(right.id) ?? 0) - (priority.get(left.id) ?? 0))
      .slice(0, limit)
      .map((node) => node.id),
  );
  return {
    ...graph,
    nodes: graph.nodes.filter((node) => selected.has(node.id)),
    relationships: graph.relationships.filter((rel) => selected.has(rel.source) && selected.has(rel.target)),
  };
}

function endpointId(endpoint: unknown) {
  if (endpoint && typeof endpoint === "object" && "id" in endpoint) {
    return String((endpoint as { id?: string | number }).id);
  }
  return String(endpoint ?? "");
}

function nodeLabel(node: Neo4jNode) {
  return String(node.properties.name ?? node.properties.term ?? node.properties.cid ?? node.properties.cui ?? node.id);
}

function nodeColor(node: Neo4jNode) {
  if (node.labels.includes("Drug")) return "#60a5fa";
  if (node.labels.includes("SideEffect") || node.labels.includes("MedDRATerm")) return "#f87171";
  if (node.labels.includes("Evidence")) return "#22d3ee";
  if (node.labels.includes("Lab")) return "#34d399";
  if (node.labels.includes("Mechanism")) return "#a78bfa";
  return "#34d399";
}

function relationshipColor(rel: Neo4jRelationship) {
  if (rel.type === "HAS_SIDE_EFFECT") return "#38bdf8";
  if (rel.type === "INCREASES_RISK") return "#fb7185";
  if (rel.type === "SUPPORTS" || rel.type === "SUPPORTED_BY") return "#22d3ee";
  if (rel.type === "NORMALIZED_TO") return "#a78bfa";
  return "#94a3b8";
}
