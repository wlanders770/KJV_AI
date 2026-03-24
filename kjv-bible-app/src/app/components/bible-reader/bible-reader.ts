import {
  Component, signal, computed, viewChild, OnDestroy,
  effect, untracked, ElementRef, AfterViewInit, NgZone, DestroyRef, inject
} from '@angular/core';
import { NavigationService } from '../../services/navigation.service';
import { BibleApiService } from '../../services/bible-api';
import { ReadingHistoryService } from '../../services/reading-history.service';
import { ChapterBlock, CrossReference, Verse } from '../../models/bible.models';

/** A single row in the scroll list */
export interface VirtualRow {
  type: 'book-divider' | 'chapter-header' | 'verse' | 'separator';
  book: string;
  chapter: number;
  verse?: Verse;
  id: string;        // unique key for trackBy
}

@Component({
  selector: 'app-bible-reader',
  imports: [],
  templateUrl: './bible-reader.html',
  styleUrl: './bible-reader.scss',
})
export class BibleReader implements OnDestroy, AfterViewInit {
  readonly scrollContainer = viewChild<ElementRef<HTMLElement>>('scrollContainer');
  private readonly el = inject(ElementRef);
  private readonly zone = inject(NgZone);
  private readonly destroyRef = inject(DestroyRef);

  /** Pixel height for the scroll container, measured from actual browser window */
  viewportHeight = signal(600);

  // ─── State ──────────────────────────────────────────────────────
  blocks = signal<ChapterBlock[]>([]);
  crossRefs = signal<{ [key: string]: CrossReference[] }>({});
  openPopup = signal<string | null>(null);
  previewRef = signal<string | null>(null);
  previewText = signal<string>('');

  /** Flat row list derived from blocks */
  rows = computed<VirtualRow[]>(() => {
    const result: VirtualRow[] = [];
    const blocks = this.blocks();
    for (let i = 0; i < blocks.length; i++) {
      const b = blocks[i];
      // Book divider when book changes
      if (i === 0 || blocks[i - 1].book !== b.book) {
        result.push({ type: 'book-divider', book: b.book, chapter: b.chapter, id: `div-${b.book}` });
      }
      // Chapter header
      result.push({ type: 'chapter-header', book: b.book, chapter: b.chapter, id: `hdr-${b.book}-${b.chapter}` });
      // Verses
      for (const v of b.verses) {
        result.push({ type: 'verse', book: b.book, chapter: b.chapter, verse: v, id: `v-${b.book}-${b.chapter}-${v.verse}` });
      }
      // Separator between chapters
      if (i < blocks.length - 1) {
        result.push({ type: 'separator', book: b.book, chapter: b.chapter, id: `sep-${b.book}-${b.chapter}` });
      }
    }
    return result;
  });

  private loadingNext = false;
  private loadGeneration = 0;   // incremented on each goTo() to abandon stale fetches
  private positionSaveTimer: any = null;
  private resizeListener: (() => void) | null = null;

  constructor(
    public nav: NavigationService,
    private api: BibleApiService,
    private history: ReadingHistoryService
  ) {
    effect(() => {
      const req = this.nav.navRequest();
      if (req) {
        untracked(() => this.goTo(req.book, req.chapter, req.verse));
      }
    });
  }

  ngAfterViewInit() {
    this.recalcHeight();
    this.zone.runOutsideAngular(() => {
      this.resizeListener = () => this.recalcHeight();
      window.addEventListener('resize', this.resizeListener);
    });
    this.destroyRef.onDestroy(() => {
      if (this.resizeListener) window.removeEventListener('resize', this.resizeListener);
    });
  }

  private recalcHeight() {
    const hostTop = (this.el.nativeElement as HTMLElement).getBoundingClientRect().top;
    const available = window.innerHeight - hostTop;
    const px = Math.max(available, 200);
    this.zone.run(() => this.viewportHeight.set(Math.floor(px)));
  }

  ngOnDestroy() {
    clearTimeout(this.positionSaveTimer);
  }

  // ═══════════════════════════════════════════════════════════════
  //  1. NAVIGATE
  // ═══════════════════════════════════════════════════════════════

  goTo(book: string, chapter: number, verse = 0) {
    // Already loaded? Just scroll to it
    const blocks = this.blocks();
    const existing = blocks.find(b => b.book === book && b.chapter === chapter);
    if (existing) {
      this.setActive(book, chapter, existing.verses);
      setTimeout(() => this.scrollToRow(
        verse > 0 ? `v-${book}-${chapter}-${verse}` : `hdr-${book}-${chapter}`,
        verse
      ));
      return;
    }

    // Fresh load — reset everything
    const gen = ++this.loadGeneration;
    this.loadingNext = false;
    this.blocks.set([]);

    this.api.getChapter(book, chapter).subscribe(data => {
      if (gen !== this.loadGeneration) return; // stale
      const block: ChapterBlock = { book, chapter, verses: data.verses || [] };
      this.blocks.set([block]);
      this.setActive(book, chapter, block.verses);

      // Scroll to the requested verse (after DOM renders)
      setTimeout(() => {
        if (verse > 0) {
          this.scrollToRow(`v-${book}-${chapter}-${verse}`, verse);
        } else {
          const container = this.scrollContainer()?.nativeElement;
          if (container) container.scrollTop = 0;
        }
      }, 50);

      // Preload next 2 chapters
      this.appendNextChapters(2, gen);
    });
  }

  // ═══════════════════════════════════════════════════════════════
  //  2. CONTINUOUS SCROLL — append chapters
  // ═══════════════════════════════════════════════════════════════

  private appendNextChapters(count: number, gen: number) {
    if (count <= 0 || this.loadingNext || gen !== this.loadGeneration) return;
    this.loadingNext = true;
    this.appendOne(gen, () => {
      this.loadingNext = false;
      if (count > 1) this.appendNextChapters(count - 1, gen);
    });
  }

