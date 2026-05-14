import { ref } from 'vue';

interface AxiosLikeError {
  response?: {
    status?: number;
    data?: unknown;
  };
}

function isObject(v: unknown): v is Record<string, unknown> {
  return typeof v === 'object' && v !== null && !Array.isArray(v);
}

function joinMessages(v: unknown): string {
  if (typeof v === 'string') return v;
  if (Array.isArray(v)) return v.filter((x) => typeof x === 'string').join(' ');
  return '';
}

export function useFormErrors() {
  const errors = ref<Record<string, string>>({});
  const globalError = ref<string>('');

  function reset() {
    errors.value = {};
    globalError.value = '';
  }

  function captureError(e: unknown, fallback = 'Salvataggio non riuscito') {
    reset();
    const err = e as AxiosLikeError;
    const status = err.response?.status;
    const data = err.response?.data;

    if (status === 400 && isObject(data)) {
      const fieldErrors: Record<string, string> = {};
      const globals: string[] = [];
      for (const [field, value] of Object.entries(data)) {
        const msg = joinMessages(value);
        if (!msg) continue;
        if (field === 'non_field_errors' || field === 'detail') {
          globals.push(msg);
        } else {
          fieldErrors[field] = msg;
        }
      }
      errors.value = fieldErrors;
      globalError.value = globals.join(' ');
      if (!globalError.value && Object.keys(fieldErrors).length === 0) {
        globalError.value = fallback;
      }
      return;
    }

    if (isObject(data) && typeof data.detail === 'string') {
      globalError.value = data.detail;
      return;
    }
    globalError.value = fallback;
  }

  function errorOf(field: string): string {
    return errors.value[field] ?? '';
  }

  return { errors, globalError, captureError, reset, errorOf };
}
