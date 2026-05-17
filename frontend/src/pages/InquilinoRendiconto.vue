<template>
  <q-page padding class="vp-rd">
    <div class="vp-rd__toolbar no-print">
      <q-btn-toggle
        v-model="vista"
        no-caps
        dense
        unelevated
        toggle-color="primary"
        color="grey-3"
        text-color="grey-8"
        class="vp-rd__vista"
        :options="[
          { label: 'Per causale', value: 'causale' },
          { label: 'Cronologica', value: 'cronologica' },
        ]"
      />
      <q-space />
      <q-btn
        unelevated
        color="primary"
        no-caps
        icon="print"
        label="Stampa"
        :disable="!rendiconto"
        @click="stampa"
      />
    </div>

    <div v-if="store.loading && !rendiconto" class="vp-rd__loader">
      <q-spinner color="primary" size="32px" />
    </div>

    <article v-else-if="rendiconto" class="vp-rd__doc">
      <header class="vp-rd__head">
        <h1 class="vp-display vp-rd__titolo">Rendiconto</h1>
        <div class="vp-rd__meta">
          <div class="vp-rd__nominativo">{{ rendiconto.tenant.nominativo }}</div>
          <div v-if="rendiconto.tenant.codice_fiscale" class="vp-mono">
            C.F. {{ rendiconto.tenant.codice_fiscale }}
          </div>
          <div>
            Periodo locazione:
            {{ rendiconto.periodo.da ? formattaData(rendiconto.periodo.da) : '—' }}
            →
            {{ rendiconto.periodo.a ? formattaData(rendiconto.periodo.a) : 'in corso' }}
          </div>
          <div class="vp-rd__emesso">
            Emesso il {{ formattaData(rendiconto.emesso_il) }}
          </div>
        </div>
        <p class="vp-rd__intro no-print">
          Questo è il riepilogo completo di tutto il rapporto di locazione.
          Controllalo prima del saldo finale e della restituzione del
          deposito: se qualcosa non torna, segnalalo al proprietario.
        </p>
      </header>

      <section
        v-for="sez in (vista === 'causale' ? rendiconto.sezioni : [])"
        :key="sez.causale"
        class="vp-rd__sez"
      >
        <h2 class="vp-rd__sez-tit">{{ sez.label }}</h2>
        <div class="vp-rd__tabwrap">
          <table class="vp-rd__tab">
            <thead>
              <tr>
                <th class="vp-rd__c-data">Data</th>
                <th>Descrizione</th>
                <th class="vp-rd__c-num">Dovuto</th>
                <th class="vp-rd__c-num">Pagato</th>
                <th class="vp-rd__c-num">Differenza</th>
                <th class="vp-rd__c-nota">Nota</th>
              </tr>
            </thead>
            <tbody>
              <template v-for="(r, i) in sez.righe" :key="i">
                <tr>
                  <td class="vp-rd__c-data">{{ r.data ? formattaData(r.data) : '—' }}</td>
                  <td>{{ r.descrizione }}</td>
                  <td class="vp-rd__c-num vp-mono">{{ formattaEuro(r.dovuto) }}</td>
                  <td class="vp-rd__c-num vp-mono">
                    {{ r.pagato ? formattaEuro(r.pagato) : '—' }}
                  </td>
                  <td
                    class="vp-rd__c-num vp-mono"
                    :class="diffClass(diffRiga(sez, r) ?? 0)"
                  >
                    {{ formattaDiff(diffRiga(sez, r)) }}
                  </td>
                  <td class="vp-rd__c-nota">
                    <span :class="notaClass(r.nota)">{{ etichettaNota(r) }}</span>
                  </td>
                </tr>
                <tr v-if="r.allocazioni.length" class="vp-rd__cover">
                  <td></td>
                  <td colspan="5" class="vp-rd__cover-cell">
                    <span
                      v-for="(a, j) in r.allocazioni"
                      :key="j"
                      class="vp-rd__cover-item"
                    >
                      bonifico {{ formattaData(a.data) }}
                      {{ formattaEuro(a.bonifico_totale) }}/{{ formattaEuro(a.quota) }}<span
                        v-if="a.split"
                        class="vp-rd__star"
                      > *</span><template v-if="j < r.allocazioni.length - 1">; </template>
                    </span>
                  </td>
                </tr>
                <tr
                  v-for="(a, j) in r.allocazioni.filter(
                    (x) => Math.abs(x.resto) >= 0.005,
                  )"
                  :key="`r-${i}-${j}`"
                  class="vp-rd__resto-row"
                >
                  <td></td>
                  <td>
                    ↳ versato non imputato
                    <small>(bonifico {{ formattaData(a.data) }})</small>
                  </td>
                  <td></td>
                  <td></td>
                  <td
                    class="vp-rd__c-num vp-mono"
                    :class="diffClass(a.resto)"
                  >
                    {{ formattaEuro(a.resto) }}
                  </td>
                  <td></td>
                </tr>
              </template>
            </tbody>
            <tfoot>
              <tr>
                <td colspan="2"><strong>Totale {{ sez.label.toLowerCase() }}</strong></td>
                <td class="vp-rd__c-num vp-mono">{{ formattaEuro(sez.dovuto) }}</td>
                <td class="vp-rd__c-num vp-mono">{{ formattaEuro(sez.pagato) }}</td>
                <td
                  class="vp-rd__c-num vp-mono"
                  :class="diffClass(diffSez(sez))"
                >
                  {{ formattaEuro(diffSez(sez)) }}
                </td>
                <td></td>
              </tr>
            </tfoot>
          </table>
        </div>
      </section>

      <section
        v-for="g in (vista === 'cronologica' ? cronologico : [])"
        :key="g.anno"
        class="vp-rd__sez vp-rd__anno"
      >
        <h2 class="vp-rd__sez-tit">{{ g.anno }}</h2>
        <div class="vp-rd__tabwrap">
          <table class="vp-rd__tab">
            <thead>
              <tr>
                <th class="vp-rd__c-data">Data</th>
                <th>Descrizione</th>
                <th class="vp-rd__c-num">Dovuto</th>
                <th class="vp-rd__c-num">Pagato</th>
                <th class="vp-rd__c-num">Differenza</th>
                <th class="vp-rd__c-nota">Nota</th>
              </tr>
            </thead>
            <tbody>
              <template v-for="(r, i) in g.righe" :key="i">
                <tr>
                  <td class="vp-rd__c-data">{{ r.data ? formattaData(r.data) : '—' }}</td>
                  <td>{{ r.descrizione }}</td>
                  <td class="vp-rd__c-num vp-mono">{{ formattaEuro(r.dovuto) }}</td>
                  <td class="vp-rd__c-num vp-mono">
                    {{ r.pagato ? formattaEuro(r.pagato) : '—' }}
                  </td>
                  <td
                    class="vp-rd__c-num vp-mono"
                    :class="diffClass(diffRow(r) ?? 0)"
                  >
                    {{ formattaDiff(diffRow(r)) }}
                  </td>
                  <td class="vp-rd__c-nota">
                    <span :class="notaClass(r.nota)">{{ etichettaNota(r) }}</span>
                  </td>
                </tr>
                <tr v-if="r.allocazioni.length" class="vp-rd__cover">
                  <td></td>
                  <td colspan="5" class="vp-rd__cover-cell">
                    <span
                      v-for="(a, j) in r.allocazioni"
                      :key="j"
                      class="vp-rd__cover-item"
                    >
                      bonifico {{ formattaData(a.data) }}
                      {{ formattaEuro(a.bonifico_totale) }}/{{ formattaEuro(a.quota) }}<span
                        v-if="a.split"
                        class="vp-rd__star"
                      > *</span><template v-if="j < r.allocazioni.length - 1">; </template>
                    </span>
                  </td>
                </tr>
                <tr
                  v-for="(a, j) in r.allocazioni.filter(
                    (x) => Math.abs(x.resto) >= 0.005,
                  )"
                  :key="`r-${i}-${j}`"
                  class="vp-rd__resto-row"
                >
                  <td></td>
                  <td>
                    ↳ versato non imputato
                    <small>(bonifico {{ formattaData(a.data) }})</small>
                  </td>
                  <td></td>
                  <td></td>
                  <td
                    class="vp-rd__c-num vp-mono"
                    :class="diffClass(a.resto)"
                  >
                    {{ formattaEuro(a.resto) }}
                  </td>
                  <td></td>
                </tr>
              </template>
            </tbody>
            <tfoot>
              <tr>
                <td colspan="2"><strong>Totale {{ g.anno }}</strong></td>
                <td class="vp-rd__c-num vp-mono">{{ formattaEuro(g.dovuto) }}</td>
                <td class="vp-rd__c-num vp-mono">{{ formattaEuro(g.pagato) }}</td>
                <td
                  class="vp-rd__c-num vp-mono"
                  :class="diffClass(totDiffGruppo(g))"
                >
                  {{ formattaEuro(totDiffGruppo(g)) }}
                </td>
                <td></td>
              </tr>
              <tr
                v-if="parzialeByAnno.get(g.anno)"
                class="vp-rd__quad vp-rd__quad--prog"
              >
                <td colspan="4">
                  <strong>Saldo progressivo a fine {{ g.anno }}</strong>
                </td>
                <td
                  class="vp-rd__c-num vp-mono"
                  :class="diffClass(parzialeByAnno.get(g.anno)!.saldo_progressivo)"
                >
                  {{ formattaEuro(parzialeByAnno.get(g.anno)!.saldo_progressivo) }}
                </td>
                <td></td>
              </tr>
            </tfoot>
          </table>
        </div>
      </section>

      <section class="vp-rd__totali">
        <div class="vp-rd__tot-row">
          <span>Totale dovuto</span>
          <span class="vp-mono">{{ formattaEuro(rendiconto.totali.dovuto) }}</span>
        </div>
        <div class="vp-rd__tot-row">
          <span>Totale pagato (imputato)</span>
          <span class="vp-mono">{{ formattaEuro(rendiconto.totali.pagato) }}</span>
        </div>
        <div
          v-if="Math.abs(rendiconto.totali.resto) >= 0.01"
          class="vp-rd__tot-row"
        >
          <span>Versato non imputato (resti bonifici)</span>
          <span class="vp-mono">{{ formattaEuro(rendiconto.totali.resto) }}</span>
        </div>
        <div class="vp-rd__tot-row vp-rd__tot-row--saldo">
          <span>
            Sbilancio reale
            <small>
              ({{ rendiconto.totali.sbilancio_reale >= 0
                ? 'a tuo favore' : 'a tuo debito' }})
            </small>
          </span>
          <span class="vp-mono">
            {{ formattaEuro(rendiconto.totali.sbilancio_reale) }}
          </span>
        </div>
        <div class="vp-rd__tot-row vp-rd__tot-nota">
          <span>
            <small>di cui ancora da riconciliare (saldo-imputazioni):</small>
          </span>
          <span class="vp-mono">
            <small>{{ formattaEuro(rendiconto.totali.saldo) }}</small>
          </span>
        </div>
      </section>

      <section v-if="rendiconto.parziali_anno.length" class="vp-rd__sez">
        <h2 class="vp-rd__sez-tit">Parziali per anno (senza deposito)</h2>
        <div class="vp-rd__tabwrap">
          <table class="vp-rd__tab">
            <thead>
              <tr>
                <th>Anno</th>
                <th class="vp-rd__c-num">Dovuto</th>
                <th class="vp-rd__c-num">Pagato</th>
                <th class="vp-rd__c-num">Resto</th>
                <th class="vp-rd__c-num">Saldo anno</th>
                <th class="vp-rd__c-num">Progressivo</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="pa in rendiconto.parziali_anno" :key="pa.anno">
                <td>{{ pa.anno }}</td>
                <td class="vp-rd__c-num vp-mono">{{ formattaEuro(pa.dovuto) }}</td>
                <td class="vp-rd__c-num vp-mono">{{ formattaEuro(pa.pagato) }}</td>
                <td class="vp-rd__c-num vp-mono" :class="diffClass(pa.resto)">
                  {{ formattaEuro(pa.resto) }}
                </td>
                <td class="vp-rd__c-num vp-mono" :class="diffClass(pa.saldo_anno)">
                  {{ formattaEuro(pa.saldo_anno) }}
                </td>
                <td
                  class="vp-rd__c-num vp-mono"
                  :class="diffClass(pa.saldo_progressivo)"
                >
                  {{ formattaEuro(pa.saldo_progressivo) }}
                </td>
              </tr>
            </tbody>
            <tfoot>
              <tr>
                <td><strong>Totale</strong></td>
                <td class="vp-rd__c-num vp-mono">{{ formattaEuro(rendiconto.totali.dovuto) }}</td>
                <td class="vp-rd__c-num vp-mono">{{ formattaEuro(rendiconto.totali.pagato) }}</td>
                <td class="vp-rd__c-num vp-mono" :class="diffClass(rendiconto.totali.resto)">
                  {{ formattaEuro(rendiconto.totali.resto) }}
                </td>
                <td
                  class="vp-rd__c-num vp-mono"
                  :class="diffClass(rendiconto.totali.sbilancio_reale)"
                  colspan="2"
                >
                  {{ formattaEuro(rendiconto.totali.sbilancio_reale) }}
                </td>
              </tr>
            </tfoot>
          </table>
        </div>
      </section>

      <section v-if="rendiconto.versamenti.length" class="vp-rd__sez">
        <button
          type="button"
          class="vp-rd__expander"
          :aria-expanded="mostraVersamenti"
          @click="mostraVersamenti = !mostraVersamenti"
        >
          <span class="vp-rd__expander-ic">
            {{ mostraVersamenti ? '▾' : '▸' }}
          </span>
          Versamenti e imputazioni
          <small>(dettaglio completo di ogni bonifico)</small>
        </button>
        <div v-show="mostraVersamenti">
          <p class="vp-rd__legenda">
            <span class="vp-rd__star">*</span> il bonifico ha coperto anche
            altre voci: qui sotto la ripartizione completa di ogni versamento.
          </p>
          <div class="vp-rd__tabwrap">
            <table class="vp-rd__tab">
              <tbody>
                <template
                  v-for="(v, i) in rendiconto.versamenti"
                  :key="i"
                >
                  <tr class="vp-rd__bon">
                    <td class="vp-rd__c-data">{{ formattaData(v.data) }}</td>
                    <td>{{ v.descrizione || 'Bonifico' }}</td>
                    <td class="vp-rd__c-num vp-mono">{{ formattaEuro(v.importo) }}</td>
                  </tr>
                  <tr
                    v-for="(imp, j) in v.imputazioni"
                    :key="`${i}-${j}`"
                    class="vp-rd__imp"
                  >
                    <td></td>
                    <td class="vp-rd__imp-desc">→ {{ imp.descrizione }}</td>
                    <td class="vp-rd__c-num vp-mono">{{ formattaEuro(imp.quota) }}</td>
                  </tr>
                </template>
              </tbody>
              <tfoot>
                <tr>
                  <td colspan="2"><strong>Totale versato (imputato)</strong></td>
                  <td class="vp-rd__c-num vp-mono">
                    {{ formattaEuro(rendiconto.totale_versato) }}
                  </td>
                </tr>
              </tfoot>
            </table>
          </div>
        </div>
      </section>

      <section class="vp-rd__dep">
        <h2 class="vp-rd__sez-tit">Chiusura deposito</h2>
        <div class="vp-rd__tot-row">
          <span>
            Deposito versato
            <small v-if="rendiconto.deposito.data_versamento">
              (il {{ formattaData(rendiconto.deposito.data_versamento) }})
            </small>
          </span>
          <span class="vp-mono">{{ formattaEuro(rendiconto.deposito.versato) }}</span>
        </div>
        <div v-if="rendiconto.deposito.override" class="vp-rd__tot-row">
          <span>Importo da rendere <small>(override sul versato)</small></span>
          <span class="vp-mono">{{ formattaEuro(rendiconto.deposito.da_restituire) }}</span>
        </div>
        <div class="vp-rd__tot-row">
          <span>Sbilancio <small>(versato − dovuto)</small></span>
          <span class="vp-mono">
            {{ formattaEuro(rendiconto.totali.sbilancio_reale) }}
          </span>
        </div>
        <div class="vp-rd__tot-row vp-rd__tot-row--saldo">
          <span>
            {{ rendiconto.deposito.restituito_effettivo
              ? 'Deposito già restituito'
              : 'Netto da restituire' }}
          </span>
          <span class="vp-mono">
            {{ formattaEuro(rendiconto.deposito.netto_da_restituire) }}
          </span>
        </div>
        <p
          v-if="rendiconto.deposito.residuo_debito > 0"
          class="vp-rd__warn"
        >
          Il deposito non copre il debito: resterebbe a tuo carico un
          residuo di {{ formattaEuro(rendiconto.deposito.residuo_debito) }}.
        </p>
        <p
          v-if="rendiconto.deposito.data_restituzione_prevista && !rendiconto.deposito.restituito_effettivo"
          class="vp-rd__nota-dep"
        >
          Restituzione dovuta il
          {{ formattaData(rendiconto.deposito.data_restituzione_prevista) }}.
        </p>
      </section>

      <footer class="vp-rd__foot">
        Documento riepilogativo a fini di rendicontazione. Gli importi
        sono calcolati alla data di emissione.
      </footer>
    </article>

    <EmptyState
      v-else
      icon="error_outline"
      title="Rendiconto non disponibile"
      :message="store.errore ?? 'Impossibile caricare il rendiconto.'"
    />
  </q-page>
