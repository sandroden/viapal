<template>
  <q-page class="vp-th">
    <!-- Header -->
    <header class="vp-th__header">
      <div class="vp-eyebrow">La tua casa</div>
      <h1 class="vp-display vp-th__titolo">Ciao, {{ saluto }}</h1>
      <div v-if="daPagare.length > 0" class="vp-th__riga">
        <span class="vp-th__count">
          <b>{{ daPagare.length }} {{ daPagare.length === 1 ? 'pagamento' : 'pagamenti' }}</b>
          da sistemare
        </span>
        <span v-if="numParziali > 0" class="vp-badge vp-badge--neutral vp-th__badge">
          {{ numParziali }} già {{ numParziali === 1 ? 'pagato' : 'pagati' }} in parte
        </span>
      </div>
    </header>

    <!-- Stato vuoto -->
    <div v-if="!loading && daPagare.length === 0" class="vp-th__vuoto">
      <EmptyState
        icon="check_circle"
        title="Tutto in regola"
        message="Quando ci sarà un affitto o un'utenza da saldare, lo vedrai qui."
      />
    </div>

    <template v-else>
      <!-- Credito già versato non ancora imputato: evidenziato e scalato dal totale -->
      <div v-if="haCredito" class="vp-th__credito">
        <q-icon name="savings" size="20px" class="vp-th__credito-ic" />
        <div class="vp-th__credito-txt">
          Hai <b>{{ formattaEuro(creditoDisponibile) }}</b> già versati e non ancora abbinati a una
          bolletta: li abbiamo <b>scalati dal totale</b> qui sotto, così non paghi due volte.
        </div>
      </div>

      <!-- Barra di selezione -->
      <div class="vp-th__selbar">
        <button class="vp-th__selall" @click="toggleAll">
          <ThCheck :on="allOn" :size="20" />
          {{ allOn ? 'Deseleziona tutti' : 'Seleziona tutti' }}
        </button>
        <router-link to="/i/rendiconto" class="vp-th__rendlink">Vedi rendiconto →</router-link>
      </div>

      <!-- Lista card -->
      <div class="vp-th__lista">
        <RitardoCard
          v-for="item in daPagare"
          :key="chiave(item)"
          :item="item"
          :selected="sel.has(chiave(item))"
          :show-ritardo="false"
          stacco="forte"
          @toggle="toggle(item)"
          @paga="paga(item)"
          @ho-pagato="hoPagato(item)"
          @dettaglio="apriDettaglio(item)"
        />
      </div>

      <!-- Nota gentile -->
      <div class="vp-th__nota">
        <q-icon name="eco" size="16px" :style="{ color: 'var(--vp-leaf)', marginTop: '2px', flexShrink: 0 }" />
        <span>
          Controlla pure i conteggi con calma: se qualcosa non torna, scrivici e lo sistemiamo
          insieme prima di pagare.
        </span>
      </div>

      <!-- Barra totale (fissa sopra la bottom-nav) -->
      <div class="vp-th__totalbar">
        <div class="vp-th__totalbar-inner">
          <div class="vp-th__totale">
            <div class="vp-eyebrow vp-th__totale-eyebrow">
              {{ haCredito && creditoApplicato > 0 ? 'Da versare' : 'Totale selezionato' }}
            </div>
            <div class="vp-display vp-mono vp-th__totale-val" :class="{ 'vp-th__totale-val--off': count === 0 }">
              {{ formattaEuro(nettoDaPagare) }}
            </div>
            <!-- Scomposizione: lordo selezionato − credito già versato -->
            <div v-if="haCredito && creditoApplicato > 0 && count > 0" class="vp-th__scomposizione">
              <span class="vp-mono">{{ formattaEuro(totaleSel) }}</span>
              <span class="vp-th__scomp-meno">− credito {{ formattaEuro(creditoApplicato) }}</span>
            </div>
            <div class="vp-th__totale-sub">
              <template v-if="count > 0 && nettoDaPagare <= 0">
                Coperto dal credito già versato
              </template>
              <template v-else-if="count > 0">
                {{ count }} {{ count === 1 ? 'ritardo' : 'ritardi' }} · un unico bonifico
              </template>
              <template v-else>Spunta i ritardi da saldare insieme</template>
            </div>
          </div>
          <q-btn
            unelevated
            no-caps
            color="primary"
            icon="account_balance_wallet"
            :label="$q.screen.gt.sm ? 'Paga con bonifico' : 'Paga'"
            :disable="count === 0 || nettoDaPagare <= 0"
            class="vp-th__paga-btn"
            @click="bonificoUnico"
          />
        </div>
      </div>
    </template>

    <!-- Pagamenti fatti (storico), sotto le notifiche dei ritardi -->
    <section v-if="!loading && pagamentiFatti.length" class="vp-th__pagamenti">
      <div class="vp-th__pagamenti-head">
        <h2 class="vp-display vp-th__pagamenti-titolo">I tuoi pagamenti</h2>
        <span class="vp-th__pagamenti-sub">{{ pagamentiFatti.length }} movimenti</span>
      </div>
      <q-list bordered separator class="vp-th__pagamenti-lista">
        <q-item v-for="p in pagamentiFatti" :key="`${p.tipo}-${p.id}`">
          <q-item-section avatar>
            <q-icon :name="iconaPer(p.tipo)" color="primary" />
          </q-item-section>
          <q-item-section>
            <q-item-label>{{ p.descrizione }}</q-item-label>
            <q-item-label caption>{{ formattaData(p.data_pagamento) }}</q-item-label>
          </q-item-section>
          <q-item-section side>
            <div class="vp-mono">{{ formattaEuro(p.importo) }}</div>
            <SemaforoBadge :livello="livelloPer(p.stato)" :label="labelPer(p.stato)" />
          </q-item-section>
        </q-item>
      </q-list>
    </section>

    <q-dialog v-model="dialogQr">
      <QrBonifico
        v-if="pagamentoBonifico"
        :pagamento="pagamentoBonifico"
        :importo="nettoDaPagare"
      />
    </q-dialog>

    <q-dialog v-model="dialogDettaglio">
      <DettaglioPagamento
        v-if="itemDettaglio"
        :item="itemDettaglio"
        @paga="paga(itemDettaglio)"
      />
    </q-dialog>
  </q-page>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue';
