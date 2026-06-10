<template>
  <q-page padding class="vp-ce">
    <header class="vp-ce__head">
      <div>
        <div class="vp-eyebrow">Redditività dell'immobile</div>
        <h1 class="vp-display vp-ce__titolo">Conto economico</h1>
      </div>
      <div class="vp-ce__head-azioni">
        <q-select
          v-model="annoSelezionato"
          dense
          outlined
          :options="anniDisponibili"
          label="Anno"
          class="vp-ce__anno"
        />
        <q-btn-toggle
          v-model="basis"
          no-caps
          unelevated
          toggle-color="primary"
          :options="[
            { label: 'Cassa', value: 'cassa' },
            { label: 'Competenza', value: 'competenza' },
          ]"
        />
      </div>
    </header>

    <p class="vp-ce__hint">
      <template v-if="basis === 'cassa'">
        Lettura per <strong>cassa</strong>: conta ciò che è stato davvero
        incassato e speso nell'anno, alla data del pagamento.
      </template>
      <template v-else>
        Lettura per <strong>competenza</strong>: conta ciò che è maturato
        nell'anno (canoni dovuti, bollette del periodo), anche se pagato
        dopo. È la misura della redditività vera.
      </template>
    </p>

    <div v-if="store.errore" class="text-negative q-mb-md">{{ store.errore }}</div>
    <q-inner-loading :showing="store.loading" />

    <template v-if="data">
      <div class="vp-ce__griglia">
        <!-- Scaletta conto economico -->
        <q-card flat bordered class="vp-ce__card">
          <q-card-section>
            <div class="vp-eyebrow">Anno {{ data.anno }}</div>
            <q-list dense class="vp-ce__scaletta">
              <q-item dense>
                <q-item-section>Affitti</q-item-section>
                <q-item-section side class="vp-mono">
                  {{ formattaEuro(blocco.ricavi.rent) }}
                </q-item-section>
              </q-item>
              <q-item dense>
                <q-item-section>Utenze rifatturate</q-item-section>
                <q-item-section side class="vp-mono">
                  {{ formattaEuro(blocco.ricavi.utility) }}
                </q-item-section>
              </q-item>
              <q-item dense>
                <q-item-section>Extra e registrazioni</q-item-section>
                <q-item-section side class="vp-mono">
                  {{ formattaEuro(blocco.ricavi.extra) }}
                </q-item-section>
              </q-item>
              <q-separator spaced />
              <q-item dense class="vp-ce__riga-forte">
                <q-item-section>Ricavi</q-item-section>
                <q-item-section side class="vp-mono">
                  {{ formattaEuro(blocco.ricavi.totale) }}
                </q-item-section>
              </q-item>
              <q-item dense>
                <q-item-section>
                  Spese ordinarie
                  <q-btn
                    flat
                    dense
                    size="sm"
                    no-caps
                    color="primary"
                    label="dettaglio"
                    @click="dettaglioSpese = 'ordinarie'"
                  />
                </q-item-section>
                <q-item-section side class="vp-mono">
                  −{{ formattaEuro(blocco.spese_ordinarie) }}
                </q-item-section>
              </q-item>
              <q-item dense class="vp-ce__riga-forte">
                <q-item-section>Margine operativo</q-item-section>
                <q-item-section side class="vp-mono" :class="segnoClass(blocco.margine_operativo)">
                  {{ formattaEuro(blocco.margine_operativo) }}
                </q-item-section>
              </q-item>
              <q-item dense>
                <q-item-section>
                  Spese straordinarie
                  <q-btn
                    v-if="data.spese_dettaglio.straordinarie.length"
                    flat
                    dense
                    size="sm"
                    no-caps
                    color="primary"
                    label="dettaglio"
                    @click="dettaglioSpese = 'straordinarie'"
                  />
                </q-item-section>
                <q-item-section side class="vp-mono">
                  −{{ formattaEuro(blocco.spese_straordinarie) }}
                </q-item-section>
              </q-item>
              <q-separator spaced />
              <q-item class="vp-ce__riga-utile">
                <q-item-section>Utile {{ data.anno }}</q-item-section>
                <q-item-section side class="vp-mono" :class="segnoClass(blocco.utile)">
                  {{ formattaEuro(blocco.utile) }}
                </q-item-section>
              </q-item>
            </q-list>

            <q-banner
              v-if="basis === 'competenza' && data.competenza.non_incassato > 0"
              dense
              rounded
              class="vp-ce__banner-scoperto"
            >
              Di questi, <strong>{{ formattaEuro(data.competenza.non_incassato) }}</strong>
              ({{ data.competenza.non_incassato_voci }} voci) non sono ancora
              stati incassati<template v-if="data.competenza.insoluti > 0">,
              di cui {{ formattaEuro(data.competenza.insoluti) }} insoluti</template>.
            </q-banner>
          </q-card-section>
        </q-card>

        <!-- Utile pro-quota -->
        <q-card flat bordered class="vp-ce__card">
          <q-card-section>
            <div class="vp-eyebrow">Utile pro-quota</div>
            <p class="vp-ce__nota">
              Quanto ha <em>guadagnato</em> ciascun fratello, in base alla
              quota di proprietà. È diverso da quanto ha incassato: il
              dare/avere è in
              <router-link to="/p/saldi-fratelli">Saldi fratelli</router-link>.
            </p>
            <q-list dense separator>
              <q-item v-for="pq in data.utile_pro_quota" :key="pq.owner_id" dense>
                <q-item-section>
                  {{ pq.nominativo }}
                  <span class="vp-ce__quota">({{ (pq.quota * 100).toFixed(2) }}%)</span>
                </q-item-section>
                <q-item-section side class="vp-mono" :class="segnoClass(utileProQuotaVal(pq))">
                  {{ formattaEuro(utileProQuotaVal(pq)) }}
                </q-item-section>
              </q-item>
            </q-list>

            <div class="vp-eyebrow q-mt-lg">Occupazione stanze</div>
            <div v-if="data.occupazione.tasso_medio !== null" class="vp-ce__occupazione-media">
              media {{ (data.occupazione.tasso_medio * 100).toFixed(0) }}%
            </div>
            <div
              v-for="o in data.occupazione.per_stanza"
              :key="o.stanza"
              class="vp-ce__occupazione-riga"
            >
              <span class="vp-ce__occupazione-nome">{{ o.stanza }}</span>
              <q-linear-progress
                :value="o.tasso"
                size="10px"
                rounded
                color="primary"
                track-color="grey-3"
                class="vp-ce__occupazione-bar"
              />
              <span class="vp-mono vp-ce__occupazione-pct">
                {{ (o.tasso * 100).toFixed(0) }}%
              </span>
            </div>
          </q-card-section>
        </q-card>
      </div>

      <!-- Serie multi-anno -->
      <section class="vp-ce__sezione">
        <div class="vp-eyebrow">Andamento per anno (cassa)</div>
        <div class="vp-ce__serie">
          <BarChartAnni :righe="righeGrafico" :height="220" />
          <q-markup-table flat bordered dense class="vp-ce__tabella-anni">
            <thead>
              <tr>
                <th class="text-left">Anno</th>
                <th class="text-right">Ricavi</th>
                <th class="text-right">Spese</th>
                <th class="text-right">Utile</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="r in serieOrdinata" :key="r.anno">
                <td>{{ r.anno }}</td>
                <td class="text-right vp-mono">{{ formattaEuro(r.ricavi) }}</td>
                <td class="text-right vp-mono">{{ formattaEuro(r.spese) }}</td>
                <td class="text-right vp-mono" :class="segnoClass(r.utile)">
                  {{ formattaEuro(r.utile) }}
                </td>
              </tr>
            </tbody>
          </q-markup-table>
        </div>
      </section>
    </template>

    <!-- Dialog dettaglio spese -->
    <q-dialog :model-value="dettaglioSpese !== null" @update:model-value="dettaglioSpese = null">
      <q-card class="vp-ce__dialog">
        <q-card-section class="row items-center q-pb-none">
          <div class="vp-eyebrow">
            Spese {{ dettaglioSpese }} — {{ data?.anno }}
          </div>
          <q-space />
          <q-btn icon="close" flat round dense v-close-popup />
        </q-card-section>
        <q-card-section>
          <q-list dense separator>
            <q-item v-for="v in vociDettaglioSpese" :key="v.nome" dense>
              <q-item-section>{{ v.nome }}</q-item-section>
              <q-item-section side class="vp-mono">
                {{ formattaEuro(v.importo) }}
              </q-item-section>
            </q-item>
            <q-item v-if="vociDettaglioSpese.length === 0">
              <q-item-section class="text-grey-7">Nessuna voce.</q-item-section>
            </q-item>
          </q-list>
        </q-card-section>
      </q-card>
    </q-dialog>
  </q-page>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue';
