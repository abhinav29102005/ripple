export function computeRippleAppearTime(hopDistance: number, hopDelayMs: number = 200): number {
  return (hopDistance * hopDelayMs) / 1000;
}

export function isNodeVisibleInRipple(elapsedSeconds: number, hopDistance: number, hopDelayMs: number = 200): boolean {
  return elapsedSeconds >= computeRippleAppearTime(hopDistance, hopDelayMs);
}

export function computeRippleScale(elapsedSeconds: number, hopDistance: number, durationSeconds: number = 0.3): number {
  const appearTime = computeRippleAppearTime(hopDistance);
  if (elapsedSeconds < appearTime) return 0.001;
  const progress = (elapsedSeconds - appearTime) / durationSeconds;
  if (progress >= 1.0) return 1.0;
  return Math.sin((progress * Math.PI) / 2);
}
