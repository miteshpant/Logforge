/** Routes the app renders without a session, and where to send a visitor who has none. */

const PUBLIC_ROUTES = ['/login', '/forgot-password', '/reset-password', '/accept-invite']

export const isPublicRoute = (pathname: string | null) =>
  !!pathname && PUBLIC_ROUTES.some(p => pathname === p || pathname.startsWith(`${p}/`))

/** /login?next=<path and query>, so a link like /verify-email?token=… survives signing in. */
export const loginRedirect = (pathname: string | null, search: string) =>
  `/login?next=${encodeURIComponent((pathname || '/') + (search || ''))}`
