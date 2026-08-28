<template>
  <q-page padding class="vp-lead">
    <header class="vp-lead__head">
      <div>
        <div class="vp-eyebrow">Chi cerca stanza</div>
        <h1 class="vp-display vp-lead__titolo">Cerca inquilini</h1>
      </div>
      <div class="vp-lead__azioni">
        <q-btn
          flat
          dense
          no-caps
          color="primary"
          icon="refresh"
          label="Aggiorna"
          :loading="store.loading"
          @click="ricarica"
        />
        <q-btn flat dense round icon="more_vert" aria-label="Altre azioni">
          <q-menu>
            <q-list style="min-width: 220px">
              <q-item clickable v-close-popup @click="chiediChiusura">
                <q-item-section avatar>
                  <q-icon name="delete_sweep" color="negative" />
                </q-item-section>
                <q-item-section>
                  <q-item-label>Chiudi la campagna</q-item-label>
                  <q-item-label caption>Cancella tutti i contatti</q-item-label>
                </q-item-section>
              </q-item>
            </q-list>
          </q-menu>
        </q-btn>
      </div>
    </header>

    <!-- Filtri: sono anche il conto di come sta andando la campagna. -->
    <div class="vp-lead__filtri">
      <!-- Su telefono i cinque stati non ci stanno in riga: scorrono, invece
           di andare a capo spezzando le etichette. -->
      <div class="vp-lead__filtri-scroll">
        <q-btn-toggle
          v-model="filtroStato"
          :options="opzioniStato"
          no-caps
          unelevated
          dense
          toggle-color="primary"
          data-testid="filtro-stato"
        />
      </div>
      <q-toggle v-model="soloMiei" label="Solo i miei" dense />
      <q-space />
      <span class="vp-lead__conteggio">{{ leadVisibili.length }} in elenco</span>
    </div>

    <q-banner v-if="store.errore" class="bg-red-1 text-negative q-mb-md" rounded>
      {{ store.errore }}
    </q-banner>

    <div v-if="store.loading && !store.leads.length" class="vp-lead__vuoto">
      <q-spinner-dots size="32px" color="primary" />
    </div>

    <div v-else-if="!leadVisibili.length" class="vp-lead__vuoto">
      <q-icon name="search" size="42px" color="grey-5" />
      <p v-if="!store.riepilogo?.totale">
        Nessun contatto ancora. Li porta qui il bot mentre gira sui gruppi.
      </p>
      <p v-else>Nessun contatto con questo filtro.</p>
    </div>

    <div v-else class="vp-lead__lista">
      <article
        v-for="lead in leadVisibili"
        :key="lead.id"
        class="vp-card vp-lead__card"
        :class="[
          `vp-lead__card--st-${lead.stato}`,
          { 'vp-lead__card--mio': mio(lead), 'vp-lead__card--altrui': altrui(lead) },
        ]"
        :data-stato="lead.stato"
        data-testid="lead-card"
      >
        <div class="vp-lead__riga1">
          <div class="vp-lead__chi">
            <!-- In mezzo a decine di annunci la faccia è quello che si
                 ricorda: il nome, spesso, no. -->
            <LeadFotina
              :foto="lead.foto"
              :nome="lead.author_name"
              @cambia="(f: string) => cambiaFoto(lead, f)"
            />
            <span class="vp-lead__nome">{{ lead.author_name || 'Anonimo' }}</span>
            <!-- Il "da contattare" non porta badge: la card pulita è quella
                 ancora da lavorare, e il colore segnala solo ciò che è stato
                 fatto. -->
            <span
              v-if="lead.stato !== 'nuovo'"
              class="vp-badge vp-lead__badge"
              :class="`vp-lead__badge--${lead.stato}`"
              data-testid="lead-stato"
            >
              <q-icon :name="statoIcona(lead.stato)" size="14px" />
              {{ lead.stato_display }}
            </span>
            <!-- Chi ci sta scrivendo è l'informazione che evita il doppio
                 messaggio: sta in testa, non in fondo alla card. -->
            <span
              v-if="lead.preso_da"
              class="vp-badge vp-lead__preso"
              :class="mio(lead) ? 'vp-lead__preso--io' : 'vp-lead__preso--altrui'"
              data-testid="lead-preso"
            >
              <q-icon name="person" size="14px" />
              {{ mio(lead) ? 'lo contatti tu' : lead.preso_da_nome }}
            </span>
          </div>
          <span class="vp-lead__quando">{{ quando(lead.seen_at) }}</span>
        </div>

        <div class="vp-lead__fatti">
          <span v-if="lead.analisi?.zona"><q-icon name="place" size="16px" />{{ lead.analisi.zona }}</span>
          <span v-if="lead.analisi?.budget_max">
            <q-icon name="euro" size="16px" />max {{ lead.analisi.budget_max }}
          </span>
          <span v-if="lead.analisi?.disponibile_da">
            <q-icon name="event" size="16px" />{{ lead.analisi.disponibile_da }}
          </span>
          <span v-if="lead.analisi?.stanze_compatibili?.length" class="vp-lead__stanze">
            <q-icon name="bed" size="16px" />{{ lead.analisi.stanze_compatibili.join(', ') }}
          </span>
          <span v-if="mostraGruppo && lead.group_label" class="vp-lead__gruppo">
            <q-icon name="groups" size="16px" />{{ lead.group_label }}
          </span>
        </div>

        <p v-if="lead.analisi?.motivo" class="vp-lead__motivo">{{ lead.analisi.motivo }}</p>

        <p class="vp-lead__testo" :class="{ 'vp-lead__testo--aperto': aperti.has(lead.id) }">
          {{ lead.testo }}
        </p>
        <button
          v-if="lead.testo.length > 220"
          class="vp-lead__piu"
          @click="alterna(lead.id)"
        >
          {{ aperti.has(lead.id) ? 'meno' : 'tutto il post' }}
        </button>

        <div class="vp-lead__bottoni">
          <q-btn
            v-if="lead.link_messenger"
            unelevated
            dense
            no-caps
            color="primary"
            icon="chat"
            label="Messenger"
            class="vp-lead__vai"
            :href="lead.link_messenger"
            target="_blank"
          />
          <q-btn
            v-if="lead.permalink"
            outline
            dense
            no-caps
            color="primary"
            icon="open_in_new"
            label="Il post"
            class="vp-lead__vai"
            :href="lead.permalink"
            target="_blank"
          />
          <q-btn
            v-if="lead.commento_proposto"
            flat
            dense
            no-caps
            size="sm"
            icon="content_copy"
            label="commento"
            @click="copia(lead.commento_proposto, 'Commento copiato')"
          />
          <q-btn
            v-if="lead.privato_proposto"
            flat
            dense
            no-caps
            size="sm"
            icon="content_copy"
            label="privato"
            @click="copia(lead.privato_proposto, 'Messaggio copiato')"
          />
        </div>

        <!-- La nota è scritta a mano ed è l'unica cosa che il bot non sa:
             va letta scorrendo la lista. Nel tooltip non esisteva, perché su
             telefono non c'è il passaggio del dito sopra. -->
        <button v-if="lead.note" class="vp-lead__nota" @click="apriNote(lead)">
          <q-icon name="sticky_note_2" size="15px" />
          <span class="vp-lead__nota-testo" data-testid="lead-nota">{{ lead.note }}</span>
        </button>

        <div class="vp-lead__piede">
          <q-btn
            v-if="!lead.preso_da"
            unelevated
            dense
            no-caps
            color="secondary"
            icon="pan_tool_alt"
            label="Lo contatto io"
            @click="prendi(lead)"
          />
          <q-btn
            v-else-if="mio(lead)"
            flat
            dense
            no-caps
            size="sm"
            icon="undo"
            label="lascia ad altri"
            @click="rilascia(lead)"
          />

          <q-space />

          <q-select
            :model-value="lead.stato"
            :options="opzioniStatoSelect"
            dense
            outlined
            emit-value
            map-options
            options-dense
            class="vp-lead__stato"
            @update:model-value="(s: StatoLead) => cambiaStato(lead, s)"
          />
          <q-btn
            flat
            dense
            round
            :icon="lead.note ? 'edit_note' : 'sticky_note_2'"
            :aria-label="lead.note ? 'Modifica la nota' : 'Aggiungi una nota'"
            @click="apriNote(lead)"
          >
            <q-tooltip>{{ lead.note ? 'Modifica la nota' : 'Aggiungi una nota' }}</q-tooltip>
          </q-btn>
        </div>
      </article>
    </div>

    <!-- Note: sono il posto dove finisce ciò che il bot non sa (ha risposto
         al telefono, viene a vedere giovedì…). -->
    <q-dialog v-model="noteAperte">
      <q-card style="min-width: 320px; max-width: 460px">
        <q-card-section>
          <div class="text-subtitle1">Note su {{ leadNote?.author_name }}</div>
        </q-card-section>
        <q-card-section>
          <q-input
            v-model="testoNote"
            type="textarea"
            outlined
            autogrow
            autofocus
            placeholder="Ha risposto, viene a vedere giovedì…"
          />
        </q-card-section>
        <q-card-actions align="right">
          <q-btn flat no-caps label="Annulla" v-close-popup />
          <q-btn unelevated no-caps color="primary" label="Salva" @click="salvaNote" />
        </q-card-actions>
      </q-card>
    </q-dialog>
  </q-page>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue';
