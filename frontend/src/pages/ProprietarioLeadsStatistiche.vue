<template>
  <q-page padding class="vp-lst">
    <header class="vp-lst__head">
      <div>
        <div class="vp-eyebrow">Cerca inquilini</div>
        <h1 class="vp-display vp-lst__titolo">Statistiche per canale</h1>
      </div>
      <q-btn
        flat
        dense
        no-caps
        color="primary"
        icon="arrow_back"
        label="Alla lista"
        :to="{ name: 'p-leads' }"
      />
    </header>

    <q-banner v-if="errore" class="bg-red-1 text-negative q-mb-md" rounded>
      {{ errore }}
    </q-banner>

    <div v-if="caricamento" class="vp-lst__vuoto">
      <q-spinner-dots size="32px" color="primary" />
    </div>

    <div v-else-if="!stat || !stat.totale.totale" class="vp-lst__vuoto">
      <q-icon name="bar_chart" size="42px" color="grey-5" />
      <p>Nessun contatto ancora: le statistiche arrivano con i primi.</p>
    </div>

    <template v-else>
      <!-- I totali rispondono alla domanda di fondo — «sta funzionando?» —
           prima di dire da dove. -->
      <div class="vp-lst__totali" data-testid="stat-totali">
        <div class="vp-lst__tot">
          <span class="vp-lst__tot-n">{{ stat.totale.totale }}</span>
          <span class="vp-lst__tot-l">contatti</span>
        </div>
        <div class="vp-lst__tot">
          <span class="vp-lst__tot-n">{{ stat.totale.contattati }}</span>
          <span class="vp-lst__tot-l">contattati</span>
        </div>
        <div class="vp-lst__tot">
          <span class="vp-lst__tot-n">
            {{ stat.totale.risposto }}
            <small>{{ percentuale(stat.totale) }}</small>
          </span>
          <span class="vp-lst__tot-l">hanno risposto</span>
        </div>
        <div class="vp-lst__tot">
          <span class="vp-lst__tot-n">{{ stat.totale.attivi }}</span>
          <span class="vp-lst__tot-l">attivi</span>
        </div>
      </div>

      <div class="vp-lst__lista">
        <article
          v-for="c in stat.canali"
          :key="c.canale"
          class="vp-card vp-lst__card"
          data-testid="stat-canale"
        >
          <div class="vp-lst__riga1">
            <span class="vp-lst__nome">
              <q-icon :name="iconaCanale(c.canale)" size="20px" />{{ c.nome }}
            </span>
            <span v-if="c.ultimo_at" class="vp-lst__quando">
              ultimo contatto: {{ quando(c.ultimo_at) }}
            </span>
          </div>

          <dl class="vp-lst__numeri">
            <div>
              <dt>contatti</dt>
              <dd>{{ c.totale }}</dd>
            </div>
            <div>
              <dt>contattati</dt>
              <dd>{{ c.contattati }}</dd>
            </div>
            <div>
              <dt>hanno risposto</dt>
              <dd>
                {{ c.risposto }} <small>{{ percentuale(c) }}</small>
              </dd>
            </div>
            <div>
              <dt>attivi</dt>
              <dd>{{ c.attivi }}</dd>
            </div>
            <div>
              <dt>trovato altro</dt>
              <dd>{{ c.persi }}</dd>
            </div>
            <div>
              <dt>scartati</dt>
              <dd>{{ c.scartati }}</dd>
            </div>
          </dl>

          <!-- La barra è la quota di risposte sui contatti: quanto rende il
               canale, a colpo d'occhio, senza leggere i numeri. -->
          <div
            class="vp-lst__barra"
            role="img"
            :aria-label="`${c.risposto} risposte su ${c.totale} contatti`"
          >
            <div class="vp-lst__barra-pieno" :style="{ width: quota(c) }" />
          </div>

          <ul v-if="c.gruppi?.length" class="vp-lst__gruppi">
            <li v-for="g in c.gruppi" :key="g.id" class="vp-lst__gruppo">
              <span class="vp-lst__gruppo-nome">{{ g.nome }}</span>
              <span class="vp-lst__gruppo-n">
                {{ g.totale }} contatti · {{ g.contattati }} contattati · {{ g.risposto }}
                risposte
              </span>
            </li>
          </ul>
        </article>
      </div>
    </template>
  </q-page>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue';
import { messaggioErrore } from 'src/utils/apiErrors';
import { quando } from 'src/utils/quando';
import {
  CANALI,
  useLeadsStore,
  type CanaleLead,
  type RigaStatistica,
  type StatisticheLead,
} from 'src/stores/leads';