import { useRouter } from 'vue-router';
import { useQuasar, Notify } from 'quasar';
import { useAuthStore } from 'stores/auth';
import {
  useDashboardStore,
  type DaPagareItem,
  type DatiPagamento,
  type TipoPagamento,
} from 'stores/dashboard';
import RitardoCard from 'src/components/RitardoCard.vue';
import ThCheck from 'src/components/ThCheck.vue';
import EmptyState from 'src/components/EmptyState.vue';
import QrBonifico from 'src/components/QrBonifico.vue';
import DettaglioPagamento from 'src/components/DettaglioPagamento.vue';
import SemaforoBadge from 'src/components/SemaforoBadge.vue';
import type { SemaforoLivello } from 'src/types/semaforo';
import { useFormatoEuro } from 'src/composables/useFormatoEuro';
import { useFormatoData } from 'src/composables/useFormatoData';

const auth = useAuthStore();
const store = useDashboardStore();
const router = useRouter();
const $q = useQuasar();
const { formattaEuro } = useFormatoEuro();
const { formattaData } = useFormatoData();

const saluto = computed(() => auth.user?.first_name?.trim() || auth.user?.username || 'Inquilino');
const daPagare = computed(() => store.inquilinoData?.da_pagare ?? []);
const pagamentiFatti = computed(() => store.inquilinoData?.ultimi_pagamenti ?? []);

function iconaPer(tipo: string): string {
  if (tipo === 'rent') return 'home';
  if (tipo === 'utility_charge') return 'bolt';
  return 'note_add';
}
function livelloPer(stato: string): SemaforoLivello {
  if (stato === 'pagato') return 'salvia';
  if (stato === 'dichiarato') return 'miele';
  return 'argilla_chiaro';
}
function labelPer(stato: string): string {
  if (stato === 'pagato') return 'Pagato';
  if (stato === 'dichiarato') return 'Dichiarato';
  return stato;
}
const saldoTotale = computed(() => store.inquilinoData?.saldo_totale ?? null);
const loading = computed(() => store.loadingInquilino);
const numParziali = computed(() => daPagare.value.filter((x) => x.parziale).length);

const chiave = (item: DaPagareItem) => `${item.tipo}-${item.id}`;
const sel = ref<Set<string>>(new Set());
const dialogQr = ref(false);
const dialogDettaglio = ref(false);
const itemDettaglio = ref<DaPagareItem | null>(null);

const count = computed(() => sel.value.size);
const allOn = computed(
  () => daPagare.value.length > 0 && sel.value.size === daPagare.value.length,
);
const itemsSel = computed(() => daPagare.value.filter((x) => sel.value.has(chiave(x))));
const totaleSel = computed(() => itemsSel.value.reduce((s, x) => s + x.residuo, 0));

// Credito già versato e non ancora imputato (resti dei bonifici): va scalato
// dal totale così non chiediamo soldi che l'inquilino ha già versato. Si applica
// alla selezione corrente, mai oltre il suo importo.
const creditoDisponibile = computed(() => saldoTotale.value?.credito_disponibile ?? 0);
const creditoApplicato = computed(() => Math.min(creditoDisponibile.value, totaleSel.value));
const nettoDaPagare = computed(() => Math.max(0, totaleSel.value - creditoApplicato.value));
const haCredito = computed(() => creditoDisponibile.value > 0.005);

