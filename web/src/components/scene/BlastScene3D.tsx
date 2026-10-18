import React, { useRef, useMemo, useEffect } from 'react';
import { Canvas, useFrame, useThree } from '@react-three/fiber';
import { OrbitControls, Html } from '@react-three/drei';
import * as THREE from 'three';
import { forceSimulation, forceLink, forceManyBody, forceRadial, forceCollide } from 'd3-force-3d';
import { useUiStore } from '../../store/uiStore';
import type { GraphNode, GraphEdge } from '../../api/types';

interface BlastScene3DProps {
  nodes: GraphNode[];
  edges: GraphEdge[];
}

interface SimNode extends GraphNode {
  x: number;
  y: number;
  z: number;
  hop: number;
  index?: number;
}

const HOP_MAP: Record<string, number> = {
  Retraction: 0,
  Trial: 1,
  Review: 2,
  Guideline: 3,
  Decision: 4,
  Committee: 5,
  Person: 5,
};


export const BlastScene3D: React.FC<BlastScene3DProps> = ({ nodes, edges }) => {
  return (
    <div className="w-full h-full relative bg-[#0B0D10]">
      <Canvas
        frameloop="demand"
        dpr={[1, 2]}
        camera={{ position: [0, 90, 240], fov: 42 }}
        gl={{ antialias: true, alpha: false, powerPreference: 'high-performance' }}
      >
        <color attach="background" args={['#0B0D10']} />
        <fog attach="fog" args={['#0B0D10', 160, 420]} />
        <ambientLight intensity={0.5} />
        <directionalLight position={[60, 100, 60]} intensity={0.9} />
        <hemisphereLight args={['#5B8CFF', '#12151A', 0.4]} />

        <SceneContent nodes={nodes} edges={edges} />
      </Canvas>
    </div>
  );
};

