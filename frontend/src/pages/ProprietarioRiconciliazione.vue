<template>
  <q-page padding class="vp-p-rec">
    <header class="vp-p-rec__head">
      <div>
        <div class="vp-eyebrow">Bonifici ↔ addebiti</div>
        <h1 class="vp-display vp-p-rec__titolo">Riconciliazione</h1>
        <p class="vp-p-rec__sub">
          Seleziona una transazione (Ctrl-click per aggiungerne altre, ad es.
          per pagamenti spezzati), poi gli addebiti che essa copre. Salva
          quando il residuo è a zero (o accetta sopra/sotto-allocazione).
        </p>
      </div>
      <q-btn
        flat
        color="primary"
        icon="refresh"
        :loading="store.loadingBts || store.loadingReceivables"
        no-caps
        label="Ricarica"
        @click="ricarica"
      />
    </header>

    <section class="vp-p-rec__filtri">
      <div class="vp-p-rec__filtro-gruppo">
        <span class="vp-eyebrow">Stato BT</span>
        <q-btn-toggle
          v-model="filtroRiconciliato"
          no-caps
          unelevated
          dense
          :options="opzioniRiconciliato"
          color="paper-3"
          text-color="ink"
          toggle-color="primary"
          toggle-text-color="white"
          class="vp-p-rec__toggle"
        />
      </div>
      <div class="vp-p-rec__filtro-gruppo">
        <span class="vp-eyebrow">Causale</span>
        <q-btn-toggle
          v-model="filtroCausale"
          no-caps
          unelevated
          dense
          :options="opzioniCausale"
          color="paper-3"
          text-color="ink"
          toggle-color="primary"
          toggle-text-color="white"
          class="vp-p-rec__toggle"
        />
      </div>
      <q-input
        v-model="filtroDataDa"
        dense
        outlined
        type="date"
        label="Da"
        class="vp-p-rec__date"
      />
      <q-input
        v-model="filtroDataA"
        dense
        outlined
        type="date"
        label="A"
        class="vp-p-rec__date"
      />
      <q-select
        v-model="filtroTenant"
        dense
        outlined
        clearable
        emit-value
        map-options
        :options="tenantsOpzioni"
        label="Inquilino"
        class="vp-p-rec__tenant-select"
      />
    </section>
    <section class="vp-p-rec__preset">
      <span class="vp-eyebrow">Periodo rapido</span>
      <q-btn
        flat
        dense
        round
        size="sm"
        icon="chevron_left"
        :disable="!filtroDataDa || !filtroDataA"
        @click="onFrecciaIndietro"
      >
        <q-tooltip>Periodo precedente · Ctrl-click: allarga indietro</q-tooltip>
      </q-btn>
      <q-btn
        flat
        dense
        round
        size="sm"
        icon="chevron_right"
        :disable="!filtroDataDa || !filtroDataA"
        @click="onFrecciaAvanti"
      >
        <q-tooltip>Periodo successivo · Ctrl-click: allarga avanti</q-tooltip>
      </q-btn>
      <q-btn flat dense no-caps size="sm" label="Quest'anno" @click="presetQuestAnno" />
      <q-btn flat dense no-caps size="sm" label="Anno scorso" @click="presetAnnoScorso" />
      <q-btn flat dense no-caps size="sm" label="Ultimo trimestre" @click="presetUltimoTrimestre" />
      <q-btn flat dense no-caps size="sm" label="Ultimi 12 mesi" @click="presetUltimi12Mesi" />
      <q-btn flat dense no-caps size="sm" label="Tutto" @click="presetReset" />
    </section>

    <div class="vp-p-rec__grid">
      <!-- Colonna sinistra: BankTransaction -->
      <q-card flat bordered class="vp-p-rec__col">
        <q-card-section class="vp-p-rec__col-head">
          <div class="vp-eyebrow">Transazioni bancarie</div>
          <div class="vp-p-rec__col-meta">
            {{ store.bts.length }} risultati
            <span v-if="btSelezionate.size > 0" class="vp-p-rec__badge">
              {{ btSelezionate.size }} selezionate
            </span>
          </div>
        </q-card-section>
        <q-separator />
        <q-banner
          v-if="btFuoriFiltro.length > 0"
          dense
          class="vp-p-rec__banner-fuori"
        >
          <template #avatar>
            <q-icon name="info" color="warning" />
          </template>
          {{ btFuoriFiltro.length }} transazion{{ btFuoriFiltro.length === 1 ? 'e selezionata non è' : 'i selezionate non sono' }}
          in lista (filtri attivi).
          Le vedi nel pannello "Allocazioni" qui sotto.
          <template #action>
            <q-btn flat dense no-caps label="Mostra tutte" @click="mostraTutteBt" />
          </template>
        </q-banner>
        <q-list separator class="vp-p-rec__lista">
          <q-item
            v-for="bt in btOrdinate"
            :key="bt.id"
            v-ripple
            clickable
            :active="btSelezionate.has(bt.id)"
            active-class="vp-p-rec__item--active"
            class="vp-p-rec__item"
            @click="(e: Event) => clickBt(bt, e as MouseEvent)"
          >
            <q-item-section>
              <q-item-label class="vp-p-rec__bt-row">
                <span class="vp-p-rec__bt-data">{{ formattaData(bt.data) }}</span>
                <span class="vp-mono vp-p-rec__bt-importo">
                  {{ formattaEuro(bt.importo) }}
                </span>
              </q-item-label>
              <q-item-label caption lines="2">{{ bt.descrizione }}</q-item-label>
              <q-item-label caption class="vp-p-rec__bt-meta">
                <span
                  class="vp-p-rec__chip"
                  :class="`vp-p-rec__chip--${bt.stato_riconciliazione}`"
                >
                  {{ etichettaStato(bt.stato_riconciliazione) }}
                </span>
                <span v-if="Number(bt.residuo) > 0" class="vp-mono">
                  residuo: {{ formattaEuro(bt.residuo) }}
                </span>
              </q-item-label>
            </q-item-section>
          </q-item>
          <q-item v-if="store.bts.length === 0 && !store.loadingBts">
            <q-item-section class="text-grey-7">
              Nessuna transazione coi filtri attivi.
            </q-item-section>
          </q-item>
        </q-list>
      </q-card>

      <!-- Colonna destra: Receivable -->
      <q-card flat bordered class="vp-p-rec__col">
        <q-card-section class="vp-p-rec__col-head">
          <div>
            <div class="vp-eyebrow">Addebiti</div>
            <div class="vp-p-rec__col-meta">
              <template v-if="tenantInferito">
                Inquilino: <strong>{{ tenantInferito.nominativo }}</strong>
              </template>
              <template v-else-if="btSelezionate.size > 0">
                Nessun inquilino dedotto — seleziona dal filtro o forza tutti
              </template>
              <template v-else>
                Clicca un addebito per vedere chi lo paga, oppure seleziona prima una transazione
              </template>
            </div>
          </div>
          <q-toggle
            v-model="mostraTuttiInquilini"
            label="Mostra tutti"
            dense
            color="primary"
          />
        </q-card-section>
        <q-separator />
        <q-list separator class="vp-p-rec__lista">
          <q-item
            v-for="r in receivablesVisibili"
            :key="r.id"
            v-ripple
            clickable
            :active="receivableSelezionati.has(r.id)"
            active-class="vp-p-rec__item--active"
            class="vp-p-rec__item"
            @click="toggleReceivable(r)"
          >
            <q-item-section avatar>
              <q-checkbox
                :model-value="receivableSelezionati.has(r.id)"
                dense
                @click.stop="toggleReceivable(r)"
              />
            </q-item-section>
            <q-item-section>
              <q-item-label class="vp-p-rec__bt-row">
                <span class="vp-p-rec__rec-titolo">
                  <span
                    class="vp-p-rec__chip vp-p-rec__chip--causale"
                    :class="`vp-p-rec__chip--c-${r.causale}`"
                  >
                    {{ etichettaCausale(r.causale) }}
                  </span>
                  {{ r.descrizione_estesa }}
                </span>
                <span class="vp-mono vp-p-rec__bt-importo">
                  {{ formattaEuro(r.importo_dovuto) }}
                </span>
              </q-item-label>
              <q-item-label caption>
                {{ r.tenant_nominativo }} —
                scadenza {{ formattaData(r.scadenza) }}
              </q-item-label>
              <q-item-label caption class="vp-p-rec__rec-coperto">
                <span
                  class="vp-mono"
                  :class="coperturaClass(r)"
                >
                  coperto {{ formattaEuro(r.importo_allocato) }} /
                  {{ formattaEuro(r.importo_dovuto) }}
                </span>
                <span v-if="Number(r.residuo) > 0.005" class="vp-mono text-negative">
                  · residuo {{ formattaEuro(r.residuo) }}
                </span>
              </q-item-label>
            </q-item-section>
          </q-item>
          <q-item
            v-if="receivablesVisibili.length === 0 && !store.loadingReceivables"
          >
            <q-item-section class="text-grey-7">
              Nessun addebito da abbinare.
            </q-item-section>
          </q-item>
        </q-list>
      </q-card>
    </div>

    <!-- Pannello allocazioni -->
    <q-card
      v-if="pannelloVisibile"
      flat
      bordered
      class="vp-p-rec__pannello"
    >
      <q-card-section class="vp-p-rec__pannello-head">
        <div class="vp-eyebrow">Allocazioni</div>
        <div class="vp-p-rec__pannello-actions">
          <q-btn
            flat
            no-caps
            color="negative"
            icon="close"
            label="Annulla"
            @click="annulla"
          />
          <q-btn
            unelevated
            no-caps
            color="primary"
            icon="save"
            :label="etichettaSalva"
            :loading="store.saving"
            :disable="!salvaAbilitato"
            @click="salva"
          />
        </div>
      </q-card-section>
      <q-separator />
      <q-banner
        v-if="allocazioni.length === 0"
        dense
        class="vp-p-rec__banner-vuoto"
      >
        <template #avatar>
          <q-icon name="warning" color="negative" />
        </template>
        Nessuna allocazione: salvando, le abbinature esistenti delle BT
        selezionate verranno <strong>cancellate</strong>.
      </q-banner>
      <q-markup-table v-else flat dense class="vp-p-rec__tabella">
        <thead>
          <tr>
            <th class="text-left">Transazione</th>
            <th class="text-left">Addebito</th>
            <th class="text-right">Dovuto</th>
            <th class="text-right">Importo da allocare</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="a in allocazioni" :key="`${a.bt_id}-${a.rec_id}`">
            <td>
              <span class="vp-mono">{{ formattaData(a.bt_data) }}</span>
              <br />
              <span class="vp-mono text-grey-7">
                {{ formattaEuro(a.bt_importo) }}
              </span>
            </td>
            <td>
              {{ a.rec_descrizione }}
              <br />
              <small class="text-grey-7">{{ a.rec_tenant }}</small>
            </td>
            <td class="text-right vp-mono">{{ formattaEuro(a.rec_dovuto) }}</td>
            <td class="text-right">
              <q-input
                v-model.number="a.importo"
                dense
                outlined
                type="number"
                step="0.01"
                input-class="text-right vp-mono"
                style="max-width: 130px; display: inline-block"
              />
            </td>
            <td class="text-right">
              <q-btn
                flat
                dense
                round
                icon="delete"
                color="negative"
                @click="rimuoviAllocazione(a)"
              />
            </td>
          </tr>
        </tbody>
        <tfoot>
          <tr v-for="r in riepilogoBt" :key="`bt-${r.bt_id}`">
            <td colspan="3" class="text-right text-bold">
              Allocato BT {{ formattaData(r.bt_data) }}:
            </td>
            <td class="text-right vp-mono text-bold">
              {{ formattaEuro(r.allocato) }} / {{ formattaEuro(r.importo) }}
            </td>
            <td
              class="text-right vp-mono text-bold"
              :class="{
                'text-negative': r.residuo < -0.01,
                'text-positive': Math.abs(r.residuo) <= 0.01,
              }"
            >
              residuo {{ formattaEuro(r.residuo) }}
            </td>
          </tr>
        </tfoot>
      </q-markup-table>
    </q-card>
  </q-page>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue';
