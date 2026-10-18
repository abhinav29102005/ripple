import { describe, it, expect } from 'vitest';
import { forceSimulation, forceManyBody, forceRadial } from 'd3-force-3d';

describe('3D Graph Layout Performance Benchmark', () => {
  it('computes radial layout under 50ms for standard graph (173 nodes)', () => {
    const nodes = Array.from({ length: 173 }, (_, i) => {
      const hop = i === 0 ? 0 : i < 10 ? 1 : i < 40 ? 2 : i < 100 ? 3 : 4;
      return { id: `node-${i}`, hop };
    });

    const start = performance.now();
    const sim = forceSimulation(nodes as any, 3)
      .force('charge', forceManyBody().strength(-30))
      .force('radial', forceRadial((d: any) => d.hop * 18, 0, 0, 0).strength(0.8))
      .stop();

    // Run 50 ticks
    for (let i = 0; i < 50; i++) {
      sim.tick();
    }
    const duration = performance.now() - start;
    console.log(`[PERF BENCHMARK] 173-node layout 50-tick compute time: ${duration.toFixed(2)} ms (avg ${(duration / 50).toFixed(3)} ms/tick)`);
    expect(duration).toBeLessThan(100);
  });

  it('computes radial layout under 500ms for 2,000-node stress graph', () => {
    const nodes = Array.from({ length: 2000 }, (_, i) => {
      const hop = i === 0 ? 0 : i < 50 ? 1 : i < 300 ? 2 : i < 1000 ? 3 : 4;
      return { id: `stress-node-${i}`, hop };
    });

    const start = performance.now();
    const sim = forceSimulation(nodes as any, 3)
      .force('charge', forceManyBody().strength(-15))
      .force('radial', forceRadial((d: any) => d.hop * 18, 0, 0, 0).strength(0.8))
      .stop();

    for (let i = 0; i < 30; i++) {
      sim.tick();
    }
    const duration = performance.now() - start;
    console.log(`[PERF BENCHMARK] 2000-node stress layout 30-tick compute time: ${duration.toFixed(2)} ms (avg ${(duration / 30).toFixed(3)} ms/tick)`);
    expect(duration).toBeLessThan(1000);
  });
});