const SceneContent: React.FC<BlastScene3DProps> = ({ nodes, edges }) => {
  const { selectedNode, setSelectedNode, hoveredNode, rippleTrigger } = useUiStore();
  const { camera, invalidate } = useThree();
  const controlsRef = useRef<any>(null);

  // Compute 3D node positions via d3-force-3d
  const { simNodes, nodeMap, linksData } = useMemo(() => {
    const sNodes: SimNode[] = nodes.map((n) => {
      const hop = HOP_MAP[n.label] ?? 2;
      return {
        ...n,
        hop,
        x: (Math.random() - 0.5) * 10,
        y: (Math.random() - 0.5) * 10,
        z: (Math.random() - 0.5) * 10,
      };
    });

    const nMap = new Map<string, SimNode>();
    sNodes.forEach((n) => nMap.set(n.id, n));

    const sLinks = edges
      .filter((e) => nMap.has(e.source) && nMap.has(e.target))
      .map((e) => ({
        source: e.source,
        target: e.target,
        type: e.type,
      }));

    const sim = forceSimulation(sNodes, 3)
      .force('charge', forceManyBody().strength(-40))
      .force(
        'radial',
        forceRadial<SimNode>((d) => d.hop * 26, 0, 0, 0).strength(0.85)
      )
      .force('collide', forceCollide<SimNode>(9).strength(0.7))
      .force(
        'link',
        forceLink(sLinks)
          .id((d: any) => d.id)
          .distance(28)
          .strength(0.2)
      )
      .stop();

    // Execute 90 ticks deterministically
    for (let i = 0; i < 90; ++i) sim.tick();

    return { simNodes: sNodes, nodeMap: nMap, linksData: sLinks };
  }, [nodes, edges]);

  // Neighbor lookup for hover highlighting
  const neighborsMap = useMemo(() => {
    const map = new Map<string, Set<string>>();
    linksData.forEach((l: any) => {
      const sId = typeof l.source === 'object' ? l.source.id : l.source;
      const tId = typeof l.target === 'object' ? l.target.id : l.target;
      if (!map.has(sId)) map.set(sId, new Set());
      if (!map.has(tId)) map.set(tId, new Set());
      map.get(sId)!.add(tId);
      map.get(tId)!.add(sId);
    });
    return map;
  }, [linksData]);

  // Ripple Animation state
  const rippleStartTime = useRef(Date.now());
  useEffect(() => {
    rippleStartTime.current = Date.now();
    invalidate();
  }, [rippleTrigger, invalidate]);

  // Camera focus animation state
  const targetCamPos = useRef<THREE.Vector3 | null>(null);
  const targetLookAt = useRef<THREE.Vector3 | null>(null);

  useEffect(() => {
    if (selectedNode) {
      const node = nodeMap.get(selectedNode.id);
      if (node) {
        targetLookAt.current = new THREE.Vector3(node.x, node.y, node.z);
        targetCamPos.current = new THREE.Vector3(node.x, node.y + 20, node.z + 50);
        invalidate();
      }
    }
  }, [selectedNode, nodeMap, invalidate]);

  // Wire up Reset Camera button
  useEffect(() => {
    const btn = document.getElementById('btn-reset-camera');
    if (!btn) return;
    const handleReset = () => {
      targetLookAt.current = new THREE.Vector3(0, 0, 0);
      targetCamPos.current = new THREE.Vector3(0, 90, 240);
      setSelectedNode(null);
      invalidate();
    };
    btn.addEventListener('click', handleReset);
    return () => btn.removeEventListener('click', handleReset);
  }, [setSelectedNode, invalidate]);

  // Group nodes by shape for InstancedMesh
  const groupedNodes = useMemo(() => {
    const groups: Record<string, SimNode[]> = {
      Retraction: [],
      Trial: [],
      Review: [],
      Guideline: [],
      Decision: [],
      Committee: [],
    };

    simNodes.forEach((n) => {
      if (n.label === 'Committee' || n.label === 'Person') {
        groups.Committee.push(n);
      } else if (groups[n.label]) {
        groups[n.label].push(n);
      } else {
        groups.Review.push(n);
      }
    });

    return groups;
  }, [simNodes]);

  // Line segments geometry
  const edgeLinePositions = useMemo(() => {
    const pos = new Float32Array(linksData.length * 6);
    let idx = 0;
    linksData.forEach((l: any) => {
      const s = typeof l.source === 'object' ? l.source : nodeMap.get(l.source);
      const t = typeof l.target === 'object' ? l.target : nodeMap.get(l.target);
      if (s && t) {
        pos[idx++] = s.x;
        pos[idx++] = s.y;
        pos[idx++] = s.z;
        pos[idx++] = t.x;
        pos[idx++] = t.y;
        pos[idx++] = t.z;
      }
    });
    return pos.subarray(0, idx);
  }, [linksData, nodeMap]);

  // Ripple wave ring mesh reference
  const ringRef = useRef<THREE.Mesh>(null);

  // Animation frame loop
  useFrame(() => {
    const now = Date.now();
    const rippleElapsed = (now - rippleStartTime.current) / 1000;

    // Expand ripple ring across shells (up to 1.5 seconds)
    if (ringRef.current && rippleElapsed < 1.6) {
      const scale = rippleElapsed * 100;
      ringRef.current.scale.set(scale, scale, 1);
      const mat = ringRef.current.material as THREE.MeshBasicMaterial;
      mat.opacity = Math.max(0, 0.45 * (1 - rippleElapsed / 1.5));
      invalidate();
    }

    // Camera tween interpolation
    if (targetCamPos.current && targetLookAt.current && controlsRef.current) {
      camera.position.lerp(targetCamPos.current, 0.08);
      controlsRef.current.target.lerp(targetLookAt.current, 0.08);
      controlsRef.current.update();

      if (camera.position.distanceTo(targetCamPos.current) < 0.5) {
        targetCamPos.current = null;
        targetLookAt.current = null;
      } else {
        invalidate();
      }
    }
  });

  const activeId = hoveredNode?.id || selectedNode?.id || null;
  const activeNeighbors = activeId ? neighborsMap.get(activeId) : null;

  return (
    <>
      <OrbitControls
        ref={controlsRef}
        enableDamping
        dampingFactor={0.08}
        minDistance={40}
        maxDistance={450}
        maxPolarAngle={Math.PI / 2 + 0.1}
        onChange={() => invalidate()}
      />

      {/* Ripple ring wave in X-Z ground plane */}
      <mesh ref={ringRef} rotation={[-Math.PI / 2, 0, 0]} position={[0, -2, 0]}>
        <ringGeometry args={[0.98, 1.0, 64]} />
        <meshBasicMaterial color="#5B8CFF" transparent opacity={0.3} side={THREE.DoubleSide} />
      </mesh>

      {/* Edges as single LineSegments */}
      {edgeLinePositions.length > 0 && (
        <lineSegments>
          <bufferGeometry>
            <bufferAttribute
              attach="attributes-position"
              args={[edgeLinePositions, 3]}
            />
          </bufferGeometry>
          <lineBasicMaterial color="#9AA3AF" transparent opacity={0.22} />
        </lineSegments>
      )}

      {/* Instanced Meshes per Node Type */}
      <InstancedTypeGroup
        type="Retraction"
        nodes={groupedNodes.Retraction}
        geometry={<octahedronGeometry args={[4.5, 0]} />}
        baseColor="#E5484D"
        activeId={activeId}
        activeNeighbors={activeNeighbors}
        rippleStartTime={rippleStartTime}
      />

      <InstancedTypeGroup
        type="Trial"
        nodes={groupedNodes.Trial}
        geometry={<sphereGeometry args={[3.2, 16, 16]} />}
        baseColor="#F5A524"
        activeId={activeId}
        activeNeighbors={activeNeighbors}
        rippleStartTime={rippleStartTime}
      />

      <InstancedTypeGroup
        type="Review"
        nodes={groupedNodes.Review}
        geometry={<boxGeometry args={[4.8, 4.8, 4.8]} />}
        baseColor="#5B8CFF"
        activeId={activeId}
        activeNeighbors={activeNeighbors}
        rippleStartTime={rippleStartTime}
      />

      <InstancedTypeGroup
        type="Guideline"
        nodes={groupedNodes.Guideline}
        geometry={<icosahedronGeometry args={[4.0, 0]} />}
        baseColor="#6366f1"
        activeId={activeId}
        activeNeighbors={activeNeighbors}
        rippleStartTime={rippleStartTime}
      />

      <InstancedTypeGroup
        type="Decision"
        nodes={groupedNodes.Decision}
        geometry={<dodecahedronGeometry args={[4.2, 0]} />}
        baseColor="#d946ef"
        activeId={activeId}
        activeNeighbors={activeNeighbors}
        rippleStartTime={rippleStartTime}
      />

      <InstancedTypeGroup
        type="Committee"
        nodes={groupedNodes.Committee}
        geometry={<coneGeometry args={[2.8, 5.0, 12]} />}
        baseColor="#9AA3AF"
        activeId={activeId}
        activeNeighbors={activeNeighbors}
        rippleStartTime={rippleStartTime}
      />

      {/* Monospace Labels for Selected, Hovered, and Epicenter ONLY */}
      {simNodes.map((n) => {
        const isSelected = selectedNode?.id === n.id;
        const isHovered = hoveredNode?.id === n.id;
        const isRetraction = n.label === 'Retraction';

        if (!isSelected && !isHovered && !isRetraction) return null;

        return (
          <Html
            key={n.id}
            position={[n.x, n.y + 7.5, n.z]}
            center
            style={{ pointerEvents: 'none' }}
          >
            <div className="bg-[#12151A]/95 text-[#E6E8EB] border border-[#232831] px-1.5 py-0.5 rounded text-[10px] font-mono whitespace-nowrap shadow-md select-none flex items-center gap-1">
              <span className="font-semibold">{n.id}</span>
              {n.status === 'at_risk' && (
                <span className="text-[#F5A524] font-bold">[at_risk]</span>
              )}
            </div>
          </Html>
        );
      })}
    </>
  );
};

