import { Injectable, signal, computed } from '@angular/core';
import { NavigationState, Book, Verse } from '../models/bible.models';

@Injectable({ providedIn: 'root' })
export class NavigationService {
  // Reactive signals for navigation state
  readonly currentBook = signal<string>('');
  readonly currentChapter = signal<number>(0);
  readonly currentVerse = signal<number>(0);
  readonly books = signal<Book[]>([]);
  readonly chapterVerses = signal<Verse[]>([]);
  readonly highlightedVerse = signal<number>(0);
  readonly navOpen = signal<boolean>(false);
  readonly chatOpen = signal<boolean>(false);

  /**
   * Explicit navigation request — only set by user actions
   * (navigator click, back/fwd, cross-ref navigation).
   * The reader watches this and calls goTo().
   * The `id` field is a counter so repeated requests to the same chapter still fire.
   */
  readonly navRequest = signal<{ book: string; chapter: number; verse: number; id: number } | null>(null);
  private navRequestId = 0;

  /** Call this to navigate the reader to a specific location */
  requestNavigation(book: string, chapter: number, verse = 0) {
    this.navRequestId++;
    this.navRequest.set({ book, chapter, verse, id: this.navRequestId });
  }

  // Computed breadcrumb
  readonly breadcrumb = computed(() => {
    const book = this.currentBook();
    const ch = this.currentChapter();
    const v = this.currentVerse();
    if (!book) return 'Select a Book';
    if (!ch) return book;
    if (!v) return `${book} ${ch}`;
    return `${book} ${ch}:${v}`;
  });

  readonly currentBookData = computed(() =>
    this.books().find(b => b.name === this.currentBook())
  );

  toggleNav() {
    this.navOpen.update(v => !v);
  }

  openNav() {
    this.navOpen.set(true);
  }

  closeNav() {
    this.navOpen.set(false);
  }

  toggleChat() {
    this.chatOpen.update(v => !v);
  }

  selectBook(bookName: string) {
    this.currentBook.set(bookName);
    this.currentChapter.set(0);
    this.currentVerse.set(0);
    this.chapterVerses.set([]);
  }

  selectChapter(chapter: number) {
    this.currentChapter.set(chapter);
    this.currentVerse.set(0);
  }

  selectVerse(verse: number, closeNav = false) {
    this.currentVerse.set(verse);
    this.highlightedVerse.set(verse);

    if (closeNav) {
      this.closeNav();
    }

    // Clear highlight after animation
    setTimeout(() => this.highlightedVerse.set(0), 2500);
  }

  setBooks(books: Book[]) {
    this.books.set(books);
  }

  setChapterVerses(verses: Verse[]) {
    this.chapterVerses.set(verses);
  }

  /** Get the next book/chapter after the given one, or null if at end of Bible */
  getNextChapter(book: string, chapter: number): { book: string; chapter: number } | null {
    const allBooks = this.books();
    const bookData = allBooks.find(b => b.name === book);
    if (!bookData) return null;

    if (chapter < bookData.chapters) {
      return { book, chapter: chapter + 1 };
    }
    // Move to next book
    const idx = allBooks.indexOf(bookData);
    if (idx < allBooks.length - 1) {
      return { book: allBooks[idx + 1].name, chapter: 1 };
    }
    return null; // End of Revelation
  }

  /** Get the previous book/chapter before the given one, or null if at start of Bible */
  getPreviousChapter(book: string, chapter: number): { book: string; chapter: number } | null {
    const allBooks = this.books();
    const bookData = allBooks.find(b => b.name === book);
    if (!bookData) return null;

    if (chapter > 1) {
      return { book, chapter: chapter - 1 };
    }
    // Move to previous book, last chapter
    const idx = allBooks.indexOf(bookData);
    if (idx > 0) {
      const prevBook = allBooks[idx - 1];
      return { book: prevBook.name, chapter: prevBook.chapters };
    }
    return null; // Start of Genesis
  }
}