import { Notify } from 'quasar';
import { useRiconciliazioneStore, type BankTransactionFE, type ReceivableFE } from 'stores/riconciliazione';
import { useTenantsStore } from 'stores/tenants';
import { useFormatoEuro } from 'src/composables/useFormatoEuro';
import { useFormatoData } from 'src/composables/useFormatoData';

interface Allocazione {
  bt_id: number;
  bt_data: string;
  bt_importo: number;
  rec_id: number;
  rec_descrizione: string;
  rec_tenant: string;
  rec_dovuto: number;
  importo: number;
}

const store = useRiconciliazioneStore();
const tenantsStore = useTenantsStore();
const { formattaEuro } = useFormatoEuro();
const { formattaData } = useFormatoData();

const filtroRiconciliato = ref<'all' | 'true' | 'false'>('false');
const filtroDataDa = ref<string | null>(null);
const filtroDataA = ref<string | null>(null);
const filtroTenant = ref<number | null>(null);
const filtroCausale = ref<'all' | 'affitto' | 'utenze' | 'extra'>('all');
const mostraTuttiInquilini = ref(false);

const opzioniRiconciliato = [
  { label: 'Da abbinare', value: 'false' },
  { label: 'Tutti', value: 'all' },
  { label: 'Abbinati', value: 'true' },
];

