<template>
  <!-- Il blocco tiene insieme la riga e, per i documenti firmati, le sue
       versioni: il bordo che separa le voci sta qui, non sulla riga. -->
  <div class="vp-dvoce-blocco">
    <div
      class="vp-dvoce"
      :class="{ 'vp-dvoce--attiva': selezionata }"
      role="button"
      tabindex="0"
      :aria-expanded="conVersioni ? espansa : undefined"
      @click="clic"
      @keydown.enter="clic"
    >
      <DocMiniatura
        v-if="voce.pagine[0]"
        :pagina="voce.pagine[0]"
        :stato="voce.stato"
        :larghezza="larghezza"
        :altezza="altezza"
      />

      <div class="vp-dvoce__testo">
        <div class="vp-dvoce__nome">{{ voce.titolo ?? voce.tipo_display }}</div>
        <div class="vp-dvoce__riga">
          <!-- Per i documenti firmati lo stato che conta è la firma della
               versione principale; la scadenza resta, se mai ci fosse. -->
          <DocBadgeFirma v-if="voce.versioni" :stato="voce.stato_firma" />
          <DocBadgeStato v-if="mostraBadge" :stato="voce.stato" :testo="testoBadge" />
          <span class="vp-dvoce__meta">{{ dettaglio }}</span>
        </div>
      </div>

      <slot name="azioni">
        <q-icon
          v-if="voce.pagine.length && !conVersioni"
          name="chevron_right"
          size="18px"
          class="vp-dvoce__chevron"
        />
      </slot>
      <q-icon
        v-if="conVersioni"
        :name="espansa ? 'expand_less' : 'expand_more'"
        size="20px"
        class="vp-dvoce__chevron"
      />
    </div>

    <!-- Le versioni, la più avanzata per prima: ognuna si apre da sé. -->
    <div
      v-if="conVersioni && espansa"
      class="vp-dvoce__versioni"
      :style="{ '--vp-dvoce-rientro': `${larghezza}px` }"
    >
      <div
        v-for="p in voce.pagine"
        :key="p.id"
        class="vp-dvoce__versione"
        :class="{ 'vp-dvoce__versione--attiva': selezionata && p.id === paginaAttivaId }"
        role="button"
        tabindex="0"
        @click="emit('apriVersione', voce, p)"
        @keydown.enter="emit('apriVersione', voce, p)"
      >
        <div class="vp-dvoce__vtesto">
          <DocBadgeFirma :stato="p.stato_firma" />
          <span class="vp-dvoce__vdata">
            {{ p.generato ? 'generata' : 'caricata' }} il {{ formattaData(p.created_at) }}
          </span>
        </div>
        <a
          :href="p.file"
          :download="p.nome_file"
          class="vp-dvoce__vazione"
          aria-label="Scarica questa versione"
          @click.stop
        >
          <q-icon name="download" size="16px" />
        </a>
        <button
          v-if="p.modificabile && !soloLettura"
          class="vp-dvoce__vazione vp-dvoce__vazione--rischio"
          aria-label="Elimina questa versione"
          @click.stop="confermaEliminaFile($q, voce, p, () => emit('elimina', p.id))"
        >
          <q-icon name="delete_outline" size="16px" />
        </button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue';
import { useQuasar } from 'quasar';
import DocMiniatura from './DocMiniatura.vue';
import DocBadgeStato from './DocBadgeStato.vue';
import DocBadgeFirma from './DocBadgeFirma.vue';
import type { PaginaDocumento, VoceFascicolo } from 'stores/fascicolo';
import { confermaEliminaFile, dettaglioVoce } from 'src/utils/statoDocumento';
import { useFormatoData } from 'src/composables/useFormatoData';

const props = withDefaults(
  defineProps<{
    voce: VoceFascicolo;
    /** Riga evidenziata: il documento aperto nel visore affiancato (desktop). */
    selezionata?: boolean;
    larghezza?: number;
    altezza?: number;
    /** Il badge di stato compare anche quando il documento è valido. */
    badgeSempre?: boolean;
    /** Badge con la data ("scade 14/10/2026"): la riga di dettaglio mostra
     *  allora il caricamento invece della scadenza (uso desktop). */
    badgeConData?: boolean;
    /** Versione mostrata nel visore: la sotto-riga corrispondente è evidenziata. */
    paginaAttivaId?: number | null;
    /** Con le versioni il clic sulla riga apre anche la principale. Senza
     *  visore affiancato (mobile) si limita a espandere: aprire subito a
     *  schermo intero nasconderebbe proprio l'elenco appena aperto. */
    apriSubito?: boolean;
    /** Nessun cestino sulle versioni. */
    soloLettura?: boolean;
  }>(),
  {
    selezionata: false,
    paginaAttivaId: null,
    apriSubito: true,
    soloLettura: false,
    larghezza: 40,
    altezza: 50,
    badgeSempre: false,
    badgeConData: false,
  },
);