</template>

<script setup lang="ts">
import { computed, onMounted, onBeforeUnmount, ref, watch } from 'vue';
import {
  useRendicontoStore,
  type RendicontoRiga,
  type RendicontoSezione,
  type RendicontoParzialeAnno,
} from 'stores/rendiconto';
import { useDashboardStore } from 'stores/dashboard';
import { useFormatoEuro } from 'src/composables/useFormatoEuro';
import { useFormatoData } from 'src/composables/useFormatoData';
import EmptyState from 'src/components/EmptyState.vue';

const store = useRendicontoStore();
const dashboard = useDashboardStore();
const { formattaEuro } = useFormatoEuro();
const { formattaData } = useFormatoData();

// Il tenant_id dell'inquilino loggato arriva dalla dashboard inquilino.
const tenantId = computed<number | null>(
  () => dashboard.inquilinoData?.tenant.id ?? null,
);
const rendiconto = computed(() =>
  tenantId.value ? store.get(tenantId.value) : null,
);

type RigaCron = RendicontoRiga & { causale: string };
interface GruppoAnno {
  anno: number;
  righe: RigaCron[];
  dovuto: number;
  pagato: number;
}

const vista = ref<'causale' | 'cronologica'>('cronologica');
const mostraVersamenti = ref(false);

