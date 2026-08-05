<script setup lang="ts">
// Riepilogo annuale delle bollette caricate: righe = mesi, colonne =
// prodotto/fornitore, cella = importo. Una bolletta compare nel mese in cui
// INIZIA il suo periodo di competenza; una bimestrale resta su quel mese e
// mostra il range di copertura sotto l'importo.
import { computed, ref, watch } from 'vue';
import VpIcon from './VpIcon.vue';
import { eur, mediaPath, meseCapitalize, prodottoToTipo, rangePeriodo, utility } from './format';
import type { UtilityStyle } from './format';
import type { BollettaFE } from 'stores/utenze';

const props = defineProps<{ bollette: BollettaFE[]; loading?: boolean }>();
const emit = defineEmits<{ 'view-pdf': [v: { url: string; title: string }] }>();

const MESI = [
  'Gennaio', 'Febbraio', 'Marzo', 'Aprile', 'Maggio', 'Giugno',
  'Luglio', 'Agosto', 'Settembre', 'Ottobre', 'Novembre', 'Dicembre',
];
const ORDINE_PRODOTTO = ['luce', 'gas', 'acqua'];

function num(v: number | string | null | undefined): number {
  const n = typeof v === 'string' ? parseFloat(v) : (v ?? 0);
  return Number.isFinite(n) ? n : 0;
}
function annoDi(b: BollettaFE): number {
  return Number((b.periodo_da || '').slice(0, 4));
}
function meseDi(b: BollettaFE): number {
  return Number((b.periodo_da || '').slice(5, 7));
}
function fornitoreDi(b: BollettaFE): string {
  return b.supplier_nome || b.pagata_da_nominativo || '—';
}

// ── Anno selezionato (solo anni con almeno una bolletta) ─────────────────
const anni = computed<number[]>(() => {
  const s = new Set<number>();
  for (const b of props.bollette) {
    const a = annoDi(b);
    if (Number.isFinite(a) && a > 0) s.add(a);
  }
  return [...s].sort((x, y) => x - y);
});

const annoSel = ref(new Date().getFullYear());
watch(
  anni,
  (v) => {
    if (v.length && !v.includes(annoSel.value)) annoSel.value = v[v.length - 1]!;
  },
  { immediate: true },
);

const idxAnno = computed(() => anni.value.indexOf(annoSel.value));
const puoPrec = computed(() => idxAnno.value > 0);
const puoSucc = computed(() => idxAnno.value >= 0 && idxAnno.value < anni.value.length - 1);
function cambiaAnno(d: number): void {
  const a = anni.value[idxAnno.value + d];
  if (a !== undefined) annoSel.value = a;
}

const delAnno = computed(() => props.bollette.filter((b) => annoDi(b) === annoSel.value));

// ── Colonne: una per combinazione prodotto/fornitore presente nell'anno ──
interface Colonna {
  key: string;
  prodotto: string;
  tipoLabel: string;
  fornitore: string;
  style: UtilityStyle;
}

const colonne = computed<Colonna[]>(() => {
  const map = new Map<string, Colonna>();
  for (const b of delAnno.value) {
    const key = `${b.prodotto}|${fornitoreDi(b)}`;
    if (!map.has(key)) {
      const tipo = prodottoToTipo(b.prodotto);
      map.set(key, {
        key,
        prodotto: b.prodotto,
        tipoLabel: meseCapitalize(tipo),
        fornitore: fornitoreDi(b),
        style: utility(tipo),
      });
    }
  }
  const rank = (p: string): number => {
    const i = ORDINE_PRODOTTO.indexOf(p);
    return i === -1 ? ORDINE_PRODOTTO.length : i;
  };
  return [...map.values()].sort(
    (a, b) => rank(a.prodotto) - rank(b.prodotto) || a.fornitore.localeCompare(b.fornitore),
  );
});

// ── Celle e totali ───────────────────────────────────────────────────────
interface Cella {
  key: string;
  importo: number;
  count: number;
  sub: string;
  pdfUrl: string | null;
  title: string;
}
interface Riga {
  mese: number;
  label: string;
  celle: Cella[];
  totale: number;
}