const opzioniCausale = [
  { label: 'Tutte', value: 'all' },
  { label: 'Affitto', value: 'affitto' },
  { label: 'Utenze', value: 'utenze' },
  { label: 'Extra', value: 'extra' },
];

function pad2(n: number): string {
  return n < 10 ? `0${n}` : `${n}`;
}
function isoDate(d: Date): string {
  return `${d.getFullYear()}-${pad2(d.getMonth() + 1)}-${pad2(d.getDate())}`;
}
function presetQuestAnno() {
  const oggi = new Date();
  filtroDataDa.value = `${oggi.getFullYear()}-01-01`;
  filtroDataA.value = `${oggi.getFullYear()}-12-31`;
}
function presetAnnoScorso() {
  const oggi = new Date();
  filtroDataDa.value = `${oggi.getFullYear() - 1}-01-01`;
  filtroDataA.value = `${oggi.getFullYear() - 1}-12-31`;
}
function presetUltimoTrimestre() {
  const oggi = new Date();
  const inizio = new Date(oggi);
  inizio.setMonth(inizio.getMonth() - 3);
  filtroDataDa.value = isoDate(inizio);
  filtroDataA.value = isoDate(oggi);
}
function presetUltimi12Mesi() {
  const oggi = new Date();
  const inizio = new Date(oggi);
  inizio.setFullYear(inizio.getFullYear() - 1);
  filtroDataDa.value = isoDate(inizio);
  filtroDataA.value = isoDate(oggi);
}
function presetReset() {
  filtroDataDa.value = null;
  filtroDataA.value = null;
}
function aggiungiGiorni(iso: string, giorni: number): string {
  const d = new Date(iso);
  d.setDate(d.getDate() + giorni);
  return isoDate(d);
}
function navigaPeriodo(direzione: -1 | 1, allarga: boolean) {
  if (!filtroDataDa.value || !filtroDataA.value) return;
  const da = new Date(filtroDataDa.value);
  const a = new Date(filtroDataA.value);
  const span = Math.round((a.getTime() - da.getTime()) / 86400000) + 1;
  if (allarga) {
    if (direzione === -1) {
      filtroDataDa.value = aggiungiGiorni(filtroDataDa.value, -span);
    } else {
      filtroDataA.value = aggiungiGiorni(filtroDataA.value, span);
    }
  } else {
    filtroDataDa.value = aggiungiGiorni(filtroDataDa.value, span * direzione);
    filtroDataA.value = aggiungiGiorni(filtroDataA.value, span * direzione);
  }
}
function onFrecciaIndietro(e: Event) {
  const m = e as MouseEvent;
  navigaPeriodo(-1, m.ctrlKey || m.metaKey);
}
function onFrecciaAvanti(e: Event) {
  const m = e as MouseEvent;
  navigaPeriodo(1, m.ctrlKey || m.metaKey);
}
function mostraTutteBt() {
  filtroRiconciliato.value = 'all';
}

