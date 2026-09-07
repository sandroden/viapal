<template>
  <q-dialog v-model="aperto" :maximized="$q.screen.lt.sm" @before-show="carica">
    <q-card style="width: 100%; max-width: 520px" class="vp-lmd">
      <q-card-section class="vp-lmd__testa">
        <div class="vp-eyebrow">Cerca inquilini</div>
        <div class="text-subtitle1">
          {{ lead ? `Modifica ${lead.author_name || 'contatto'}` : 'Nuovo contatto' }}
        </div>
      </q-card-section>

      <q-card-section class="vp-lmd__campi">
        <q-select
          v-model="form.canale"
          :options="CANALI"
          option-value="value"
          option-label="label"
          emit-value
          map-options
          options-dense
          dense
          outlined
          label="Da dove arriva"
          data-testid="lead-canale"
        >
          <template #prepend>
            <q-icon :name="iconaCanale" />
          </template>
          <template #option="{ itemProps, opt }">
            <q-item v-bind="itemProps">
              <q-item-section avatar>
                <q-icon :name="opt.icona" size="20px" />
              </q-item-section>
              <q-item-section>{{ opt.label }}</q-item-section>
            </q-item>
          </template>
        </q-select>

        <q-input
          v-model="form.author_name"
          dense
          outlined
          autofocus
          label="Nome"
          :error="tentato && !form.author_name.trim()"
          error-message="Il nome serve per riconoscerlo in lista"
          data-testid="lead-nome"
          @keydown.ctrl.enter.prevent="salva"
          @keydown.meta.enter.prevent="salva"
        />

        <q-input
          v-model="form.contatto"
          dense
          outlined
          label="Contatto"
          hint="Telefono, email o nick sulla piattaforma"
          hide-hint
          @keydown.ctrl.enter.prevent="salva"
          @keydown.meta.enter.prevent="salva"
        />

        <q-input
          v-model="form.author_url"
          dense
          outlined
          type="url"
          label="Link (profilo o annuncio)"
          @keydown.ctrl.enter.prevent="salva"
          @keydown.meta.enter.prevent="salva"
        />

        <div class="vp-lmd__riga">
          <q-input
            v-model="form.zona"
            dense
            outlined
            label="Zona"
            @keydown.ctrl.enter.prevent="salva"
            @keydown.meta.enter.prevent="salva"
          />
          <q-input
            v-model.number="form.budget_max"
            dense
            outlined
            type="number"
            inputmode="numeric"
            label="Budget max"
            suffix="€"
            class="vp-lmd__budget"
            @keydown.ctrl.enter.prevent="salva"
            @keydown.meta.enter.prevent="salva"
          />
        </div>

        <q-input
          v-model="form.disponibile_da"
          dense
          outlined
          label="Disponibile da"
          placeholder="subito, 1 ottobre, metà mese…"
          @keydown.ctrl.enter.prevent="salva"
          @keydown.meta.enter.prevent="salva"
        />

        <q-input
          v-model="form.testo"
          type="textarea"
          dense
          outlined
          autogrow
          label="Cosa cerca / messaggio"
          @keydown.ctrl.enter.prevent="salva"
          @keydown.meta.enter.prevent="salva"
        />

        <q-input
          v-model="form.note"
          type="textarea"
          dense
          outlined
          autogrow
          label="Note"
          @keydown.ctrl.enter.prevent="salva"
          @keydown.meta.enter.prevent="salva"
        />

        <!-- Lo stato di partenza si sceglie solo alla creazione: chi
             inserisce un contatto a cui ha già scritto non deve poi aprire
             la card per dirlo. In modifica lo stato ha la sua select. -->
        <q-select
          v-if="!lead"
          v-model="form.stato"
          :options="opzioniStato"
          emit-value
          map-options
          options-dense
          dense
          outlined
          label="Stato"
        />

        <q-banner v-if="errore" class="bg-red-1 text-negative" rounded dense>
          {{ errore }}
        </q-banner>
        <div class="vp-lmd__scorciatoia">Ctrl-Invio per salvare</div>
      </q-card-section>

      <q-card-actions class="vp-lmd__azioni">
        <q-btn
          v-if="lead"
          flat
          no-caps
          color="negative"
          icon="delete_outline"
          label="Elimina"
          :disable="salvataggio"
          @click="chiediElimina"
        />
        <q-space />
        <q-btn flat no-caps label="Annulla" :disable="salvataggio" v-close-popup />
        <q-btn
          unelevated
          no-caps
          color="primary"
          :label="lead ? 'Salva' : 'Aggiungi'"
          :loading="salvataggio"
          data-testid="lead-salva"
          @click="salva"
        />
      </q-card-actions>
    </q-card>
  </q-dialog>
</template>