import { Dialog, Notify } from 'quasar';
import { useLeadsStore, STATI, type Lead, type StatoLead } from 'src/stores/leads';
import LeadFotina from 'components/leads/LeadFotina.vue';
import { useAuthStore } from 'src/stores/auth';

const store = useLeadsStore();
const auth = useAuthStore();

const filtroStato = ref<string>('nuovo');
const soloMiei = ref(false);
const aperti = ref(new Set<number>());

// "Tutti" è una stringa vuota: il backend accetta stato assente come
// "nessun filtro", e i conteggi arrivano dal riepilogo.
const opzioniStato = computed(() => [
  { value: '', label: etichettaConto('Tutti', store.riepilogo?.totale) },
  ...STATI.map((s) => ({
    value: s.value,
    label: etichettaConto(s.label, store.riepilogo?.per_stato?.[s.value]),
  })),
]);

const opzioniStatoSelect = STATI.map((s) => ({ value: s.value, label: s.label }));

const ICONE = Object.fromEntries(STATI.map((s) => [s.value, s.icona])) as Record<
  StatoLead,
  string
>;
const ETICHETTE = Object.fromEntries(STATI.map((s) => [s.value, s.label])) as Record<
  StatoLead,
  string
>;

function statoIcona(stato: StatoLead): string {
  return ICONE[stato] ?? 'help';
}