const tenantsOpzioni = computed(() =>
  tenantsStore.tenants.map((t) => ({ label: t.nominativo, value: t.id })),
);

// Selezione: una o più BT, e per ognuna gli addebiti abbinati.
// btSelezionate = unione di btEsplicite (cliccate dall'utente a sinistra)
//                 + le BT auto-caricate dal click su un Receivable (flusso simmetrico).
// Il "modo creazione abbinamento" è attivo quando btEsplicite ha almeno un elemento.
const btSelezionate = reactive<Set<number>>(new Set());
const btEsplicite = reactive<Set<number>>(new Set());
const receivableSelezionati = reactive<Set<number>>(new Set());
const allocazioni = ref<Allocazione[]>([]);

const btOrdinate = computed<BankTransactionFE[]>(() =>
  [...store.bts].sort((a, b) => (a.data < b.data ? 1 : -1)),
);

// Inquilino dedotto: priorità (1) allocations esistenti, (2) match
// testuale sul nominativo nella descrizione del bonifico (es. "Bon. da Rossi").
function inquilinoDaDescrizione(descr: string) {
  const lower = descr.toLowerCase();
  for (const t of tenantsStore.tenants) {
    const tokens = t.nominativo
      .split(/\s+/)
      .filter((tok) => tok.length >= 3);
    if (tokens.some((tok) => lower.includes(tok.toLowerCase()))) {
      return t;
    }
  }
  return null;
}

const tenantInferito = computed(() => {
  if (mostraTuttiInquilini.value) return null;
  if (filtroTenant.value) {
    return tenantsStore.tenants.find((t) => t.id === filtroTenant.value) ?? null;
  }
  for (const id of btSelezionate) {
    const bt = store.bts.find((b) => b.id === id);
    if (!bt) continue;
    const alloc = bt.allocations[0];
    if (alloc) {
      const r = store.receivables.find((rr) => rr.id === alloc.receivable);
      if (r) {
        const t = tenantsStore.tenants.find((tt) => tt.id === r.tenant_id);
        if (t) return t;
      }
    }
    const dalTesto = inquilinoDaDescrizione(bt.descrizione);
    if (dalTesto) return dalTesto;
  }
  return null;
});

