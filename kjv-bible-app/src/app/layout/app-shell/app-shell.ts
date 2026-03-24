import { Component, OnInit, viewChild, effect } from '@angular/core';
import { BibleNavigator } from '../../components/bible-navigator/bible-navigator';
import { BibleReader } from '../../components/bible-reader/bible-reader';
import { ChatDrawer } from '../../components/chat-drawer/chat-drawer';
import { SearchBar } from '../../components/search-bar/search-bar';
import { AuthDialog } from '../../components/auth-dialog/auth-dialog';
import { NavigationService } from '../../services/navigation.service';
import { BibleApiService } from '../../services/bible-api';
import { AuthService } from '../../services/auth.service';
import { ReadingHistoryService } from '../../services/reading-history.service';
import { ButtonModule } from 'primeng/button';
import { DrawerModule } from 'primeng/drawer';
import { ToolbarModule } from 'primeng/toolbar';
import { TooltipModule } from 'primeng/tooltip';

@Component({
  selector: 'app-shell',
  imports: [
    BibleNavigator,
    BibleReader,
    ChatDrawer,
    SearchBar,
    AuthDialog,
    ButtonModule,
    DrawerModule,
    ToolbarModule,
    TooltipModule,
  ],
  templateUrl: './app-shell.html',
  styleUrl: './app-shell.scss',
})
export class AppShell implements OnInit {
  readonly authDialog = viewChild<AuthDialog>('authDialog');
  mobileMode = window.innerWidth < 768;

  constructor(
    public nav: NavigationService,
    public auth: AuthService,
    public historyService: ReadingHistoryService,
    private api: BibleApiService
  ) {
    // When a position loads from server (after login), navigate to it
    effect(() => {
      const pos = this.historyService.lastPosition();
      if (pos && pos.book && pos.chapter) {
        // Small delay to ensure books are loaded
        setTimeout(() => this.navigateTo(pos.book, pos.chapter, pos.verse || 0), 200);
      }
    });
  }

  ngOnInit() {
    this.api.getBooks().subscribe(data => {
      this.nav.setBooks(data.books);
    });
  }

  openAuth() {
    this.authDialog()?.open();
  }

  confirmLogout() {
    if (confirm('Sign out of ' + this.auth.displayName() + '?')) {
      this.auth.logout();
    }
  }

  goBack() {
    const current = {
      book: this.nav.currentBook(),
      chapter: this.nav.currentChapter(),
      verse: this.nav.currentVerse()
    };
    const dest = this.historyService.goBack(current);
    if (dest) {
      this.navigateTo(dest.book, dest.chapter, dest.verse);
    }
  }

  goForward() {
    const current = {
      book: this.nav.currentBook(),
      chapter: this.nav.currentChapter(),
      verse: this.nav.currentVerse()
    };
    const dest = this.historyService.goForward(current);
    if (dest) {
      this.navigateTo(dest.book, dest.chapter, dest.verse);
    }
  }

  private navigateTo(book: string, chapter: number, verse: number) {
    this.nav.requestNavigation(book, chapter, verse);
    this.historyService.doneNavigating();
  }

  // Position restoration is now handled reactively via effect() in constructor
}
