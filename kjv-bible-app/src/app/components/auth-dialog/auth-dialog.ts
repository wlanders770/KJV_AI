import { Component, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { DialogModule } from 'primeng/dialog';
import { ButtonModule } from 'primeng/button';
import { InputTextModule } from 'primeng/inputtext';
import { SelectButtonModule } from 'primeng/selectbutton';
import { AuthService } from '../../services/auth.service';

@Component({
  selector: 'app-auth-dialog',
  imports: [CommonModule, FormsModule, DialogModule, ButtonModule, InputTextModule, SelectButtonModule],
  templateUrl: './auth-dialog.html',
  styleUrl: './auth-dialog.scss',
})
export class AuthDialog {
  visible = signal(false);
  mode = signal<'login' | 'register'>('login');
  username = '';
  password = '';
  displayName = '';
  error = signal<string>('');
  loading = signal(false);

  modeOptions = [
    { label: 'Sign In', value: 'login' },
    { label: 'Register', value: 'register' }
  ];

  constructor(public auth: AuthService) {}

  open() {
    this.username = '';
    this.password = '';
    this.displayName = '';
    this.error.set('');
    this.visible.set(true);
  }

  close() {
    this.visible.set(false);
  }

  submit() {
    this.error.set('');
    this.loading.set(true);

    if (this.mode() === 'login') {
      this.auth.login(this.username, this.password).subscribe({
        next: (resp) => {
          this.auth.setSession(resp);
          this.loading.set(false);
          this.close();
        },
        error: (err) => {
          this.loading.set(false);
          this.error.set(err.error?.error || 'Login failed');
        }
      });
    } else {
      this.auth.register(this.username, this.password, this.displayName || this.username).subscribe({
        next: (resp) => {
          this.auth.setSession(resp);
          this.loading.set(false);
          this.close();
        },
        error: (err) => {
          this.loading.set(false);
          this.error.set(err.error?.error || 'Registration failed');
        }
      });
    }
  }
}
