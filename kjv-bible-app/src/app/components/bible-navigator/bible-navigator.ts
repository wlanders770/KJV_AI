import { Component, computed, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { NavigationService } from '../../services/navigation.service';
import { BibleApiService } from '../../services/bible-api';
import { ReadingHistoryService } from '../../services/reading-history.service';
import { InputTextModule } from 'primeng/inputtext';
import { IconFieldModule } from 'primeng/iconfield';
import { InputIconModule } from 'primeng/inputicon';

@Component({
  selector: 'app-bible-navigator',
  imports: [
    CommonModule, FormsModule,
    InputTextModule, IconFieldModule, InputIconModule
  ],
  templateUrl: './bible-navigator.html',
  styleUrl: './bible-navigator.scss',
})
export class BibleNavigator {
  bookFilter = signal('');
  selectedChapter = signal<number>(0);

  filteredBooks = computed(() => {
    const filter = this.bookFilter().toLowerCase();
    const books = this.nav.books();
    if (!filter) return books;
    return books.filter(b => b.name.toLowerCase().includes(filter));
  });

  chapterCount = computed(() => {
    const data = this.nav.currentBookData();
    return data ? data.chapters : 0;
  });

  chapters = computed(() => {
    const count = this.chapterCount();
    return Array.from({ length: count }, (_, i) => i + 1);
  });

  verses = computed(() => {
    return this.nav.chapterVerses().map(v => v.verse);
  });

  constructor(
    public nav: NavigationService,
    private api: BibleApiService,
    private history: ReadingHistoryService
  ) {}

  onSelectBook(bookName: string) {
    this.recordCurrentPosition();
    this.nav.requestNavigation(bookName, 1);
  }

  onSelectChapter(chapter: number) {
    this.recordCurrentPosition();
    this.nav.requestNavigation(this.nav.currentBook(), chapter);
  }

  onSelectVerse(verse: number) {
    this.nav.requestNavigation(this.nav.currentBook(), this.nav.currentChapter(), verse);
    this.nav.closeNav();
  }

  /** Push current position onto back stack before navigating away */
  private recordCurrentPosition() {
    const book = this.nav.currentBook();
    const chapter = this.nav.currentChapter();
    const verse = this.nav.currentVerse();
    if (book && chapter) {
      this.history.pushHistory({ book, chapter, verse });
    }
  }


}
