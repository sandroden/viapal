<template>
  <q-page padding class="vp-p-home">
    <header class="vp-p-home__hero">
      <div class="vp-eyebrow">Dashboard rendita</div>
      <h1 class="vp-display vp-p-home__titolo">
        Buon lavoro, {{ saluto }}
      </h1>
      <p class="vp-p-home__sottotitolo">
        Quadro complessivo
        <template v-if="data?.is_storico">
          dell'anno {{ data.anno }} (vista storica).
        </template>
        <template v-else-if="data">
          dell'anno {{ data.anno }}, mese {{ nomeMese(data.mese) }}.
        </template>
      </p>

      <div class="vp-p-home__filtri">
        <q-btn
          flat
          round
          dense
          icon="chevron_left"
          aria-label="Anno precedente"
          @click="cambiaAnno(-1)"
          :disable="!puoIndietro"
        />
        <q-select
          v-model="annoSelezionato"
          :options="anniDisponibili"
          dense
          outlined
          label="Anno"
          class="vp-p-home__sel"
          @update:model-value="onPeriodoChange"
        />
        <q-btn
          flat
          round
          dense
          icon="chevron_right"
          aria-label="Anno successivo"
          @click="cambiaAnno(1)"
          :disable="!puoAvanti"
        />
      </div>
    </header>

    <div v-if="store.loadingProprietario && !data" class="vp-p-home__loader">
      <q-spinner color="primary" size="32px" />
    </div>

    <template v-else-if="data">
      <section class="vp-p-home__kpi">
        <KpiCard
          label="Incasso anno"
          :value="data.kpi.incasso_anno"
          is-currency
          :sublabel="`Mese ${nomeMese(data.mese)}: ${formattaEuro(data.kpi.incasso_mese)}`"
          accent
          info-tooltip="Dettaglio composizione incassi"
        >
          <template #dettaglio>
            <div class="vp-eyebrow">Anno {{ data.anno }} — composizione</div>
            <q-list dense class="vp-p-home__breakdown">
              <q-item>
                <q-item-section>Affitti</q-item-section>
                <q-item-section side class="vp-mono">
                  {{ formattaEuro(data.incasso_anno_dettaglio.rent) }}
                </q-item-section>
              </q-item>
              <q-item>
                <q-item-section>Utenze</q-item-section>
                <q-item-section side class="vp-mono">
                  {{ formattaEuro(data.incasso_anno_dettaglio.utility) }}
                </q-item-section>
              </q-item>
              <q-item>
                <q-item-section>Addebiti extra</q-item-section>
                <q-item-section side class="vp-mono">
                  {{ formattaEuro(data.incasso_anno_dettaglio.extra) }}
                </q-item-section>
              </q-item>
              <q-separator />
              <q-item>
                <q-item-section class="text-bold">Totale</q-item-section>
                <q-item-section side class="vp-mono text-bold">
                  {{ formattaEuro(data.incasso_anno_dettaglio.totale) }}
                </q-item-section>
              </q-item>
            </q-list>

            <div class="vp-eyebrow q-mt-md">Per inquilino</div>
            <q-table
              flat
              dense
              :rows="data.breakdown_incassi"
              :columns="colonneBreakdown"
              row-key="tenant"
              :pagination="{ rowsPerPage: 0 }"
              hide-bottom
              class="vp-p-home__breakdown-table"
            />
          </template>
        </KpiCard>
        <KpiCard
          label="Spese anno"
          :value="data.kpi.spese_anno"
          is-currency
          sublabel="Totale spese registrate"
          info-tooltip="Dettaglio spese per categoria"
        >
          <template #dettaglio>
            <div class="vp-eyebrow">Anno {{ data.anno }} — per categoria</div>
            <q-list dense class="vp-p-home__breakdown">
              <q-item v-for="row in data.spese_anno_dettaglio.per_categoria" :key="row.nome">
                <q-item-section>{{ row.nome }}</q-item-section>
                <q-item-section side class="vp-mono">{{ formattaEuro(row.importo) }}</q-item-section>
              </q-item>
              <q-separator />
              <q-item>
                <q-item-section class="text-bold">Totale</q-item-section>
                <q-item-section side class="vp-mono text-bold">
                  {{ formattaEuro(data.spese_anno_dettaglio.totale) }}
                </q-item-section>
              </q-item>
            </q-list>
            <div class="vp-eyebrow q-mt-md">Anticipate da</div>
            <q-list dense class="vp-p-home__breakdown">
              <q-item v-for="row in data.spese_anno_dettaglio.per_owner" :key="row.nome">
                <q-item-section>{{ row.nome }}</q-item-section>
                <q-item-section side class="vp-mono">{{ formattaEuro(row.importo) }}</q-item-section>
              </q-item>
            </q-list>
          </template>
        </KpiCard>
        <KpiCard
          v-if="!data.is_storico"
          label="Pagamenti in ritardo"
          :value="data.kpi.ritardi_count"
          :sublabel="data.kpi.ritardi_count === 0 ? 'Nessuno' : 'Da sollecitare'"
        />
        <KpiCard
          v-if="!data.is_storico"
          :label="`In scadenza (${data.finestra_scadenza_giorni ?? 14} gg)`"
          :value="data.kpi.in_scadenza_count"
          sublabel="Prossime scadenze"
        />
      </section>

      <section v-if="!data.is_storico" class="vp-p-home__sezione">
        <div class="vp-p-home__sezione-head">
          <div>
            <div class="vp-eyebrow">Ritardi</div>
            <h2 class="vp-display vp-p-home__h2">Pagamenti scaduti</h2>
          </div>
          <q-btn flat color="primary" label="Tutti i ritardi" no-caps to="/p/ritardi" />
        </div>

        <EmptyState
          v-if="data.ritardi.length === 0"
          icon="check_circle"
          title="Nessun ritardo"
          message="Tutti i pagamenti sono in regola."
        />

        <q-list v-else bordered separator class="vp-p-home__lista">
          <q-item v-for="r in data.ritardi.slice(0, 5)" :key="`${r.tipo}-${r.id}`">
            <q-item-section>
              <q-item-label>{{ r.tenant }} · {{ r.descrizione }}</q-item-label>
              <q-item-label caption>
                Scadenza {{ formattaData(r.scadenza) }} · {{ formattaEuro(r.importo) }}
              </q-item-label>
            </q-item-section>
            <q-item-section side>
              <SemaforoBadge
                :livello="livelloDaGiorni(r.giorni_ritardo)"
                :giorni-ritardo="r.giorni_ritardo"
              />
            </q-item-section>
          </q-item>
        </q-list>
      </section>

      <section v-if="!data.is_storico" class="vp-p-home__sezione">
        <div class="vp-p-home__sezione-head">
          <div>
            <div class="vp-eyebrow">In scadenza</div>
            <h2 class="vp-display vp-p-home__h2">
              Prossimi {{ data.finestra_scadenza_giorni ?? 14 }} giorni
            </h2>
          </div>
        </div>

        <EmptyState
          v-if="data.in_scadenza.length === 0"
          icon="schedule"
          title="Nessuna scadenza imminente"
          message="Nei prossimi 7 giorni non ci sono pagamenti attesi."
        />

        <q-list v-else bordered separator class="vp-p-home__lista">
          <q-item v-for="r in data.in_scadenza" :key="`${r.tipo}-${r.id}`">
            <q-item-section>
              <q-item-label>{{ r.tenant }} · {{ r.descrizione }}</q-item-label>
              <q-item-label caption>
                Scadenza {{ formattaData(r.scadenza) }} · {{ formattaEuro(r.importo) }}
              </q-item-label>
            </q-item-section>
            <q-item-section side>
              <SemaforoBadge
                :livello="livelloDaGiorni(r.giorni_ritardo)"
                :giorni-ritardo="r.giorni_ritardo"
              />
            </q-item-section>
          </q-item>
        </q-list>
      </section>

      <section
        v-if="data.bilancio_proprietari?.length"
        class="vp-p-home__sezione"
      >
        <div class="vp-p-home__sezione-head">
          <div>
            <div class="vp-eyebrow">Bilancio proprietari</div>
            <h2 class="vp-display vp-p-home__h2">Entrate vs uscite — anno {{ data.anno }}</h2>
          </div>
        </div>
        <q-table
          flat
          dense
          bordered
          :rows="data.bilancio_proprietari"
          :columns="colonneBilancio"
          row-key="owner_id"
          :pagination="{ rowsPerPage: 0 }"
          hide-bottom
          class="vp-p-home__bilancio"
        >
          <template #body-cell-entrate_totali="props">
            <q-td :props="props" class="text-right">
              <button
                type="button"
                class="vp-p-home__cella-cliccabile vp-mono"
                :disabled="props.row.entrate_totali === 0"
                @click="apriDettaglioEntrate(props.row)"
              >
                {{ formattaEuro(props.row.entrate_totali) }}
              </button>
            </q-td>
          </template>
          <template #body-cell-uscite="props">
            <q-td :props="props" class="text-right">
              <button
                type="button"
                class="vp-p-home__cella-cliccabile vp-mono"
                :disabled="props.row.uscite === 0"
                @click="apriDettaglioUscite(props.row)"
              >
                {{ formattaEuro(props.row.uscite) }}
              </button>
            </q-td>
          </template>
          <template #body-cell-saldo="props">
            <q-td :props="props" class="text-right">
              <span
                class="vp-mono"
                :class="props.row.saldo >= 0 ? 'text-positive' : 'text-negative'"
              >
                {{ formattaEuro(props.row.saldo) }}
              </span>
            </q-td>
          </template>
        </q-table>

        <q-dialog v-model="dettaglioBilancioOpen">
          <q-card class="vp-p-home__dialog">
            <q-card-section class="row items-center q-pb-none">
              <div class="vp-display vp-p-home__dialog-titolo">
                {{ dettaglioBilancioTitolo }}
              </div>
              <q-space />
              <q-btn icon="close" flat round dense v-close-popup />
            </q-card-section>
            <q-card-section>
              <div class="vp-eyebrow">
                {{ dettaglioBilancioOwner?.nominativo }} — anno {{ data.anno }}
              </div>
              <q-list dense class="vp-p-home__breakdown">
                <q-item v-for="row in dettaglioBilancioVoci" :key="row.nome">
                  <q-item-section>{{ row.nome }}</q-item-section>
                  <q-item-section side class="vp-mono">
                    {{ formattaEuro(row.importo) }}
                  </q-item-section>
                </q-item>
                <q-item v-if="dettaglioBilancioVoci.length === 0">
                  <q-item-section class="text-italic">
                    Nessuna voce.
                  </q-item-section>
                </q-item>
                <q-separator />
                <q-item>
                  <q-item-section class="text-bold">Totale</q-item-section>
                  <q-item-section side class="vp-mono text-bold">
                    {{ formattaEuro(dettaglioBilancioTotale) }}
                  </q-item-section>
                </q-item>
              </q-list>
            </q-card-section>
            <q-card-actions
              v-if="dettaglioBilancioOwner"
              align="right"
              class="q-px-md q-pb-md"
            >
              <q-btn
                flat
                color="primary"
                no-caps
                icon-right="arrow_forward"
                label="Vedi tutte le voci"
                :to="{
                  name: 'p-bilancio-dettaglio',
                  params: { ownerId: dettaglioBilancioOwner.owner_id },
                  query: { anno: data.anno, tipo: dettaglioBilancioTipo },
                }"
                @click="dettaglioBilancioOpen = false"
              />
            </q-card-actions>
          </q-card>
        </q-dialog>
      </section>

      <section v-if="data.is_storico" class="vp-p-home__nota-storico">
        <q-banner rounded class="bg-cream">
          <template #avatar>
            <q-icon name="history" color="primary" />
          </template>
          Stai consultando dati storici dell'anno {{ data.anno }}. Le sezioni "Ritardi" e
          "In scadenza" sono attive solo sull'anno corrente.
        </q-banner>
      </section>
    </template>
  </q-page>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue';
