import type { NextConfig } from 'next'
import path from 'path'
import fs from 'fs'

// Load root .env if NEXT_PUBLIC_API_URL or BACKEND_PORT is not set in environment
if (!process.env.NEXT_PUBLIC_API_URL) {
  const rootEnvPath = path.resolve(__dirname, '../.env')
  if (fs.existsSync(rootEnvPath)) {
    try {
      const content = fs.readFileSync(rootEnvPath, 'utf8')
      for (const line of content.split('\n')) {
        const trimmed = line.trim()
        if (!trimmed || trimmed.startsWith('#')) continue
        const eqIdx = trimmed.indexOf('=')
        if (eqIdx > 0) {
          const key = trimmed.slice(0, eqIdx).trim()
          let val = trimmed.slice(eqIdx + 1).trim()
          if ((val.startsWith('"') && val.endsWith('"')) || (val.startsWith("'") && val.endsWith("'"))) {
            val = val.slice(1, -1)
          }
          if (!process.env[key]) {
            process.env[key] = val
          }
        }
      }
    } catch {}
  }
}

const backendPort = process.env.BACKEND_PORT || process.env.API_PORT || '18000'
const apiDestination = (process.env.NEXT_PUBLIC_API_URL || process.env.PUBLIC_API_URL || `http://localhost:${backendPort}/api`).replace(/\/$/, '')

const nextConfig: NextConfig = {
  reactStrictMode: true,

  env: {
    NEXT_PUBLIC_API_URL: apiDestination,
  },

  async rewrites() {
    return [
      {
        source: '/api/:path*',
        destination: `${apiDestination}/:path*`,
      },
    ]
  },
}

export default nextConfig