const store = useLeadsStore();
const stat = ref<StatisticheLead | null>(null);
const caricamento = ref(true);
const errore = ref<string | null>(null);

const ICONE_CANALE = Object.fromEntries(CANALI.map((c) => [c.value, c.icona])) as Record<
  CanaleLead,
  string
>;

function iconaCanale(canale: CanaleLead): string {
  return ICONE_CANALE[canale] ?? 'more_horiz';
}

/** Risposte sui contattati: è la resa del canale. Se non si è scritto a
 *  nessuno (risposte a un post nostro) il denominatore è il totale. */
function percentuale(r: RigaStatistica): string {
  const base = r.contattati || r.totale;
  if (!base) return '';
  return `${Math.round((r.risposto / base) * 100)}%`;
}

/** La barra invece è sempre sui contatti: due canali si confrontano solo con
 *  lo stesso denominatore. */
function quota(r: RigaStatistica): string {
  if (!r.totale) return '0%';
  return `${Math.round((r.risposto / r.totale) * 100)}%`;
}

onMounted(async () => {
  try {
    stat.value = await store.fetchStatistiche();
  } catch (e: unknown) {
    errore.value = messaggioErrore(e, 'Errore nel caricamento delle statistiche');
  } finally {
    caricamento.value = false;
  }
});
</script>

<style scoped>
.vp-lst__head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 20px;
}
.vp-lst__titolo {
  font-size: var(--vp-text-3xl);
  margin: 2px 0 0;
}

.vp-lst__totali {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
  margin-bottom: 18px;
}
@media (min-width: 600px) {
  .vp-lst__totali {
    grid-template-columns: repeat(4, minmax(0, 1fr));
  }
}
.vp-lst__tot {
  display: flex;
  flex-direction: column;
  gap: 2px;
  padding: 12px 14px;
  border-radius: var(--vp-r-md);
  background: var(--vp-paper-2);
}
.vp-lst__tot-n {
  font-family: var(--vp-font-display);
  font-size: var(--vp-text-2xl);
  line-height: 1.1;
  color: var(--vp-ink);
  font-variant-numeric: tabular-nums;
}
.vp-lst__tot-n small,
.vp-lst__numeri small {
  font-family: var(--vp-font-ui);
  font-size: var(--vp-text-sm);
  color: var(--vp-sage-deep);
  margin-left: 4px;
}
.vp-lst__tot-l {
  font-size: var(--vp-text-xs);
  color: var(--vp-ink-3);
}

.vp-lst__lista {
  display: grid;
  gap: 14px;
  grid-template-columns: 1fr;
}
@media (min-width: 1100px) {
  .vp-lst__lista {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}
.vp-lst__card {
  padding: 16px;
}
.vp-lst__riga1 {
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 6px 12px;
}
.vp-lst__nome {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  font-family: var(--vp-font-display);
  font-size: var(--vp-text-lg);
  color: var(--vp-ink);
}
.vp-lst__quando {
  font-size: var(--vp-text-xs);
  color: var(--vp-ink-3);
  white-space: nowrap;
}

.vp-lst__numeri {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 10px 12px;
  margin: 14px 0 0;
}
.vp-lst__numeri div {
  display: flex;
  flex-direction: column;
}
.vp-lst__numeri dt {
  font-size: var(--vp-text-xs);
  color: var(--vp-ink-3);
}
.vp-lst__numeri dd {
  margin: 0;
  font-size: var(--vp-text-lg);
  color: var(--vp-ink);
  font-variant-numeric: tabular-nums;
}

.vp-lst__barra {
  margin-top: 14px;
  height: 6px;
  border-radius: var(--vp-r-pill);
  background: var(--vp-paper-3);
  overflow: hidden;
}
.vp-lst__barra-pieno {
  height: 100%;
  border-radius: var(--vp-r-pill);
  background: var(--vp-sage);
  transition: width 0.3s;
}

.vp-lst__gruppi {
  list-style: none;
  margin: 12px 0 0;
  padding: 10px 0 0;
  border-top: 1px solid var(--vp-paper-3);
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.vp-lst__gruppo {
  display: flex;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 2px 10px;
  font-size: var(--vp-text-sm);
}
.vp-lst__gruppo-nome {
  color: var(--vp-ink-2);
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
}
.vp-lst__gruppo-n {
  color: var(--vp-ink-3);
  white-space: nowrap;
  font-variant-numeric: tabular-nums;
}

.vp-lst__vuoto {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 10px;
  padding: 48px 0;
  color: var(--vp-ink-3);
  text-align: center;
}
</style>