const receivablesVisibili = computed<ReceivableFE[]>(() => {
  // Quando una BT è selezionata e ha allocations già esistenti, i recv coperti
  // devono essere SEMPRE visibili, anche se non rispettano filtri causale/tenant
  // (l'utente vuole vedere/correggere le componenti dell'abbinamento esistente).
  const recIdsCoinvolti = new Set(allocazioni.value.map((a) => a.rec_id));
  function bypass(r: ReceivableFE): boolean {
    return recIdsCoinvolti.has(r.id);
  }

  let lista = store.receivables;
  // Filtro tenant
  if (!mostraTuttiInquilini.value) {
    if (tenantInferito.value) {
      lista = lista.filter((r) => bypass(r) || r.tenant_id === tenantInferito.value!.id);
    } else if (filtroTenant.value) {
      lista = lista.filter((r) => bypass(r) || r.tenant_id === filtroTenant.value);
    }
  }
  // Filtro causale
  if (filtroCausale.value !== 'all') {
    lista = lista.filter((r) => bypass(r) || r.causale === filtroCausale.value);
  }
  return lista;
});

const btFuoriFiltro = computed(() =>
  Array.from(btSelezionate).filter((id) => !store.bts.some((b) => b.id === id)),
);

const riepilogoBt = computed(() =>
  Array.from(btSelezionate).map((bt_id) => {
    const bt = store.bts.find((b) => b.id === bt_id);
    // Fallback: la BT potrebbe non essere in store.bts perché filtrata
    // (es. abbinata, mentre il filtro è su "da abbinare"); recupero data/importo
    // dalle allocations già caricate (vedi caricaAllocazioniDaReceivable).
    const fromAlloc = allocazioni.value.find((a) => a.bt_id === bt_id);
    const importo = Number(bt?.importo ?? fromAlloc?.bt_importo ?? 0);
    const data = bt?.data ?? fromAlloc?.bt_data ?? '';
    const allocato = allocazioni.value
      .filter((a) => a.bt_id === bt_id)
      .reduce((s, a) => s + (Number.isFinite(a.importo) ? a.importo : 0), 0);
    return {
      bt_id,
      bt_data: data,
      importo,
      allocato,
      residuo: importo - allocato,
    };
  }),
);

const pannelloVisibile = computed(
  () => allocazioni.value.length > 0 || btEsplicite.size > 0,
);

const etichettaSalva = computed(() =>
  allocazioni.value.length === 0 && btEsplicite.size > 0
    ? 'Cancella abbinamenti'
    : 'Salva',
);

const salvaAbilitato = computed(() => {
  // Caso "scollega": nessuna allocazione, ma BT esplicitamente selezionate →
  // salvataggio cancella le allocations esistenti sul backend.
  if (allocazioni.value.length === 0) return btEsplicite.size > 0;
  // Tutte le BT selezionate non devono essere sovra-allocate.
  return riepilogoBt.value.every((r) => r.residuo >= -0.01)
    && allocazioni.value.every((a) => a.importo > 0);
});

function caricaAllocazioniEsistenti(bt: BankTransactionFE) {
  for (const alloc of bt.allocations) {
    if (allocazioni.value.some((a) => a.bt_id === bt.id && a.rec_id === alloc.receivable)) {
      continue;
    }
    const rec = store.receivables.find((r) => r.id === alloc.receivable);
    allocazioni.value.push({
      bt_id: bt.id,
      bt_data: bt.data,
      bt_importo: Number(bt.importo),
      rec_id: alloc.receivable,
      rec_descrizione: rec?.descrizione_estesa ?? alloc.receivable_descrizione,
      rec_tenant: rec?.tenant_nominativo ?? '',
      rec_dovuto: Number(rec?.importo_dovuto ?? 0),
      importo: Number(alloc.importo),
    });
    receivableSelezionati.add(alloc.receivable);
  }
}