  private appendOne(gen: number, done: () => void) {
    const blocks = this.blocks();
    if (!blocks.length) { done(); return; }
    const last = blocks[blocks.length - 1];
    const next = this.nav.getNextChapter(last.book, last.chapter);
    if (!next || blocks.some(b => b.book === next.book && b.chapter === next.chapter)) {
      done(); return;
    }
    this.api.getChapter(next.book, next.chapter).subscribe({
      next: data => {
        if (gen !== this.loadGeneration) return; // stale
        this.blocks.update(b => [...b, { book: next.book, chapter: next.chapter, verses: data.verses || [] }]);
        done();
      },
      error: () => done()
    });
  }

  // ═══════════════════════════════════════════════════════════════
  //  3. SCROLL EVENT — breadcrumb + fetch-ahead
  // ═══════════════════════════════════════════════════════════════

  onScroll() {
    const container = this.scrollContainer()?.nativeElement;
    if (!container) return;

    // Find the first visible chapter header by checking element positions
    const rows = container.querySelectorAll<HTMLElement>('[data-row-id]');
    const containerTop = container.getBoundingClientRect().top;

    let visibleBook = '';
    let visibleChapter = 0;
    for (const row of Array.from(rows)) {
      const rect = row.getBoundingClientRect();
      if (rect.bottom > containerTop) {
        const rowId = row.getAttribute('data-row-id') || '';
        // Parse book and chapter from row id (hdr-Book-Ch, v-Book-Ch-V, etc.)
        const match = rowId.match(/^(?:hdr|v|div|sep)-(.+?)-(\d+)/);
        if (match) {
          visibleBook = match[1];
          visibleChapter = parseInt(match[2]);
          break;
        }
      }
    }

    if (visibleBook && (visibleBook !== this.nav.currentBook() || visibleChapter !== this.nav.currentChapter())) {
      this.nav.currentBook.set(visibleBook);
      this.nav.currentChapter.set(visibleChapter);
      const block = this.blocks().find(b => b.book === visibleBook && b.chapter === visibleChapter);
      if (block) this.nav.setChapterVerses(block.verses);
      this.debounceSavePosition(visibleBook, visibleChapter);
    }

    // Near the end? Prefetch more chapters
    const scrollBottom = container.scrollTop + container.clientHeight;
    if (scrollBottom > container.scrollHeight - 500 && !this.loadingNext) {
      this.appendNextChapters(3, this.loadGeneration);
    }
  }

  // ═══════════════════════════════════════════════════════════════
  //  4. HELPERS
  // ═══════════════════════════════════════════════════════════════

  private scrollToRow(rowId: string, verse: number) {
    const container = this.scrollContainer()?.nativeElement;
    if (!container) return;
    const el = container.querySelector(`[data-row-id="${rowId}"]`);
    if (el) {
      el.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }
    if (verse > 0) {
      this.nav.selectVerse(verse, false);
      this.nav.highlightedVerse.set(verse);
      setTimeout(() => this.nav.highlightedVerse.set(0), 2500);
    }
  }

  private setActive(book: string, chapter: number, verses: Verse[]) {
    this.nav.currentBook.set(book);
    this.nav.currentChapter.set(chapter);
    this.nav.setChapterVerses(verses);
    this.history.savePosition({ book, chapter, verse: 0 });
  }

  private debounceSavePosition(book: string, chapter: number) {
    clearTimeout(this.positionSaveTimer);
    this.positionSaveTimer = setTimeout(() => {
      this.history.savePosition({ book, chapter, verse: 0 });
    }, 2000);
  }

  // ─── Cross-ref key helper ──────────────────────────────────────
  refKey(book: string, chapter: number, verse: number): string {
    return `${book}:${chapter}:${verse}`;
  }

  // ═══════════════════════════════════════════════════════════════
  //  5. CROSS-REFERENCES
  // ═══════════════════════════════════════════════════════════════

  toggleCrossRefs(book: string, chapter: number, verse: number, event: Event) {
    event.stopPropagation();
    const key = this.refKey(book, chapter, verse);
    if (this.openPopup() === key) { this.openPopup.set(null); return; }
    this.openPopup.set(key);
    if (!this.crossRefs()[key]) {
      this.api.getCrossReferences(book, chapter, verse).subscribe(refs => {
        this.crossRefs.update(curr => ({ ...curr, [key]: refs }));
      });
    }
  }

  onCrossRefClick(reference: string, event: Event) {
    event.stopPropagation();
    this.openPopup.set(null);
    this.showPreview(reference);
  }

  showPreview(reference: string) {
    this.previewRef.set(reference);
    this.previewText.set('Loading...');
    this.api.getVerseByReference(reference).subscribe({
      next: data => this.previewText.set(
        data.verses?.length ? data.verses.map((v: Verse) => v.text).join(' ') : 'Verse not found.'
      ),
      error: () => this.previewText.set('Could not load verse.')
    });
  }

  closePreview() {
    this.previewRef.set(null);
    this.previewText.set('');
  }

  navigateToRef(reference: string) {
    const match = reference.match(/^(.+?)\s+(\d+):(\d+)/);
    if (match) {
      const book = match[1];
      const chapter = parseInt(match[2]);
      const verse = parseInt(match[3]);

      const curBook = this.nav.currentBook();
      const curChapter = this.nav.currentChapter();
      const curVerse = this.nav.currentVerse();
      if (curBook && curChapter) {
        this.history.pushHistory({ book: curBook, chapter: curChapter, verse: curVerse });
      }

      this.goTo(book, chapter, verse);
    }
    this.closePreview();
  }
}