const cronologico = computed<GruppoAnno[]>(() => {
  const r = rendiconto.value;
  if (!r) return [];
  const rows: RigaCron[] = [];
  for (const s of r.sezioni) {
    for (const x of s.righe) rows.push({ ...x, causale: s.causale });
  }
  rows.sort((a, b) => (a.data ?? '').localeCompare(b.data ?? ''));
  const gruppi: GruppoAnno[] = [];
  let cur: GruppoAnno | null = null;
  for (const row of rows) {
    const anno = row.data ? Number(row.data.slice(0, 4)) : 0;
    if (!cur || cur.anno !== anno) {
      cur = { anno, righe: [], dovuto: 0, pagato: 0 };
      gruppi.push(cur);
    }
    cur.righe.push(row);
    cur.dovuto += row.dovuto;
    cur.pagato += row.pagato;
  }
  return gruppi;
});

const parzialeByAnno = computed<Map<number, RendicontoParzialeAnno>>(() => {
  const m = new Map<number, RendicontoParzialeAnno>();
  const r = rendiconto.value;
  if (r) for (const pa of r.parziali_anno) m.set(pa.anno, pa);
  return m;
});

const ETICHETTE_NOTA: Record<string, string> = {
  ok: '',
  non_pagata: 'Non pagata',
  parziale: 'Parziale',
  eccesso: 'In eccesso',
};
function etichettaNota(r: RendicontoRiga): string {
  if (r.nota === 'parziale') {
    return `Parziale (manca ${formattaEuro(r.dovuto - r.pagato)})`;
  }
  if (r.nota === 'eccesso') {
    return `In eccesso (+${formattaEuro(r.pagato - r.dovuto)})`;
  }
  return ETICHETTE_NOTA[r.nota] ?? '';
}
function notaClass(nota: string): string {
  if (nota === 'non_pagata' || nota === 'parziale') return 'vp-rd__nota--bad';
  if (nota === 'eccesso') return 'vp-rd__nota--warn';
  return '';
}
function diffClass(v: number): string {
  if (v < 0) return 'vp-rd__diff--neg';
  if (v > 0) return 'vp-rd__diff--pos';
  return '';
}
function diffRiga(_sez: RendicontoSezione, r: RendicontoRiga): number | null {
  return r.diff;
}
function diffRow(r: RigaCron): number | null {
  return r.diff;
}
function formattaDiff(v: number | null): string {
  if (v === null || v === 0) return '—';
  return formattaEuro(v);
}
function sommaResti(righe: { allocazioni: { resto: number }[] }[]): number {
  return righe.reduce(
    (s, r) => s + r.allocazioni.reduce((t, a) => t + (a.resto || 0), 0),
    0,
  );
}
function diffSez(sez: RendicontoSezione): number {
  return sez.righe.reduce((s, r) => s + (r.diff ?? 0), 0)
    + sommaResti(sez.righe);
}
function totDiffGruppo(g: GruppoAnno): number {
  return g.righe.reduce((s, r) => s + (r.diff ?? 0), 0)
    + sommaResti(g.righe);
}