import type { QTableProps } from 'quasar';
import { useAuthStore } from 'stores/auth';
import { useDashboardStore, type BilancioProprietario } from 'stores/dashboard';
import KpiCard from 'src/components/KpiCard.vue';
import SemaforoBadge from 'src/components/SemaforoBadge.vue';
import type { SemaforoLivello } from 'src/types/semaforo';
import EmptyState from 'src/components/EmptyState.vue';
import { useFormatoEuro } from 'src/composables/useFormatoEuro';
import { useFormatoData } from 'src/composables/useFormatoData';

const auth = useAuthStore();
const store = useDashboardStore();
const { formattaEuro } = useFormatoEuro();
const { formattaData } = useFormatoData();

const oggi = new Date();
const annoCorrente = oggi.getFullYear();
const meseCorrente = oggi.getMonth() + 1;

const annoSelezionato = ref<number>(annoCorrente);
const meseSelezionato = ref<number>(meseCorrente);

type DettaglioBilancioTipo = 'entrate' | 'uscite';
const dettaglioBilancioOpen = ref(false);
const dettaglioBilancioTipo = ref<DettaglioBilancioTipo>('entrate');
const dettaglioBilancioOwner = ref<BilancioProprietario | null>(null);

const dettaglioBilancioTitolo = computed(() =>
  dettaglioBilancioTipo.value === 'entrate' ? 'Entrate — dettaglio' : 'Uscite — dettaglio',
);

