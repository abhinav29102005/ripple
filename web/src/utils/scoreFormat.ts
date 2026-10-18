export function formatScore(score: number): string {
  if (isNaN(score)) return '0.0000';
  return score.toFixed(4);
}

export function formatWeightShare(share: number): string {
  if (isNaN(share)) return '0.0%';
  return `${(share * 100).toFixed(1)}%`;
}

export function getScoreTrend(delta: number): 'drop' | 'boost' | 'neutral' {
  if (delta < -0.0001) return 'drop';
  if (delta > 0.0001) return 'boost';
  return 'neutral';
}