const righe = computed<Riga[]>(() => {
  const out: Riga[] = [];
  for (let m = 1; m <= 12; m++) {
    const celle = colonne.value.map((c) => {
      const bills = delAnno.value.filter(
        (b) => meseDi(b) === m && `${b.prodotto}|${fornitoreDi(b)}` === c.key,
      );
      const first = bills[0];
      let sub = '';
      if (bills.length > 1) sub = `${bills.length} bollette`;
      else if (first && first.periodo_da.slice(0, 7) !== first.periodo_a.slice(0, 7))
        sub = rangePeriodo(first.periodo_da, first.periodo_a);
      return {
        key: `${m}-${c.key}`,
        importo: bills.reduce((s, b) => s + num(b.importo_totale), 0),
        count: bills.length,
        sub,
        pdfUrl: bills.length === 1 ? mediaPath(first?.file_pdf) : null,
        title: `${c.tipoLabel} ${c.fornitore} · ${MESI[m - 1]} ${annoSel.value}`,
      };
    });
    out.push({
      mese: m,
      label: MESI[m - 1]!,
      celle,
      totale: celle.reduce((s, c) => s + c.importo, 0),
    });
  }
  return out;
});

const totaliColonna = computed(() =>
  colonne.value.map((_c, i) => righe.value.reduce((s, r) => s + (r.celle[i]?.importo ?? 0), 0)),
);
const totaleAnno = computed(() => righe.value.reduce((s, r) => s + r.totale, 0));

function apri(cell: Cella): void {
  if (cell.pdfUrl) emit('view-pdf', { url: cell.pdfUrl, title: cell.title });
}
</script>

<template>
  <div class="rb">
    <div class="rb-head">
      <div>
        <h1 class="vp-display rb-title">
          Bollette, <span class="rb-anno-tit">{{ annoSel }}</span>
        </h1>
        <div class="rb-sub">
          {{ delAnno.length }} bollette caricate · totale {{ eur(totaleAnno) }}
        </div>
      </div>

      <div class="rb-nav">
        <div class="vp-eyebrow" style="margin-bottom: 4px">Anno</div>
        <div class="group">
          <button
            class="arrow"
            aria-label="Anno precedente"
            :disabled="!puoPrec"
            @click="cambiaAnno(-1)"
          >
            <VpIcon name="back" :size="15" />
          </button>
          <span class="anno-val vp-mono">{{ annoSel }}</span>
          <button
            class="arrow"
            aria-label="Anno successivo"
            :disabled="!puoSucc"
            @click="cambiaAnno(1)"
          >
            <VpIcon name="chevron" :size="15" />
          </button>
        </div>
      </div>
    </div>

    <div v-if="loading && !bollette.length" class="rb-vuoto">
      <q-spinner-dots size="32px" color="primary" />
    </div>
    <div v-else-if="!colonne.length" class="rb-vuoto">
      Nessuna bolletta caricata per il {{ annoSel }}.
    </div>

    <div v-else class="rb-scroll">
      <table class="rb-table">
        <thead>
          <tr>
            <th class="c-mese">Mese</th>
            <th v-for="c in colonne" :key="c.key" class="c-forn">
              <span class="col-tipo" :style="{ color: c.style.fg }">
                <VpIcon :name="c.style.icon" :size="14" /> {{ c.tipoLabel }}
              </span>
              <span class="col-forn">{{ c.fornitore }}</span>
            </th>
            <th class="c-tot">Totale</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="r in righe" :key="r.mese">
            <td class="c-mese">{{ r.label }}</td>
            <td
              v-for="cell in r.celle"
              :key="cell.key"
              class="c-cella"
              :class="{ cliccabile: !!cell.pdfUrl }"
              :title="cell.pdfUrl ? 'Apri il PDF' : undefined"
              @click="apri(cell)"
            >
              <template v-if="cell.count">
                <span class="imp vp-mono">{{ eur(cell.importo) }}</span>
                <span v-if="cell.sub" class="sub">{{ cell.sub }}</span>
              </template>
              <span v-else class="vuoto">—</span>
            </td>
            <td class="c-tot vp-mono">
              <template v-if="r.totale">{{ eur(r.totale) }}</template>
              <span v-else class="vuoto">—</span>
            </td>
          </tr>
        </tbody>
        <tfoot>
          <tr>
            <td class="c-mese">Totale</td>
            <td v-for="(c, i) in colonne" :key="c.key" class="c-cella vp-mono">
              {{ eur(totaliColonna[i] ?? 0) }}
            </td>
            <td class="c-tot vp-mono">{{ eur(totaleAnno) }}</td>
          </tr>
        </tfoot>
      </table>
    </div>
  </div>
