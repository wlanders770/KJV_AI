import { Injectable, signal, computed, effect } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { AuthService } from './auth.service';
import { HistoryEntry, ReadingPosition } from '../models/bible.models';

@Injectable({ providedIn: 'root' })
export class ReadingHistoryService {
  /** Back stack — most recent on top (end of array) */
  readonly history = signal<HistoryEntry[]>([]);
  /** Forward stack — for redo navigation */
  readonly forwardStack = signal<HistoryEntry[]>([]);
  /** Current saved position from backend */
  readonly lastPosition = signal<ReadingPosition | null>(null);

  readonly canGoBack = computed(() => this.history().length > 0);
  readonly canGoForward = computed(() => this.forwardStack().length > 0);

  /** Flag to suppress recording during back/forward navigation */
  private _navigating = false;

  constructor(
    private http: HttpClient,
    private auth: AuthService
  ) {
    // When user logs in, load their history from the server
    effect(() => {
      if (this.auth.isLoggedIn()) {
        this.loadFromServer();
      } else {
        // Logged out — clear
        this.history.set([]);
        this.forwardStack.set([]);
        this.lastPosition.set(null);
      }
    });
  }

  /** Whether we're in a programmatic back/forward navigation */
  get isNavigating(): boolean {
    return this._navigating;
  }

  /**
   * Record navigating TO a new location.
   * Push the PREVIOUS position onto the back stack.
   */
  pushHistory(previous: ReadingPosition) {
    if (this._navigating) return;
    if (!previous.book || !previous.chapter) return;

    // Don't push duplicates
    const stack = this.history();
    const top = stack[stack.length - 1];
    if (top && top.book === previous.book && top.chapter === previous.chapter && top.verse === previous.verse) {
      return;
    }

    this.history.update(h => [...h, { ...previous }]);
    // New navigation clears the forward stack
    this.forwardStack.set([]);

    // Persist to server
    if (this.auth.isLoggedIn()) {
      this.saveHistoryEntry(previous);
    }
  }

  /**
   * Go back: pop from history, push current onto forward stack.
   * Returns the position to navigate to, or null.
   */
  goBack(current: ReadingPosition): ReadingPosition | null {
    const stack = this.history();
    if (stack.length === 0) return null;

    const dest = stack[stack.length - 1];
    this.history.update(h => h.slice(0, -1));

    // Push current onto forward stack
    if (current.book && current.chapter) {
      this.forwardStack.update(f => [...f, { ...current }]);
    }

    this._navigating = true;
    return dest;
  }

  /**
   * Go forward: pop from forward stack, push current onto history.
   * Returns the position to navigate to, or null.
   */
  goForward(current: ReadingPosition): ReadingPosition | null {
    const fwd = this.forwardStack();
    if (fwd.length === 0) return null;

    const dest = fwd[fwd.length - 1];
    this.forwardStack.update(f => f.slice(0, -1));

    // Push current onto back stack
    if (current.book && current.chapter) {
      this.history.update(h => [...h, { ...current }]);
    }

    this._navigating = true;
    return dest;
  }

  /** Call after the navigation from goBack/goForward is complete */
  doneNavigating() {
    this._navigating = false;
  }

  /**
   * Save the user's current reading position to the server.
   * Called on every chapter/verse load.
   */
  savePosition(pos: ReadingPosition) {
    if (!this.auth.isLoggedIn()) return;
    const headers = this.auth.getAuthHeaders();
    this.http.put('/api/reading/position', {
      book: pos.book,
      chapter: pos.chapter,
      verse: pos.verse,
      forwardStack: this.forwardStack()
    }, { headers }).subscribe({ error: () => {} });
  }

  /** Load history + position from the backend on login */
  private loadFromServer() {
    const headers = this.auth.getAuthHeaders();

    // Load position
    this.http.get<{ position: ReadingPosition | null; forwardStack: HistoryEntry[] }>(
      '/api/reading/position', { headers }
    ).subscribe({
      next: (data) => {
        this.lastPosition.set(data.position);
        this.forwardStack.set(data.forwardStack || []);
      },
      error: () => {}
    });

    // Load history (back stack)
    this.http.get<{ history: HistoryEntry[] }>(
      '/api/reading/history?limit=100', { headers }
    ).subscribe({
      next: (data) => {
        // Server returns newest first; we want oldest-first so the most recent is the last element
        this.history.set((data.history || []).reverse());
      },
      error: () => {}
    });
  }

  /** Persist a single history entry to the server */
  private saveHistoryEntry(entry: ReadingPosition) {
    const headers = this.auth.getAuthHeaders();
    this.http.post('/api/reading/history', {
      book: entry.book,
      chapter: entry.chapter,
      verse: entry.verse
    }, { headers }).subscribe({ error: () => {} });
  }
}
