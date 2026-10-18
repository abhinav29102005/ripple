import React, { useRef, useMemo, useEffect, useState } from 'react';
import { Canvas, useFrame, useThree } from '@react-three/fiber';
import { OrbitControls, Html } from '@react-three/drei';
import * as THREE from 'three';
import { forceSimulation, forceLink, forceManyBody, forceCollide, forceX, forceY, forceZ } from 'd3-force-3d';
import { useUiStore } from '../../store/uiStore';
import type { GraphNode, GraphEdge } from '../../api/types';
import { ShieldAlert, Brain } from 'lucide-react';

interface BlastScene3DProps {
  nodes: GraphNode[];
  edges: GraphEdge[];
}

interface SimNode extends GraphNode {
  x: number;
  y: number;
  z: number;
  hop: number;
  targetX: number;
  targetY: number;
  targetZ: number;
  hemisphere: 'left' | 'right' | 'core' | 'bridge';
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

// Category Theme Palette
const PALETTE: Record<string, { base: string; glow: string; name: string }> = {
  Retraction: { base: '#EF4444', glow: '#DC2626', name: 'Retraction Notice' },
  Trial: { base: '#F59E0B', glow: '#D97706', name: 'Clinical Trial' },
  Review: { base: '#06B6D4', glow: '#0891B2', name: 'Systematic Review' },
  Guideline: { base: '#818CF8', glow: '#6366F1', name: 'Clinical Guideline' },
  Decision: { base: '#EC4899', glow: '#DB2777', name: 'Operational Decision' },
  Committee: { base: '#A78BFA', glow: '#8B5CF6', name: 'Governance Committee' },
  Person: { base: '#38BDF8', glow: '#0284C7', name: 'Clinical Leader' },
};

export const BlastScene3D: React.FC<BlastScene3DProps> = ({ nodes, edges }) => {
  const [cursorState, setCursorState] = useState<'grab' | 'grabbing' | 'pointer'>('grab');

  return (
    <div
      className={`w-full h-full relative bg-[#07090E] select-none ${
        cursorState === 'pointer'
          ? 'cursor-pointer'
          : cursorState === 'grabbing'
          ? 'cursor-grabbing'
          : 'cursor-grab'
      }`}
    >
      {/* Subtle brain hemisphere spatial badges */}
      <div className="absolute top-3 left-4 pointer-events-none z-10 flex items-center gap-2 text-[10px] font-mono text-muted/80">
        <span className="flex items-center gap-1.5 px-2 py-0.5 rounded bg-surface/60 border border-border/40 backdrop-blur-sm">
          <Brain className="w-3 h-3 text-cyan-400" />
          <span>Left Lobe: Cardiology Evidence</span>
        </span>
      </div>
      <div className="absolute top-3 right-4 pointer-events-none z-10 flex items-center gap-2 text-[10px] font-mono text-muted/80">
        <span className="flex items-center gap-1.5 px-2 py-0.5 rounded bg-surface/60 border border-border/40 backdrop-blur-sm">
          <span>Right Lobe: Oncology Formulary</span>
          <Brain className="w-3 h-3 text-indigo-400" />
        </span>
      </div>

      <Canvas
        frameloop="always"
        dpr={[1, 2]}
        camera={{ position: [0, 45, 230], fov: 42 }}
        gl={{ antialias: true, alpha: false, powerPreference: 'high-performance' }}
        onPointerDown={() => setCursorState((prev) => (prev === 'pointer' ? 'pointer' : 'grabbing'))}
        onPointerUp={() => setCursorState((prev) => (prev === 'pointer' ? 'pointer' : 'grab'))}
      >
        <color attach="background" args={['#07090E']} />
        <fog attach="fog" args={['#07090E', 180, 480]} />
        <ambientLight intensity={0.65} />
        <pointLight position={[0, 0, 0]} intensity={1.5} distance={180} color="#38BDF8" />
        <directionalLight position={[80, 120, 80]} intensity={1.1} color="#E0F2FE" />
        <directionalLight position={[-80, -60, -60]} intensity={0.5} color="#818CF8" />

        <SceneContent nodes={nodes} edges={edges} setCursorState={setCursorState} />
      </Canvas>
    </div>
  );
};

const SceneContent: React.FC<BlastScene3DProps & { setCursorState: React.Dispatch<React.SetStateAction<'grab' | 'grabbing' | 'pointer'>> }> = ({
  nodes,
  edges,
  setCursorState,
}) => {
  const { selectedNode, setSelectedNode, hoveredNode, rippleTrigger } = useUiStore();
  const { camera } = useThree();
  const controlsRef = useRef<any>(null);

  // Compute 3D dual-hemisphere brain layout
  const { simNodes, nodeMap, linksData } = useMemo(() => {
    const sNodes: SimNode[] = nodes.map((n, i) => {
      const hop = HOP_MAP[n.label] ?? 2;

      // Determine hemisphere assignment
      let hemi: 'left' | 'right' | 'core' | 'bridge' = 'left';
      if (n.label === 'Retraction') {
        hemi = 'core';
      } else if (n.hemisphere === 'right' || n.id.includes('ONCO') || i % 2 === 1) {
        hemi = 'right';
      } else if (n.hemisphere === 'bridge' || (n.label === 'Trial' && i % 4 === 0)) {
        hemi = 'bridge';
      } else {
        hemi = 'left';
      }

      // Brain anatomical manifold target coordinates:
      // Left hemisphere: x < 0, Right hemisphere: x > 0, Core: center thalamus
      const sign = hemi === 'core' ? 0 : hemi === 'bridge' ? (i % 2 === 0 ? 0.35 : -0.35) : hemi === 'right' ? 1 : -1;
      const angle = (i * 2.39996) % (2 * Math.PI); // golden angle distribution
      const elevation = Math.sin(i * 1.618) * 0.75; // vertical spread

      const hopRad = 16 + hop * 18;
      // Ellipsoidal brain lobes (wider along Z, curved along Y, separated on X)
      const targetX = sign === 0 ? 0 : sign * (14 + hopRad * 0.75 * Math.abs(Math.cos(elevation) * Math.sin(angle)));
      const targetY = hopRad * 0.85 * elevation + (hop === 0 ? -12 : (Math.sin(angle) * 8));
      const targetZ = hopRad * 1.15 * Math.cos(elevation) * Math.cos(angle) - (hop === 0 ? 8 : 4);

      return {
        ...n,
        hop,
        hemisphere: hemi,
        targetX,
        targetY,
        targetZ,
        x: targetX + (Math.random() - 0.5) * 6,
        y: targetY + (Math.random() - 0.5) * 6,
        z: targetZ + (Math.random() - 0.5) * 6,
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

    // 3D physics simulation to relax positions along brain target manifold
    const sim = forceSimulation(sNodes, 3)
      .force('targetX', forceX<SimNode>((d: SimNode) => d.targetX).strength(0.65))
      .force('targetY', forceY<SimNode>((d: SimNode) => d.targetY).strength(0.65))
      .force('targetZ', forceZ<SimNode>((d: SimNode) => d.targetZ).strength(0.65))
      .force('charge', forceManyBody().strength(-30))
      .force('collide', forceCollide<SimNode>(8.5).strength(0.85))
      .force(
        'link',
        forceLink(sLinks)
          .id((d: any) => d.id)
          .distance(24)
          .strength(0.2)
      )
      .stop();

    // Execute 85 deterministic relaxation ticks
    for (let i = 0; i < 85; ++i) sim.tick();

    return { simNodes: sNodes, nodeMap: nMap, linksData: sLinks };
  }, [nodes, edges]);

  // Neighbors map for hover tracing
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

  // Ripple Wave trigger timing
  const rippleStartTime = useRef(Date.now());
  useEffect(() => {
    rippleStartTime.current = Date.now();
  }, [rippleTrigger]);

  // Camera lerp animation state
  const targetCamPos = useRef<THREE.Vector3 | null>(null);
  const targetLookAt = useRef<THREE.Vector3 | null>(null);

  useEffect(() => {
    if (selectedNode) {
      const node = nodeMap.get(selectedNode.id);
      if (node) {
        targetLookAt.current = new THREE.Vector3(node.x, node.y, node.z);
        targetCamPos.current = new THREE.Vector3(node.x, node.y + 18, node.z + 55);
      }
    }
  }, [selectedNode, nodeMap]);

  // Reset camera handler
  useEffect(() => {
    const btn = document.getElementById('btn-reset-camera');
    if (!btn) return;
    const handleReset = () => {
      targetLookAt.current = new THREE.Vector3(0, 0, 0);
      targetCamPos.current = new THREE.Vector3(0, 45, 230);
      setSelectedNode(null);
    };
    btn.addEventListener('click', handleReset);
    return () => btn.removeEventListener('click', handleReset);
  }, [setSelectedNode]);

  // Edge line segments geometry
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

  // Continuous animation loop: camera lerping, breathing, ripple expansion
  const rippleRingRef = useRef<THREE.Mesh>(null);
  useFrame(() => {
    const now = Date.now();
    const rippleElapsed = (now - rippleStartTime.current) / 1000;

    // Expand ripple ring across the neural core
    if (rippleRingRef.current) {
      if (rippleElapsed < 1.8) {
        const scale = rippleElapsed * 90;
        rippleRingRef.current.scale.set(scale, scale, 1);
        const mat = rippleRingRef.current.material as THREE.MeshBasicMaterial;
        mat.opacity = Math.max(0, 0.5 * (1 - rippleElapsed / 1.8));
      } else {
        rippleRingRef.current.scale.set(0.001, 0.001, 1);
      }
    }

    // Camera tween interpolation
    if (targetCamPos.current && targetLookAt.current && controlsRef.current) {
      camera.position.lerp(targetCamPos.current, 0.08);
      controlsRef.current.target.lerp(targetLookAt.current, 0.08);
      controlsRef.current.update();

      if (camera.position.distanceTo(targetCamPos.current) < 0.6) {
        targetCamPos.current = null;
        targetLookAt.current = null;
      }
    }
  });

  const activeId = hoveredNode?.id || selectedNode?.id || null;
  const activeNeighbors = activeId ? neighborsMap.get(activeId) : null;

  // Group nodes by shape for instanced rendering
  const groupedNodes = useMemo(() => {
    const groups: Record<string, SimNode[]> = {
      Retraction: [],
      Trial: [],
      Review: [],
      Guideline: [],
      Decision: [],
      Committee: [],
      Person: [],
    };

    simNodes.forEach((n) => {
      if (groups[n.label]) {
        groups[n.label].push(n);
      } else {
        groups.Decision.push(n);
      }
    });

    return groups;
  }, [simNodes]);

  return (
    <>
      <OrbitControls
        ref={controlsRef}
        enableDamping
        dampingFactor={0.08}
        minDistance={35}
        maxDistance={420}
        maxPolarAngle={Math.PI / 2 + 0.15}
      />

      {/* Anatomical Brain Silhouette Wireframe Contours */}
      <BrainSilhouetteContours />

      {/* Ambient Neural Glial Particles */}
      <NeuralGlialParticles count={90} />

      {/* Ripple wave ring in X-Z plane */}
      <mesh ref={rippleRingRef} rotation={[-Math.PI / 2, 0, 0]} position={[0, -10, -4]}>
        <ringGeometry args={[0.95, 1.05, 64]} />
        <meshBasicMaterial color="#38BDF8" transparent opacity={0.3} side={THREE.DoubleSide} />
      </mesh>

      {/* Synaptic Axon Edges */}
      {edgeLinePositions.length > 0 && (
        <lineSegments>
          <bufferGeometry>
            <bufferAttribute attach="attributes-position" args={[edgeLinePositions, 3]} />
          </bufferGeometry>
          <lineBasicMaterial color="#38BDF8" transparent opacity={0.22} />
        </lineSegments>
      )}

      {/* Synaptic Action-Potential Pulses */}
      <SynapticPulses linksData={linksData} nodeMap={nodeMap} rippleStartTime={rippleStartTime} />

      {/* Instanced Neuron Nodes */}
      <InstancedNeuronGroup
        type="Retraction"
        nodes={groupedNodes.Retraction}
        geometry={<octahedronGeometry args={[4.8, 0]} />}
        baseColor="#EF4444"
        activeId={activeId}
        activeNeighbors={activeNeighbors}
        rippleStartTime={rippleStartTime}
        setCursorState={setCursorState}
      />

      <InstancedNeuronGroup
        type="Trial"
        nodes={groupedNodes.Trial}
        geometry={<sphereGeometry args={[3.2, 16, 16]} />}
        baseColor="#F59E0B"
        activeId={activeId}
        activeNeighbors={activeNeighbors}
        rippleStartTime={rippleStartTime}
        setCursorState={setCursorState}
      />

      <InstancedNeuronGroup
        type="Review"
        nodes={groupedNodes.Review}
        geometry={<boxGeometry args={[4.4, 4.4, 4.4]} />}
        baseColor="#06B6D4"
        activeId={activeId}
        activeNeighbors={activeNeighbors}
        rippleStartTime={rippleStartTime}
        setCursorState={setCursorState}
      />

      <InstancedNeuronGroup
        type="Guideline"
        nodes={groupedNodes.Guideline}
        geometry={<icosahedronGeometry args={[4.0, 0]} />}
        baseColor="#818CF8"
        activeId={activeId}
        activeNeighbors={activeNeighbors}
        rippleStartTime={rippleStartTime}
        setCursorState={setCursorState}
      />

      <InstancedNeuronGroup
        type="Decision"
        nodes={groupedNodes.Decision}
        geometry={<dodecahedronGeometry args={[4.2, 0]} />}
        baseColor="#EC4899"
        activeId={activeId}
        activeNeighbors={activeNeighbors}
        rippleStartTime={rippleStartTime}
        setCursorState={setCursorState}
      />

      <InstancedNeuronGroup
        type="Committee"
        nodes={groupedNodes.Committee}
        geometry={<coneGeometry args={[3.2, 5.5, 12]} />}
        baseColor="#A78BFA"
        activeId={activeId}
        activeNeighbors={activeNeighbors}
        rippleStartTime={rippleStartTime}
        setCursorState={setCursorState}
      />

      <InstancedNeuronGroup
        type="Person"
        nodes={groupedNodes.Person}
        geometry={<tetrahedronGeometry args={[3.4, 0]} />}
        baseColor="#38BDF8"
        activeId={activeId}
        activeNeighbors={activeNeighbors}
        rippleStartTime={rippleStartTime}
        setCursorState={setCursorState}
      />

      {/* Hover HUD / Monospace Label for Active & Retraction Nodes */}
      {simNodes.map((n) => {
        const isSelected = selectedNode?.id === n.id;
        const isHovered = hoveredNode?.id === n.id;
        const isRetraction = n.label === 'Retraction';

        if (!isSelected && !isHovered && !isRetraction) return null;

        const info = PALETTE[n.label] || PALETTE.Review;
        const isAtRisk = n.status === 'at_risk';
        const isRetracted = n.status === 'retracted';
        const connCount = neighborsMap.get(n.id)?.size || 0;

        return (
          <Html
            key={n.id}
            position={[n.x, n.y + 8, n.z]}
            center
            style={{ pointerEvents: 'none' }}
          >
            <div className="bg-[#0D1117]/95 text-[#E6E8EB] border border-[#232831] px-2.5 py-1.5 rounded-md shadow-2xl backdrop-blur-md text-[11px] font-mono whitespace-nowrap select-none min-w-[140px] transform transition-transform">
              <div className="flex items-center justify-between gap-2 border-b border-border/50 pb-1 mb-1">
                <span className="font-bold text-xs" style={{ color: info.base }}>
                  {n.id}
                </span>
                <span className="text-[9px] uppercase px-1 rounded bg-surface border border-border text-muted">
                  {n.label}
                </span>
              </div>

              {n.title && (
                <div className="text-[10px] text-secondary max-w-[200px] truncate mb-0.5">
                  {n.title}
                </div>
              )}

              <div className="flex items-center justify-between text-[9px] text-muted pt-0.5">
                <span className="flex items-center gap-1">
                  {isAtRisk ? (
                    <span className="text-at-risk-amber font-semibold flex items-center gap-0.5">
                      <ShieldAlert className="w-2.5 h-2.5" /> at_risk
                    </span>
                  ) : isRetracted ? (
                    <span className="text-retraction-red font-semibold">retracted</span>
                  ) : (
                    <span className="text-ok-green">active</span>
                  )}
                </span>
                <span>{connCount} synapses</span>
              </div>
            </div>
          </Html>
        );
      })}
    </>
  );
};

// Subtle Holographic Brain Silhouette Contours
const BrainSilhouetteContours: React.FC = () => {
  const lineGeo = useMemo(() => {
    // Left & Right Hemisphere Ellipsoidal Outline Loops
    const pts: THREE.Vector3[] = [];
    const segments = 48;

    // Left hemisphere contour
    for (let i = 0; i <= segments; i++) {
      const a = (i / segments) * Math.PI * 2;
      pts.push(new THREE.Vector3(-42 + 28 * Math.cos(a), 32 * Math.sin(a), 48 * Math.sin(a) * Math.cos(a)));
    }
    // Right hemisphere contour
    for (let i = 0; i <= segments; i++) {
      const a = (i / segments) * Math.PI * 2;
      pts.push(new THREE.Vector3(42 + 28 * Math.cos(a), 32 * Math.sin(a), 48 * Math.sin(a) * Math.cos(a)));
    }
    // Medial longitudinal fissure arch
    for (let i = 0; i <= segments; i++) {
      const a = (i / segments) * Math.PI;
      pts.push(new THREE.Vector3(0, 36 * Math.sin(a) - 6, 52 * Math.cos(a)));
    }

    const geo = new THREE.BufferGeometry().setFromPoints(pts);
    return geo;
  }, []);

  return (
    <line>
      <primitive object={lineGeo} attach="geometry" />
      <lineBasicMaterial color="#1E293B" transparent opacity={0.35} />
    </line>
  );
};

// Ambient Floating Neural Particles
const NeuralGlialParticles: React.FC<{ count: number }> = ({ count }) => {
  const pointsRef = useRef<THREE.Points>(null);

  const [positions, phases] = useMemo(() => {
    const pos = new Float32Array(count * 3);
    const ph = new Float32Array(count);
    for (let i = 0; i < count; i++) {
      const sign = i % 2 === 0 ? 1 : -1;
      pos[i * 3] = sign * (12 + Math.random() * 55);
      pos[i * 3 + 1] = (Math.random() - 0.5) * 65;
      pos[i * 3 + 2] = (Math.random() - 0.5) * 85;
      ph[i] = Math.random() * Math.PI * 2;
    }
    return [pos, ph];
  }, [count]);

  useFrame((state) => {
    if (!pointsRef.current) return;
    const t = state.clock.getElapsedTime();
    const posAttr = pointsRef.current.geometry.attributes.position;
    for (let i = 0; i < count; i++) {
      const yOrig = positions[i * 3 + 1];
      posAttr.setY(i, yOrig + Math.sin(t * 0.8 + phases[i]) * 2.5);
    }
    posAttr.needsUpdate = true;
  });

  return (
    <points ref={pointsRef}>
      <bufferGeometry>
        <bufferAttribute attach="attributes-position" args={[positions, 3]} />
      </bufferGeometry>
      <pointsMaterial size={1.8} color="#38BDF8" transparent opacity={0.35} sizeAttenuation />
    </points>
  );
};

// Synaptic Action-Potential Transmission Pulses
const SynapticPulses: React.FC<{
  linksData: any[];
  nodeMap: Map<string, SimNode>;
  rippleStartTime: React.MutableRefObject<number>;
}> = ({ linksData, nodeMap, rippleStartTime }) => {
  const pointsRef = useRef<THREE.Points>(null);
  const pulseCount = Math.min(linksData.length, 64);

  const [positions, linkIndices] = useMemo(() => {
    const pos = new Float32Array(pulseCount * 3);
    const indices: number[] = [];
    for (let i = 0; i < pulseCount; i++) {
      indices.push(i % linksData.length);
    }
    return [pos, indices];
  }, [pulseCount, linksData.length]);

  useFrame((state) => {
    if (!pointsRef.current || linksData.length === 0) return;
    const t = state.clock.getElapsedTime();
    const rippleElapsed = (Date.now() - rippleStartTime.current) / 1000;
    const isWaveActive = rippleElapsed < 1.5;
    const speed = isWaveActive ? 2.5 : 0.8;

    const posAttr = pointsRef.current.geometry.attributes.position;

    linkIndices.forEach((lIdx, pIdx) => {
      const l = linksData[lIdx];
      const s = typeof l.source === 'object' ? l.source : nodeMap.get(l.source);
      const target = typeof l.target === 'object' ? l.target : nodeMap.get(l.target);

      if (s && target) {
        // Pulse traveling from source to target
        const progress = ((t * speed + (pIdx / pulseCount)) % 1);
        const px = s.x + (target.x - s.x) * progress;
        const py = s.y + (target.y - s.y) * progress;
        const pz = s.z + (target.z - s.z) * progress;
        posAttr.setXYZ(pIdx, px, py, pz);
      }
    });

    posAttr.needsUpdate = true;
  });

  return (
    <points ref={pointsRef}>
      <bufferGeometry>
        <bufferAttribute attach="attributes-position" args={[positions, 3]} />
      </bufferGeometry>
      <pointsMaterial
        size={3.2}
        color="#F59E0B"
        transparent
        opacity={0.85}
        sizeAttenuation
        blending={THREE.AdditiveBlending}
      />
    </points>
  );
};

interface InstancedNeuronGroupProps {
  type: string;
  nodes: SimNode[];
  geometry: React.ReactNode;
  baseColor: string;
  activeId: string | null;
  activeNeighbors: Set<string> | null | undefined;
  rippleStartTime: React.MutableRefObject<number>;
  setCursorState: React.Dispatch<React.SetStateAction<'grab' | 'grabbing' | 'pointer'>>;
}

const InstancedNeuronGroup: React.FC<InstancedNeuronGroupProps> = ({
  nodes,
  geometry,
  baseColor,
  activeId,
  activeNeighbors,
  rippleStartTime,
  setCursorState,
}) => {
  const meshRef = useRef<THREE.InstancedMesh>(null);
  const { setSelectedNode, setHoveredNode } = useUiStore();
  const dummy = useMemo(() => new THREE.Object3D(), []);
  const color = useMemo(() => new THREE.Color(), []);

  useFrame((state) => {
    if (!meshRef.current || nodes.length === 0) return;
    const now = Date.now();
    const elapsed = (now - rippleStartTime.current) / 1000;
    const t = state.clock.getElapsedTime();

    nodes.forEach((node, i) => {
      // Scale-in ripple animation across hops
      const nodeAppearTime = node.hop * 0.18;
      let scale = 1.0;
      if (elapsed < nodeAppearTime) {
        scale = 0.001;
      } else if (elapsed < nodeAppearTime + 0.3) {
        const p = (elapsed - nodeAppearTime) / 0.3;
        scale = Math.sin((p * Math.PI) / 2);
      } else {
        // Organic neural breathing harmonic pulse
        const breath = 1.0 + Math.sin(t * 1.8 + node.x * 0.1 + node.y * 0.1) * 0.05;
        scale = breath;
      }

      // Expand hovered or selected node
      const isSelf = node.id === activeId;
      if (isSelf) scale *= 1.35;

      dummy.position.set(node.x, node.y, node.z);
      dummy.scale.set(scale, scale, scale);
      dummy.updateMatrix();
      meshRef.current!.setMatrixAt(i, dummy.matrix);

      // Color computation: Decision at_risk turns golden amber
      const isAtRisk = node.label === 'Decision' && node.status === 'at_risk';
      const nodeCol = isAtRisk ? '#F59E0B' : baseColor;
      color.set(nodeCol);

      // Focus lighting & dimming on hover
      if (activeId) {
        const isNeighbor = activeNeighbors?.has(node.id);
        if (!isSelf && !isNeighbor) {
          color.multiplyScalar(0.18);
        } else if (isSelf) {
          color.addScalar(0.35);
        } else if (isNeighbor) {
          color.addScalar(0.15);
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
          setCursorState('pointer');
        }
      }}
      onPointerOut={() => {
        setHoveredNode(null);
        setCursorState('grab');
      }}
    >
      {geometry}
      <meshStandardMaterial roughness={0.25} metalness={0.25} />
    </instancedMesh>
  );
};