<script setup lang="ts">
import { computed, reactive, ref } from 'vue';
import { Dialog, Notify, useQuasar } from 'quasar';
import { messaggioErrore } from 'src/utils/apiErrors';
import {
  CANALI,
  STATI,
  useLeadsStore,
  type CanaleLead,
  type DatiLeadManuale,
  type Lead,
  type StatoLead,
} from 'src/stores/leads';

const props = defineProps<{
  /** Assente = creazione; presente = modifica di quel lead (dev'essere
   *  manuale: il server rifiuta i campi descrittivi sui lead del bot). */
  lead?: Lead | null;
}>();
const aperto = defineModel<boolean>({ required: true });
const emit = defineEmits<{
  (e: 'salvato', lead: Lead): void;
  (e: 'eliminato', lead: Lead): void;
}>();

const $q = useQuasar();
const store = useLeadsStore();

interface Form {
  canale: CanaleLead;
  author_name: string;
  contatto: string;
  author_url: string;
  zona: string;
  budget_max: number | null;
  disponibile_da: string;
  testo: string;
  note: string;
  stato: StatoLead;
}

const form = reactive<Form>({
  canale: 'fb_post',
  author_name: '',
  contatto: '',
  author_url: '',
  zona: '',
  budget_max: null,
  disponibile_da: '',
  testo: '',
  note: '',
  stato: 'nuovo',
});
const tentato = ref(false);
const salvataggio = ref(false);
const errore = ref<string | null>(null);

const opzioniStato = STATI.map((s) => ({ value: s.value, label: s.label }));

const iconaCanale = computed(
  () => CANALI.find((c) => c.value === form.canale)?.icona ?? 'more_horiz',
);

/** Il form si riempie all'apertura, non alla creazione del componente: lo
 *  stesso dialog serve prima per un lead e poi per un altro. */
function carica() {
  const l = props.lead;
  form.canale = l?.canale ?? 'fb_post';
  form.author_name = l?.author_name ?? '';
  form.contatto = l?.contatto ?? '';
  form.author_url = l?.author_url ?? '';
  form.zona = l?.analisi?.zona ?? '';
  const budget = Number(l?.analisi?.budget_max);
  form.budget_max = l && Number.isFinite(budget) && budget > 0 ? budget : null;
  form.disponibile_da = l?.analisi?.disponibile_da ?? '';
  form.testo = l?.testo ?? '';
  form.note = l?.note ?? '';
  form.stato = 'nuovo';
  tentato.value = false;
  errore.value = null;
}

function dati(): DatiLeadManuale {
  const d: DatiLeadManuale = {
    canale: form.canale,
    author_name: form.author_name.trim(),
    contatto: form.contatto.trim(),
    author_url: form.author_url.trim(),
    testo: form.testo.trim(),
    note: form.note,
    analisi: {
      zona: form.zona.trim() || null,
      budget_max: form.budget_max || null,
      disponibile_da: form.disponibile_da.trim() || null,
    },
  };
  if (!props.lead) d.stato = form.stato;
  return d;
}

async function salva() {
  tentato.value = true;
  if (!form.author_name.trim() || salvataggio.value) return;
  salvataggio.value = true;
  errore.value = null;
  try {
    const salvato = props.lead
      ? await store.modifica(props.lead, dati())
      : await store.crea(dati());
    emit('salvato', salvato);
    aperto.value = false;
  } catch (e: unknown) {
    errore.value = messaggioErrore(e, 'Non è stato possibile salvare');
  } finally {
    salvataggio.value = false;
  }
}

function chiediElimina() {
  const lead = props.lead;
  if (!lead) return;
  Dialog.create({
    title: 'Eliminare il contatto?',
    message: `${lead.author_name || 'Questo contatto'} sparisce dall'elenco, note comprese.`,
    ok: { label: 'Elimina', color: 'negative', unelevated: true, noCaps: true },
    cancel: { label: 'Annulla', flat: true, noCaps: true },
  }).onOk(() => {
    void store
      .elimina(lead)
      .then(() => {
        emit('eliminato', lead);
        aperto.value = false;
      })
      .catch((e: unknown) => {
        Notify.create({
          type: 'warning',
          message: messaggioErrore(e, 'Non è stato possibile eliminarlo'),
        });
      });
  });
}
</script>

<style scoped>
.vp-lmd__testa {
  padding-bottom: 4px;
}
.vp-lmd__campi {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.vp-lmd__riga {
  display: flex;
  gap: 10px;
}
.vp-lmd__riga > * {
  flex: 1 1 0;
  min-width: 0;
}
.vp-lmd__budget {
  flex: 0 1 150px;
}
.vp-lmd__scorciatoia {
  font-size: var(--vp-text-xs);
  color: var(--vp-ink-3);
  text-align: right;
}
.vp-lmd__azioni {
  padding: 8px 16px 16px;
}
</style>