// --- Causale dinamica del bonifico cumulativo --------------------------------
// Raggruppa le voci selezionate per tipo e ne elenca i mesi, es:
//   "Utenze: ago 25, dic 25, gen 26 - Affitto: mag 26"
const MESI_BREVI = [
  '', 'gen', 'feb', 'mar', 'apr', 'mag', 'giu', 'lug', 'ago', 'set', 'ott', 'nov', 'dic',
];
const GRUPPO_LABEL: Record<TipoPagamento, string> = {
  rent: 'Affitto',
  utility_charge: 'Utenze',
  extra: 'Extra',
};
function meseBreve(iso: string): string {
  const [anno, mese] = iso.split('-');
  return `${MESI_BREVI[Number(mese)]} ${anno!.slice(-2)}`;
}

const causaleDinamica = computed(() => {
  const perTipo = new Map<TipoPagamento, DaPagareItem[]>();
  for (const it of itemsSel.value) {
    const voci = perTipo.get(it.tipo) ?? [];
    voci.push(it);
    perTipo.set(it.tipo, voci);
  }
  const segmenti = [...perTipo.entries()].map(([tipo, voci]) => {
    const ordinate = [...voci].sort((a, b) => a.competenza.localeCompare(b.competenza));
    // Le voci pagate solo in parte si versano "a saldo": va segnalato.
    const mesi = [
      ...new Set(ordinate.map((v) => meseBreve(v.competenza) + (v.parziale ? ' (saldo)' : ''))),
    ].join(', ');
    return { minDate: ordinate[0]?.competenza ?? '', testo: `${GRUPPO_LABEL[tipo]}: ${mesi}` };
  });
  segmenti.sort((a, b) => a.minDate.localeCompare(b.minDate));
  return segmenti.map((s) => s.testo).join(' - ');
});

// Nome dell'inquilino in coda alla causale, per facilitare la riconciliazione.
// Intero se ci sta nei 140 char dello standard EPC, altrimenti solo il cognome.
const CAUSALE_MAX = 140;
function conNome(descrizione: string, nominativo: string): string {
  const nome = nominativo.trim();
  if (!nome) return descrizione.slice(0, CAUSALE_MAX);
  const intero = `${descrizione} - ${nome}`;
  if (intero.length <= CAUSALE_MAX) return intero;
  const cognome = nome.split(/\s+/).pop() ?? nome;
  return `${descrizione} - ${cognome}`.slice(0, CAUSALE_MAX);
}

// Pagamento per il QR: stesso conto del saldo totale, ma con la causale
// costruita sulle voci effettivamente spuntate.
const pagamentoBonifico = computed<DatiPagamento | null>(() => {
  const base = saldoTotale.value?.pagamento;
  if (!base) return null;
  const descrizione = causaleDinamica.value || base.causale;
  const nominativo = store.inquilinoData?.tenant?.nominativo ?? '';
  return { ...base, causale: conNome(descrizione, nominativo) };
});

function selezionaTutti() {
  sel.value = new Set(daPagare.value.map(chiave));
}
function toggle(item: DaPagareItem) {
  const k = chiave(item);
  const n = new Set(sel.value);
  if (n.has(k)) n.delete(k);
  else n.add(k);
  sel.value = n;
}
function toggleAll() {
  if (allOn.value) sel.value = new Set();
  else selezionaTutti();
}
function paga(item: DaPagareItem) {
  void router.push(`/i/paga/${item.tipo}/${item.id}`);
}
function apriDettaglio(item: DaPagareItem) {
  itemDettaglio.value = item;
  dialogDettaglio.value = true;
}
function hoPagato(item: DaPagareItem) {
  void router.push({ path: `/i/paga/${item.tipo}/${item.id}`, query: { dichiara: '1' } });
}
function bonificoUnico() {
  if (count.value === 0 || nettoDaPagare.value <= 0) return;
  if (pagamentoBonifico.value) dialogQr.value = true;
  else Notify.create({ type: 'warning', message: 'Conto per il bonifico non disponibile' });
}

onMounted(async () => {
  await store.loadInquilino();
  selezionaTutti(); // all'apertura tutti i ritardi sono selezionati
});
</script>