function clickBt(bt: BankTransactionFE, e: MouseEvent) {
  const additivo = e.ctrlKey || e.metaKey;
  if (additivo) {
    // Ctrl/Cmd+Click: toggle nella selezione multipla.
    if (btEsplicite.has(bt.id)) {
      btEsplicite.delete(bt.id);
      btSelezionate.delete(bt.id);
      const recIdsRimossi = allocazioni.value
        .filter((a) => a.bt_id === bt.id)
        .map((a) => a.rec_id);
      allocazioni.value = allocazioni.value.filter((a) => a.bt_id !== bt.id);
      for (const rid of recIdsRimossi) {
        if (!allocazioni.value.some((x) => x.rec_id === rid)) {
          receivableSelezionati.delete(rid);
        }
      }
    } else {
      btSelezionate.add(bt.id);
      btEsplicite.add(bt.id);
      caricaAllocazioniEsistenti(bt);
    }
    return;
  }
  // Click semplice: sostituisce la selezione corrente.
  if (btEsplicite.size === 1 && btEsplicite.has(bt.id)) {
    // Riclick sull'unica BT esplicita: deseleziona tutto.
    btSelezionate.clear();
    btEsplicite.clear();
    allocazioni.value = [];
    receivableSelezionati.clear();
    return;
  }
  btSelezionate.clear();
  btEsplicite.clear();
  allocazioni.value = [];
  receivableSelezionati.clear();
  btSelezionate.add(bt.id);
  btEsplicite.add(bt.id);
  caricaAllocazioniEsistenti(bt);
}

function caricaAllocazioniDaReceivable(r: ReceivableFE) {
  // Popola il pannello con le allocazioni esistenti del receivable.
  // Auto-seleziona le BT che lo coprono (anche se non sono in store.bts
  // perché filtrate fuori dalla lista a sinistra: il pannello in basso le mostra).
  for (const alloc of r.allocations) {
    if (allocazioni.value.some((a) => a.bt_id === alloc.bank_transaction && a.rec_id === r.id)) {
      continue;
    }
    allocazioni.value.push({
      bt_id: alloc.bank_transaction,
      bt_data: alloc.bt_data,
      bt_importo: Number(alloc.bt_importo),
      rec_id: r.id,
      rec_descrizione: r.descrizione_estesa,
      rec_tenant: r.tenant_nominativo,
      rec_dovuto: Number(r.importo_dovuto),
      importo: Number(alloc.importo),
    });
    btSelezionate.add(alloc.bank_transaction);
  }
  receivableSelezionati.add(r.id);
}

function toggleReceivable(r: ReceivableFE) {
  // Caso A: l'utente NON ha cliccato esplicitamente alcuna BT → modalità
  // "vedere chi paga il receivable". Click su un altro recv = sostituisce.
  if (btEsplicite.size === 0) {
    if (receivableSelezionati.has(r.id)) {
      // Riclick: deseleziona e svuota il pannello.
      receivableSelezionati.delete(r.id);
      allocazioni.value = allocazioni.value.filter((a) => a.rec_id !== r.id);
      pulisciBtAuto();
      return;
    }
    // Click su un nuovo recv: rimpiazza il contesto attuale.
    allocazioni.value = [];
    receivableSelezionati.clear();
    btSelezionate.clear();
    if (r.allocations.length === 0) {
      Notify.create({
        type: 'info',
        message: 'Questo addebito non ha pagamenti. Seleziona una transazione per abbinarlo.',
      });
      return;
    }
    caricaAllocazioniDaReceivable(r);
    return;
  }
  // Caso B: BT esplicita già selezionata → flusso di creazione/modifica abbinamento.
  if (receivableSelezionati.has(r.id)) {
    receivableSelezionati.delete(r.id);
    allocazioni.value = allocazioni.value.filter((a) => a.rec_id !== r.id);
    pulisciBtAuto();
  } else {
    aggiungiAllocazione(r);
  }
}

function aggiungiAllocazione(r: ReceivableFE) {
  // Sceglie la BT selezionata col residuo maggiore.
  const candidate = riepilogoBt.value
    .filter((b) => b.residuo > 0.005)
    .sort((a, b) => b.residuo - a.residuo);
  const target = candidate[0];
  if (!target) {
    Notify.create({
      type: 'warning',
      message: 'Le BT selezionate sono già completamente allocate.',
    });
    return;
  }
  const dovuto = Number(r.importo_dovuto);
  const allocato = Number(r.importo_allocato);
  const residuoRec = Math.max(dovuto - allocato, 0);
  const importo = Math.min(target.residuo, residuoRec || target.residuo);
  const bt = store.bts.find((b) => b.id === target.bt_id)!;
  allocazioni.value.push({
    bt_id: target.bt_id,
    bt_data: bt.data,
    bt_importo: Number(bt.importo),
    rec_id: r.id,
    rec_descrizione: r.descrizione_estesa,
    rec_tenant: r.tenant_nominativo,
    rec_dovuto: dovuto,
    importo: Number(importo.toFixed(2)),
  });
  receivableSelezionati.add(r.id);
}