const dettaglioBilancioVoci = computed<{ nome: string; importo: number }[]>(() => {
  const owner = dettaglioBilancioOwner.value;
  if (!owner) return [];
  if (dettaglioBilancioTipo.value === 'entrate') {
    return [
      { nome: 'Affitti', importo: owner.entrate_rent },
      { nome: 'Utenze', importo: owner.entrate_utility },
      { nome: 'Addebiti extra', importo: owner.entrate_extra },
    ].filter((v) => v.importo !== 0);
  }
  return Object.entries(owner.uscite_dettaglio)
    .map(([nome, importo]) => ({ nome, importo }))
    .sort((a, b) => b.importo - a.importo);
});

const dettaglioBilancioTotale = computed(() => {
  const owner = dettaglioBilancioOwner.value;
  if (!owner) return 0;
  return dettaglioBilancioTipo.value === 'entrate' ? owner.entrate_totali : owner.uscite;
});

function apriDettaglioEntrate(owner: BilancioProprietario) {
  if (owner.entrate_totali === 0) return;
  dettaglioBilancioOwner.value = owner;
  dettaglioBilancioTipo.value = 'entrate';
  dettaglioBilancioOpen.value = true;
}

function apriDettaglioUscite(owner: BilancioProprietario) {
  if (owner.uscite === 0) return;
  dettaglioBilancioOwner.value = owner;
  dettaglioBilancioTipo.value = 'uscite';
  dettaglioBilancioOpen.value = true;
}

