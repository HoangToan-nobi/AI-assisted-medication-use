"use client";

import { useMemo, useRef, useState } from "react";
import MaterialIcon from "@/components/MaterialIcon";
import type { Severity } from "@/lib/api";
import { NODE_FILL_PALETTE, circleLayout, type GraphGroup } from "@/lib/interactionGraph";
import GraphTooltip from "./GraphTooltip";

export type GraphNodeVM = { id: string; label: string; groupId: string };
export type GraphEdgeVM = { id: string; sourceId: string; targetId: string; muc_do?: Severity; hasIncompletePair: boolean };

export const SEVERITY_EDGE_COLOR: Record<Severity, string> = { nang: "#c94740", trung_binh: "#c58a32", nhe: "#5d9b78", chua_phan_loai: "#8d98a4" };

type Hovered = { type: "node" | "edge"; id: string };

type InteractionGraphViewProps = {
  nodes: GraphNodeVM[];
  edges: GraphEdgeVM[];
  groups: GraphGroup[];
  ariaLabel: string;
};

function truncateLabel(label: string, max = 17): string {
  return label.length > max ? `${label.slice(0, max)}…` : label;
}

// Bấm vào 1 cạnh không drill-down xuống cấp dưới nữa (đó là việc của nút "Xem chi
// tiết" trên từng thẻ giải thích) - chỉ cuộn tới đúng thẻ giải thích tương ứng và
// nháy viền vàng để người dùng dễ nhận ra, tái dùng class ".interaction-pair-card--focused" đã có sẵn.
function scrollToPairCard(edgeId: string) {
  const target = document.getElementById(`interaction-pair-${edgeId}`);
  if (!target) return;
  target.scrollIntoView({ behavior: "smooth", block: "center" });
  target.classList.add("interaction-pair-card--focused");
  window.setTimeout(() => target.classList.remove("interaction-pair-card--focused"), 1600);
}

