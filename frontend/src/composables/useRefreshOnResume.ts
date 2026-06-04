import { onBeforeUnmount, onMounted } from 'vue';

export interface RefreshOnResumeOptions {
  /**
   * Intervallo minimo tra due refresh consecutivi (ms). Serve a deduplicare i
   * trigger ravvicinati: al rientro nell'app `visibilitychange` (→ visible) e
   * `focus` scattano quasi insieme. Default 1500ms.
   */
  throttleMs?: number;
}

/**
 * Esegue `refresh` quando l'utente RIENTRA nell'app (tab/PWA tornata in
 * primo piano), così i dati non restano vecchi se la pagina è rimasta aperta a
 * lungo in background. NON viene chiamato al mount: l'onMounted della pagina
 * carica già i dati.
 */
export function useRefreshOnResume(
  refresh: () => void | Promise<void>,
  options: RefreshOnResumeOptions = {},
): void {
  const throttleMs = options.throttleMs ?? 1500;
  let last = 0;

  function trigger(): void {
    const now = Date.now();
    if (now - last < throttleMs) return;
    last = now;
    void refresh();
  }

  function onVisibility(): void {
    if (document.visibilityState === 'visible') trigger();
  }

  onMounted(() => {
    document.addEventListener('visibilitychange', onVisibility);
    window.addEventListener('focus', trigger);
  });

  onBeforeUnmount(() => {
    document.removeEventListener('visibilitychange', onVisibility);
    window.removeEventListener('focus', trigger);
  });
}