function pulisciBtAuto() {
  // Rimuove dalla btSelezionate le BT che (a) non sono state cliccate
  // esplicitamente dall'utente e (b) non hanno più allocations nel pannello.
  // Le BT esplicite restano selezionate anche con pannello vuoto.
  for (const id of Array.from(btSelezionate)) {
    if (btEsplicite.has(id)) continue;
    if (!allocazioni.value.some((a) => a.bt_id === id)) {
      btSelezionate.delete(id);
    }
  }
}

function rimuoviAllocazione(a: Allocazione) {
  // Rimuovere l'allocazione è una modifica esplicita dell'utente: promuoviamo
  // la BT a "esplicita" (anche se era stata auto-aggiunta dal flusso
  // "vedi chi paga"), così il pannello resta visibile col bottone Salva
  // — altrimenti sparirebbe senza che il backend venga aggiornato.
  btEsplicite.add(a.bt_id);
  btSelezionate.add(a.bt_id);
  allocazioni.value = allocazioni.value.filter(
    (x) => !(x.bt_id === a.bt_id && x.rec_id === a.rec_id),
  );
  // Se il receivable non ha più nessuna allocation, deselezionalo.
  if (!allocazioni.value.some((x) => x.rec_id === a.rec_id)) {
    receivableSelezionati.delete(a.rec_id);
  }
  pulisciBtAuto();
}

function annulla() {
  allocazioni.value = [];
  receivableSelezionati.clear();
  btSelezionate.clear();
  btEsplicite.clear();
}