export default function InteractionGraphView({ nodes, edges, groups, ariaLabel }: InteractionGraphViewProps) {
  const svgRef = useRef<SVGSVGElement>(null);
  const [hovered, setHovered] = useState<Hovered | null>(null);
  const [tooltip, setTooltip] = useState<{ left: number; top: number; content: string; below: boolean; background?: string } | null>(null);

  const positions = useMemo(() => circleLayout(nodes.length), [nodes.length]);
  const positionById = useMemo(() => new Map(nodes.map((n, i) => [n.id, positions[i]])), [nodes, positions]);
  const groupById = useMemo(() => new Map(groups.map((g) => [g.id, g])), [groups]);
  const nodeById = useMemo(() => new Map(nodes.map((n) => [n.id, n])), [nodes]);
  const edgeById = useMemo(() => new Map(edges.map((e) => [e.id, e])), [edges]);
  // Tập id các node kề (bao gồm chính nó) cho từng node - dùng để làm sáng cả cụm
  // node+cạnh+node liên quan khi hover 1 node, không chỉ riêng node đó.
  const neighborsById = useMemo(() => {
    const map = new Map<string, Set<string>>();
    for (const node of nodes) map.set(node.id, new Set([node.id]));
    for (const edge of edges) {
      map.get(edge.sourceId)?.add(edge.targetId);
      map.get(edge.targetId)?.add(edge.sourceId);
    }
    return map;
  }, [nodes, edges]);

  function colorForNode(node: GraphNodeVM, index: number): string {
    return groupById.get(node.groupId)?.color ?? NODE_FILL_PALETTE[index % NODE_FILL_PALETTE.length];
  }

  function edgePath(edge: GraphEdgeVM): string | null {
    const p1 = positionById.get(edge.sourceId);
    const p2 = positionById.get(edge.targetId);
    if (!p1 || !p2) return null;
    const [x1, y1] = p1;
    const [x2, y2] = p2;
    const mx = (x1 + x2) / 2;
    const my = (y1 + y2) / 2;
    const dx = x2 - x1;
    const dy = y2 - y1;
    const len = Math.hypot(dx, dy) || 1;
    const nx = -dy / len;
    const ny = dx / len;
    // Bẻ cong điểm điều khiển về phía tâm layout (50,50, khớp mặc định của
    // circleLayout) thay vì đổi hướng tùy tiện theo chỉ số - để cạnh luôn võng
    // vào trong như mạng lưới tròn, không bao giờ phình ra ngoài rìa đồ thị.
    const towardCenterX = 50 - mx;
    const towardCenterY = 50 - my;
    const sign = nx * towardCenterX + ny * towardCenterY >= 0 ? 1 : -1;
    const offset = len * 0.18 * sign;
    const cx = mx + nx * offset;
    const cy = my + ny * offset;
    return `M ${x1},${y1} Q ${cx},${cy} ${x2},${y2}`;
  }

  function edgeOpacity(edge: GraphEdgeVM): number {
    if (!hovered) return 0.55;
    if (hovered.type === "edge") return hovered.id === edge.id ? 1 : 0.08;
    return edge.sourceId === hovered.id || edge.targetId === hovered.id ? 1 : 0.08;
  }

  function nodeVisualState(node: GraphNodeVM): { opacity: number; filter: string } {
    if (!hovered) return { opacity: 1, filter: "none" };
    const connected = hovered.type === "node"
      ? (neighborsById.get(hovered.id)?.has(node.id) ?? node.id === hovered.id)
      : (() => {
          const edge = edgeById.get(hovered.id);
          return edge ? node.id === edge.sourceId || node.id === edge.targetId : false;
        })();
    return connected ? { opacity: 1, filter: "none" } : { opacity: 0.3, filter: "saturate(0.3)" };
  }

  function svgPointToClient(x: number, y: number): { left: number; top: number } | null {
    const svg = svgRef.current;
    if (!svg) return null;
    const ctm = svg.getScreenCTM();
    if (!ctm) return null;
    const pt = svg.createSVGPoint();
    pt.x = x;
    pt.y = y;
    const p = pt.matrixTransform(ctm);
    const rect = svg.getBoundingClientRect();
    return { left: p.x - rect.left, top: p.y - rect.top };
  }

  // Lật tooltip xuống dưới khi điểm neo quá gần mép trên của canvas (0..100),
  // tránh bị cắt bởi phần header phía trên khung đồ thị.
  function anchorY(y: number, offsetAbove: number, offsetBelow: number): { y: number; below: boolean } {
    return y < 18 ? { y: y + offsetBelow, below: true } : { y: y - offsetAbove, below: false };
  }

  function handleEdgeEnter(edge: GraphEdgeVM) {
    setHovered({ type: "edge", id: edge.id });
    const p1 = positionById.get(edge.sourceId);
    const p2 = positionById.get(edge.targetId);
    if (!p1 || !p2) return;
    const midY = (p1[1] + p2[1]) / 2;
    const anchor = anchorY(midY, 6, 6);
    const pos = svgPointToClient((p1[0] + p2[0]) / 2, anchor.y);
    if (!pos) return;
    const nodeA = nodeById.get(edge.sourceId);
    const nodeB = nodeById.get(edge.targetId);
    const background = edge.muc_do ? SEVERITY_EDGE_COLOR[edge.muc_do] : "#8d98a4";
    setTooltip({ ...pos, below: anchor.below, background, content: `${nodeA?.label ?? ""} ⇄ ${nodeB?.label ?? ""}` });
  }

  function handleNodeEnter(node: GraphNodeVM) {
    setHovered({ type: "node", id: node.id });
    const p = positionById.get(node.id);
    if (!p) return;
    const anchor = anchorY(p[1], 10, 14);
    const pos = svgPointToClient(p[0], anchor.y);
    if (!pos) return;
    setTooltip({ ...pos, below: anchor.below, content: node.label });
  }

  function handleLeave() {
    setHovered(null);
    setTooltip(null);
  }

  if (nodes.length === 0) {
    return <div className="graph-placeholder"><MaterialIcon name="hub" size={42} /><span>Đồ thị sẽ hiển thị sau khi bạn chọn thuốc</span></div>;
  }

  return (
    <div className="tt-graph-canvas">
      <svg ref={svgRef} viewBox="0 0 100 100" role="img" aria-label={ariaLabel} onMouseLeave={handleLeave}>
        {edges.map((edge) => {
          const d = edgePath(edge);
          if (!d) return null;
          const color = edge.muc_do ? SEVERITY_EDGE_COLOR[edge.muc_do] : "#9bb1c9";
          return (
            <g key={edge.id} className="tt-graph-edge-group tt-graph-edge-group--clickable">
              <path
                d={d}
                className="tt-graph-edge-hit"
                onPointerEnter={() => handleEdgeEnter(edge)}
                onPointerLeave={handleLeave}
                onClick={() => scrollToPairCard(edge.id)}
              />
              <path d={d} className="tt-graph-edge" style={{ stroke: color, opacity: edgeOpacity(edge) }} />
            </g>
          );
        })}
        {nodes.map((node, index) => {
          const pos = positionById.get(node.id);
          if (!pos) return null;
          const state = nodeVisualState(node);
          return (
            <g
              key={node.id}
              className="tt-graph-node"
              transform={`translate(${pos[0]} ${pos[1]})`}
              style={{ opacity: state.opacity, filter: state.filter }}
              onPointerEnter={() => handleNodeEnter(node)}
              onPointerLeave={handleLeave}
            >
              <circle r="8" fill={colorForNode(node, index)} />
              <text className="tt-graph-node__label" y="13" textAnchor="middle">{truncateLabel(node.label)}</text>
            </g>
          );
        })}
      </svg>
      {tooltip && <GraphTooltip left={tooltip.left} top={tooltip.top} below={tooltip.below} background={tooltip.background}>{tooltip.content}</GraphTooltip>}
      {groups.length > 0 && (
        <div className="tt-graph-legend">
          {groups.map((g) => <span key={g.id}><i className="tt-graph-legend__dot" style={{ background: g.color }} /> {g.label}</span>)}
        </div>
      )}
    </div>
  );
}
