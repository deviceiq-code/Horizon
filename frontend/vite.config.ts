import { fileURLToPath, URL } from 'node:url'
import { defineConfig, loadEnv } from 'vite'
import vue from '@vitejs/plugin-vue'
import vuetify from 'vite-plugin-vuetify'

/**
 * Who may reach the development server, from the repository's .env (shared with Django):
 * - DEV_LISTEN_HOST: where Vite listens — "localhost" (default, this machine only) or "0.0.0.0"
 *   (every network interface: the local network, or the internet through a tunnel / port
 *   forwarding, for tests).
 * - ALLOWED_HOSTS: the names the site may be opened by — the same list Django checks
 *   ("horizon.example.com", ".example.com" for its subdomains, "*" for any).
 * Django itself stays on 127.0.0.1: it is only reached through the /api proxy below.
 */
function devServerAccess() {
  // The repository's .env (not per mode)
  const env = loadEnv(
    process.env.NODE_ENV ?? 'development',
    fileURLToPath(new URL('..', import.meta.url)),
    '',
  )
  const hosts = (env.ALLOWED_HOSTS ?? '')
    .split(',')
    .map((host) => host.trim())
    .filter(Boolean)
  return {
    host: env.DEV_LISTEN_HOST?.trim() || 'localhost',
    allowedHosts: hosts.includes('*') ? (true as const) : hosts,
  }
}

export default defineConfig({
  plugins: [vue(), vuetify({ autoImport: true })],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    },
  },
  server: {
    ...devServerAccess(),
    // In development, /api goes to Django — same origin, no CORS. The Host header is kept
    // (Django checks it against ALLOWED_HOSTS).
    proxy: {
      '/api': { target: 'http://localhost:8000' },
    },
  },
})
