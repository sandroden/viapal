<template>
  <q-page padding class="vp-saldi">
    <header class="vp-saldi__head">
      <div>
        <div class="vp-eyebrow">Contabilità tra fratelli</div>
        <h1 class="vp-display vp-saldi__titolo">Saldi fratelli</h1>
      </div>
      <div class="vp-saldi__head-azioni">
        <q-input
          v-model="atDate"
          dense
          outlined
          type="date"
          label="Saldi alla data"
          class="vp-saldi__date"
        />
        <q-btn
          flat
          color="primary"
          icon="refresh"
          :loading="store.loading"
          no-caps
          label="Ricarica"
          @click="ricarica"
        />
      </div>
    </header>

    <!-- Sezione 1: saldi live -->
    <section class="vp-saldi__sezione">
      <div class="vp-eyebrow">Saldi live alla data</div>
      <p class="vp-saldi__hint">
        Calcolati al volo: ultimo settlement chiuso + flussi del periodo
        aperto. Non sono persistiti — usali per decidere dove dirottare un
        pagamento o sapere chi vanta crediti.
      </p>
      <div class="vp-saldi__grid">
        <q-card
          v-for="s in store.saldi"
          :key="s.owner.id"
          flat
          bordered
          class="vp-saldi__card"
        >
          <q-card-section>
            <div class="vp-saldi__owner">{{ s.owner.nominativo }}</div>
            <div class="vp-saldi__quota">
              quota {{ formattaQuota(s.quota) }}
            </div>
            <div class="vp-saldi__totale" :class="totaleClass(s.totale)">
              {{ formattaEuro(s.totale) }}
            </div>
          </q-card-section>
          <q-separator />
          <q-list dense class="vp-saldi__decomp">
            <q-expansion-item
              v-if="hasEntries(s.incassi_per_causale)"
              label="Incassi per causale"
              expand-icon-class="vp-saldi__icon"
              dense
            >
              <q-item
                v-for="[k, v] in entriesOrdinate(s.incassi_per_causale)"
                :key="k"
                dense
              >
                <q-item-section>{{ etichettaCausale(k) }}</q-item-section>
                <q-item-section side class="vp-mono" :class="totaleClass(v)">
                  {{ formattaEuro(v) }}
                </q-item-section>
              </q-item>
            </q-expansion-item>
            <q-expansion-item
              v-if="hasEntries(s.spese_per_categoria)"
              label="Spese pro-quota"
              expand-icon-class="vp-saldi__icon"
              dense
            >
              <q-item
                v-for="[k, v] in entriesOrdinate(s.spese_per_categoria)"
                :key="k"
                dense
              >
                <q-item-section>{{ etichettaCategoria(k) }}</q-item-section>
                <q-item-section side class="vp-mono" :class="totaleClass(v)">
                  {{ formattaEuro(v) }}
                </q-item-section>
              </q-item>
            </q-expansion-item>
            <q-item v-if="Number(s.baseline_settlement) !== 0" dense>
              <q-item-section caption>Baseline ultimo settlement</q-item-section>
              <q-item-section side class="vp-mono" :class="totaleClass(s.baseline_settlement)">
                {{ formattaEuro(s.baseline_settlement) }}
              </q-item-section>
            </q-item>
            <q-item v-if="Number(s.anticipi_pendenti) !== 0" dense>
              <q-item-section caption>Anticipi pendenti</q-item-section>
              <q-item-section side class="vp-mono" :class="totaleClass(s.anticipi_pendenti)">
                {{ formattaEuro(s.anticipi_pendenti) }}
              </q-item-section>
            </q-item>
            <q-item v-if="Number(s.bt_inter_owner) !== 0" dense>
              <q-item-section caption>Da BT inter-owner</q-item-section>
              <q-item-section side class="vp-mono" :class="totaleClass(s.bt_inter_owner)">
                {{ formattaEuro(s.bt_inter_owner) }}
              </q-item-section>
            </q-item>
          </q-list>
        </q-card>
        <q-card v-if="store.saldi.length === 0" flat bordered class="vp-saldi__empty">
          <q-card-section>
            Nessun proprietario con quota attiva alla data.
          </q-card-section>
        </q-card>
      </div>
    </section>

    <!-- Sezione 2: settlement chiusi -->
    <section class="vp-saldi__sezione">
      <div class="vp-eyebrow">Settlement chiusi</div>
      <q-list separator bordered class="vp-saldi__lista">
        <q-item
          v-for="set in store.settlements"
          :key="set.id"
          v-ripple
          clickable
          @click="apriSettlement(set)"
        >
          <q-item-section>
            <q-item-label>
              {{ set.descrizione }}
              <span class="text-grey-7">
                ({{ formattaData(set.periodo_da) }} → {{ formattaData(set.periodo_a) }})
              </span>
            </q-item-label>
            <q-item-label caption>
              <span
                v-for="[ownerId, saldo] in Object.entries(set.snapshot)"
                :key="ownerId"
                class="vp-saldi__snap-chip"
              >
                {{ nominativoOwner(Number(ownerId)) }}:
                <span class="vp-mono" :class="totaleClass(saldo)">
                  {{ formattaEuro(saldo) }}
                </span>
              </span>
            </q-item-label>
          </q-item-section>
          <q-item-section side>
            <q-icon name="chevron_right" />
          </q-item-section>
        </q-item>
        <q-item v-if="store.settlements.length === 0">
          <q-item-section class="text-grey-7">
            Nessun settlement chiuso. Lancia
            <code>uv run manage.py genera_settlement --anno YYYY</code>.
          </q-item-section>
        </q-item>
      </q-list>
    </section>

    <!-- Sezione 3: BT inter-owner marcate -->
    <section class="vp-saldi__sezione">
      <div class="vp-eyebrow">BT inter-owner marcate</div>
      <q-list separator bordered class="vp-saldi__lista">
        <q-item
          v-for="v in ledgerEntriesAggregate"
          :key="v.bank_transaction!"
          dense
        >
          <q-item-section>
            <q-item-label>
              {{ formattaData(v.data) }} — {{ v.descrizione }}
            </q-item-label>
            <q-item-label caption>
              {{ v.tipo_display }} · {{ v.owner_nominativo }}
            </q-item-label>
          </q-item-section>
          <q-item-section side class="vp-mono" :class="totaleClass(v.importo)">
            {{ formattaEuro(v.importo) }}
          </q-item-section>
        </q-item>
        <q-item v-if="ledgerEntriesAggregate.length === 0">
          <q-item-section class="text-grey-7">
            Nessuna BT marcata come inter-owner. Marcale dalla pagina
            <router-link to="/p/riconciliazione">Riconciliazione</router-link>.
          </q-item-section>
        </q-item>
      </q-list>
    </section>

    <!-- Sezione 4: movimenti bilaterali (Livello B) -->
    <section class="vp-saldi__sezione">
      <div class="vp-eyebrow">Movimenti bilaterali (privati)</div>
      <q-list separator bordered class="vp-saldi__lista">
        <q-item v-for="b in store.bilaterali" :key="b.id" dense>
          <q-item-section>
            <q-item-label>
              {{ formattaData(b.data) }} —
              <strong>{{ b.owner_da_nominativo }}</strong>
              <q-icon name="east" size="14px" class="q-mx-xs" />
              <strong>{{ b.owner_a_nominativo }}</strong>
            </q-item-label>
            <q-item-label caption>{{ b.descrizione }}</q-item-label>
          </q-item-section>
          <q-item-section side class="vp-mono">
            {{ formattaEuro(b.importo) }}
          </q-item-section>
        </q-item>
        <q-item v-if="store.bilaterali.length === 0">
          <q-item-section class="text-grey-7">
            Nessun movimento bilaterale.
          </q-item-section>
        </q-item>
      </q-list>
    </section>

    <!-- Modal voci settlement -->
    <q-dialog v-model="dialogSettlementAperto">
      <q-card class="vp-saldi__dialog">
        <q-card-section class="row items-center q-pb-none">
          <div>
            <div class="vp-eyebrow">Settlement</div>
            <div class="vp-display vp-saldi__dialog-titolo">
              {{ settlementSelezionato?.descrizione }}
            </div>
          </div>
          <q-space />
          <q-btn icon="close" flat round dense v-close-popup />
        </q-card-section>
        <q-card-section>
          <q-list dense separator>
            <q-item v-for="v in vociSettlement" :key="v.id" dense>
              <q-item-section>
                <q-item-label>{{ v.descrizione }}</q-item-label>
                <q-item-label caption>
                  {{ formattaData(v.data) }} · {{ v.tipo_display }} · {{ v.owner_nominativo }}
                </q-item-label>
              </q-item-section>
              <q-item-section side class="vp-mono" :class="totaleClass(v.importo)">
                {{ formattaEuro(v.importo) }}
              </q-item-section>
            </q-item>
            <q-item v-if="vociSettlement.length === 0">
              <q-item-section class="text-grey-7">
                Caricamento voci…
              </q-item-section>
            </q-item>
          </q-list>
        </q-card-section>
      </q-card>
    </q-dialog>
  </q-page>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue';