const ANNO_MIN = annoCorrente - 5;
const ANNO_MAX = annoCorrente;

const anniDisponibili = computed<number[]>(() => {
  const lista: number[] = [];
  for (let a = ANNO_MAX; a >= ANNO_MIN; a -= 1) lista.push(a);
  return lista;
});

const puoIndietro = computed(() => annoSelezionato.value > ANNO_MIN);
const puoAvanti = computed(() => annoSelezionato.value < ANNO_MAX);

const NOMI_MESI = [
  'Gennaio', 'Febbraio', 'Marzo', 'Aprile', 'Maggio', 'Giugno',
  'Luglio', 'Agosto', 'Settembre', 'Ottobre', 'Novembre', 'Dicembre',
];
function nomeMese(m: number): string {
  return NOMI_MESI[m - 1] ?? '';
}

const saluto = computed(() => auth.user?.first_name || auth.user?.username || 'Proprietario');
const data = computed(() => store.proprietarioData);

onMounted(() => {
  void store.loadProprietario(annoSelezionato.value, meseSelezionato.value);
});

function onPeriodoChange() {
  void store.loadProprietario(annoSelezionato.value, meseSelezionato.value);
}

function cambiaAnno(delta: number) {
  const nuovo = annoSelezionato.value + delta;
  if (nuovo < ANNO_MIN || nuovo > ANNO_MAX) return;
  annoSelezionato.value = nuovo;
  onPeriodoChange();
}

function livelloDaGiorni(g: number): SemaforoLivello {
  if (g > 7) return 'argilla_scuro';
  if (g > 0) return 'argilla_chiaro';
  if (g > -7) return 'miele';
  return 'salvia';
}

