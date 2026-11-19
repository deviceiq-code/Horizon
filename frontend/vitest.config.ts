import { fileURLToPath } from 'node:url'
import { mergeConfig, defineConfig, configDefaults } from 'vitest/config'
import viteConfig from './vite.config.ts'

export default mergeConfig(
  viteConfig,
  defineConfig({
    test: {
      environment: 'jsdom',
      // Node 25+ ships its own localStorage (unusable without --localstorage-file) that
      // shadows jsdom's; disabling it makes tests use the jsdom localStorage.
      execArgv: ['--no-experimental-webstorage'],
      exclude: [...configDefaults.exclude, 'e2e/**'],
      root: fileURLToPath(new URL('./', import.meta.url)),
    },
  }),
)
