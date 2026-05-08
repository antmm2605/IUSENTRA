import type { ReactNode } from 'react'
import { APP_ROUTES, LEGACY_ROUTE_TARGETS, type AppRouteDefinition } from './routes'

export type RouterMatch = {
  route: AppRouteDefinition
  params: Record<string, string>
}

function normalise(pathname: string): string {
  const clean = pathname.replace(/\/+$/, '') || '/'
  if (clean === '/app-v2') return '/app'
  if (clean.startsWith('/app-v2/')) return `/app${clean.slice('/app-v2'.length)}`
  return LEGACY_ROUTE_TARGETS[clean] || clean
}

function matchPattern(pattern: string, pathname: string): Record<string, string> | null {
  const patternParts = pattern.split('/').filter(Boolean)
  const pathParts = pathname.split('/').filter(Boolean)
  if (patternParts.length !== pathParts.length) return null
  const params: Record<string, string> = {}
  for (let index = 0; index < patternParts.length; index += 1) {
    const expected = patternParts[index]
    const received = pathParts[index]
    if (expected.startsWith(':')) {
      params[expected.slice(1)] = decodeURIComponent(received)
    } else if (expected !== received) {
      return null
    }
  }
  return params
}

export function resolveAppRoute(pathname = window.location.pathname): RouterMatch {
  const normalised = normalise(pathname)
  for (const route of APP_ROUTES) {
    const params = matchPattern(route.path, normalised)
    if (params) return { route, params }
  }
  return { route: APP_ROUTES[0], params: {} }
}

export function RouterOutlet({ children }: { children: ReactNode }) {
  return <>{children}</>
}
