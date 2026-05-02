<template>
  <q-page padding class="vp-p-home">
    <header class="vp-p-home__hero">
      <div class="vp-eyebrow">Dashboard rendita</div>
      <h1 class="vp-display vp-p-home__titolo">
        Buon lavoro, {{ saluto }}
      </h1>
      <p class="vp-p-home__sottotitolo">
        Quadro complessivo dell'anno {{ annoCorrente }}.
      </p>
    </header>

    <div v-if="store.loadingProprietario && !data" class="vp-p-home__loader">
      <q-spinner color="primary" size="32px" />
    </div>

    <template v-else-if="data">
      <section class="vp-p-home__kpi">
        <KpiCard
          label="Incasso anno"
          :value="data.kpi.incasso_anno_corrente"
          is-currency
          :sublabel="`Mese corrente: ${formattaEuro(data.kpi.incasso_mese_corrente)}`"
          accent
        />
        <KpiCard
          label="Spese anno"
          :value="data.kpi.spese_anno_corrente"
          is-currency
          sublabel="Totale spese registrate"
        />
        <KpiCard
          label="Pagamenti in ritardo"
          :value="data.kpi.ritardi_count"
          :sublabel="data.kpi.ritardi_count === 0 ? 'Nessuno' : 'Da sollecitare'"
        />
        <KpiCard
          label="In scadenza (7 gg)"
          :value="data.kpi.in_scadenza_count"
          sublabel="Prossime scadenze"
        />
      </section>

      <section class="vp-p-home__sezione">
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

      <section class="vp-p-home__sezione">
        <div class="vp-p-home__sezione-head">
          <div>
            <div class="vp-eyebrow">In scadenza</div>
            <h2 class="vp-display vp-p-home__h2">Prossimi 7 giorni</h2>
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
    </template>
  </q-page>
</template>

<script setup lang="ts">
import { computed, onMounted } from 'vue';
import { useAuthStore } from 'stores/auth';
import { useDashboardStore } from 'stores/dashboard';
import KpiCard from 'src/components/KpiCard.vue';
import SemaforoBadge, { type SemaforoLivello } from 'src/components/SemaforoBadge.vue';
import EmptyState from 'src/components/EmptyState.vue';
import { useFormatoEuro } from 'src/composables/useFormatoEuro';
import { useFormatoData } from 'src/composables/useFormatoData';

const auth = useAuthStore();
const store = useDashboardStore();
const { formattaEuro } = useFormatoEuro();
const { formattaData } = useFormatoData();

const annoCorrente = new Date().getFullYear();
const saluto = computed(() => auth.user?.first_name || auth.user?.username || 'Proprietario');
const data = computed(() => store.proprietarioData);

onMounted(() => {
  void store.loadProprietario();
});

function livelloDaGiorni(g: number): SemaforoLivello {
  if (g > 7) return 'argilla_scuro';
  if (g > 0) return 'argilla_chiaro';
  if (g > -7) return 'miele';
  return 'salvia';
}
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
  margin: 0;
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
</style>
