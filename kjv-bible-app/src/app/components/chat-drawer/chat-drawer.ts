import { Component, signal, ElementRef, viewChild } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { BibleApiService } from '../../services/bible-api';
import { ChatMessage } from '../../models/bible.models';
import { InputTextModule } from 'primeng/inputtext';
import { ButtonModule } from 'primeng/button';

@Component({
  selector: 'app-chat-drawer',
  imports: [CommonModule, FormsModule, InputTextModule, ButtonModule],
  templateUrl: './chat-drawer.html',
  styleUrl: './chat-drawer.scss',
})
export class ChatDrawer {
  readonly messagesContainer = viewChild<ElementRef>('messagesContainer');

  messages = signal<ChatMessage[]>([
    {
      content: `Welcome! I can help you understand the Bible. Try asking:\n• What does the Bible say about love?\n• Tell me about faith\n• Who was David?\n• What is salvation?`,
      type: 'assistant'
    }
  ]);

  userInput = '';
  loading = signal(false);

  constructor(private api: BibleApiService) {}

  sendMessage() {
    const msg = this.userInput.trim();
    if (!msg || this.loading()) return;

    this.messages.update(msgs => [...msgs, { content: msg, type: 'user' }]);
    this.userInput = '';
    this.loading.set(true);
    this.scrollToBottom();

    this.api.chat(msg).subscribe({
      next: (res) => {
        let content = res.response;
        if (res.verses?.length) {
          content += '\n\n📖 Related Verses:\n';
          res.verses.forEach(v => {
            const ref = v.reference || `${v.book} ${v.chapter}:${v.verse}`;
            content += `\n${ref}: ${v.text}`;
          });
        }
        this.messages.update(msgs => [...msgs, { content, type: 'assistant', verses: res.verses }]);
        this.loading.set(false);
        this.scrollToBottom();
      },
      error: () => {
        this.messages.update(msgs => [...msgs, {
          content: 'Sorry, there was an error processing your request.',
          type: 'assistant'
        }]);
        this.loading.set(false);
        this.scrollToBottom();
      }
    });
  }

  onKeydown(event: KeyboardEvent) {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault();
      this.sendMessage();
    }
  }

  private scrollToBottom() {
    setTimeout(() => {
      const container = this.messagesContainer();
      if (container) {
        container.nativeElement.scrollTop = container.nativeElement.scrollHeight;
      }
    }, 50);
  }
}
