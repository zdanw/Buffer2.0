import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'path'
import { execSync } from 'node:child_process'

const BASE_VERSION = '2.0'

function getAppVersion(): string {
  try {
    const commitCount = execSync('git rev-list --count HEAD', {
      cwd: path.resolve(__dirname, '..'),
      encoding: 'utf-8',
    }).trim()
    return `${BASE_VERSION}.${commitCount}`
  } catch {
    return `${BASE_VERSION}.0`
  }
}

export default defineConfig({
  plugins: [react()],
  define: {
    __APP_VERSION__: JSON.stringify(getAppVersion()),
  },
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  server: {
    port: 5174,
    strictPort: true,
    proxy: {
      '/v1': {
        target: 'http://localhost:8080',
        changeOrigin: true,
      },
    },
  },
})