import BarChartAnni from 'src/components/BarChartAnni.vue';
import {
  useContoEconomicoStore,
  type UtileProQuota,
  type VoceCategoria,
} from 'stores/contoEconomico';
import { useFormatoEuro } from 'src/composables/useFormatoEuro';

const store = useContoEconomicoStore();
const { formattaEuro } = useFormatoEuro();

const basis = ref<'cassa' | 'competenza'>('cassa');
const annoSelezionato = ref<number>(new Date().getFullYear());
const dettaglioSpese = ref<'ordinarie' | 'straordinarie' | null>(null);

const data = computed(() => store.data);
const blocco = computed(() =>
  basis.value === 'cassa' ? data.value!.cassa : data.value!.competenza,
);
const anniDisponibili = computed(() => data.value?.anni_disponibili ?? [annoSelezionato.value]);

const serieOrdinata = computed(() =>
  [...(data.value?.serie_anni ?? [])].sort((a, b) => b.anno - a.anno),
);

const righeGrafico = computed(() =>
  (data.value?.serie_anni ?? []).map((r) => ({
    anno: r.anno,
    perCategoria: { Ricavi: r.ricavi },
  })),
);

const vociDettaglioSpese = computed<VoceCategoria[]>(() => {
  if (!data.value || !dettaglioSpese.value) return [];
  return data.value.spese_dettaglio[dettaglioSpese.value];
});

