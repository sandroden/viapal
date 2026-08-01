<template>
  <q-dialog v-model="aperto" maximized transition-show="slide-up" transition-hide="slide-down">
    <div v-if="voce" class="vp-dvis">
      <!-- Testata: chi è il documento, non solo il nome del file -->
      <header class="vp-dvis__testa">
        <q-btn flat round dense icon="close" color="white" aria-label="Chiudi" @click="chiudi" />
        <div class="vp-dvis__titolo">
          <div class="vp-dvis__nome">{{ voce.titolo ?? voce.tipo_display }}</div>
          <div class="vp-dvis__meta">{{ meta }}</div>
        </div>
        <DocBadgeStato v-if="voce.stato !== 'ok'" :stato="voce.stato" />
      </header>

      <!-- La pagina -->
      <div class="vp-dvis__foglio" :class="{ 'vp-dvis__foglio--pdf': pagina?.is_pdf }">
        <DocPagina v-if="pagina" :key="pagina.id" :pagina="pagina" />
      </div>

      <!-- Fronte e retro: due pagine dello stesso documento, non due file -->
      <div v-if="voce.pagine.length > 1" class="vp-dvis__pagine">
        <button
          v-for="(p, i) in voce.pagine"
          :key="p.id"
          class="vp-dvis__tab"
          :class="{ 'vp-dvis__tab--on': i === indice }"
          @click="indice = i"
        >
          {{ p.etichetta }}
        </button>
      </div>

      <!-- Azioni -->
      <footer class="vp-dvis__azioni">
        <a :href="pagina?.file" :download="pagina?.nome_file" class="vp-dvis__azione">
          <q-icon name="download" size="20px" />
          Scarica
        </a>
        <button v-if="!soloLettura" class="vp-dvis__azione" @click="emit('sostituisci', voce)">
          <q-icon name="photo_camera" size="20px" />
          Sostituisci
        </button>
        <button
          v-if="!soloLettura"
          class="vp-dvis__azione vp-dvis__azione--rischio"
          @click="confermaElimina"
        >
          <q-icon name="delete_outline" size="20px" />
          Elimina
        </button>
      </footer>
    </div>
  </q-dialog>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue';
import { useQuasar } from 'quasar';
import DocPagina from './DocPagina.vue';
import DocBadgeStato from './DocBadgeStato.vue';
import type { VoceFascicolo } from 'stores/fascicolo';
import { useFormatoData } from 'src/composables/useFormatoData';

const props = defineProps<{
  modelValue: boolean;
  /** Voce da visualizzare (con almeno una pagina). */
  voce: VoceFascicolo | null;
  soloLettura?: boolean;
}>();

const emit = defineEmits<{
  'update:modelValue': [valore: boolean];
  sostituisci: [voce: VoceFascicolo];
  elimina: [id: number];
}>();

const $q = useQuasar();
const { formattaData } = useFormatoData();

const aperto = computed({
  get: () => props.modelValue,
  set: (v: boolean) => emit('update:modelValue', v),
});

const indice = ref(0);
watch(
  () => props.voce,
  () => {
    indice.value = 0;
  },
);

const pagina = computed(() => props.voce?.pagine[indice.value] ?? null);

const meta = computed(() => {
  const voce = props.voce;
  if (!voce) return '';
  const parti: string[] = [];
  if (voce.pagine.length > 1 && pagina.value) parti.push(pagina.value.etichetta);
  if (voce.data_scadenza) {
    parti.push(
      (voce.stato === 'scaduto' ? 'scaduto il ' : 'scade il ') +
        formattaData(voce.data_scadenza),
    );
  } else if (voce.caricato_il) {
    parti.push(`caricato il ${formattaData(voce.caricato_il)}`);
  }
  return parti.join(' · ');
});

function chiudi() {
  aperto.value = false;
}

function confermaElimina() {
  const corrente = pagina.value;
  if (!corrente) return;
  const cosa =
    props.voce && props.voce.pagine.length > 1
      ? `la pagina "${corrente.etichetta}"`
      : `"${props.voce?.tipo_display}"`;
  $q.dialog({
    title: 'Elimina documento',
    message: `Eliminare ${cosa}? L'operazione non è reversibile.`,
    cancel: { label: 'Annulla', flat: true, noCaps: true },
    ok: { label: 'Elimina', color: 'negative', unelevated: true, noCaps: true },
  }).onOk(() => {
    emit('elimina', corrente.id);
  });
}
</script>

<style scoped>
/* Fondo scuro: il documento è la cosa illuminata, il resto sparisce. */
.vp-dvis {
  display: flex;
  flex-direction: column;
  height: 100%;
  background: oklch(0.24 0.02 55);
  color: var(--vp-cream);
}
.vp-dvis__testa {
  display: flex;
  align-items: center;
  gap: var(--vp-gap-3);
  padding: var(--vp-gap-3) var(--vp-gap-4);
  padding-top: max(var(--vp-gap-3), env(safe-area-inset-top));
}
.vp-dvis__titolo {
  flex: 1;
  min-width: 0;
}
.vp-dvis__nome {
  font-size: var(--vp-text-md);
  font-weight: 500;
}
.vp-dvis__meta {
  font-size: var(--vp-text-xs);
  color: oklch(0.78 0.015 70);
}
.vp-dvis__foglio {
  flex: 1;
  min-height: 0;
  padding: var(--vp-gap-1) var(--vp-gap-5) 0;
  display: flex;
  align-items: center;
  justify-content: center;
}
/* Il PDF ha già i suoi margini interni: gli si dà tutta la finestra. */
.vp-dvis__foglio--pdf {
  padding: 0;
}
.vp-dvis__pagine {
  display: flex;
  justify-content: center;
  gap: var(--vp-gap-2);
  padding: var(--vp-gap-4) 0 var(--vp-gap-1);
}
.vp-dvis__tab {
  height: 28px;
  padding: 0 12px;
  border: none;
  border-radius: var(--vp-r-pill);
  cursor: pointer;
  font-family: var(--vp-font-ui);
  font-size: 12.5px;
  background: oklch(0.34 0.02 55);
  color: oklch(0.8 0.015 70);
}
.vp-dvis__tab--on {
  background: var(--vp-cream);
  color: var(--vp-ink);
}
.vp-dvis__azioni {
  display: grid;
  grid-auto-flow: column;
  grid-auto-columns: 1fr;
  gap: 1px;
  background: oklch(0.32 0.018 55);
  border-top: 1px solid oklch(0.32 0.018 55);
  padding-bottom: env(safe-area-inset-bottom);
}
.vp-dvis__azione {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--vp-gap-1);
  padding: 14px 0 10px;
  border: none;
  background: oklch(0.24 0.02 55);
  color: var(--vp-cream);
  font-family: var(--vp-font-ui);
  font-size: var(--vp-text-xs);
  text-decoration: none;
  cursor: pointer;
}
.vp-dvis__azione--rischio {
  color: oklch(0.76 0.09 28);
}
</style>