async function salva() {
  const replace_for_transactions = Array.from(btSelezionate);
  const items = allocazioni.value.map((a) => ({
    bank_transaction: a.bt_id,
    receivable: a.rec_id,
    importo: a.importo.toFixed(2),
  }));
  try {
    await store.saveBulk({ replace_for_transactions, items });
    Notify.create({
      type: 'positive',
      message: 'Riconciliazione salvata.',
      icon: 'check_circle',
    });
    annulla();
    await ricarica();
  } catch (e: unknown) {
    const msg =
      (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail
      || 'Salvataggio non riuscito';
    Notify.create({ type: 'negative', message: msg });
  }
}

function etichettaStato(s: string): string {
  if (s === 'pieno') return 'abbinato';
  if (s === 'parziale') return 'parziale';
  return 'da abbinare';
}

function etichettaCausale(c: string): string {
  if (c === 'affitto') return 'Affitto';
  if (c === 'utenze') return 'Utenze';
  if (c === 'extra') return 'Extra';
  return c;
}

function coperturaClass(r: ReceivableFE): string {
  const allocato = Number(r.importo_allocato) || 0;
  const dovuto = Number(r.importo_dovuto);
  if (allocato + 0.01 >= dovuto) return 'vp-p-rec__cop--pieno';
  if (allocato > 0.005) return 'vp-p-rec__cop--parziale';
  return 'vp-p-rec__cop--vuoto';
}

async function ricarica() {
  await Promise.all([
    store.fetchBankTransactions({
      data_da: filtroDataDa.value,
      data_a: filtroDataA.value,
      riconciliato: filtroRiconciliato.value,
      tenant: filtroTenant.value,
    }),
    store.fetchReceivables({
      tenant: filtroTenant.value,
      riconciliato: 'all',
      data_da: filtroDataDa.value,
      data_a: filtroDataA.value,
    }),
  ]);
}

onMounted(async () => {
  await tenantsStore.fetchTenants(true);
  await ricarica();
});

watch([filtroRiconciliato, filtroDataDa, filtroDataA, filtroTenant], () => {
  void ricarica();
});
</script>

<style scoped>
.vp-p-rec__head {
  display: flex;
  justify-content: space-between;
  align-items: flex-end;
  gap: var(--vp-gap-3);
  flex-wrap: wrap;
  margin-bottom: var(--vp-gap-4);
}
.vp-p-rec__titolo {
  font-size: var(--vp-text-2xl);
  margin: var(--vp-gap-1) 0 0;
}
.vp-p-rec__sub {
  margin: var(--vp-gap-2) 0 0;
  color: var(--vp-ink-2);
  max-width: 60ch;
}
.vp-p-rec__filtri {
  display: flex;
  flex-wrap: wrap;
  gap: var(--vp-gap-3);
  align-items: flex-end;
  margin-bottom: var(--vp-gap-4);
}
.vp-p-rec__filtro-gruppo {
  display: flex;
  align-items: center;
  gap: var(--vp-gap-2);
}
.vp-p-rec__toggle {
  border: 1px solid var(--vp-paper-3);
  border-radius: var(--vp-r-md);
  background: var(--vp-cream);
}
.vp-p-rec__date {
  width: 160px;
}
.vp-p-rec__tenant-select {
  min-width: 220px;
}
.vp-p-rec__grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: var(--vp-gap-4);
  margin-bottom: var(--vp-gap-4);
}
@media (max-width: 900px) {
  .vp-p-rec__grid {
    grid-template-columns: 1fr;
  }
}
.vp-p-rec__col {
  background: var(--vp-cream);
  display: flex;
  flex-direction: column;
  max-height: 60vh;
}
.vp-p-rec__col-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-wrap: wrap;
  gap: var(--vp-gap-2);
}
.vp-p-rec__col-meta {
  color: var(--vp-ink-2);
  font-size: 0.85rem;
}
.vp-p-rec__badge {
  margin-left: var(--vp-gap-2);
  padding: 2px 8px;
  border-radius: var(--vp-r-sm);
  background: var(--vp-terra-soft);
  color: var(--vp-terra-deep);
  font-weight: 500;
}
.vp-p-rec__lista {
  overflow-y: auto;
  flex: 1;
}
.vp-p-rec__item {
  cursor: pointer;
}
.vp-p-rec__item--active {
  background: var(--vp-terra-soft);
}
.vp-p-rec__bt-row {
  display: flex;
  justify-content: space-between;
  gap: var(--vp-gap-2);
}
.vp-p-rec__bt-data {
  font-weight: 500;
}
.vp-p-rec__bt-importo {
  font-weight: 600;
}
.vp-p-rec__bt-meta {
  display: flex;
  gap: var(--vp-gap-2);
  align-items: center;
  flex-wrap: wrap;
  margin-top: var(--vp-gap-1);
}
.vp-p-rec__chip {
  padding: 1px 8px;
  border-radius: var(--vp-r-sm);
  font-size: 0.7rem;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  background: var(--vp-paper-2);
  color: var(--vp-ink-2);
}
.vp-p-rec__chip--vuoto {
  background: var(--vp-argilla-chiaro, #f3d9c8);
  color: var(--vp-ink);
}
.vp-p-rec__chip--parziale {
  background: var(--vp-miele, #f6e1a3);
  color: var(--vp-ink);
}
.vp-p-rec__chip--pieno {
  background: var(--vp-salvia, #c6d6c6);
  color: var(--vp-ink);
}
.vp-p-rec__chip--causale {
  margin-right: var(--vp-gap-1);
  font-weight: 600;
}
.vp-p-rec__chip--c-affitto {
  background: var(--vp-salvia, #c6d6c6);
  color: var(--vp-ink);
}
.vp-p-rec__chip--c-utenze {
  background: var(--vp-miele, #f6e1a3);
  color: var(--vp-ink);
}
.vp-p-rec__chip--c-extra {
  background: var(--vp-terra-soft, #ead0bd);
  color: var(--vp-terra-deep, #6c3a18);
}
.vp-p-rec__rec-titolo {
  display: inline-flex;
  align-items: center;
  gap: var(--vp-gap-1);
}
.vp-p-rec__rec-coperto {
  margin-top: 2px;
  display: flex;
  gap: var(--vp-gap-1);
  align-items: center;
  flex-wrap: wrap;
}
.vp-p-rec__cop--pieno {
  color: var(--vp-salvia-deep, #4f6b4d);
  font-weight: 500;
}
.vp-p-rec__cop--parziale {
  color: var(--vp-miele-deep, #8a6b1f);
  font-weight: 500;
}
.vp-p-rec__cop--vuoto {
  color: var(--vp-ink-2);
}
.vp-p-rec__preset {
  display: flex;
  flex-wrap: wrap;
  gap: var(--vp-gap-1);
  align-items: center;
  margin-bottom: var(--vp-gap-3);
  padding: var(--vp-gap-2);
  background: var(--vp-cream);
  border: 1px solid var(--vp-paper-3);
  border-radius: var(--vp-r-md);
}
.vp-p-rec__banner-fuori {
  background: var(--vp-miele, #f6e1a3);
  color: var(--vp-ink);
  font-size: 0.85rem;
}
.vp-p-rec__banner-vuoto {
  background: var(--vp-argilla-chiaro, #f3d9c8);
  color: var(--vp-ink);
  font-size: 0.85rem;
}
.vp-p-rec__pannello {
  background: var(--vp-cream);
  margin-bottom: var(--vp-gap-4);
}
.vp-p-rec__pannello-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-wrap: wrap;
  gap: var(--vp-gap-2);
}
.vp-p-rec__pannello-actions {
  display: flex;
  gap: var(--vp-gap-2);
}
.vp-p-rec__tabella {
  background: var(--vp-cream);
}
.vp-mono {
  font-variant-numeric: tabular-nums;
}
</style>
