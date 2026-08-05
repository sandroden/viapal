<template>
  <q-card flat bordered class="vp-card q-mb-md" style="max-width: 720px">
    <q-card-section>
      <div class="row items-center">
        <div class="vp-section-title">Quote di proprietà</div>
        <q-space />
        <q-btn
          v-if="sonoProprietario"
          dense
          flat
          color="primary"
          icon="edit"
          label="Nuovo assetto"
          @click="apriDialogQuote"
          data-testid="apri-quote"
        />
      </div>
      <q-list separator class="q-mt-sm">
        <q-item v-for="q in quoteCorrenti" :key="q.id">
          <q-item-section>
            <q-item-label>{{ q.owner_nominativo }}</q-item-label>
            <q-item-label caption>dal {{ q.valid_from }}</q-item-label>
          </q-item-section>
          <q-item-section side>
            <q-chip dense>{{ percentuale(q.quota) }}</q-chip>
          </q-item-section>
        </q-item>
        <q-item v-if="quoteCorrenti.length === 0">
          <q-item-section class="text-grey">
            Nessuna quota attiva configurata.
          </q-item-section>
        </q-item>
      </q-list>
    </q-card-section>
  </q-card>

  <!-- Dialog nuovo assetto quote -->
  <q-dialog v-model="dialogQuote">
    <q-card style="min-width: 420px">
      <q-card-section>
        <div class="vp-section-title">Nuovo assetto quote</div>
        <div class="vp-hint">
          La somma deve fare 100%. Valido dal giorno indicato; le quote
          precedenti vengono chiuse a quella data.
        </div>
      </q-card-section>
      <q-card-section class="q-gutter-sm">
        <q-input
          v-model="quoteValidFrom"
          label="Valido dal"
          type="date"
          outlined
          dense
        />
        <div
          v-for="riga in quoteForm"
          :key="riga.user"
          class="row items-center q-gutter-sm"
        >
          <div class="col">{{ riga.nominativo }}</div>
          <q-input
            v-model="riga.percento"
            type="number"
            dense
            outlined
            suffix="%"
            style="width: 110px"
            min="0"
            max="100"
            step="0.01"
          />
        </div>
        <div class="vp-hint">Totale: {{ totalePercento.toFixed(2) }}%</div>
        <q-banner v-if="quoteErrore" class="vp-banner-errore" rounded dense>
          {{ quoteErrore }}
        </q-banner>
      </q-card-section>
      <q-card-actions align="right">
        <q-btn v-close-popup flat label="Annulla" />
        <q-btn
          color="primary"
          label="Salva assetto"
          :loading="quoteSaving"
          @click="salvaAssetto"
        />
      </q-card-actions>
    </q-card>
  </q-dialog>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue';
import { useQuasar } from 'quasar';
import { messaggioErrore } from 'src/utils/apiErrors';
import { usePropertiesStore, type Membro, type Quota } from 'stores/properties';

const props = defineProps<{
  propertyId: number;
  membri: Membro[];
  quote: Quota[];
  sonoProprietario: boolean;
}>();

const emit = defineEmits<{
  (e: 'aggiornate', quote: Quota[]): void;
}>();

const $q = useQuasar();
const propStore = usePropertiesStore();

const dialogQuote = ref(false);
const quoteValidFrom = ref(new Date().toISOString().slice(0, 10));
const quoteForm = ref<Array<{ user: number; nominativo: string; percento: string }>>([]);
const quoteSaving = ref(false);
const quoteErrore = ref('');

const quoteCorrenti = computed(() => props.quote.filter((q) => q.valid_to === null));
const totalePercento = computed(() =>
  quoteForm.value.reduce((tot, r) => tot + (Number(r.percento) || 0), 0),
);

function percentuale(quota: string): string {
  return `${(Number(quota) * 100).toFixed(2).replace(/\.00$/, '')}%`;
}

function apriDialogQuote() {
  quoteErrore.value = '';
  const proprietari = props.membri.filter((m) => m.ruolo === 'proprietario');
  const attive = new Map(quoteCorrenti.value.map((q) => [q.owner_nominativo, q.quota]));
  quoteForm.value = proprietari.map((m) => ({
    user: m.user,
    nominativo: m.nominativo,
    percento: attive.has(m.nominativo)
      ? String(Number(attive.get(m.nominativo)) * 100)
      : '',
  }));
  dialogQuote.value = true;
}

async function salvaAssetto() {
  quoteErrore.value = '';
  if (Math.abs(totalePercento.value - 100) > 0.1) {
    quoteErrore.value = `La somma è ${totalePercento.value.toFixed(2)}%: deve fare 100%.`;
    return;
  }
  quoteSaving.value = true;
  try {
    await propStore.salvaQuote(props.propertyId, {
      valid_from: quoteValidFrom.value,
      quote: quoteForm.value
        .filter((r) => Number(r.percento) > 0)
        .map((r) => ({
          user: r.user,
          quota: (Number(r.percento) / 100).toFixed(4),
        })),
    });
    dialogQuote.value = false;
    emit('aggiornate', await propStore.caricaQuote(props.propertyId));
    $q.notify({ type: 'positive', message: 'Assetto quote salvato.' });
  } catch (e: unknown) {
    quoteErrore.value = messaggioErrore(e, 'Salvataggio quote non riuscito.');
  } finally {
    quoteSaving.value = false;
  }
}
</script>

<style scoped>
.vp-section-title {
  font-weight: 600;
  font-size: 16px;
  color: var(--vp-ink-1);
}
.vp-hint {
  color: var(--vp-ink-3);
  font-size: 13px;
}
.vp-banner-errore {
  background: var(--vp-clay-soft, #fbeae5);
  color: var(--vp-clay-deep, #8c3b21);
}
</style>
