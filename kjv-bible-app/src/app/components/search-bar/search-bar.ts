import { Component, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { BibleApiService } from '../../services/bible-api';
import { NavigationService } from '../../services/navigation.service';
import { Verse } from '../../models/bible.models';
import { InputTextModule } from 'primeng/inputtext';
import { ButtonModule } from 'primeng/button';
import { SelectButtonModule } from 'primeng/selectbutton';
import { IconFieldModule } from 'primeng/iconfield';
import { InputIconModule } from 'primeng/inputicon';

@Component({
  selector: 'app-search-bar',
  imports: [
    CommonModule, FormsModule,
    InputTextModule, ButtonModule, SelectButtonModule, IconFieldModule, InputIconModule
  ],
  templateUrl: './search-bar.html',
  styleUrl: './search-bar.scss',
})
export class SearchBar {
  query = '';
  searchType = 'semantic';
  searchTypeOptions = [
    { label: 'Semantic', value: 'semantic' },
    { label: 'Keyword', value: 'keyword' }
  ];
  loading = signal(false);
  searchResults = signal<Verse[]>([]);
  showResults = signal(false);

  constructor(
    private api: BibleApiService,
    private nav: NavigationService
  ) {}

  search() {
    if (!this.query.trim()) return;
    this.loading.set(true);
    this.showResults.set(true);

    this.api.search(this.query, this.searchType as 'semantic' | 'keyword').subscribe({
      next: (data) => {
        this.searchResults.set(data.verses || []);
        this.loading.set(false);
      },
      error: () => {
        this.searchResults.set([]);
        this.loading.set(false);
      }
    });
  }

  onKeydown(event: KeyboardEvent) {
    if (event.key === 'Enter') {
      this.search();
    }
  }

  navigateToResult(verse: Verse) {
    this.nav.requestNavigation(verse.book, verse.chapter, verse.verse);
    this.showResults.set(false);
  }

  closeResults() {
    this.showResults.set(false);
  }
}
