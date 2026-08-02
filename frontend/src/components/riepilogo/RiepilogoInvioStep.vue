<script setup lang="ts">
// Anteprima e selezione dei riepiloghi addebiti da inviare.
//
// Copia adattata di `components/utenze/InvioStep.vue`, non un refactor
// condiviso: il wizard utenze è delicato e la semantica diverge in due punti.
//   1. la chiave è il **tenant_id**, non il receivable;
//   2. l'inquilino **uscito** resta in lista ma parte spento: la spunta è
//      abilitata, così sollecitarlo è possibile ma deve essere un gesto
//      deliberato (i suoi arretrati sono spesso partite storiche).
// Niente QR client-side: la mail non ne ha, il pagamento si fa in app.
import { computed, ref } from 'vue';
import VpIcon from 'src/components/utenze/VpIcon.vue';
import VpAvatar from 'src/components/utenze/VpAvatar.vue';
import { eur } from 'src/components/utenze/format';
import { inviabile as calcolaInviabile, type RiepilogoFE } from 'stores/riepilogoAddebiti';

const props = defineProps<{
  riepiloghi: RiepilogoFE[];
  escludi: number[]; // tenant_id di attivi tolti a mano
  includi: number[]; // tenant_id di ex inquilini rimessi a mano
  giorni: number;
  loading?: boolean;
}>();
const emit = defineEmits<{ invia: []; toggle: [tenantId: number] }>();

const openIdx = ref(-1);

function senzaNulla(r: RiepilogoFE): boolean {
  // Solo voci dichiarate: niente da sollecitare, il backend non invia.
  return !r.da_sollecitare;
}
function escluso(r: RiepilogoFE): boolean {
  return props.escludi.includes(r.tenant_id);
}
function bloccato(r: RiepilogoFE): boolean {
  // La spunta non si tocca solo quando non c'è proprio nulla da mandare.
  return senzaNulla(r) || !r.email;
}
function inviabile(r: RiepilogoFE): boolean {
  return calcolaInviabile(r, props.escludi, props.includi);
}

const daInviare = computed(() => props.riepiloghi.filter((r) => inviabile(r)));
const esclusiCount = computed(() => props.riepiloghi.length - daInviare.value.length);

function dataIt(iso: string | null): string {
  if (!iso) return '';
  const d = new Date(iso);
  return d.toLocaleDateString('it-IT', { day: '2-digit', month: '2-digit', year: 'numeric' });
}

function scadenzaLabel(v: { scadenza: string }): string {
  const oggi = new Date().toISOString().slice(0, 10);
  const [a, m, g] = v.scadenza.split('-');
  const data = `${g}/${m}/${a}`;
  return v.scadenza < oggi ? `scaduta il ${data}` : `in scadenza il ${data}`;
}

function toggleRiga(i: number): void {
  openIdx.value = openIdx.value === i ? -1 : i;
}
function onFlag(r: RiepilogoFE): void {
  if (bloccato(r)) return;
  emit('toggle', r.tenant_id);
}

/** Ex inquilini con arretrati che l'invio automatico sta saltando. Senza
 *  email restano fuori dal conto: la spunta è disabilitata e il banner
 *  suggerirebbe un gesto impossibile. */
const usciti = computed(() =>
  props.riepiloghi.filter((r) => r.uscito && !bloccato(r) && !inviabile(r)),
);
</script>

