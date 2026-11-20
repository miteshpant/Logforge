'use client'

import { useEffect } from 'react'
import { usePathname, useRouter } from 'next/navigation'
import { useAuth } from '@/contexts/AuthContext'

import { isPublicRoute, loginRedirect } from '@/lib/authRoutes'

export { isPublicRoute }

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
      router.replace(loginRedirect(pathname, typeof window === 'undefined' ? '' : window.location.search))
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