const colonneBilancio: QTableProps['columns'] = [
  { name: 'nominativo', label: 'Proprietario', field: 'nominativo', align: 'left' },
  {
    name: 'entrate_totali',
    label: 'Entrate',
    field: 'entrate_totali',
    align: 'right',
    format: (v: number) => formattaEuro(v),
  },
  {
    name: 'uscite',
    label: 'Uscite',
    field: 'uscite',
    align: 'right',
    format: (v: number) => formattaEuro(v),
  },
  { name: 'saldo', label: 'Saldo', field: 'saldo', align: 'right' },
];

const colonneBreakdown: QTableProps['columns'] = [
  { name: 'tenant', label: 'Inquilino', field: 'tenant', align: 'left', sortable: true },
  {
    name: 'rent',
    label: 'Affitti',
    field: 'rent',
    align: 'right',
    format: (v: number) => formattaEuro(v),
    sortable: true,
  },
  {
    name: 'utility',
    label: 'Utenze',
    field: 'utility',
    align: 'right',
    format: (v: number) => formattaEuro(v),
    sortable: true,
  },
  {
    name: 'extra',
    label: 'Extra',
    field: 'extra',
    align: 'right',
    format: (v: number) => formattaEuro(v),
    sortable: true,
  },
  {
    name: 'totale',
    label: 'Totale',
    field: 'totale',
    align: 'right',
    format: (v: number) => formattaEuro(v),
    sortable: true,
  },
];
</script>

<style scoped>
.vp-p-home__hero {
  margin-bottom: var(--vp-gap-6);
}
.vp-p-home__titolo {
  font-size: var(--vp-text-3xl);
  margin: var(--vp-gap-2) 0 var(--vp-gap-1);
}
.vp-p-home__sottotitolo {
  color: var(--vp-ink-2);
  margin: 0 0 var(--vp-gap-3);
}
.vp-p-home__filtri {
  display: flex;
  gap: var(--vp-gap-3);
  flex-wrap: wrap;
}
.vp-p-home__sel {
  min-width: 140px;
}
.vp-p-home__kpi {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: var(--vp-gap-4);
  margin-bottom: var(--vp-gap-6);
}
.vp-p-home__sezione {
  margin-bottom: var(--vp-gap-6);
}
.vp-p-home__sezione-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: var(--vp-gap-3);
  gap: var(--vp-gap-3);
}
.vp-p-home__h2 {
  font-size: var(--vp-text-xl);
  margin: 4px 0 0;
}
.vp-p-home__lista {
  background: var(--vp-cream);
  border-radius: var(--vp-r-lg);
  border-color: var(--vp-paper-3) !important;
  overflow: hidden;
}
.vp-p-home__loader {
  display: flex;
  justify-content: center;
  padding: var(--vp-gap-7);
}
.vp-p-home__nota-storico {
  margin-top: var(--vp-gap-4);
}
.vp-p-home__breakdown {
  background: var(--vp-paper-2);
  border-radius: var(--vp-r-md);
}
.vp-p-home__breakdown-table {
  background: var(--vp-cream);
  margin-top: var(--vp-gap-2);
}
.vp-p-home__bilancio {
  background: var(--vp-cream);
}
.text-positive { color: var(--vp-salvia, #4f6e3f); }
.text-negative { color: var(--vp-argilla, #9c4a4a); }
.vp-mono {
  font-variant-numeric: tabular-nums;
}
.vp-p-home__cella-cliccabile {
  background: transparent;
  border: 0;
  padding: 0;
  font: inherit;
  color: var(--vp-terra, #b56a3b);
  text-decoration: underline dotted;
  text-underline-offset: 3px;
  cursor: pointer;
}
.vp-p-home__cella-cliccabile:hover {
  color: var(--vp-ink);
}
.vp-p-home__cella-cliccabile:disabled {
  color: var(--vp-ink-3);
  text-decoration: none;
  cursor: default;
}
.vp-p-home__dialog {
  min-width: min(480px, 92vw);
  max-width: 640px;
  border-radius: var(--vp-r-lg);
  background: var(--vp-cream);
}
.vp-p-home__dialog-titolo {
  font-size: var(--vp-text-xl);
}
</style>
