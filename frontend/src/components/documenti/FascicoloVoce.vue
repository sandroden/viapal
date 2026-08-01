<template>
  <div
    class="vp-dvoce"
    :class="{
      'vp-dvoce--vuota': vuota,
      'vp-dvoce--attiva': selezionata,
      'vp-dvoce--cliccabile': cliccabile,
    }"
    :role="cliccabile ? 'button' : undefined"
    :tabindex="cliccabile ? 0 : undefined"
    @click="attiva"
    @keydown.enter="attiva"
  >
    <DocMiniatura
      :pagina="voce.pagine[0] ?? null"
      :stato="voce.stato"
      :attesa="voce.stato === 'attesa'"
      :larghezza="larghezza"
      :altezza="altezza"
    />

    <div class="vp-dvoce__testo">
      <div class="vp-dvoce__nome">{{ voce.titolo ?? voce.tipo_display }}</div>
      <div class="vp-dvoce__riga">
        <DocBadgeStato v-if="mostraBadge" :stato="voce.stato" :testo="testoBadge" />
        <span class="vp-dvoce__meta">{{ dettaglio }}</span>
      </div>
    </div>

    <slot name="azioni">
      <button
        v-if="voce.stato === 'mancante' && !soloLettura"
        class="vp-btn vp-btn--soft vp-dvoce__aggiungi"
        @click.stop="emit('aggiungi', voce)"
      >
        Aggiungi
      </button>
      <q-icon
        v-else-if="voce.pagine.length"
        name="chevron_right"
        size="18px"
        class="vp-dvoce__chevron"
      />
    </slot>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue';
import DocMiniatura from './DocMiniatura.vue';
import DocBadgeStato from './DocBadgeStato.vue';
import type { VoceFascicolo } from 'stores/fascicolo';
import { dettaglioVoce } from 'src/utils/statoDocumento';
import { useFormatoData } from 'src/composables/useFormatoData';

const props = withDefaults(
  defineProps<{
    voce: VoceFascicolo;
    /** Niente azioni di caricamento (documenti della casa, ruolo sola lettura). */
    soloLettura?: boolean;
    /** Riga evidenziata: il documento aperto nel visore affiancato (desktop). */
    selezionata?: boolean;
    larghezza?: number;
    altezza?: number;
    /** Il badge di stato compare anche quando il documento è valido. */
    badgeSempre?: boolean;
    /** Badge con la data ("scade 14/10/2026"): la riga di dettaglio mostra
     *  allora il caricamento invece della scadenza (uso desktop). */
    badgeConData?: boolean;
    /** Vista del proprietario: "lo carichi tu" invece di "non devi fare nulla". */
    latoProprieta?: boolean;
  }>(),
  {
    soloLettura: false,
    selezionata: false,
    larghezza: 40,
    altezza: 50,
    badgeSempre: false,
    badgeConData: false,
    latoProprieta: false,
  },
);

const emit = defineEmits<{
  apri: [voce: VoceFascicolo];
  aggiungi: [voce: VoceFascicolo];
}>();

const { formattaData } = useFormatoData();

const vuota = computed(() => props.voce.pagine.length === 0);
// Per l'inquilino la voce "a carico della proprietà" è inerte: nessun bottone,
// nessuna ansia. Per il proprietario è invece la riga da cui caricarla.
const cliccabile = computed(() => {
  if (props.voce.pagine.length) return true;
  if (props.soloLettura) return false;
  return props.voce.stato === 'mancante' || (props.voce.stato === 'attesa' && props.latoProprieta);
});
const mostraBadge = computed(
  () => props.badgeSempre || (props.voce.stato !== 'ok' && props.voce.stato !== 'mancante'),
);
const testoBadge = computed(() => {
  const { stato, data_scadenza } = props.voce;
  if (!props.badgeConData || !data_scadenza) return undefined;
  if (stato === 'scadenza') return `scade ${formattaData(data_scadenza)}`;
  if (stato === 'scaduto') return `scaduto ${formattaData(data_scadenza)}`;
  return undefined;
});
// Con la data nel badge la riga sotto racconta il caricamento, non la scadenza:
// ripetere due volte la stessa data è rumore.
const dettaglio = computed(() =>
  dettaglioVoce(props.voce, formattaData, {
    scadenzaNelBadge: props.badgeConData,
    latoProprieta: props.latoProprieta,
  }),
);

function attiva() {
  if (!cliccabile.value) return;
  // Lato proprietario anche le voci vuote si "aprono": il pannello mostra di
  // chi è il turno e il bottone per caricare.
  if (props.voce.pagine.length || props.latoProprieta) emit('apri', props.voce);
  else emit('aggiungi', props.voce);
}
</script>

<style scoped>
.vp-dvoce {
  display: flex;
  align-items: center;
  gap: var(--vp-gap-3);
  padding: var(--vp-gap-3) var(--vp-gap-4);
  background: var(--vp-cream);
  border-bottom: 1px solid var(--vp-paper-3);
  text-align: left;
}
.vp-dvoce:last-child {
  border-bottom: none;
}
.vp-dvoce--vuota {
  background: transparent;
}
.vp-dvoce--cliccabile {
  cursor: pointer;
}
.vp-dvoce--cliccabile:hover {
  background: var(--vp-paper-2);
}
.vp-dvoce--attiva,
.vp-dvoce--attiva:hover {
  background: var(--vp-terra-soft);
  box-shadow: inset 3px 0 0 var(--vp-terra);
}
.vp-dvoce__testo {
  flex: 1;
  min-width: 0;
}
.vp-dvoce__nome {
  font-size: var(--vp-text-md);
  font-weight: 500;
  color: var(--vp-ink);
  margin-bottom: 3px;
}
.vp-dvoce--vuota .vp-dvoce__nome {
  color: var(--vp-ink-2);
}
.vp-dvoce__riga {
  display: flex;
  align-items: center;
  gap: var(--vp-gap-2);
  flex-wrap: wrap;
}
.vp-dvoce__meta {
  font-size: 12.5px;
  color: var(--vp-ink-3);
}
.vp-dvoce__aggiungi {
  height: 32px;
  padding: 0 12px;
  font-size: var(--vp-text-sm);
  white-space: nowrap;
}
.vp-dvoce__chevron {
  color: var(--vp-ink-4);
  flex: none;
}
</style>
