import { describe, it, expect } from 'vitest';
import { computeHopDistance, computeRadialRadius } from '../utils/hopDistance';
import { formatScore, formatWeightShare, getScoreTrend } from '../utils/scoreFormat';
import { groupTasksByStatus } from '../utils/taskGrouping';
import { computeRippleAppearTime, isNodeVisibleInRipple, computeRippleScale } from '../utils/rippleTiming';

describe('Hop Distance Computation', () => {
  it('maps retraction to center hop 0', () => {
    expect(computeHopDistance('Retraction')).toBe(0);
    expect(computeRadialRadius(0)).toBe(0);
  });

  it('maps trials, reviews, guidelines, decisions to outward shells', () => {
    expect(computeHopDistance('Trial')).toBe(1);
    expect(computeHopDistance('Review')).toBe(2);
    expect(computeHopDistance('Guideline')).toBe(3);
    expect(computeHopDistance('Decision')).toBe(4);
    expect(computeHopDistance('Committee')).toBe(5);
    expect(computeHopDistance('Person')).toBe(5);

    expect(computeRadialRadius(1, 26)).toBe(26);
    expect(computeRadialRadius(4, 26)).toBe(104);
  });
});

describe('Score Formatting', () => {
  it('formats scores with 4 decimal places tabularly', () => {
    expect(formatScore(0.589712)).toBe('0.5897');
    expect(formatScore(0)).toBe('0.0000');
  });

  it('formats weight shares with percentage', () => {
    expect(formatWeightShare(0.5212)).toBe('52.1%');
    expect(formatWeightShare(0.014)).toBe('1.4%');
  });

  it('detects score trend direction', () => {
    expect(getScoreTrend(-0.3)).toBe('drop');
    expect(getScoreTrend(0.15)).toBe('boost');
    expect(getScoreTrend(0.0)).toBe('neutral');
  });
});

describe('Task State Grouping', () => {
  it('correctly partitions tasks into 4 coordination columns', () => {
    const tasks = [
      { id: 't1', status: 'queued' as const },
      { id: 't2', status: 'claimed' as const },
      { id: 't3', status: 'done' as const },
      { id: 't4', status: 'done' as const },
      { id: 't5', status: 'failed' as const },
    ];
    const grouped = groupTasksByStatus(tasks);
    expect(grouped.queued.length).toBe(1);
    expect(grouped.claimed.length).toBe(1);
    expect(grouped.done.length).toBe(2);
    expect(grouped.failed.length).toBe(1);
  });
});

describe('Ripple Timing Schedule', () => {
  it('calculates wave appear times based on 200ms per hop', () => {
    expect(computeRippleAppearTime(0)).toBe(0);
    expect(computeRippleAppearTime(1)).toBe(0.2);
    expect(computeRippleAppearTime(4)).toBe(0.8);
  });

  it('determines node visibility wavefront', () => {
    expect(isNodeVisibleInRipple(0.1, 0)).toBe(true);
    expect(isNodeVisibleInRipple(0.1, 1)).toBe(false);
    expect(isNodeVisibleInRipple(0.25, 1)).toBe(true);
  });

  it('computes smooth ease-out scale for nodes as wavefront passes', () => {
    expect(computeRippleScale(0.1, 1)).toBe(0.001); // before arrival
    const scaleHalfway = computeRippleScale(0.35, 1, 0.3);
    expect(scaleHalfway).toBeGreaterThan(0.5);
    expect(scaleHalfway).toBeLessThan(1.0);
    expect(computeRippleScale(0.6, 1, 0.3)).toBe(1.0); // fully settled
  });
});
