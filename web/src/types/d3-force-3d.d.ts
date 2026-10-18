declare module 'd3-force-3d' {
  export interface SimulationNodeDatum {
    index?: number;
    x?: number;
    y?: number;
    z?: number;
    vx?: number;
    vy?: number;
    vz?: number;
    fx?: number | null;
    fy?: number | null;
    fz?: number | null;
    [key: string]: any;
  }

  export interface SimulationLinkDatum<NodeDatum extends SimulationNodeDatum> {
    source: NodeDatum | string | number;
    target: NodeDatum | string | number;
    index?: number;
    [key: string]: any;
  }

  export function forceSimulation<NodeDatum extends SimulationNodeDatum>(
    nodes?: NodeDatum[],
    numDimensions?: number
  ): Simulation<NodeDatum, SimulationLinkDatum<NodeDatum>>;

  export interface Simulation<NodeDatum extends SimulationNodeDatum, LinkDatum extends SimulationLinkDatum<NodeDatum>> {
    restart(): this;
    stop(): this;
    tick(iterations?: number): this;
    nodes(): NodeDatum[];
    nodes(nodes: NodeDatum[]): this;
    alpha(): number;
    alpha(alpha: number): this;
    alphaMin(): number;
    alphaMin(min: number): this;
    alphaDecay(): number;
    alphaDecay(decay: number): this;
    alphaTarget(): number;
    alphaTarget(target: number): this;
    velocityDecay(): number;
    velocityDecay(decay: number): this;
    force(name: string): Force<NodeDatum, LinkDatum> | undefined;
    force(name: string, force: Force<NodeDatum, LinkDatum> | null): this;
    numDimensions(): number;
    numDimensions(n: number): this;
    on(typenames: string, listener?: (this: this) => void): this;
  }

  export interface Force<NodeDatum extends SimulationNodeDatum, LinkDatum extends SimulationLinkDatum<NodeDatum>> {
    (alpha: number): void;
    initialize?(nodes: NodeDatum[], ...args: any[]): void;
  }

  export function forceLink<NodeDatum extends SimulationNodeDatum, LinkDatum extends SimulationLinkDatum<NodeDatum>>(
    links?: LinkDatum[]
  ): ForceLink<NodeDatum, LinkDatum>;

  export interface ForceLink<NodeDatum extends SimulationNodeDatum, LinkDatum extends SimulationLinkDatum<NodeDatum>>
    extends Force<NodeDatum, LinkDatum> {
    links(): LinkDatum[];
    links(links: LinkDatum[]): this;
    id(): (node: NodeDatum, i: number, nodesData: NodeDatum[]) => string | number;
    id(id: (node: NodeDatum, i: number, nodesData: NodeDatum[]) => string | number): this;
    distance(): number | ((link: LinkDatum, i: number, linksData: LinkDatum[]) => number);
    distance(distance: number | ((link: LinkDatum, i: number, linksData: LinkDatum[]) => number)): this;
    strength(): number | ((link: LinkDatum, i: number, linksData: LinkDatum[]) => number);
    strength(strength: number | ((link: LinkDatum, i: number, linksData: LinkDatum[]) => number)): this;
    iterations(): number;
    iterations(iterations: number): this;
  }

  export function forceManyBody<NodeDatum extends SimulationNodeDatum>(): ForceManyBody<NodeDatum>;

  export interface ForceManyBody<NodeDatum extends SimulationNodeDatum>
    extends Force<NodeDatum, any> {
    strength(): number | ((node: NodeDatum, i: number, d: NodeDatum[]) => number);
    strength(strength: number | ((node: NodeDatum, i: number, d: NodeDatum[]) => number)): this;
    distanceMin(): number;
    distanceMin(distance: number): this;
    distanceMax(): number;
    distanceMax(distance: number): this;
  }

  export function forceCenter<NodeDatum extends SimulationNodeDatum>(
    x?: number,
    y?: number,
    z?: number
  ): ForceCenter<NodeDatum>;

  export interface ForceCenter<NodeDatum extends SimulationNodeDatum>
    extends Force<NodeDatum, any> {
    x(): number;
    x(x: number): this;
    y(): number;
    y(y: number): this;
    z(): number;
    z(z: number): this;
    strength(): number;
    strength(strength: number): this;
  }

  export function forceRadial<NodeDatum extends SimulationNodeDatum>(
    radius: number | ((node: NodeDatum, i: number, d: NodeDatum[]) => number),
    x?: number,
    y?: number,
    z?: number
  ): ForceRadial<NodeDatum>;

  export interface ForceRadial<NodeDatum extends SimulationNodeDatum>
    extends Force<NodeDatum, any> {
    radius(): number | ((node: NodeDatum, i: number, d: NodeDatum[]) => number);
    radius(radius: number | ((node: NodeDatum, i: number, d: NodeDatum[]) => number)): this;
    x(): number;
    x(x: number): this;
    y(): number;
    y(y: number): this;
    z(): number;
    z(z: number): this;
    strength(): number | ((node: NodeDatum, i: number, d: NodeDatum[]) => number);
    strength(strength: number | ((node: NodeDatum, i: number, d: NodeDatum[]) => number)): this;
  }

  export function forceCollide<NodeDatum extends SimulationNodeDatum>(
    radius?: number | ((node: NodeDatum, i: number, d: NodeDatum[]) => number)
  ): ForceCollide<NodeDatum>;

  export interface ForceCollide<NodeDatum extends SimulationNodeDatum>
    extends Force<NodeDatum, any> {
    radius(): number | ((node: NodeDatum, i: number, d: NodeDatum[]) => number);
    radius(radius: number | ((node: NodeDatum, i: number, d: NodeDatum[]) => number)): this;
    strength(): number;
    strength(strength: number): this;
    iterations(): number;
    iterations(iterations: number): this;
  }
}
