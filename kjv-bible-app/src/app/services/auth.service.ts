import { Injectable, signal, computed } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { AuthUser, AuthResponse } from '../models/bible.models';

const TOKEN_KEY = 'kjv_auth_token';
const USER_KEY = 'kjv_auth_user';

@Injectable({ providedIn: 'root' })
export class AuthService {
  readonly user = signal<AuthUser | null>(null);
  readonly token = signal<string | null>(null);
  readonly isLoggedIn = computed(() => !!this.token());
  readonly displayName = computed(() => this.user()?.displayName ?? '');

  constructor(private http: HttpClient) {
    // Hydrate from localStorage
    const savedToken = localStorage.getItem(TOKEN_KEY);
    const savedUser = localStorage.getItem(USER_KEY);
    if (savedToken && savedUser) {
      this.token.set(savedToken);
      try {
        this.user.set(JSON.parse(savedUser));
      } catch {
        this.clearLocal();
      }
      // Validate token against backend
      this.validateSession();
    }
  }

  register(username: string, password: string, displayName: string) {
    return this.http.post<AuthResponse>('/api/auth/register', {
      username, password, displayName
    });
  }

  login(username: string, password: string) {
    return this.http.post<AuthResponse>('/api/auth/login', {
      username, password
    });
  }

  /** Save auth state after successful login/register */
  setSession(resp: AuthResponse) {
    this.token.set(resp.token);
    this.user.set(resp.user);
    localStorage.setItem(TOKEN_KEY, resp.token);
    localStorage.setItem(USER_KEY, JSON.stringify(resp.user));
  }

  logout() {
    const t = this.token();
    if (t) {
      this.http.post('/api/auth/logout', {}, {
        headers: { Authorization: `Bearer ${t}` }
      }).subscribe({ error: () => {} });
    }
    this.clearLocal();
    this.token.set(null);
    this.user.set(null);
  }

  getAuthHeaders(): { [key: string]: string } {
    const t = this.token();
    return t ? { Authorization: `Bearer ${t}` } : {};
  }

  private validateSession() {
    const t = this.token();
    if (!t) return;
    this.http.get<{ user: AuthUser }>('/api/auth/me', {
      headers: { Authorization: `Bearer ${t}` }
    }).subscribe({
      next: (data) => {
        this.user.set(data.user);
        localStorage.setItem(USER_KEY, JSON.stringify(data.user));
      },
      error: () => {
        // Token expired or invalid
        this.clearLocal();
        this.token.set(null);
        this.user.set(null);
      }
    });
  }

  private clearLocal() {
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(USER_KEY);
  }
}
