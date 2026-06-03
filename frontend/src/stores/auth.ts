import { defineStore } from 'pinia';
import { api } from 'boot/axios';

export type Role = 'proprietario' | 'inquilino' | null;

export interface BankAccountInfo {
  id: number;
  banca: string;
  intestatario: string;
  iban: string;
  owner_id: number;
}

export interface User {
  id: number;
  username: string;
  email: string;
  first_name: string;
  last_name: string;
  is_staff: boolean;
  is_superuser: boolean;
  role: Role;
  owner_profile_id: number | null;
  bank_accounts: BankAccountInfo[];
}

interface State {
  user: User | null;
  loaded: boolean;
}

export const useAuthStore = defineStore('auth', {
  state: (): State => ({
    user: null,
    loaded: false,
  }),
  getters: {
    isAuthenticated: (state): boolean => state.user !== null,
    role: (state): Role => state.user?.role ?? null,
    homePath(): string {
      if (this.role === 'proprietario') return '/p/';
      if (this.role === 'inquilino') return '/i/';
      return '/login';
    },
  },
  actions: {
    async ensureCsrf() {
      // Forza il backend a settare il cookie csrftoken
      await api.get('/api/auth/csrf/');
    },
    async fetchMe(): Promise<User | null> {
      try {
        const { data } = await api.get<User>('/api/auth/user/');
        this.user = data;
      } catch {
        this.user = null;
      }
      this.loaded = true;
      return this.user;
    },
    async login(username: string, password: string): Promise<User> {
      await this.ensureCsrf();
      await api.post('/api/auth/login/', { username, password });
      const me = await this.fetchMe();
      if (!me) throw new Error('Login fallito: utente non trovato');
      return me;
    },
    async logout() {
      try {
        await api.post('/api/auth/logout/');
      } finally {
        this.user = null;
      }
    },
    // Password dimenticata: chiede l'invio dell'email di reset. La risposta è
    // sempre 200 (non rivela se l'indirizzo esiste).
    async requestPasswordReset(email: string) {
      await this.ensureCsrf();
      await api.post('/api/auth/password/reset/', { email });
    },
    // Imposta/reimposta la password dal link ricevuto via email (invito o reset).
    async confirmPasswordReset(
      uid: string,
      token: string,
      newPassword1: string,
      newPassword2: string,
    ) {
      await this.ensureCsrf();
      await api.post('/api/auth/password/reset/confirm/', {
        uid,
        token,
        new_password1: newPassword1,
        new_password2: newPassword2,
      });
    },
    // Cambio password da utente loggato (richiede la vecchia password).
    async changePassword(
      oldPassword: string,
      newPassword1: string,
      newPassword2: string,
    ) {
      await this.ensureCsrf();
      await api.post('/api/auth/password/change/', {
        old_password: oldPassword,
        new_password1: newPassword1,
        new_password2: newPassword2,
      });
    },
  },
});
