export const HOP_MAP: Record<string, number> = {
  Retraction: 0,
  Trial: 1,
  Review: 2,
  Guideline: 3,
  Decision: 4,
  Committee: 5,
  Person: 5,
};

export function computeHopDistance(nodeType: string): number {
  return HOP_MAP[nodeType] ?? 2;
}

export function computeRadialRadius(hopDistance: number, baseShellDistance: number = 26): number {
  return hopDistance * baseShellDistance;
}
