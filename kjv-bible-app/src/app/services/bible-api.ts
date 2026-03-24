import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';
import {
  BooksResponse, ChapterResponse, ChatResponse,
  CrossReference, SearchResponse, Verse, VerseByReferenceResponse
} from '../models/bible.models';

@Injectable({ providedIn: 'root' })
export class BibleApiService {
  private baseUrl = '/api';

  constructor(private http: HttpClient) {}

  getBooks(): Observable<BooksResponse> {
    return this.http.get<BooksResponse>(`${this.baseUrl}/books`);
  }

  getChapter(book: string, chapter: number): Observable<ChapterResponse> {
    return this.http.get<ChapterResponse>(
      `${this.baseUrl}/chapter/${encodeURIComponent(book)}/${chapter}`
    );
  }

  getVerse(book: string, chapter: number, verse: number): Observable<{ verse: Verse }> {
    return this.http.get<{ verse: Verse }>(
      `${this.baseUrl}/verse/${encodeURIComponent(book)}/${chapter}/${verse}`
    );
  }

  getVerseByReference(reference: string): Observable<VerseByReferenceResponse> {
    return this.http.get<VerseByReferenceResponse>(
      `${this.baseUrl}/verse-by-reference/${encodeURIComponent(reference)}`
    );
  }

  getCrossReferences(book: string, chapter: number, verse: number): Observable<CrossReference[]> {
    return this.http.get<CrossReference[]>(
      `${this.baseUrl}/cross-references/${encodeURIComponent(book)}/${chapter}/${verse}`
    );
  }

  search(query: string, type: 'semantic' | 'keyword' = 'semantic'): Observable<SearchResponse> {
    return this.http.post<SearchResponse>(`${this.baseUrl}/search`, { query, type });
  }

  chat(message: string): Observable<ChatResponse> {
    return this.http.post<ChatResponse>(`${this.baseUrl}/chat`, { message });
  }
}
