<template>
  <q-dialog v-model="aperto" @hide="onHide">
    <q-card class="vp-bt-led">
      <q-card-section class="row items-center q-pb-none">
        <div>
          <div class="vp-eyebrow">Movimento inter-owner</div>
          <div class="vp-display vp-bt-led__titolo">
            BT {{ formattaData(bt.data) }} —
            <span class="vp-mono">{{ formattaEuro(bt.importo) }}</span>
          </div>
        </div>
        <q-space />
        <q-btn icon="close" flat round dense v-close-popup />
      </q-card-section>

      <q-card-section class="vp-bt-led__sub">
        <div class="vp-bt-led__descr">{{ bt.descrizione }}</div>
        <div v-if="bt.is_inter_owner" class="vp-bt-led__chip-on">
          già marcata
        </div>
      </q-card-section>

      <q-card-section class="vp-bt-led__conto">
        <q-icon name="account_balance" size="18px" />
        <span>
          Conto di <strong>{{ bt.owner_nominativo }}</strong>
          <span class="vp-bt-led__conto-banca"> — {{ bt.conto_banca }}</span>
        </span>
      </q-card-section>

      <q-separator />

      <q-card-section v-if="bt.is_inter_owner">
        <p class="vp-bt-led__avviso">
          Questa transazione è già marcata come inter-owner.
          Disfa la marcatura per riportarla nella lista da riconciliare.
        </p>
      </q-card-section>

      <q-card-section v-else class="vp-bt-led__form">
        <q-radio
          v-for="opt in tipiOpzioni"
          :key="opt.value"
          v-model="form.tipo"
          :val="opt.value"
          :label="opt.label"
          dense
        >
          <template #default>
            <span class="vp-bt-led__opt">
              <strong>{{ opt.label }}</strong>
              <span class="vp-bt-led__opt-help">{{ opt.help }}</span>
            </span>
          </template>
        </q-radio>

        <q-select
          v-if="richiedeControparte"
          v-model="form.controparte_owner"
          :options="opzioniControparte"
          option-label="nominativo"
          option-value="id"
          emit-value
          map-options
          dense
          outlined
          :label="etichettaControparte"
          class="vp-bt-led__select"
        />

        <q-select
          v-model="form.settlement"
          :options="opzioniSettlement"
          option-label="label"
          option-value="id"
          emit-value
          map-options
          clearable
          dense
          outlined
          :label="etichettaCampoSettlement"
          class="vp-bt-led__select"
        >
          <template #hint>
            <span class="vp-bt-led__hint">{{ hintSettlement }}</span>
          </template>
        </q-select>

        <q-input
          v-model="form.descrizione"
          dense
          outlined
          label="Descrizione (opzionale)"
          class="vp-bt-led__input"
        />

        <q-input
          v-model="form.note"
          dense
          outlined
          type="textarea"
          autogrow
          label="Note"
          class="vp-bt-led__input"
        />

        <q-banner v-if="errore" dense class="vp-bt-led__error">
          <template #avatar>
            <q-icon name="error" color="negative" />
          </template>
          {{ errore }}
        </q-banner>
      </q-card-section>

      <q-card-actions align="right">
        <q-btn flat no-caps color="grey-8" label="Chiudi" v-close-popup />
        <q-btn
          v-if="bt.is_inter_owner"
          unelevated
          no-caps
          color="negative"
          icon="link_off"
          label="Disfa marcatura"
          :loading="salvando"
          @click="onDisfa"
        />
        <q-btn
          v-else
          unelevated
          no-caps
          color="primary"
          icon="save"
          label="Marca"
          :loading="salvando"
          :disable="!salvabile"
          @click="onSalva"
        />
      </q-card-actions>
    </q-card>
  </q-dialog>
</template>

<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue';
import { Notify } from 'quasar';
import {
  useRiconciliazioneStore,
  type BankTransactionFE,
  type TipoInterOwner,
} from 'stores/riconciliazione';
import { useOwnersStore } from 'stores/owners';
import { useSaldiFratelliStore } from 'stores/saldiFratelli';
import { useFormatoEuro } from 'src/composables/useFormatoEuro';
import { useFormatoData } from 'src/composables/useFormatoData';

const props = defineProps<{
  modelValue: boolean;
  bt: BankTransactionFE;
}>();

const emit = defineEmits<{
  (e: 'update:modelValue', v: boolean): void;
  (e: 'changed'): void;
}>();

const aperto = computed({
  get: () => props.modelValue,
  set: (v) => emit('update:modelValue', v),
});

const ownersStore = useOwnersStore();
const ricStore = useRiconciliazioneStore();
const saldiStore = useSaldiFratelliStore();
const { formattaEuro } = useFormatoEuro();
const { formattaData } = useFormatoData();

interface FormState {
  tipo: TipoInterOwner;
  controparte_owner: number | null;
  settlement: number | null;
  descrizione: string;
  note: string;
}

const form = reactive<FormState>({
  tipo: 'incasso_conguaglio',
  controparte_owner: null,
  settlement: null,
  descrizione: '',
  note: '',
});
const salvando = ref(false);
const errore = ref<string | null>(null);

const tipiOpzioni: { value: TipoInterOwner; label: string; help: string }[] = [
  {
    value: 'incasso_conguaglio',
    label: 'Conguaglio settlement',
    help: 'Liquidazione della chiusura annuale tra i fratelli.',
  },
  {
    value: 'distribuzione',
    label: 'Distribuzione utili',
    help: 'Movimento periodico di distribuzione degli utili.',
  },
  {
    value: 'bilaterale',
    label: 'Bilaterale (privato)',
    help: 'Prestito o restituzione che NON passa dalla cassa virtuale.',
  },
  {
    value: 'aggiustamento',
    label: 'Aggiustamento manuale',
    help: 'Voce libera senza controparte (uso eccezionale).',
  },
];