import {
  useSaldiFratelliStore,
  type OwnerLedgerEntryFE,
  type OwnerSettlementFE,
} from 'stores/saldiFratelli';
import { useOwnersStore } from 'stores/owners';
import { useFormatoEuro } from 'src/composables/useFormatoEuro';
import { useFormatoData } from 'src/composables/useFormatoData';

const store = useSaldiFratelliStore();
const ownersStore = useOwnersStore();
const { formattaEuro } = useFormatoEuro();
const { formattaData } = useFormatoData();

function isoOggi(): string {
  const d = new Date();
  const pad = (n: number) => (n < 10 ? `0${n}` : `${n}`);
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
}

const atDate = ref<string>(isoOggi());

const dialogSettlementAperto = ref(false);
const settlementSelezionato = ref<OwnerSettlementFE | null>(null);
const vociSettlement = ref<OwnerLedgerEntryFE[]>([]);

const ledgerEntriesAggregate = computed(() => {
  // Una BT può avere più voci ledger (es. distribuzione: 2 voci simmetriche).
  // In questa lista mostriamo una riga per BT, scegliendo la voce con
  // owner_nominativo del proprietario del conto (che ha importo positivo).
  const perBt = new Map<number, OwnerLedgerEntryFE>();
  for (const v of store.ledgerEntries) {
    if (v.bank_transaction == null) continue;
    const cur = perBt.get(v.bank_transaction);
    if (!cur || Number(v.importo) > Number(cur.importo)) {
      perBt.set(v.bank_transaction, v);
    }
  }
  return Array.from(perBt.values()).sort((a, b) =>
    a.data < b.data ? 1 : -1,
  );
});