<template>
  <div class="layout">
    <!-- Destinatari -->
    <div class="vp-card list">
      <div class="list-head">
        <div class="vp-display" style="font-size: 20px">Riepiloghi agli inquilini</div>
        <span class="vp-badge vp-badge--wait">
          <VpIcon name="message" :size="13" /> anteprima
        </span>
      </div>

      <div v-if="loading && !riepiloghi.length" class="empty">
        <q-spinner-dots size="24px" color="primary" />
        <div>Sto preparando l'anteprima…</div>
      </div>

      <div v-else-if="!riepiloghi.length" class="empty">
        <VpIcon name="check" :size="22" color="var(--vp-ink-3)" />
        <div>
          Nessun inquilino da sollecitare: nessuno ha il canone del mese né voci
          scadute o in scadenza entro {{ giorni }} giorni.
        </div>
      </div>

      <template v-else>
        <div
          v-for="(r, i) in riepiloghi"
          :key="r.tenant_id"
          class="rowwrap"
          :class="{ last: i === riepiloghi.length - 1, off: !inviabile(r) }"
        >
          <div class="row">
            <label
              class="flag"
              :class="{ disabled: bloccato(r), checked: inviabile(r) }"
              @click.stop
            >
              <input
                type="checkbox"
                :checked="inviabile(r)"
                :disabled="bloccato(r)"
                @change="onFlag(r)"
              />
              <VpIcon v-if="inviabile(r)" name="check" :size="13" :stroke="2.6" color="#fff" />
            </label>

            <button class="row-btn" :class="{ open: openIdx === i }" @click="toggleRiga(i)">
              <VpAvatar :name="r.tenant_nominativo" :size="36" :hue="r.uscito ? 20 : 38" />
              <div class="row-main">
                <div class="row-name">
                  {{ r.tenant_nominativo }}
                  <span v-if="r.uscito" class="tag tag--out">ex inquilino</span>
                </div>
                <div class="row-mail">
                  <template v-if="senzaNulla(r)">
                    <span class="tag">solo voci in attesa di conferma</span>
                  </template>
                  <template v-else-if="!r.email">
                    <span class="tag tag--warn">nessuna email</span>
                  </template>
                  <template v-else-if="r.uscito && !inviabile(r)">
                    <span class="tag">fuori dall'invio: ha lasciato la casa</span>
                  </template>
                  <template v-else-if="escluso(r)">
                    <span class="tag">escluso dall'invio</span>
                  </template>
                  <template v-else>{{ r.email }}</template>
                  <span v-if="r.ultimo_invio_at" class="tag tag--sent">
                    già inviato il {{ dataIt(r.ultimo_invio_at) }}
                  </span>
                </div>
              </div>
              <div class="row-num">
                <span v-if="r.canone" class="vp-mono row-quota">{{ eur(r.canone.residuo) }}</span>
                <span class="row-sub">
                  {{ r.pendenti.length }}
                  {{ r.pendenti.length === 1 ? 'pendente' : 'pendenti' }}
                </span>
              </div>
              <VpIcon
                name="chevron"
                :size="16"
                color="var(--vp-ink-3)"
                :style="{
                  transform: openIdx === i ? 'rotate(90deg)' : 'none',
                  transition: 'transform .15s',
                }"
              />
            </button>
          </div>

          <div v-if="openIdx === i" class="msg-wrap">
            <div class="msg">
              <div class="msg-subj">{{ r.oggetto }}</div>
              <pre class="msg-corpo">{{ r.corpo }}</pre>
            </div>

            <div class="voci">
              <div v-if="r.canone" class="voci-blocco">
                <div class="voci-eyebrow">Canone del mese</div>
                <div class="voce">
                  <span>{{ r.canone.descrizione }}</span>
                  <span class="voce-scad">{{ scadenzaLabel(r.canone) }}</span>
                  <b class="vp-mono">{{ eur(r.canone.residuo) }}</b>
                </div>
              </div>
              <div v-if="r.pendenti.length" class="voci-blocco">
                <div class="voci-eyebrow">Pendenti (entro {{ giorni }} giorni)</div>
                <div v-for="v in r.pendenti" :key="v.id" class="voce">
                  <span>{{ v.descrizione }}</span>
                  <span class="voce-scad">{{ scadenzaLabel(v) }}</span>
                  <b class="vp-mono">{{ eur(v.residuo) }}</b>
                </div>
              </div>
              <div v-if="r.in_attesa.length" class="voci-blocco">
                <div class="voci-eyebrow">In attesa di conferma</div>
                <div v-for="v in r.in_attesa" :key="v.id" class="voce">
                  <span>{{ v.descrizione }}</span>
                  <span class="voce-scad">{{ scadenzaLabel(v) }}</span>
                  <b class="vp-mono">{{ eur(v.residuo) }}</b>
                </div>
              </div>
            </div>
          </div>
        </div>
      </template>
    </div>

    <!-- Riepilogo invio -->
    <aside class="aside">
      <div class="vp-card summary">
        <div class="vp-eyebrow">Riepilogo invio</div>
        <div class="vp-display sum-n">{{ daInviare.length }} email</div>
        <div class="muted" style="margin-bottom: 18px">
          pronte da inviare<span v-if="esclusiCount"> · {{ esclusiCount }} fuori</span>
        </div>

        <div class="kvs">
          <div class="kv">
            <span>Finestra pendenti</span><span class="b">{{ giorni }} giorni</span>
          </div>
          <div class="kv">
            <span>Con canone del mese</span>
            <span class="b">{{ daInviare.filter((r) => r.canone).length }}</span>
          </div>
          <div v-if="usciti.length" class="kv">
            <span>Ex inquilini non sollecitati</span>
            <span class="b">{{ usciti.length }}</span>
          </div>
          <div class="kv"><span>Canale</span><span class="b">Email</span></div>
        </div>

        <button
          class="vp-btn vp-btn--primary full"
          :disabled="!daInviare.length || loading"
          :style="{ opacity: daInviare.length && !loading ? 1 : 0.5 }"
          @click="emit('invia')"
        >
          <VpIcon name="message" :size="16" color="#fff" />
          Invia {{ daInviare.length }}
          {{ daInviare.length === 1 ? 'riepilogo' : 'riepiloghi' }}
        </button>
      </div>

      <div v-if="usciti.length" class="vp-banner" style="font-size: 13px">
        <VpIcon name="message" :size="18" :stroke="2.4" color="var(--vp-clay)" />
        <div>
          {{ usciti.length }}
          {{ usciti.length === 1 ? 'ex inquilino ha' : 'ex inquilini hanno' }}
          arretrati ma non
          {{ usciti.length === 1 ? 'riceve' : 'ricevono' }}: spesso sono partite
          storiche mai riconciliate. Per sollecitarli davvero spuntali a mano.
        </div>
      </div>

      <div class="vp-banner vp-banner--ok" style="font-size: 13px">
        <VpIcon name="check" :size="18" :stroke="2.4" color="var(--vp-sage-deep)" />
        <div>
          La mail è un <b>promemoria</b>: elenca il canone del mese e le voci in
          scadenza, senza totali né QR. Il conto completo e i pagamenti restano
          nell'app.
        </div>
      </div>
    </aside>
  </div>