const richiedeControparte = computed(
  () => form.tipo !== 'aggiustamento',
);

// Esclude il proprietario del conto della BT: la controparte è un altro fratello.
const opzioniControparte = computed(() =>
  ownersStore.owners.filter((o) => o.id !== ownerDelConto.value),
);

const etichettaControparte = computed(() => {
  const owner = props.bt.owner_nominativo;
  return owner
    ? `Controparte (l'altro fratello, oltre a ${owner})`
    : "Controparte (l'altro fratello)";
});

const opzioniSettlement = computed(() =>
  saldiStore.settlements.map((s) => ({
    id: s.id,
    label: `${s.descrizione} (${s.periodo_da} → ${s.periodo_a})`,
  })),
);

const etichettaCampoSettlement = computed(() =>
  form.tipo === 'bilaterale'
    ? 'Settlement di competenza (consigliato per BT cross-anno)'
    : 'Settlement collegato (opzionale)',
);

const hintSettlement = computed(() =>
  form.tipo === 'bilaterale'
    ? 'Es. BT del 2026 ma di competenza chiusura 2025.'
    : 'Lascia vuoto a meno che la BT chiuda proprio quel settlement.',
);

const ownerDelConto = computed<number | null>(() => props.bt.owner_id ?? null);

const salvabile = computed(() => {
  if (richiedeControparte.value && form.controparte_owner == null) return false;
  return true;
});

watch(
  () => props.modelValue,
  async (v) => {
    if (v) {
      await Promise.all([
        ownersStore.fetchOwners(),
        saldiStore.fetchSettlements(),
      ]);
      errore.value = null;
      if (!props.bt.is_inter_owner) {
        form.tipo = 'incasso_conguaglio';
        form.controparte_owner = null;
        form.settlement = null;
        form.descrizione = '';
        form.note = '';
      }
    }
  },
  { immediate: true },
);

async function onSalva() {
  salvando.value = true;
  errore.value = null;
  try {
    await ricStore.marcaInterOwner({
      bank_transaction: props.bt.id,
      tipo: form.tipo,
      controparte_owner: form.controparte_owner,
      settlement: form.settlement,
      descrizione: form.descrizione,
      note: form.note,
    });
    Notify.create({
      type: 'positive',
      icon: 'check_circle',
      message: 'BT marcata come inter-owner.',
    });
    emit('changed');
    aperto.value = false;
  } catch (e: unknown) {
    const detail =
      (e as { response?: { data?: { detail?: string } } })?.response?.data
        ?.detail ?? 'Salvataggio non riuscito';
    errore.value = detail;
  } finally {
    salvando.value = false;
  }
}

async function onDisfa() {
  salvando.value = true;
  errore.value = null;
  try {
    await ricStore.disfaInterOwner(props.bt.id);
    Notify.create({ type: 'positive', message: 'Marcatura rimossa.' });
    emit('changed');
    aperto.value = false;
  } catch (e: unknown) {
    const detail =
      (e as { response?: { data?: { detail?: string } } })?.response?.data
        ?.detail ?? 'Operazione non riuscita';
    errore.value = detail;
  } finally {
    salvando.value = false;
  }
}

function onHide() {
  errore.value = null;
}
</script>

<style scoped>
.vp-bt-led {
  background: var(--vp-cream);
  min-width: min(480px, 92vw);
  max-width: 560px;
}
.vp-bt-led__titolo {
  font-size: var(--vp-text-xl);
  margin-top: 2px;
}
.vp-bt-led__sub {
  display: flex;
  justify-content: space-between;
  gap: var(--vp-gap-2);
  align-items: flex-start;
  color: var(--vp-ink-2);
}
.vp-bt-led__descr {
  flex: 1 1 auto;
  font-size: 0.9rem;
  white-space: pre-wrap;
}
.vp-bt-led__chip-on {
  flex: 0 0 auto;
  padding: 2px 10px;
  border-radius: var(--vp-r-sm);
  background: var(--vp-terra-soft);
  color: var(--vp-terra-deep);
  font-size: 0.7rem;
  text-transform: uppercase;
  letter-spacing: 0.05em;
}
.vp-bt-led__conto {
  display: flex;
  align-items: center;
  gap: var(--vp-gap-1, 6px);
  padding-top: 0;
  padding-bottom: var(--vp-gap-2);
  color: var(--vp-ink-2);
  font-size: 0.85rem;
}
.vp-bt-led__conto-banca {
  color: var(--vp-ink-3, var(--vp-ink-2));
}
.vp-bt-led__form {
  display: flex;
  flex-direction: column;
  gap: var(--vp-gap-3);
}
.vp-bt-led__opt {
  display: flex;
  flex-direction: column;
}
.vp-bt-led__opt-help {
  color: var(--vp-ink-2);
  font-size: 0.78rem;
}
.vp-bt-led__select,
.vp-bt-led__input {
  background: var(--vp-paper-2);
}
.vp-bt-led__hint {
  color: var(--vp-ink-2);
  font-size: 0.75rem;
}
.vp-bt-led__avviso {
  color: var(--vp-ink-2);
  margin: 0;
}
.vp-bt-led__error {
  background: var(--vp-argilla-chiaro, #f3d9c8);
  color: var(--vp-ink);
}
.vp-mono {
  font-variant-numeric: tabular-nums;
}
</style>
