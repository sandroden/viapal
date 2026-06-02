<script setup lang="ts">
// STEP 3 · INVIO
// Anteprime espandibili per inquilino (sinistra) + riepilogo invio (destra).
// Ogni riga ha un flag "Invia": gli inquilini usciti sono esclusi d'ufficio
// (non vivono più qui); per gli altri il proprietario può togliere il flag
// (es. chi ha già saldato). Mostra il testo REALE dell'email (dry-run).
import { ref, computed } from 'vue';
import VpIcon from './VpIcon.vue';
import VpAvatar from './VpAvatar.vue';
import { eur, criterioFrase } from './format';
import type { Criterio, PeriodoView, QuotaView } from './format';
import { useEpcQr, type EpcDati } from 'src/composables/useEpcQr';

const props = defineProps<{
  periodo: PeriodoView;
  quote: QuotaView[];
  criterio: Criterio;
  needsEmetti: boolean;
  giaInviatoAt?: string | null;
  escludi: number[]; // receivable_id esclusi a mano
}>();
const emit = defineEmits<{ invia: []; emetti: []; toggle: [receivableId: number] }>();

const openIdx = ref(0);
const critFrase = computed(() => criterioFrase(props.criterio));

function uscito(q: QuotaView): boolean {
  return q.notificare === false;
}
function escluso(q: QuotaView): boolean {
  return props.escludi.includes(Number(q.receivableId));
}
function inviabile(q: QuotaView): boolean {
  return !uscito(q) && !escluso(q);
}

const daInviare = computed(() => props.quote.filter((q) => inviabile(q)));
const totale = computed(() => daInviare.value.reduce((s, q) => s + q.quota, 0));
const media = computed(() => (daInviare.value.length ? totale.value / daInviare.value.length : 0));
const esclusiCount = computed(() => props.quote.length - daInviare.value.length);

// QR dell'avviso attualmente aperto (uno alla volta), come nell'email reale.
const epcOpen = computed<EpcDati | null>(() => {
  const q = props.quote[openIdx.value];
  if (!q?.bonifico) return null;
  return {
    beneficiario: q.bonifico.beneficiario,
    iban: q.bonifico.iban,
    causale: q.bonifico.causale,
    importo: q.bonifico.importo,
  };
});
const { dataUrl: qrOpen } = useEpcQr(epcOpen);

function toggle(i: number): void {
  openIdx.value = openIdx.value === i ? -1 : i;
}
function onFlag(q: QuotaView): void {
  if (uscito(q) || q.receivableId == null) return;
  emit('toggle', Number(q.receivableId));
}
</script>

