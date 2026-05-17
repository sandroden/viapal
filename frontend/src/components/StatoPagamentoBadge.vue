<template>
  <span
    class="vp-stp"
    :class="`vp-stp--${categoria} vp-stp--liv-${livello}`"
  >
    <span
      v-if="categoria === 'parziale'"
      class="vp-stp__fill"
      :style="{ width: `${percInt}%` }"
    />
    <span class="vp-stp__content">
      <q-icon :name="icona" size="14px" class="vp-stp__icon" />
      <span class="vp-stp__label">{{ etichetta }}</span>
    </span>
    <q-tooltip class="vp-stp__tip">{{ descrizione }}</q-tooltip>
  </span>
</template>

<script setup lang="ts">
import { computed } from 'vue';
import type { SemaforoLivello } from 'src/types/semaforo';
import { useFormatoEuro } from 'src/composables/useFormatoEuro';

const props = withDefaults(
  defineProps<{
    importoDovuto: number;
    importoPagato: number;
    stato: string;
    giorniRitardo?: number;
    /** Sotto questo ammanco (in €) la riga è considerata "pagata" (verde),
     *  così piccoli resti non fanno scattare l'allarme. */
    sogliaResto?: number;
  }>(),
  { giorniRitardo: 0, sogliaResto: 10 },
);

const { formattaEuro } = useFormatoEuro();

const dovuto = computed(() => Number(props.importoDovuto) || 0);
const pagato = computed(() => Math.max(0, Number(props.importoPagato) || 0));
const ammanco = computed(() => dovuto.value - pagato.value);

const perc = computed(() => {
  if (dovuto.value <= 0) return props.stato === 'pagato' ? 1 : 0;
  return Math.min(1, Math.max(0, pagato.value / dovuto.value));
});

const categoria = computed<'pagato' | 'parziale' | 'mancante'>(() => {
  if (props.stato === 'pagato') return 'pagato';
  if (dovuto.value <= 0) return 'mancante';
  // Ammanco trascurabile: lo trattiamo come pagato (niente campanello),
  // il resto si vedrà comunque nei saldi cumulativi.
  if (ammanco.value <= props.sogliaResto) return 'pagato';
  if (pagato.value > 0) return 'parziale';
  return 'mancante';
});

// Percentuale mostrata: per i parziali non arrotondiamo mai a 100
// (un parziale al 99,7% resta "99%", non "pagato").
const percInt = computed(() =>
  categoria.value === 'parziale'
    ? Math.min(99, Math.floor(perc.value * 100))
    : Math.round(perc.value * 100),
);

const livello = computed<SemaforoLivello>(() => {
  const g = props.giorniRitardo;
  if (g > 7) return 'argilla_scuro';
  if (g > 0) return 'argilla_chiaro';
  if (g > -7) return 'miele';
  return 'salvia';
});

// La riga è sostanzialmente saldata ma con un piccolo resto non versato.
const restoTrascurabile = computed(
  () =>
    props.stato !== 'pagato' &&
    ammanco.value > 0 &&
    ammanco.value <= props.sogliaResto,
);

const icona = computed(() => {
  if (categoria.value === 'pagato') return 'check_circle';
  if (categoria.value === 'parziale') return 'incomplete_circle';
  return livello.value === 'argilla_scuro' || livello.value === 'argilla_chiaro'
    ? 'error'
    : 'schedule';
});

const etichetta = computed(() => {
  if (categoria.value === 'parziale') return `${percInt.value}%`;
  if (categoria.value === 'pagato') return 'pagato';
  return props.stato.replace(/_/g, ' ');
});

const descrizione = computed(() => {
  if (categoria.value === 'parziale') {
    return `Pagato ${formattaEuro(pagato.value)} di ${formattaEuro(dovuto.value)} · manca ${formattaEuro(ammanco.value)}`;
  }
  if (categoria.value === 'pagato') {
    if (restoTrascurabile.value) {
      return `Considerato pagato — resto di ${formattaEuro(ammanco.value)} non versato`;
    }
    return `Pagato ${formattaEuro(pagato.value)}`;
  }
  const base = `Da incassare ${formattaEuro(dovuto.value)}`;
  const g = props.giorniRitardo;
  if (g > 0) return `${base} · ${g} g di ritardo`;
  if (g < 0) return `${base} · ${Math.abs(g)} g alla scadenza`;
  return base;
});
</script>

<style scoped>
.vp-stp {
  position: relative;
  display: inline-flex;
  align-items: center;
  height: 24px;
  padding: 0 10px;
  border-radius: var(--vp-r-pill);
  font-size: 12px;
  font-weight: 500;
  white-space: nowrap;
  font-family: var(--vp-font-ui);
  overflow: hidden;
}
.vp-stp__content {
  position: relative;
  z-index: 1;
  display: inline-flex;
  align-items: center;
  gap: 6px;
}
.vp-stp__icon {
  opacity: 0.85;
}

/* ── Riempimento (solo parziali): base "in difetto", sopra il verde
      largo quanto la percentuale versata ───────────────────────── */
.vp-stp__fill {
  position: absolute;
  left: 0;
  top: 0;
  bottom: 0;
  z-index: 0;
  background: var(--vp-status-ok-bg);
  border-radius: var(--vp-r-pill) 0 0 var(--vp-r-pill);
}
.vp-stp__fill::after {
  content: '';
  position: absolute;
  right: 0;
  top: 2px;
  bottom: 2px;
  width: 2px;
  background: var(--vp-sage);
  opacity: 0.55;
}

/* ── Pagato (incluso ammanco trascurabile): verde pieno ─────────── */
.vp-stp--pagato {
  background: var(--vp-status-ok-bg);
  color: var(--vp-status-ok-fg);
}

/* ── Parziale: base = colore urgenza, testo scuro leggibile sui
      due toni pastello, riempimento verde sovrapposto ───────────── */
.vp-stp--parziale {
  color: var(--vp-ink);
}
.vp-stp--parziale.vp-stp--liv-miele {
  background: var(--vp-status-wait-bg);
}
.vp-stp--parziale.vp-stp--liv-argilla_chiaro,
.vp-stp--parziale.vp-stp--liv-argilla_scuro {
  background: var(--vp-status-late-bg);
}
.vp-stp--parziale.vp-stp--liv-salvia {
  background: var(--vp-status-wait-bg);
}

/* ── Mancante: tinta piena secondo l'urgenza (semaforo) ─────────── */
.vp-stp--mancante.vp-stp--liv-miele,
.vp-stp--mancante.vp-stp--liv-salvia {
  background: var(--vp-status-wait-bg);
  color: var(--vp-status-wait-fg);
}
.vp-stp--mancante.vp-stp--liv-argilla_chiaro {
  background: oklch(0.92 0.045 35);
  color: oklch(0.45 0.11 30);
}
.vp-stp--mancante.vp-stp--liv-argilla_scuro {
  background: var(--vp-status-late-bg);
  color: var(--vp-status-late-fg);
}
</style>