function etichettaConto(testo: string, n?: number): string {
  return n ? `${testo} (${n})` : testo;
}

/** Il gruppo si mostra solo se ce n'è più d'uno: con un gruppo solo sarebbe
 *  rumore ripetuto su ogni card. */
const mostraGruppo = computed(() => (store.riepilogo?.gruppi.length ?? 0) > 1);

const leadVisibili = computed(() => {
  if (!soloMiei.value) return store.leads;
  return store.leads.filter((l) => l.preso_da === auth.user?.id);
});

function mio(lead: Lead): boolean {
  return !!lead.preso_da && lead.preso_da === auth.user?.id;
}

function altrui(lead: Lead): boolean {
  return !!lead.preso_da && lead.preso_da !== auth.user?.id;
}

function quando(iso: string): string {
  const minuti = Math.round((Date.now() - new Date(iso).getTime()) / 60000);
  if (minuti < 60) return `${Math.max(minuti, 1)} min fa`;
  if (minuti < 60 * 24) return `${Math.round(minuti / 60)} h fa`;
  return new Date(iso).toLocaleDateString('it-IT', { day: 'numeric', month: 'short' });
}

function alterna(id: number) {
  const s = new Set(aperti.value);
  if (!s.delete(id)) s.add(id);
  aperti.value = s;
}

async function copia(testo: string, messaggio: string) {
  try {
    await navigator.clipboard.writeText(testo);
    Notify.create({ type: 'positive', message: messaggio, icon: 'check' });
  } catch {
    Notify.create({ type: 'warning', message: 'Copia non riuscita' });
  }
}

async function ricarica() {
  await Promise.all([
    store.fetch(filtroStato.value ? { stato: filtroStato.value } : {}),
    store.fetchRiepilogo(),
  ]);
}

watch(filtroStato, ricarica);
onMounted(ricarica);

async function prendi(lead: Lead) {
  const esito = await store.prendi(lead);
  if (!esito.ok) {
    Notify.create({ type: 'warning', message: esito.messaggio ?? '', icon: 'group' });
  }
}

