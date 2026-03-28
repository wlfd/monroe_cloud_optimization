import { defineConfig } from 'vite'
import { defineConfig as defineTestConfig, mergeConfig } from 'vitest/config'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import path from 'path'

const viteConfig = defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  server: {
    port: 3000,
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
        // withCredentials handled by axios; proxy needed to avoid CORS errors in dev
      },
    },
  },
})

// https://vite.dev/config/
export default mergeConfig(
  viteConfig,
  defineTestConfig({
    test: {
      globals: true,
      environment: 'jsdom',
      setupFiles: './src/test/setup.ts',
      css: true,
      // Point Vitest at the test-specific tsconfig so jest-dom and vitest/globals
      // types are available without polluting the app build's type surface.
      typecheck: {
        tsconfig: './tsconfig.test.json',
      },
    },
  })
)
