/// <reference types="vitest" />
import { defineConfig, loadEnv } from 'vite';
import react from '@vitejs/plugin-react';

function validateEnv(mode: string) {
  const env = { ...process.env, ...loadEnv(mode, process.cwd(), '') };
  const forbidden = ['KEY', 'SECRET', 'TOKEN', 'PASSWORD'];
  for (const key of Object.keys(env)) {
    if (key.startsWith('VITE_')) {
      const upper = key.toUpperCase();
      for (const pattern of forbidden) {
        if (upper.includes(pattern)) {
          throw new Error(
            `[Security Violation] Build aborted: Client environment variable '${key}' contains forbidden keyword '${pattern}'. Secrets must never be exposed to browser bundles.`
          );
        }
      }
    }
  }
}

export default defineConfig(({ mode }) => {
  validateEnv(mode);
  return {
    test: {
      include: ['src/**/*.test.ts'],
    },
    plugins: [react()],
    server: {
      port: 5173,
      proxy: {
        '/api': {
          target: 'http://localhost:8000',
          changeOrigin: true,
        },
      },
    },
    build: {
      outDir: 'dist',
      rollupOptions: {
        output: {
          manualChunks(id) {
            if (id.includes('three') || id.includes('@react-three') || id.includes('d3-force-3d')) {
              return 'three-chunk';
            }
          },
        },
      },
    },
  };
});