async function rilascia(lead: Lead) {
  const esito = await store.rilascia(lead);
  if (!esito.ok) Notify.create({ type: 'warning', message: esito.messaggio ?? '' });
}

async function cambiaStato(lead: Lead, stato: StatoLead) {
  await store.cambiaStato(lead, stato);
  await store.fetchRiepilogo();
  // Con un filtro attivo, il lead appena cambiato non appartiene più
  // all'elenco che si sta guardando: si toglie da solo. Sparire e basta però
  // sembra un errore: si dice dov'è andato, e si offre di andarci.
  if (filtroStato.value && filtroStato.value !== stato) {
    store.leads = store.leads.filter((l) => l.id !== lead.id);
    Notify.create({
      type: 'positive',
      icon: statoIcona(stato),
      message: `${lead.author_name || 'Contatto'}: ${ETICHETTE[stato]}`,
      actions: [
        { label: 'vedi', color: 'white', handler: () => (filtroStato.value = stato) },
      ],
    });
  }
}

async function cambiaFoto(lead: Lead, foto: string) {
  const esito = await store.salvaFoto(lead, foto);
  if (!esito.ok) Notify.create({ type: 'warning', message: esito.messaggio ?? '' });
}

// --- note ---------------------------------------------------------------
const noteAperte = ref(false);
const leadNote = ref<Lead | null>(null);
const testoNote = ref('');

function apriNote(lead: Lead) {
  leadNote.value = lead;
  testoNote.value = lead.note;
  noteAperte.value = true;
}

async function salvaNote() {
  if (leadNote.value) await store.salvaNote(leadNote.value, testoNote.value);
  noteAperte.value = false;
}

// --- chiusura campagna --------------------------------------------------
function chiediChiusura() {
  Dialog.create({
    title: 'Chiudere la campagna?',
    message:
      `Cancella tutti i ${store.riepilogo?.totale ?? 0} contatti raccolti, ` +
      'note e presa in carico comprese. Sono dati di altre persone e non ' +
      'vanno tenuti oltre il necessario: è la stessa pulizia che si fa sul ' +
      'portatile del bot. Non si torna indietro.',
    ok: { label: 'Cancella tutto', color: 'negative', unelevated: true, noCaps: true },
    cancel: { label: 'Annulla', flat: true, noCaps: true },
  }).onOk(() => {
    void store.chiudiCampagna().then((n) => {
      Notify.create({ type: 'positive', message: `Cancellati ${n} contatti.` });
    });
  });
}
</script>

<style scoped>
.vp-lead__head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 20px;
}
.vp-lead__titolo {
  font-size: var(--vp-text-3xl);
  margin: 2px 0 0;
}
.vp-lead__azioni {
  display: flex;
  align-items: center;
  gap: 4px;
}

.vp-lead__filtri {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 10px 16px;
  margin-bottom: 18px;
}
.vp-lead__filtri-scroll {
  overflow-x: auto;
  max-width: 100%;
  scrollbar-width: none;
}
.vp-lead__filtri-scroll::-webkit-scrollbar {
  display: none;
}
.vp-lead__filtri-scroll :deep(.q-btn-group) {
  flex-wrap: nowrap;
  width: max-content;
}
.vp-lead__filtri-scroll :deep(.q-btn) {
  white-space: nowrap;
}

.vp-lead__conteggio {
  font-size: var(--vp-text-sm);
  color: var(--vp-ink-3);
  padding-right: 4px;
  white-space: nowrap;
}

.vp-lead__vai {
  padding-left: 12px;
  padding-right: 12px;
}