function nominativoOwner(id: number): string {
  return ownersStore.byId(id)?.nominativo ?? `Owner ${id}`;
}

function formattaQuota(q: string): string {
  const n = Number(q);
  if (!Number.isFinite(n)) return q;
  return `${(n * 100).toFixed(2)}%`;
}

function totaleClass(v: number | string): string {
  const n = Number(v);
  if (n > 0.005) return 'vp-saldi__pos';
  if (n < -0.005) return 'vp-saldi__neg';
  return '';
}

function entriesOrdinate(d: Record<string, string>): [string, string][] {
  return Object.entries(d)
    .filter(([, v]) => Math.abs(Number(v)) > 0.005)
    .sort((a, b) => Math.abs(Number(b[1])) - Math.abs(Number(a[1])));
}

function hasEntries(d: Record<string, string>): boolean {
  return entriesOrdinate(d).length > 0;
}

function etichettaCausale(c: string): string {
  if (c === 'affitto') return 'Affitto';
  if (c === 'utenze') return 'Utenze';
  if (c === 'extra') return 'Extra';
  return c;
}

function etichettaCategoria(chiave: string): string {
  // Formato: "<codice>|<ord|straord>"
  const [codice, tipo] = chiave.split('|');
  const tag = tipo === 'straord' ? ' (straord.)' : '';
  return `${codice ?? chiave}${tag}`;
}

async function apriSettlement(set: OwnerSettlementFE) {
  settlementSelezionato.value = set;
  vociSettlement.value = [];
  dialogSettlementAperto.value = true;
  vociSettlement.value = await store.fetchLedgerBySettlement(set.id);
}

async function ricarica() {
  await Promise.all([
    store.fetchSaldi(atDate.value),
    store.fetchSettlements(),
    store.fetchLedgerInterOwner(),
    store.fetchBilaterali(),
  ]);
}

onMounted(async () => {
  await ownersStore.fetchOwners();
  await ricarica();
});

watch(atDate, () => {
  void store.fetchSaldi(atDate.value);
});
</script>

<style scoped>
.vp-saldi__head {
  display: flex;
  justify-content: space-between;
  align-items: flex-end;
  flex-wrap: wrap;
  gap: var(--vp-gap-3);
  margin-bottom: var(--vp-gap-4);
}
.vp-saldi__head-azioni {
  display: flex;
  gap: var(--vp-gap-2);
  align-items: flex-end;
}
.vp-saldi__date {
  width: 200px;
}
.vp-saldi__titolo {
  font-size: var(--vp-text-2xl);
  margin: var(--vp-gap-1) 0 0;
}
.vp-saldi__sezione {
  margin-bottom: var(--vp-gap-5);
}
.vp-saldi__hint {
  color: var(--vp-ink-2);
  font-size: 0.85rem;
  margin: var(--vp-gap-1) 0 var(--vp-gap-3);
}
.vp-saldi__grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
  gap: var(--vp-gap-3);
  margin-top: var(--vp-gap-2);
}
.vp-saldi__card {
  background: var(--vp-cream);
}
.vp-saldi__owner {
  font-weight: 600;
  font-size: 1.1rem;
}
.vp-saldi__quota {
  color: var(--vp-ink-2);
  font-size: 0.8rem;
}
.vp-saldi__totale {
  font-size: 1.6rem;
  font-weight: 600;
  margin-top: var(--vp-gap-1);
  font-variant-numeric: tabular-nums;
}
.vp-saldi__decomp {
  background: var(--vp-paper-2);
}
.vp-saldi__lista {
  background: var(--vp-cream);
  margin-top: var(--vp-gap-2);
}
.vp-saldi__snap-chip {
  margin-right: var(--vp-gap-2);
}
.vp-saldi__pos {
  color: #2e7a39;
}
.vp-saldi__neg {
  color: #b14a2b;
}
.vp-saldi__empty {
  background: var(--vp-paper-2);
  color: var(--vp-ink-2);
}
.vp-saldi__dialog {
  background: var(--vp-cream);
  min-width: min(560px, 95vw);
  max-width: 720px;
}
.vp-saldi__dialog-titolo {
  font-size: var(--vp-text-xl);
  margin-top: 2px;
}
.vp-mono {
  font-variant-numeric: tabular-nums;
}
</style>
