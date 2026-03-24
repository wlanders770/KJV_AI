export interface Book {
  name: string;
  chapters: number;
}

export interface Verse {
  book: string;
  chapter: number;
  verse: number;
  text: string;
  reference?: string;
  similarity?: number;
}

export interface ChapterResponse {
  verses: Verse[];
}

export interface BooksResponse {
  books: Book[];
}

export interface SearchRequest {
  query: string;
  type: 'semantic' | 'keyword';
}

export interface SearchResponse {
  verses: Verse[];
}

export interface ChatRequest {
  message: string;
}

export interface ChatResponse {
  response: string;
  verses: Verse[];
}

export interface CrossReference {
  reference: string;
  votes: number;
}

export interface VerseByReferenceResponse {
  verses: Verse[];
  reference: string;
}

export interface NavigationState {
  currentBook: string;
  currentChapter: number;
  currentVerse: number;
}

export interface ChatMessage {
  content: string;
  type: 'user' | 'assistant';
  verses?: Verse[];
}

// Auth models
export interface AuthUser {
  id: number;
  username: string;
  displayName: string;
}

export interface AuthResponse {
  token: string;
  user: AuthUser;
}

// Continuous reader models
export interface ChapterBlock {
  book: string;
  chapter: number;
  verses: Verse[];
}

// Reading history models
export interface ReadingPosition {
  book: string;
  chapter: number;
  verse: number;
}

export interface HistoryEntry {
  book: string;
  chapter: number;
  verse: number;
  visitedAt?: string;
}