<style scoped>
.vp-th {
  background: var(--vp-paper);
  padding: 6px 18px 140px; /* 140px in basso: spazio per la barra totale fissa */
}
.vp-th__header {
  padding: 0 0 14px;
}
.vp-th__titolo {
  font-size: 25px;
  margin: 4px 0 0;
  color: var(--vp-ink);
}
.vp-th__riga {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 12px;
  flex-wrap: wrap;
}
.vp-th__count {
  font-size: 14px;
  color: var(--vp-ink);
}
.vp-th__badge {
  height: 22px;
  font-size: 11.5px;
}
.vp-th__vuoto {
  padding: var(--vp-gap-6) 0;
}
.vp-th__credito {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  background: var(--vp-leaf-soft, oklch(0.95 0.04 145));
  border: 1px solid var(--vp-leaf, oklch(0.7 0.1 145));
  border-radius: var(--vp-r-md);
  padding: 12px 14px;
  margin-bottom: 16px;
  font-size: 13px;
  line-height: 1.45;
  color: var(--vp-ink-2);
}
.vp-th__credito-ic {
  color: var(--vp-leaf, oklch(0.6 0.12 145));
  flex-shrink: 0;
  margin-top: 1px;
}
.vp-th__credito-txt {
  min-width: 0;
}
.vp-th__scomposizione {
  display: flex;
  align-items: baseline;
  gap: 8px;
  margin-top: 3px;
  font-size: 12px;
  color: var(--vp-ink-3);
}
.vp-th__scomp-meno {
  color: var(--vp-leaf, oklch(0.55 0.12 145));
  font-weight: 500;
}
.vp-th__selbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 0 12px;
}
.vp-th__selall {
  display: flex;
  align-items: center;
  gap: 9px;
  background: transparent;
  border: none;
  cursor: pointer;
  padding: 6px 0;
  font-family: var(--vp-font-ui);
  font-size: 13.5px;
  color: var(--vp-ink-2);
}
.vp-th__rendlink {
  font-size: 13px;
  color: var(--vp-terra);
  text-decoration: none;
  font-weight: 500;
}
.vp-th__lista {
  display: grid;
  grid-template-columns: 1fr;
  gap: 18px;
  margin-bottom: 18px;
}
.vp-th__nota {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  color: var(--vp-ink-3);
  font-size: 12.5px;
  line-height: 1.5;
  max-width: 620px;
}
.vp-th__pagamenti {
  margin-top: 26px;
}
.vp-th__pagamenti-head {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  margin-bottom: 12px;
}
.vp-th__pagamenti-titolo {
  font-size: 19px;
  margin: 0;
  color: var(--vp-ink);
}
.vp-th__pagamenti-sub {
  font-size: 12.5px;
  color: var(--vp-ink-3);
}
.vp-th__pagamenti-lista {
  background: var(--vp-cream);
  border-radius: var(--vp-r-lg);
  border-color: var(--vp-paper-3) !important;
  overflow: hidden;
}
.vp-th__totalbar {
  position: fixed;
  left: 0;
  right: 0;
  bottom: calc(56px + env(safe-area-inset-bottom));
  border-top: 1px solid var(--vp-paper-3);
  background: var(--vp-paper);
  box-shadow: 0 -6px 20px oklch(0.3 0.02 50 / 0.06);
  z-index: 1500;
}
.vp-th__totalbar-inner {
  max-width: 760px;
  margin: 0 auto;
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 12px 16px;
}
.vp-th__totale {
  flex: 1;
  min-width: 0;
}
.vp-th__totale-eyebrow {
  font-size: 10.5px;
}
.vp-th__totale-val {
  font-size: 27px;
  color: var(--vp-ink);
  line-height: 1.1;
  margin-top: 2px;
}
.vp-th__totale-val--off {
  color: var(--vp-ink-4);
}
.vp-th__totale-sub {
  font-size: 11.5px;
  color: var(--vp-ink-3);
  margin-top: 2px;
}
.vp-th__paga-btn {
  height: 48px;
  font-size: 15px;
  font-weight: 600;
  border-radius: var(--vp-r-md);
  padding: 0 22px;
  flex-shrink: 0;
}
@media (min-width: 1024px) {
  /* Sfonda il container stretto del layout per dare respiro alle 2 colonne,
     ri-centrando il contenuto a max ~1040px (solo questa schermata). */
  .vp-th {
    width: 100vw;
    margin-left: calc(50% - 50vw);
    padding-left: max(28px, calc(50vw - 520px));
    padding-right: max(28px, calc(50vw - 520px));
  }
  .vp-th__titolo {
    font-size: 30px;
  }
  .vp-th__lista {
    grid-template-columns: 1fr 1fr;
  }
  .vp-th__totalbar-inner {
    max-width: 1040px;
    padding: 16px 28px;
  }
  .vp-th__totale-val {
    font-size: 34px;
  }
  .vp-th__paga-btn {
    height: 50px;
    min-width: 280px;
  }
}
</style>