function stampa(): void {
  mostraVersamenti.value = true;
  window.print();
}
function onBeforePrint(): void {
  mostraVersamenti.value = true;
}

function carica(): void {
  if (tenantId.value) void store.load(tenantId.value);
}

onMounted(async () => {
  document.body.classList.add('vp-print-doc');
  window.addEventListener('beforeprint', onBeforePrint);
  await dashboard.loadInquilino();
  carica();
});

watch(tenantId, (id) => {
  if (id) carica();
});

onBeforeUnmount(() => {
  document.body.classList.remove('vp-print-doc');
  window.removeEventListener('beforeprint', onBeforePrint);
});
</script>

<style scoped>
.vp-rd__toolbar {
  display: flex;
  align-items: center;
  gap: var(--vp-gap-2);
  margin-bottom: var(--vp-gap-4);
  flex-wrap: wrap;
}
.vp-rd__loader {
  display: flex;
  justify-content: center;
  padding: var(--vp-gap-7);
}
.vp-rd__doc {
  background: var(--vp-cream);
  border: 1px solid var(--vp-paper-3);
  border-radius: var(--vp-r-lg);
  padding: var(--vp-gap-6);
  max-width: 900px;
  margin: 0 auto;
}
.vp-rd__head {
  border-bottom: 2px solid var(--vp-ink);
  padding-bottom: var(--vp-gap-3);
  margin-bottom: var(--vp-gap-5);
}
.vp-rd__titolo {
  font-size: var(--vp-text-2xl);
  margin: 0 0 var(--vp-gap-2);
}
.vp-rd__meta {
  display: flex;
  flex-direction: column;
  gap: 2px;
  color: var(--vp-ink-2);
  font-size: var(--vp-text-sm);
}
.vp-rd__nominativo {
  font-size: var(--vp-text-md);
  font-weight: 600;
  color: var(--vp-ink);
}
.vp-rd__emesso {
  color: var(--vp-ink-3);
}
.vp-rd__intro {
  margin: var(--vp-gap-3) 0 0;
  color: var(--vp-ink-2);
  font-size: var(--vp-text-sm);
  background: var(--vp-paper-1);
  border-left: 3px solid var(--vp-terra, #b56a3b);
  padding: var(--vp-gap-2) var(--vp-gap-3);
  border-radius: 0 var(--vp-r-md, 8px) var(--vp-r-md, 8px) 0;
}
.vp-rd__sez {
  margin-bottom: var(--vp-gap-5);
}
.vp-rd__sez-tit {
  font-size: var(--vp-text-md);
  font-weight: 600;
  margin: 0 0 var(--vp-gap-2);
  color: var(--vp-ink);
}
.vp-rd__tabwrap {
  overflow-x: auto;
  -webkit-overflow-scrolling: touch;
}
.vp-rd__tab {
  width: 100%;
  border-collapse: collapse;
  font-size: var(--vp-text-sm);
  min-width: 520px;
}
.vp-rd__tab th,
.vp-rd__tab td {
  text-align: left;
  padding: 6px 8px;
  border-bottom: 1px solid var(--vp-paper-3);
}
.vp-rd__tab thead th {
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  color: var(--vp-ink-3);
  border-bottom: 1px solid var(--vp-ink-3);
}
.vp-rd__tab tfoot td {
  border-top: 1px solid var(--vp-ink-3);
  border-bottom: none;
}
.vp-rd__c-num {
  text-align: right;
  white-space: nowrap;
}
.vp-rd__c-data {
  white-space: nowrap;
}
.vp-rd__c-nota {
  white-space: nowrap;
}
.vp-rd__diff--neg {
  color: var(--vp-terra, #b56a3b);
}
.vp-rd__diff--pos {
  color: var(--vp-salvia, #4f6e3f);
}
.vp-rd__nota--bad {
  color: var(--vp-terra, #b56a3b);
  font-weight: 600;
}
.vp-rd__nota--warn {
  color: var(--vp-miele, #b08a1f);
}
.vp-rd__totali,
.vp-rd__dep {
  border-top: 2px solid var(--vp-ink);
  padding-top: var(--vp-gap-3);
  margin-top: var(--vp-gap-5);
}
.vp-rd__tot-row {
  display: flex;
  justify-content: space-between;
  padding: 4px 0;
  font-size: var(--vp-text-sm);
  gap: var(--vp-gap-3);
}
.vp-rd__tot-row--saldo {
  font-weight: 700;
  font-size: var(--vp-text-md);
  border-top: 1px solid var(--vp-paper-3);
  margin-top: var(--vp-gap-1);
  padding-top: var(--vp-gap-2);
}
.vp-rd__tot-nota {
  color: var(--vp-ink-3);
  padding-top: 0;
}
.vp-rd__quad td {
  border-top: 1px solid var(--vp-paper-3);
  color: var(--vp-ink-2, inherit);
}
.vp-rd__quad--prog td {
  border-top: 2px solid var(--vp-ink);
  font-size: var(--vp-text-md);
}
.vp-rd__resto-row td {
  border-bottom: 1px solid var(--vp-paper-3);
  padding-top: 0;
  color: var(--vp-ink-3);
  font-size: var(--vp-text-sm);
}
.vp-rd__resto-row small {
  color: var(--vp-ink-3);
}
.vp-rd__expander {
  display: flex;
  align-items: baseline;
  gap: 6px;
  width: 100%;
  background: none;
  border: none;
  padding: var(--vp-gap-2) 0;
  cursor: pointer;
  font: inherit;
  font-size: var(--vp-text-lg, 18px);
  font-weight: 700;
  color: var(--vp-ink);
  text-align: left;
}
.vp-rd__expander small {
  font-weight: 400;
  font-size: var(--vp-text-sm);
  color: var(--vp-ink-3);
}
.vp-rd__expander-ic {
  font-size: var(--vp-text-sm);
  color: var(--vp-ink-3);
}
.vp-rd__warn {
  color: var(--vp-terra, #b56a3b);
  font-size: var(--vp-text-sm);
  margin: var(--vp-gap-2) 0 0;
}
.vp-rd__nota-dep {
  color: var(--vp-ink-3);
  font-size: var(--vp-text-sm);
  margin: var(--vp-gap-1) 0 0;
}
.vp-rd__foot {
  margin-top: var(--vp-gap-6);
  color: var(--vp-ink-3);
  font-size: var(--vp-text-xs, 11px);
  border-top: 1px solid var(--vp-paper-3);
  padding-top: var(--vp-gap-2);
}
.vp-rd__cover td {
  border-bottom: 1px solid var(--vp-paper-3);
  padding-top: 0;
}
.vp-rd__cover-cell {
  font-size: var(--vp-text-xs, 11px);
  color: var(--vp-ink-3);
}
.vp-rd__cover-item {
  white-space: nowrap;
}
.vp-rd__star {
  color: var(--vp-terra, #b56a3b);
  font-weight: 700;
}
.vp-rd__legenda {
  font-size: var(--vp-text-sm);
  color: var(--vp-ink-3);
  margin: 0 0 var(--vp-gap-2);
}
.vp-rd__bon td {
  border-bottom: none;
  padding-top: var(--vp-gap-2);
  font-weight: 600;
}
.vp-rd__imp td {
  border-bottom: none;
  padding-top: 0;
  color: var(--vp-ink-2);
}
.vp-rd__imp-desc {
  padding-left: var(--vp-gap-3);
}
.vp-rd__vista {
  border: 1px solid var(--vp-paper-3);
  border-radius: var(--vp-r-md, 8px);
  overflow: hidden;
}

@media (max-width: 600px) {
  .vp-rd__doc {
    padding: var(--vp-gap-4) var(--vp-gap-3);
    border-radius: var(--vp-r-md, 8px);
  }
}

@media print {
  .no-print {
    display: none !important;
  }
  .vp-rd__doc {
    border: none;
    box-shadow: none;
    background: #fff;
    max-width: none;
    padding: 0;
  }
  .vp-rd__tabwrap {
    overflow-x: visible;
  }
  .vp-rd__tab {
    min-width: 0;
  }
  .vp-rd__anno {
    break-after: page;
  }
  .vp-rd__anno:last-of-type {
    break-after: auto;
  }
}
</style>