.vp-lead__lista {
  display: grid;
  gap: 14px;
  grid-template-columns: 1fr;
}
@media (min-width: 1100px) {
  .vp-lead__lista {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

.vp-lead__card {
  padding: 16px;
  transition: background 0.2s;
}

/* Due segnali che non si pestano i piedi: la fascia sul bordo dice *chi* ci
   lavora, il fondo della card dice *a che punto è*. Se si contendessero lo
   stesso canale, l'ultimo scritto cancellerebbe l'altro. */
.vp-lead__card--mio {
  border-left: 3px solid var(--vp-sage);
}
.vp-lead__card--altrui {
  border-left: 3px solid var(--vp-ink-4);
}

/* "Da contattare" non ha colore: la card pulita è il lavoro che resta. */
.vp-lead__card--st-contattato {
  background: var(--vp-status-declared-bg);
}
.vp-lead__card--st-risposto {
  background: var(--vp-status-ok-bg);
}
.vp-lead__card--st-scartato {
  background: var(--vp-paper-2);
  opacity: 0.6;
}
.vp-lead__card--st-scartato .vp-lead__nome {
  text-decoration: line-through;
  text-decoration-color: var(--vp-ink-4);
}

.vp-lead__badge {
  flex-shrink: 0;
}

.vp-lead__badge--contattato {
  background: var(--vp-cream);
  color: var(--vp-status-declared-fg);
}
.vp-lead__badge--risposto {
  background: var(--vp-cream);
  color: var(--vp-status-ok-fg);
}
.vp-lead__badge--scartato {
  background: var(--vp-paper-3);
  color: var(--vp-ink-2);
}

/* La nota è un foglietto attaccato sopra: si vede senza aprire nulla, e
   toccandolo si modifica. */
.vp-lead__nota {
  display: flex;
  align-items: flex-start;
  gap: 6px;
  width: 100%;
  margin-top: 12px;
  padding: 8px 10px;
  border: 0;
  border-left: 3px solid var(--vp-honey);
  border-radius: var(--vp-r-sm);
  background: var(--vp-honey-soft);
  color: var(--vp-ink-2);
  font-family: inherit;
  font-size: var(--vp-text-sm);
  line-height: 1.45;
  text-align: left;
  cursor: pointer;
}
.vp-lead__nota .q-icon {
  margin-top: 2px;
  flex-shrink: 0;
}
.vp-lead__nota-testo {
  display: -webkit-box;
  -webkit-line-clamp: 3;
  line-clamp: 3;
  -webkit-box-orient: vertical;
  overflow: hidden;
  white-space: pre-wrap;
}

.vp-lead__riga1 {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
}
.vp-lead__chi {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 6px 8px;
  min-width: 0;
}
.vp-lead__nome {
  font-family: var(--vp-font-display);
  font-size: var(--vp-text-lg);
  color: var(--vp-ink);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.vp-lead__quando {
  font-size: var(--vp-text-xs);
  color: var(--vp-ink-3);
  white-space: nowrap;
}

.vp-lead__fatti {
  display: flex;
  flex-wrap: wrap;
  gap: 4px 14px;
  margin: 10px 0 0;
  font-size: var(--vp-text-sm);
  color: var(--vp-ink-2);
}
.vp-lead__fatti span {
  display: inline-flex;
  align-items: center;
  gap: 4px;
}
.vp-lead__stanze {
  color: var(--vp-terra-deep);
  font-weight: 500;
}
.vp-lead__gruppo {
  color: var(--vp-ink-3);
}

.vp-lead__motivo {
  margin: 8px 0 0;
  font-size: var(--vp-text-sm);
  font-style: italic;
  color: var(--vp-ink-3);
}

.vp-lead__testo {
  margin: 10px 0 0;
  font-size: var(--vp-text-sm);
  line-height: 1.5;
  color: var(--vp-ink-2);
  display: -webkit-box;
  -webkit-line-clamp: 3;
  line-clamp: 3;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
.vp-lead__testo--aperto {
  -webkit-line-clamp: unset;
  line-clamp: unset;
  overflow: visible;
}
.vp-lead__piu {
  background: none;
  border: 0;
  padding: 2px 0;
  font-size: var(--vp-text-xs);
  color: var(--vp-terra);
  cursor: pointer;
}

.vp-lead__bottoni {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 14px;
}

.vp-lead__piede {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 14px;
  padding-top: 12px;
  border-top: 1px solid var(--vp-paper-3);
}
.vp-lead__preso {
  flex-shrink: 0;
}
.vp-lead__preso--io {
  background: var(--vp-sage-soft);
  color: var(--vp-sage-deep);
}
.vp-lead__preso--altrui {
  background: var(--vp-paper-3);
  color: var(--vp-ink-2);
}
.vp-lead__stato {
  min-width: 148px;
}

.vp-lead__vuoto {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 10px;
  padding: 48px 0;
  color: var(--vp-ink-3);
  text-align: center;
}
</style>
