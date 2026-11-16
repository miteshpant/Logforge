'use client'

import { useEffect } from 'react'
import { usePathname, useRouter } from 'next/navigation'
import { useAuth } from '@/contexts/AuthContext'

/** Routes that render without a session. */
const PUBLIC_ROUTES = ['/login']

export const isPublicRoute = (pathname: string | null) =>
  !!pathname && PUBLIC_ROUTES.some(p => pathname === p || pathname.startsWith(`${p}/`))

/**
 * Route guard for the whole app.
 *
 * Without it an unauthenticated visitor got the full app shell with zeroed
 * widgets while every page fired its API calls (all 401). Pages are only
 * mounted -- and so only fetch -- once AuthContext has a session; otherwise the
 * visitor is sent to /login?next=<path>, and back there after signing in.
 */
export function AuthGate({ children }: { children: React.ReactNode }) {
  const { isAuthenticated, isLoading } = useAuth()
  const pathname = usePathname()
  const router = useRouter()
  const isPublic = isPublicRoute(pathname)

  useEffect(() => {
    if (!isPublic && !isLoading && !isAuthenticated) {
      router.replace(`/login?next=${encodeURIComponent(pathname || '/')}`)
    }
  }, [isPublic, isLoading, isAuthenticated, pathname, router])

  // Gate on the session itself, not on isLoading: tenant switches also toggle
  // isLoading, and the app should not unmount while an authenticated user waits.
  if (isPublic || isAuthenticated) return <>{children}</>

  return (
    <div
      data-testid="auth-gate"
      className="min-h-screen bg-slate-950 flex items-center justify-center text-slate-400 text-sm"
    >
      Loading…
    </div>
  )
}