const emit = defineEmits<{
  apri: [voce: VoceFascicolo];
  apriVersione: [voce: VoceFascicolo, pagina: PaginaDocumento];
  /** Già confermata dall'utente. */
  elimina: [id: number];
}>();

const $q = useQuasar();
const { formattaData } = useFormatoData();

/** Con una sola versione non c'è niente da espandere: il badge dice già tutto. */
const conVersioni = computed(() => props.voce.versioni && props.voce.pagine.length > 1);
const espansa = ref(false);

function clic() {
  if (!conVersioni.value) {
    emit('apri', props.voce);
    return;
  }
  if (!props.apriSubito) {
    espansa.value = !espansa.value;
    return;
  }
  // Primo clic: apre la principale e mostra le versioni; sulla voce già
  // aperta il clic richiude l'elenco (e torna comunque alla principale).
  espansa.value = props.selezionata ? !espansa.value : true;
  emit('apri', props.voce);
}

const mostraBadge = computed(() => props.badgeSempre || props.voce.stato !== 'ok');
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
  dettaglioVoce(props.voce, formattaData, { scadenzaNelBadge: props.badgeConData }),
);
</script>

<style scoped>
.vp-dvoce-blocco {
  border-bottom: 1px solid var(--vp-paper-3);
}
.vp-dvoce-blocco:last-child {
  border-bottom: none;
}
.vp-dvoce {
  display: flex;
  align-items: center;
  gap: var(--vp-gap-3);
  padding: var(--vp-gap-3) var(--vp-gap-4);
  background: var(--vp-cream);
  text-align: left;
  cursor: pointer;
}
.vp-dvoce:hover {
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
.vp-dvoce__chevron {
  color: var(--vp-ink-4);
  flex: none;
}

/* ── Versioni: sotto-righe compatte, rientrate sotto il testo della voce ── */
.vp-dvoce__versioni {
  padding: 0 var(--vp-gap-4) var(--vp-gap-2);
  /* Il badge della versione si allinea al titolo della voce: rientro della
     miniatura più lo spazio, meno il padding della sotto-riga. */
  padding-left: calc(
    var(--vp-gap-4) + var(--vp-dvoce-rientro) + var(--vp-gap-3) - var(--vp-gap-2)
  );
  background: var(--vp-cream);
}
/* Sul telefono il rientro sotto la miniatura costa troppo: le versioni
   partono dal bordo, la gerarchia la dice già lo sfondo. */
@media (max-width: 599px) {
  .vp-dvoce__versioni {
    padding-left: var(--vp-gap-3);
    padding-right: var(--vp-gap-3);
  }
}
.vp-dvoce__versione {
  display: flex;
  min-width: 0;
  align-items: center;
  gap: var(--vp-gap-2);
  min-height: 36px;
  padding: 2px var(--vp-gap-2);
  border-radius: var(--vp-r-sm);
  cursor: pointer;
}
.vp-dvoce__versione:hover {
  background: var(--vp-paper-2);
}
.vp-dvoce__versione--attiva,
.vp-dvoce__versione--attiva:hover {
  background: var(--vp-terra-soft);
}
/* Su schermo stretto la data va a capo sotto il badge invece di troncarsi:
   è l'unica cosa che distingue due versioni con lo stesso stato. */
.vp-dvoce__vtesto {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  column-gap: var(--vp-gap-2);
  row-gap: 2px;
  padding: 2px 0;
}
.vp-dvoce__vdata {
  font-size: 12.5px;
  color: var(--vp-ink-3);
  white-space: nowrap;
}
.vp-dvoce__versione > .vp-dvoce__vazione {
  flex: none;
}
.vp-dvoce__vazione {
  display: flex;
  align-items: center;
  padding: 4px;
  border: none;
  background: none;
  color: var(--vp-ink-4);
  cursor: pointer;
}
.vp-dvoce__vazione:hover {
  color: var(--vp-terra);
}
.vp-dvoce__vazione--rischio:hover {
  color: var(--vp-clay);
}
</style>
