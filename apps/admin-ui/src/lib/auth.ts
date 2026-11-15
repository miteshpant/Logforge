interface LoginCredentials {
  email: string;
  password: string;
}

interface User {
  id: string;
  email: string;
  name: string;
  role: string;
}

/**
 * The cookie `src/proxy.ts` reads to decide whether to serve a console route
 * (LF-253).
 *
 * **It is not the credential and it is not a security control.** It carries no
 * token, only the fact that this browser signed in, and it is written by this
 * script — so it is forgeable by anything that can run script here, and a
 * forger gets the console shell: a navigation bar and empty tables. Every byte
 * of tenant data behind it comes from the API, which authenticates each request
 * on its own and never sees this cookie.
 *
 * What it buys is that an unauthenticated browser is redirected before the
 * protected markup is generated, rather than being sent the whole page and
 * having `AuthGuard` hide it a moment later.
 *
 * It becomes a real boundary when **LF-213** moves the token itself into an
 * `HttpOnly; Secure; SameSite` cookie, at which point this marker is replaced
 * by the session cookie rather than shadowing it. Deliberately NOT `HttpOnly`
 * today: a flag that implies the server set it would misrepresent what this is.
 *
 * `SameSite=Strict` so it is not sent on a cross-site navigation, and `Secure`
 * off localhost so it never travels in clear.
 */
const SESSION_MARKER = 'admin_session';

function setSessionMarker(): void {
  const secure = window.location.protocol === 'https:' ? '; Secure' : '';
  // Session cookie (no Max-Age): it should not outlive the browser, and the
  // token's own 8-hour expiry is what actually bounds the session.
  document.cookie = `${SESSION_MARKER}=1; Path=/; SameSite=Strict${secure}`;
}

function clearSessionMarker(): void {
  document.cookie = `${SESSION_MARKER}=; Path=/; Max-Age=0; SameSite=Strict`;
}

export class AuthService {
  private static instance: AuthService;
  private user: User | null = null;
  private token: string | null = null;

  static getInstance() {
    if (!AuthService.instance) {
      AuthService.instance = new AuthService();
    }
    return AuthService.instance;
  }

  async login(credentials: LoginCredentials): Promise<User> {
    const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:7080';
    
    try {
      const response = await fetch(`${API_BASE_URL}/v1/auth/login`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(credentials),
      });

      if (!response.ok) {
        const errorData = await response.text();
        throw new Error(`Login failed: ${errorData}`);
      }

      const data = await response.json();
      
      this.token = data.access_token;
      this.user = {
        id: data.user.id,
        email: data.user.email,
        name: data.user.full_name || data.user.email,
        role: data.user.role || 'admin'
      };

      // ENH-018: KNOWN WEAKNESS -- the PLATFORM ADMIN token is kept in
      // localStorage. (Correction 2026-08-23: this used to say "strictly worse
      // than the tenant UI's cookies" -- the tenant UI does not use cookies
      // either; its live client uses localStorage too. Both are exposed.)
      // it is readable by any script, carries no Secure/SameSite protection,
      // and persists until explicitly cleared. Any XSS in this application
      // yields platform-wide administrative takeover, the highest-value
      // credential in the system.
      //
      // Not changed here because migrating it requires the API to issue
      // httpOnly cookies plus a CSRF strategy -- an auth-flow change spanning
      // the API and both UIs. Tracked as the remaining work in ENH-018 and
      // deliberately left visible rather than silently rewritten.
      if (typeof window !== 'undefined') {
        localStorage.setItem('admin_token', this.token ?? '');
        localStorage.setItem('admin_user', JSON.stringify(this.user));
        setSessionMarker();
      }

      return this.user;
    } catch (error) {
      console.error('Login error:', error);
      throw error;
    }
  }

  logout() {
    this.token = null;
    this.user = null;
    
    if (typeof window !== 'undefined') {
      localStorage.removeItem('admin_token');
      localStorage.removeItem('admin_user');
      clearSessionMarker();
    }
  }

  getCurrentUser(): User | null {
    if (this.user) {
      return this.user;
    }

    // Try to restore from localStorage
    if (typeof window !== 'undefined') {
      const token = localStorage.getItem('admin_token');
      const userStr = localStorage.getItem('admin_user');
      
      if (token && userStr) {
        this.token = token;
        this.user = JSON.parse(userStr);
        // A session that predates LF-253 has a token and no marker, and the
        // proxy would bounce it to /login with a valid credential in hand.
        // Restoring the marker here means the change does not sign everyone
        // out on deploy.
        setSessionMarker();
        return this.user;
      }
    }

    return null;
  }

  getToken(): string | null {
    if (this.token) {
      // Check if current token is expired
      if (this.isTokenExpired(this.token)) {
        this.logout();
        return null;
      }
      return this.token;
    }

    if (typeof window !== 'undefined') {
      const token = localStorage.getItem('admin_token');
      if (token && this.isTokenExpired(token)) {
        this.logout();
        return null;
      }
      return token;
    }

    return null;
  }

  private isTokenExpired(token: string): boolean {
    try {
      const payload = JSON.parse(atob(token.split('.')[1]));
      const currentTime = Date.now() / 1000;
      return payload.exp < currentTime;
    } catch (error) {
      // If we can't parse the token, consider it expired
      return true;
    }
  }

  isAuthenticated(): boolean {
    return !!this.getToken();
  }
}

export const authService = AuthService.getInstance();