function utileProQuotaVal(pq: UtileProQuota): number {
  return basis.value === 'cassa' ? pq.utile_cassa : pq.utile_competenza;
}

function segnoClass(v: number): string {
  if (v > 0.005) return 'vp-ce__pos';
  if (v < -0.005) return 'vp-ce__neg';
  return '';
}

onMounted(async () => {
  await store.fetch(annoSelezionato.value);
});

watch(annoSelezionato, async (anno) => {
  await store.fetch(anno);
});
</script>

<style scoped>
.vp-ce__head {
  display: flex;
  justify-content: space-between;
  align-items: flex-end;
  flex-wrap: wrap;
  gap: var(--vp-gap-3);
}
.vp-ce__head-azioni {
  display: flex;
  gap: var(--vp-gap-2);
  align-items: center;
}
.vp-ce__anno {
  width: 120px;
}
.vp-ce__titolo {
  font-size: var(--vp-text-2xl);
  margin: var(--vp-gap-1) 0 0;
}
.vp-ce__hint {
  color: var(--vp-ink-2);
  font-size: 0.85rem;
  margin: var(--vp-gap-2) 0 var(--vp-gap-4);
}
.vp-ce__griglia {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
  gap: var(--vp-gap-3);
}
.vp-ce__card {
  background: var(--vp-cream);
}
.vp-ce__scaletta .vp-ce__riga-forte {
  font-weight: 600;
}
.vp-ce__riga-utile {
  font-weight: 700;
  font-size: 1.1rem;
}
.vp-ce__banner-scoperto {
  background: #fdf3e4;
  border: 1px solid #e8cf9a;
  margin-top: var(--vp-gap-2);
  font-size: 0.85rem;
}
.vp-ce__nota {
  color: var(--vp-ink-2);
  font-size: 0.8rem;
  margin: var(--vp-gap-1) 0 var(--vp-gap-2);
}
.vp-ce__quota {
  color: var(--vp-ink-2);
  font-size: 0.8rem;
}
.vp-ce__occupazione-media {
  color: var(--vp-ink-2);
  font-size: 0.8rem;
  margin-bottom: var(--vp-gap-1);
}
.vp-ce__occupazione-riga {
  display: flex;
  align-items: center;
  gap: var(--vp-gap-2);
  margin-bottom: 6px;
}
.vp-ce__occupazione-nome {
  width: 130px;
  font-size: 0.85rem;
}
.vp-ce__occupazione-bar {
  flex: 1;
}
.vp-ce__occupazione-pct {
  width: 44px;
  text-align: right;
  font-size: 0.85rem;
}
.vp-ce__sezione {
  margin-top: var(--vp-gap-5);
}
.vp-ce__serie {
  display: grid;
  grid-template-columns: minmax(320px, 2fr) minmax(260px, 1fr);
  gap: var(--vp-gap-3);
  align-items: start;
  margin-top: var(--vp-gap-2);
}
@media (max-width: 800px) {
  .vp-ce__serie {
    grid-template-columns: 1fr;
  }
}
.vp-ce__tabella-anni {
  background: var(--vp-cream);
}
.vp-ce__dialog {
  background: var(--vp-cream);
  min-width: min(480px, 95vw);
}
.vp-ce__pos {
  color: #2e7a39;
}
.vp-ce__neg {
  color: #b14a2b;
}
.vp-mono {
  font-variant-numeric: tabular-nums;
}
</style>