interface InstancedGroupProps {
  type: string;
  nodes: SimNode[];
  geometry: React.ReactNode;
  baseColor: string;
  activeId: string | null;
  activeNeighbors: Set<string> | null | undefined;
  rippleStartTime: React.MutableRefObject<number>;
}

const InstancedTypeGroup: React.FC<InstancedGroupProps> = ({
  nodes,
  geometry,
  baseColor,
  activeId,
  activeNeighbors,
  rippleStartTime,
}) => {
  const meshRef = useRef<THREE.InstancedMesh>(null);
  const { setSelectedNode, setHoveredNode } = useUiStore();
  const dummy = useMemo(() => new THREE.Object3D(), []);
  const color = useMemo(() => new THREE.Color(), []);

  // Update instance matrices and colors
  useFrame(() => {
    if (!meshRef.current || nodes.length === 0) return;
    const now = Date.now();
    const elapsed = (now - rippleStartTime.current) / 1000;

    nodes.forEach((node, i) => {
      // Ripple wave scale-in animation: hop distance * 200ms
      const nodeAppearTime = node.hop * 0.2;
      let scale = 1.0;
      if (elapsed < nodeAppearTime) {
        scale = 0.001;
      } else if (elapsed < nodeAppearTime + 0.3) {
        // Smooth ease-out scale
        const t = (elapsed - nodeAppearTime) / 0.3;
        scale = Math.sin((t * Math.PI) / 2);
      }

      dummy.position.set(node.x, node.y, node.z);
      dummy.scale.set(scale, scale, scale);
      dummy.updateMatrix();
      meshRef.current!.setMatrixAt(i, dummy.matrix);

      // Color computation: Decision at_risk turns amber
      const isAtRisk = node.label === 'Decision' && node.status === 'at_risk';
      const nodeCol = isAtRisk ? '#F5A524' : baseColor;
      color.set(nodeCol);

      // Dimming logic on hover
      if (activeId) {
        const isSelf = node.id === activeId;
        const isNeighbor = activeNeighbors?.has(node.id);
        if (!isSelf && !isNeighbor) {
          color.multiplyScalar(0.25);
        } else if (isSelf) {
          color.addScalar(0.25);
        }
      }

      meshRef.current!.setColorAt(i, color);
    });

    meshRef.current.instanceMatrix.needsUpdate = true;
    if (meshRef.current.instanceColor) meshRef.current.instanceColor.needsUpdate = true;
  });

  if (nodes.length === 0) return null;

  return (
    <instancedMesh
      ref={meshRef}
      args={[undefined, undefined, nodes.length]}
      onClick={(e) => {
        e.stopPropagation();
        if (e.instanceId !== undefined && nodes[e.instanceId]) {
          setSelectedNode(nodes[e.instanceId]);
        }
      }}
      onPointerOver={(e) => {
        e.stopPropagation();
        if (e.instanceId !== undefined && nodes[e.instanceId]) {
          setHoveredNode(nodes[e.instanceId]);
        }
      }}
      onPointerOut={() => {
        setHoveredNode(null);
      }}
    >
      {geometry}
      <meshStandardMaterial roughness={0.35} metalness={0.15} />
    </instancedMesh>
  );
};