<template>
  <div class="layout">
    <!-- Destinatari -->
    <div class="vp-card list">
      <div class="list-head">
        <div class="vp-display" style="font-size: 20px">Avvisi agli inquilini</div>
        <span class="vp-badge vp-badge--wait"><VpIcon name="message" :size="13" /> anteprima</span>
      </div>

      <div v-if="needsEmetti" class="empty">
        <VpIcon name="lock" :size="22" color="var(--vp-ink-3)" />
        <div>
          Gli addebiti non sono ancora stati creati. Torna al passo
          <b>Ripartizione</b> e premi <b>Crea addebiti</b>: poi qui vedrai l'anteprima degli avvisi.
        </div>
      </div>

      <template v-else>
        <div
          v-for="(q, i) in quote"
          :key="q.id"
          class="rowwrap"
          :class="{ last: i === quote.length - 1, off: !inviabile(q) }"
        >
          <div class="row">
            <!-- Flag invia -->
            <label class="flag" :class="{ disabled: uscito(q), checked: inviabile(q) }" @click.stop>
              <input
                type="checkbox"
                :checked="inviabile(q)"
                :disabled="uscito(q)"
                @change="onFlag(q)"
              />
              <VpIcon
                v-if="inviabile(q)"
                name="check"
                :size="13"
                :stroke="2.6"
                color="#fff"
              />
            </label>

            <button class="row-btn" :class="{ open: openIdx === i }" @click="toggle(i)">
              <VpAvatar :name="q.nome" :size="36" :hue="q.avatarHue" />
              <div class="row-main">
                <div class="row-name">{{ q.nome }}</div>
                <div class="row-mail">
                  <template v-if="uscito(q)">
                    <span class="tag tag--out">non verrà inviato · ex inquilino</span>
                  </template>
                  <template v-else-if="escluso(q)">
                    <span class="tag">escluso dall'invio</span>
                  </template>
                  <template v-else>{{ q.email || 'nessuna email' }}</template>
                </div>
              </div>
              <span class="vp-mono row-quota">{{ eur(q.quota) }}</span>
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
            <div v-if="q.corpo" class="msg">
              <div class="msg-subj">{{ q.oggetto }}</div>
              <pre class="msg-corpo">{{ q.corpo }}</pre>
            </div>
            <div v-else class="msg">
              <div class="msg-subj">Viapal — conguaglio utenze · {{ periodo.label }}</div>
              <div>Ciao {{ q.nome }},</div>
              <div style="margin-top: 8px">
                è disponibile il conteggio delle utenze per {{ periodo.label }} (periodo
                {{ periodo.range }}).
              </div>
              <div style="margin-top: 4px">
                Il tuo importo è di <b class="ink">{{ eur(q.quota) }}</b> (luce, gas e TARI
                ripartiti {{ critFrase }}).
              </div>
              <div style="margin-top: 10px">Dettaglio:</div>
              <ul class="msg-ul">
                <li>Luce: {{ eur(q.per.Luce) }}</li>
                <li>Gas: {{ eur(q.per.Gas) }}</li>
                <li>TARI: {{ eur(q.per.TARI) }}</li>
                <li>Giorni di presenza nel periodo: {{ q.giorni }}</li>
              </ul>
            </div>

            <!-- QR + IBAN/causale: identico a quanto incluso nell'email -->
            <div v-if="q.bonifico" class="bonifico">
              <div class="bonifico-eyebrow">Paga con bonifico (nell'email)</div>
              <div class="bonifico-row">
                <img v-if="qrOpen" :src="qrOpen" alt="QR bonifico" class="bonifico-qr" />
                <div class="bonifico-dati">
                  <div class="bd"><span>Beneficiario</span><b>{{ q.bonifico.beneficiario }}</b></div>
                  <div class="bd">
                    <span>IBAN</span><b class="vp-mono">{{ q.bonifico.iban }}</b>
                  </div>
                  <div class="bd"><span>Causale</span><b>{{ q.bonifico.causale }}</b></div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </template>
    </div>

    <!-- Riepilogo -->
    <aside class="aside">
      <div class="vp-card summary">
        <div class="vp-eyebrow">Riepilogo invio</div>
        <div class="vp-display sum-n">{{ daInviare.length }} avvisi</div>
        <div class="muted" style="margin-bottom: 18px">
          pronti per {{ periodo.label
          }}<span v-if="esclusiCount"> · {{ esclusiCount }} esclusi</span>
        </div>

        <div class="kvs">
          <div class="kv">
            <span>Totale da inviare</span><span class="vp-mono b">{{ eur(totale) }}</span>
          </div>
          <div class="kv"><span>Quota media</span><span class="vp-mono">{{ eur(media) }}</span></div>
          <div class="kv"><span>Canale</span><span class="b">Email</span></div>
        </div>

        <div v-if="giaInviatoAt" class="inviato-nota">
          <VpIcon name="check" :size="14" :stroke="2.4" color="var(--vp-sage-deep)" />
          Avvisi già inviati
        </div>

        <button
          class="vp-btn vp-btn--primary full"
          :disabled="!daInviare.length"
          :style="{ opacity: daInviare.length ? 1 : 0.5 }"
          @click="emit('invia')"
        >
          <VpIcon name="message" :size="16" color="#fff" />
          {{ giaInviatoAt ? 'Invia di nuovo' : `Invia ${daInviare.length} avvisi` }}
        </button>
      </div>

      <div class="vp-banner vp-banner--ok" style="font-size: 13px">
        <VpIcon name="check" :size="18" :stroke="2.4" color="var(--vp-sage-deep)" />
        <div>
          Gli inquilini attivi ricevono l'importo e il <b>dettaglio per utenza</b>. Chi è uscito non
          riceve l'avviso ma mantiene l'addebito.
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
.ink {
  color: var(--vp-ink);
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
}
.row-mail {
  font-size: 12px;
  color: var(--vp-ink-3);
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
.row-quota {
  font-size: 15px;
  font-weight: 600;
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
.msg-ul {
  margin: 4px 0 0;
  padding-left: 18px;
}
.bonifico {
  margin-top: 12px;
  padding: 14px 16px;
  background: var(--vp-cream);
  border: 1px solid var(--vp-paper-3);
  border-radius: 12px;
}
.bonifico-eyebrow {
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  color: var(--vp-ink-3);
  margin-bottom: 10px;
}
.bonifico-row {
  display: flex;
  gap: 16px;
  align-items: center;
  flex-wrap: wrap;
}
.bonifico-qr {
  width: 120px;
  height: 120px;
  background: #fff;
  padding: 6px;
  border-radius: 8px;
  box-shadow: var(--vp-shadow-1);
  flex-shrink: 0;
}
.bonifico-dati {
  display: flex;
  flex-direction: column;
  gap: 6px;
  font-size: 13px;
  min-width: 180px;
}
.bd {
  display: flex;
  flex-direction: column;
  gap: 1px;
}
.bd > span {
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: 0.03em;
  color: var(--vp-ink-3);
}
.bd > b {
  color: var(--vp-ink);
  font-weight: 500;
  word-break: break-all;
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
.inviato-nota {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  color: var(--vp-sage-deep);
  margin-bottom: 10px;
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