</template>

<style scoped>
.rb {
  padding: 18px 36px 48px;
  font-family: var(--vp-font-ui);
  color: var(--vp-ink);
}
.rb-head {
  display: flex;
  justify-content: space-between;
  align-items: flex-end;
  flex-wrap: wrap;
  gap: 12px;
  margin-bottom: 20px;
}
.rb-title {
  font-size: 30px;
  margin: 0;
}
.rb-anno-tit {
  color: var(--vp-ink-2);
  font-style: italic;
}
.rb-sub {
  color: var(--vp-ink-2);
  font-size: 14px;
  margin-top: 4px;
}

/* Selettore anno: stesso linguaggio del PeriodSelector */
.group {
  display: flex;
  align-items: center;
  gap: 2px;
  background: var(--vp-paper-2);
  border: 1.5px solid var(--vp-paper-3);
  border-radius: 10px;
  padding: 2px;
}
.arrow {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 26px;
  height: 26px;
  border-radius: 7px;
  background: transparent;
  border: none;
  cursor: pointer;
  color: var(--vp-ink-2);
}
.arrow:hover:not(:disabled) {
  background: var(--vp-paper-3);
}
.arrow:disabled {
  opacity: 0.35;
  cursor: default;
}
.anno-val {
  font-size: 14px;
  font-weight: 600;
  min-width: 42px;
  text-align: center;
}

.rb-vuoto {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 30vh;
  color: var(--vp-ink-3);
}

.rb-scroll {
  overflow-x: auto;
  border: 1px solid var(--vp-paper-3);
  border-radius: 14px;
  background: var(--vp-paper);
}
.rb-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 14px;
}
.rb-table th {
  text-align: left;
  padding: 10px 14px;
  background: var(--vp-paper-2);
  border-bottom: 1.5px solid var(--vp-paper-3);
  font-weight: 500;
  white-space: nowrap;
}
.col-tipo {
  display: flex;
  align-items: center;
  gap: 5px;
  font-weight: 600;
  font-size: 13px;
}
.col-forn {
  display: block;
  font-size: 12px;
  color: var(--vp-ink-3);
  margin-top: 1px;
}
.rb-table td {
  padding: 9px 14px;
  border-bottom: 1px solid var(--vp-paper-2);
  white-space: nowrap;
  vertical-align: top;
}
.rb-table tbody tr:hover td {
  background: var(--vp-cream);
}
.c-mese {
  color: var(--vp-ink-2);
  width: 110px;
}
.c-cella .imp {
  display: block;
}
.c-cella .sub {
  display: block;
  font-size: 11.5px;
  color: var(--vp-ink-3);
  margin-top: 1px;
}
.c-cella.cliccabile {
  cursor: pointer;
}
.c-cella.cliccabile:hover .imp {
  color: var(--vp-terra-deep);
  text-decoration: underline;
}
.c-tot {
  font-weight: 600;
  border-left: 1px solid var(--vp-paper-2);
}
.vuoto {
  color: var(--vp-ink-3);
  opacity: 0.55;
}
.rb-table tfoot td {
  background: var(--vp-paper-2);
  border-top: 1.5px solid var(--vp-paper-3);
  border-bottom: none;
  font-weight: 600;
}

@media (max-width: 720px) {
  .rb {
    padding: 14px 16px 32px;
  }
  .rb-title {
    font-size: 24px;
  }
}
</style>