</template>

<style scoped>
.muted {
  font-size: 13px;
  color: var(--vp-ink-3);
}
.layout {
  display: grid;
  grid-template-columns: 1fr 340px;
  gap: 22px;
  align-items: start;
}

.list {
  overflow: hidden;
}
.list-head {
  padding: 16px 22px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  border-bottom: 1px solid var(--vp-paper-3);
}
.empty {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 22px;
  font-size: 13px;
  color: var(--vp-ink-2);
}
.rowwrap {
  border-bottom: 1px solid var(--vp-paper-3);
}
.rowwrap.last {
  border-bottom: none;
}
.rowwrap.off {
  background: var(--vp-paper-2);
}
.rowwrap.off .row-name,
.rowwrap.off .row-quota {
  color: var(--vp-ink-3);
}
.row {
  display: flex;
  align-items: center;
  gap: 4px;
  padding-left: 16px;
}
.flag {
  flex-shrink: 0;
  width: 22px;
  height: 22px;
  border-radius: 6px;
  border: 1.5px solid var(--vp-paper-3);
  background: var(--vp-paper);
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  position: relative;
}
.flag input {
  position: absolute;
  inset: 0;
  opacity: 0;
  cursor: pointer;
  margin: 0;
}
.flag.checked {
  background: var(--vp-sage);
  border-color: var(--vp-sage);
}
.flag.disabled {
  opacity: 0.4;
  cursor: not-allowed;
}
.flag.disabled input {
  cursor: not-allowed;
}
.row-btn {
  flex: 1;
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 14px 22px 14px 8px;
  background: transparent;
  border: none;
  cursor: pointer;
  text-align: left;
  font-family: inherit;
  color: var(--vp-ink);
}
.row-btn.open {
  background: var(--vp-paper-2);
}
.row-main {
  flex: 1;
}
.row-name {
  font-weight: 500;
  font-size: 15px;
  display: flex;
  align-items: center;
  gap: 8px;
}
.row-mail {
  font-size: 12px;
  color: var(--vp-ink-3);
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}
.tag {
  display: inline-block;
  font-size: 11px;
  padding: 1px 8px;
  border-radius: var(--vp-r-pill);
  background: var(--vp-paper-3);
  color: var(--vp-ink-2);
}
.tag--out {
  background: var(--vp-clay-soft);
  color: var(--vp-clay);
}
.tag--warn {
  background: var(--vp-clay-soft);
  color: var(--vp-clay);
}
.tag--sent {
  background: var(--vp-sage-soft, var(--vp-paper-3));
  color: var(--vp-sage-deep);
}
.row-num {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 2px;
}
.row-quota {
  font-size: 15px;
  font-weight: 600;
}
.row-sub {
  font-size: 11px;
  color: var(--vp-ink-3);
}
.msg-wrap {
  padding: 4px 22px 22px 78px;
}
.msg {
  background: var(--vp-paper-2);
  border-radius: 12px;
  padding: 18px 20px;
  font-size: 13px;
  color: var(--vp-ink-2);
  line-height: 1.6;
}
.msg-subj {
  font-weight: 600;
  color: var(--vp-ink);
  margin-bottom: 8px;
  font-size: 14px;
}
.msg-corpo {
  white-space: pre-wrap;
  font-family: inherit;
  margin: 0;
}
.voci {
  margin-top: 12px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.voci-blocco {
  background: var(--vp-cream);
  border: 1px solid var(--vp-paper-3);
  border-radius: 12px;
  padding: 12px 16px;
}
.voci-eyebrow {
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  color: var(--vp-ink-3);
  margin-bottom: 8px;
}
.voce {
  display: grid;
  grid-template-columns: 1fr auto auto;
  gap: 12px;
  align-items: baseline;
  font-size: 13px;
  padding: 3px 0;
}
.voce-scad {
  color: var(--vp-ink-3);
  font-size: 12px;
  white-space: nowrap;
}

.aside {
  position: sticky;
  top: 0;
  display: flex;
  flex-direction: column;
  gap: 14px;
}
.summary {
  padding: 22px 24px;
}
.sum-n {
  font-size: 34px;
  margin-top: 6px;
}
.kvs {
  display: flex;
  flex-direction: column;
  gap: 9px;
  margin-bottom: 18px;
}
.kv {
  display: flex;
  justify-content: space-between;
  font-size: 14px;
}
.kv > span:first-child {
  color: var(--vp-ink-2);
}
.kv .b,
.b {
  font-weight: 600;
}
.full {
  width: 100%;
}

@media (max-width: 900px) {
  .layout {
    grid-template-columns: 1fr;
  }
  .aside {
    position: static;
  }
}
</style>
