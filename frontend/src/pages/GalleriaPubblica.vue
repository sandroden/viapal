<template>
  <q-page class="gal">
    <!-- Header pubblico -->
    <nav class="gnav">
      <div class="wrap gnav-in">
        <div class="wordmark"><b>Viapal</b> · annuncio</div>
        <div class="gnav-actions">
          <q-btn
            v-if="canEdit"
            :color="editMode ? 'primary' : undefined"
            :flat="!editMode"
            :outline="!editMode"
            dense
            no-caps
            :icon="editMode ? 'check' : 'edit'"
            :label="editMode ? 'Fine modifica' : 'Modifica'"
            @click="editMode = !editMode"
          />
          <a href="#posizione" class="vp-btn vp-btn--ghost gnav-cta">Come arrivare</a>
        </div>
      </div>
    </nav>

    <div v-if="loading" class="wrap gal-state">
      <q-spinner size="32px" color="primary" />
    </div>

    <div v-else-if="!g" class="wrap gal-state">
      <div class="vp-banner vp-banner--late">
        {{ errore || 'Galleria non disponibile.' }}
      </div>
    </div>

    <template v-else>
      <!-- Hero -->
      <section class="hero">
        <ImageSlot
          class="hero-slot"
          :url="g.foto_hero"
          :editable="editMode"
          :uploading="uploading"
          :radius="0"
          placeholder="Foto principale · esterno o zona giorno"
          @upload="(f) => uploadSingolare('foto_hero', f)"
          @remove="removeSingolare('foto_hero')"
        />
        <div class="hero-scrim"></div>
        <div class="hero-content wrap">
          <div class="hero-eyebrow">
            <EditableText :value="t('hero_eyebrow')" :editable="editMode" @save="(v) => setTesto('hero_eyebrow', v)">
              {{ t('hero_eyebrow', 'Stanza in condivisione · disponibile') }}
            </EditableText>
          </div>
          <h1 class="hero-title">
            <EditableText :value="t('hero_titolo')" :editable="editMode" @save="(v) => setTesto('hero_titolo', v)">
              {{ t('hero_titolo', g.nome) }}
            </EditableText>
          </h1>
          <div class="hero-addr">
            <EditableText :value="t('hero_indirizzo')" :editable="editMode" @save="(v) => setTesto('hero_indirizzo', v)">
              {{ t('hero_indirizzo', g.indirizzo || '—') }}
            </EditableText>
          </div>
          <div class="hero-facts">
            <div v-for="f in factsDef" :key="f.key" class="hero-fact">
              <b>
                <EditableText
                  :value="String(facts[f.key] ?? '')"
                  :editable="editMode"
                  input-type="number"
                  @save="(v) => setFact(f.key, v)"
                >{{ facts[f.key] ?? '—' }}</EditableText>
              </b>
              <span>{{ f.label }}</span>
            </div>
          </div>
        </div>
        <div class="hero-cta">
          <a href="#posizione" class="vp-btn vp-btn--primary">Richiedi informazioni</a>
        </div>
      </section>

      <!-- Pill nav -->
      <nav class="wrap pillwrap">
        <div class="pills">
          <a class="pill" href="#planimetria">Planimetria</a>
          <a
            v-for="r in roomsPubbliche"
            :key="'pill' + r.id"
            class="pill"
            :class="{ 'is-unavail': !r.disponibile }"
            :href="`#room-${r.id}`"
          >{{ r.nome }}<template v-if="!r.disponibile"> · occupata</template></a>
          <a class="pill" href="#posizione">Posizione</a>
        </div>
      </nav>

      <div class="wrap">
        <!-- Planimetria -->
        <section class="block" id="planimetria">
          <div class="block-head">
            <div>
              <div class="block-eyebrow">Planimetria</div>
              <h2 class="block-title">Come è organizzata la casa</h2>
              <div class="block-sub">
                <EditableText :value="t('planimetria_nota')" :editable="editMode" @save="(v) => setTesto('planimetria_nota', v)">
                  {{ t('planimetria_nota', 'I numeri in planimetria corrispondono alle stanze qui sotto.') }}
                </EditableText>
              </div>
            </div>
          </div>
          <div class="plan-grid">
            <ImageSlot
              class="plan-slot"
              :url="g.foto_planimetria"
              :editable="editMode"
              :uploading="uploading"
              :radius="16"
              placeholder="Planimetria (esporta immagine da Floorplanner)"
              @upload="(f) => uploadSingolare('foto_planimetria', f)"
              @remove="removeSingolare('foto_planimetria')"
            />
            <div class="legend">
              <a
                v-for="(r, i) in roomsPubbliche"
                :key="'leg' + r.id"
                class="legend-item"
                :class="{ 'is-unavail': !r.disponibile }"
                :href="`#room-${r.id}`"
              >
                <span class="legend-num" :style="{ background: r.colore || 'var(--vp-ink-3)' }">{{ i + 1 }}</span>
                <span class="legend-name">{{ r.nome }}</span>
                <span v-if="!r.disponibile" class="legend-tag">Occupata</span>
                <span class="legend-mq">{{ r.superficie_mq ? `${fmtMq(r.superficie_mq)} mq` : '' }}</span>
              </a>
            </div>
          </div>
        </section>

        <!-- Sezioni stanza -->
        <section
          v-for="(r, i) in roomsPubbliche"
          :key="r.id"
          class="room"
          :class="{ 'is-unavail': !r.disponibile }"
          :id="`room-${r.id}`"
        >
          <div class="room-head">
            <span class="room-dot" :style="{ background: r.colore || 'var(--vp-ink-3)' }"></span>
            <h3 class="room-name">
              {{ i + 1 }}.
              <EditableText :value="r.nome" :editable="editMode" @save="(v) => setRoom(r, 'nome', v)">{{ r.nome }}</EditableText>
            </h3>
            <span v-if="r.superficie_mq" class="room-mq">{{ fmtMq(r.superficie_mq) }} mq</span>
            <span v-if="r.prezzo_mensile" class="room-price">
              <EditableText :value="r.prezzo_mensile" :editable="editMode" input-type="number" @save="(v) => setRoom(r, 'prezzo_mensile', v)">
                {{ fmtEuro(r.prezzo_mensile) }}/mese
              </EditableText>
            </span>
            <q-btn
              v-else-if="editMode"
              flat
              dense
              no-caps
              size="sm"
              icon="add"
              label="prezzo"
              @click="setRoom(r, 'prezzo_mensile', '0')"
            />
            <span v-if="!r.disponibile" class="room-unavail">
              <q-icon name="lock" size="14px" /> Non disponibile
            </span>
            <span v-else-if="r.libera_dal" class="room-free">Libera dal {{ fmtData(r.libera_dal) }}</span>
            <q-toggle
              v-if="editMode"
              :model-value="r.disponibile"
              label="disponibile"
              size="sm"
              dense
              @update:model-value="(v) => setRoom(r, 'disponibile', v)"
            />
          </div>

          <p class="room-desc">
            <EditableText :value="r.descrizione" :editable="editMode" textarea @save="(v) => setRoom(r, 'descrizione', v)">
              {{ r.descrizione || (editMode ? 'Aggiungi una descrizione…' : '') }}
            </EditableText>
          </p>

          <div v-if="editMode" class="room-edit-row">
            <span class="room-edit-lbl">Libera dal:</span>
            <EditableText :value="r.libera_dal || ''" :editable="true" input-type="date" @save="(v) => setRoom(r, 'libera_dal', v || null)">
              {{ r.libera_dal ? fmtData(r.libera_dal) : 'imposta' }}
            </EditableText>
          </div>

          <div v-if="!r.disponibile && !editMode" class="room-unavail-note">
            Foto non disponibili — stanza attualmente occupata
          </div>
          <div v-else class="pgrid">
            <div v-for="foto in r.foto" :key="foto.id" class="ph">
              <ImageSlot :url="foto.url" :editable="editMode" :expandable="true" @expand="openLB" @remove="removeImage(foto.id)" />
            </div>
            <div v-if="editMode" class="ph ph-add">
              <ImageSlot
                :editable="true"
                :uploading="uploading"
                :placeholder="`Aggiungi foto ${r.nome.toLowerCase()}`"
                @upload="(f) => uploadRoomImage(r.id, f)"
              />
            </div>
          </div>
        </section>

        <!-- Posizione -->
        <section class="block" id="posizione">
          <div class="block-head">
            <div>
              <div class="block-eyebrow">Posizione &amp; raggiungibilità</div>
              <h2 class="block-title">Dove si trova</h2>
            </div>
          </div>
          <div class="locate">
            <ImageSlot
              class="map-slot"
              :url="g.foto_mappa"
              :editable="editMode"
              :uploading="uploading"
              :radius="16"
              placeholder="Screenshot mappa · indirizzo e dintorni"
              @upload="(f) => uploadSingolare('foto_mappa', f)"
              @remove="removeSingolare('foto_mappa')"
            />
            <div class="info-col">
              <div v-for="c in posizioneCards" :key="c.key" class="info-card">
                <div class="info-ic"><q-icon :name="c.icon" size="18px" /></div>
                <div class="info-body">
                  <h4>{{ c.title }}</h4>
                  <p>
                    <EditableText :value="posizione[c.key] || ''" :editable="editMode" textarea @save="(v) => setPosizione(c.key, v)">
                      {{ posizione[c.key] || (editMode ? 'Aggiungi…' : '') }}
                    </EditableText>
                  </p>
                  <div v-if="c.key === 'mezzi' && (posizione.mezzi_chips?.length)" class="chiprow">
                    <span v-for="(chip, ci) in posizione.mezzi_chips" :key="ci" class="chip">{{ chip }}</span>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </section>
      </div>

      <footer class="gal-footer">
        Pagina pubblica · nessun accesso richiesto — per candidarti scrivi tramite il modulo di contatto.
      </footer>

      <!-- Lightbox -->
      <div class="lightbox" :class="{ open: lbUrl }" @click.self="lbUrl = null">
        <button class="lightbox-close" @click="lbUrl = null">✕</button>
        <img v-if="lbUrl" :src="lbUrl" alt="" />
      </div>

      <!-- Errore inline -->
      <q-banner v-if="errore && editMode" class="gal-err">{{ errore }}</q-banner>
    </template>
  </q-page>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue';
import { useRoute } from 'vue-router';
import { storeToRefs } from 'pinia';
import {
  useGalleriaStore,
  type StanzaPubblica,
  type FactsPubblici,
  type PosizionePubblica,
} from 'stores/galleria';
import { useAuthStore } from 'stores/auth';
import ImageSlot from 'components/ImageSlot.vue';
import EditableText from 'components/EditableText.vue';

const route = useRoute();
const store = useGalleriaStore();
const auth = useAuthStore();
const { galleria: g, loading, uploading, errore } = storeToRefs(store);

const editMode = ref(false);
const lbUrl = ref<string | null>(null);

const canEdit = computed(
  () => auth.role === 'proprietario' && !auth.isImpersonating,
);

const roomsPubbliche = computed(() => g.value?.rooms ?? []);

const factsDef = [
  { key: 'mq_totali', label: 'mq totali' },
  { key: 'n_camere', label: 'camere' },
  { key: 'n_bagni', label: 'bagni' },
  { key: 'n_posti_letto', label: 'posti letto' },
] as const;

const posizioneCards = [
  { key: 'indirizzo', title: 'Indirizzo', icon: 'place' },
  { key: 'mezzi', title: 'Mezzi pubblici', icon: 'directions_bus' },
  { key: 'parcheggio', title: 'Parcheggio & note pratiche', icon: 'local_parking' },
  { key: 'regole', title: 'Regole della casa', icon: 'shield' },
] as const;

const facts = computed<FactsPubblici>(
  () => g.value?.testi_pubblici?.facts ?? {},
);
const posizione = computed<PosizionePubblica>(
  () => g.value?.testi_pubblici?.posizione ?? {},
);

function t(key: string, fallback = ''): string {
  const v = (g.value?.testi_pubblici as Record<string, unknown>)?.[key];
  return (v as string) || fallback;
}

// --- Formattazione --------------------------------------------------------
function fmtMq(v: string | null): string {
  if (!v) return '';
  return String(parseFloat(v)).replace('.', ',');
}
function fmtEuro(v: string | null): string {
  if (!v) return '';
  return `€ ${parseFloat(v).toLocaleString('it-IT')}`;
}
function fmtData(v: string): string {
  const d = new Date(v);
  return Number.isNaN(d.getTime()) ? v : d.toLocaleDateString('it-IT');
}

// --- Salvataggi testi -----------------------------------------------------
function testiCopy() {
  return JSON.parse(JSON.stringify(g.value?.testi_pubblici ?? {}));
}
async function setTesto(key: string, value: string) {
  if (!g.value) return;
  const testi = testiCopy();
  testi[key] = value;
  await store.patchProperty(g.value.id, { testi_pubblici: testi });
}
async function setFact(key: string, value: string) {
  if (!g.value) return;
  const testi = testiCopy();
  testi.facts = { ...(testi.facts ?? {}), [key]: value === '' ? null : Number(value) };
  await store.patchProperty(g.value.id, { testi_pubblici: testi });
}
async function setPosizione(key: string, value: string) {
  if (!g.value) return;
  const testi = testiCopy();
  testi.posizione = { ...(testi.posizione ?? {}), [key]: value };
  await store.patchProperty(g.value.id, { testi_pubblici: testi });
}

// --- Salvataggi stanza ----------------------------------------------------
async function setRoom(r: StanzaPubblica, key: string, value: unknown) {
  await store.patchRoom(r.id, { [key]: value });
}

// --- Immagini -------------------------------------------------------------
async function uploadSingolare(campo: 'foto_hero' | 'foto_planimetria' | 'foto_mappa', file: File) {
  if (!g.value) return;
  await store.uploadSingolare({ propertyId: g.value.id, campo, file });
}
async function removeSingolare(campo: 'foto_hero' | 'foto_planimetria' | 'foto_mappa') {
  if (!g.value) return;
  // Rimuovere = PATCH del campo immagine a null (ImageField allow_null).
  await store.patchProperty(g.value.id, { [campo]: null });
}
async function uploadRoomImage(roomId: number, file: File) {
  if (!g.value) return;
  await store.uploadImage({ propertyId: g.value.id, roomId, file });
}
async function removeImage(id: number) {
  await store.deleteImage(id);
}

function openLB(url: string) {
  lbUrl.value = url;
}

async function load() {
  const slug = route.params.slug as string;
  await store.fetchPublic(slug);
  if (!auth.loaded) await auth.fetchMe();
}

onMounted(load);
watch(() => route.params.slug, load);
</script>

<style scoped>
.gal {
  background: var(--vp-paper);
  color: var(--vp-ink);
  font-family: var(--vp-font-ui);
  padding: 0;
}
.wrap { max-width: 1180px; margin: 0 auto; padding: 0 28px; }
.gal-state { padding: 80px 28px; display: flex; justify-content: center; }

.gnav {
  position: sticky; top: 0; z-index: 30;
  background: color-mix(in oklab, var(--vp-paper) 88%, transparent);
  backdrop-filter: blur(8px);
  border-bottom: 1px solid var(--vp-paper-3);
}
.gnav-in { display: flex; align-items: center; justify-content: space-between; height: 64px; }
.gnav-actions { display: flex; align-items: center; gap: 12px; }
.gnav-cta { height: 36px; font-size: 13px; text-decoration: none; }
.wordmark { font-family: var(--vp-font-display); font-size: 20px; color: var(--vp-ink); }
.wordmark b { font-weight: 600; }

.hero { position: relative; height: 78vh; min-height: 460px; max-height: 720px; }
.hero-slot { position: absolute; inset: 0; width: 100%; height: 100%; }
.hero-scrim {
  position: absolute; inset: 0; pointer-events: none;
  background: linear-gradient(180deg, rgba(20,15,10,0.05) 0%, rgba(20,15,10,0.55) 100%);
}
.hero-content { position: absolute; left: 0; right: 0; bottom: 0; padding: 40px 28px 36px; color: #fbf7f0; }
.hero-eyebrow { font-size: 12px; letter-spacing: .1em; text-transform: uppercase; opacity: .85; margin-bottom: 8px; }
.hero-title { font-family: var(--vp-font-display); font-size: clamp(30px, 5vw, 52px); line-height: 1.05; margin: 0 0 10px; }
.hero-addr { font-size: 15px; opacity: .9; }
.hero-facts { display: flex; gap: 22px; margin-top: 20px; flex-wrap: wrap; }
.hero-fact { display: flex; flex-direction: column; }
.hero-fact b { font-family: var(--vp-font-mono); font-size: 22px; font-weight: 600; }
.hero-fact span { font-size: 12px; opacity: .8; }
.hero-cta { position: absolute; right: 28px; bottom: 36px; z-index: 4; }
.hero-cta .vp-btn, .gnav-cta { text-decoration: none; }

.pillwrap { border-bottom: 1px solid var(--vp-paper-3); }
.pills { display: flex; gap: 8px; overflow-x: auto; padding: 12px 0; scrollbar-width: none; }
.pills::-webkit-scrollbar { display: none; }
.pill {
  flex: none; padding: 8px 14px; border-radius: 999px;
  background: var(--vp-paper-2); border: 1px solid var(--vp-paper-3);
  color: var(--vp-ink-2); font-size: 13px; font-weight: 500;
  white-space: nowrap; text-decoration: none; transition: background .15s, color .15s;
}
.pill:hover { background: var(--vp-terra-soft); color: var(--vp-terra-deep); }
.pill.is-unavail { opacity: .55; }

.block { padding: 56px 0; }
.block-head { display: flex; align-items: baseline; justify-content: space-between; gap: 16px; margin-bottom: 22px; flex-wrap: wrap; }
.block-eyebrow { font-size: 11px; letter-spacing: .08em; text-transform: uppercase; color: var(--vp-ink-3); font-weight: 500; margin-bottom: 6px; }
.block-title { font-family: var(--vp-font-display); font-size: 28px; margin: 0; }
.block-sub { color: var(--vp-ink-2); font-size: 14px; max-width: 560px; }

.plan-grid { display: grid; grid-template-columns: 1.5fr 1fr; gap: 24px; align-items: start; }
.plan-slot { width: 100%; aspect-ratio: 4/3; }
.legend { display: flex; flex-direction: column; gap: 2px; }
.legend-item { display: flex; align-items: center; gap: 12px; padding: 12px 14px; border-radius: 12px; text-decoration: none; color: var(--vp-ink); }
.legend-item:hover { background: var(--vp-paper-2); }
.legend-num { width: 26px; height: 26px; border-radius: 50%; flex: none; display: flex; align-items: center; justify-content: center; font-family: var(--vp-font-mono); font-size: 12px; font-weight: 600; color: #fff; }
.legend-name { flex: 1; font-weight: 500; font-size: 14.5px; }
.legend-mq { font-size: 12.5px; color: var(--vp-ink-3); font-family: var(--vp-font-mono); }
.legend-item.is-unavail .legend-name { color: var(--vp-ink-3); }
.legend-item.is-unavail .legend-num { background: var(--vp-ink-4) !important; }
.legend-tag { font-size: 10.5px; font-weight: 600; color: var(--vp-clay); background: var(--vp-clay-soft); padding: 2px 7px; border-radius: 999px; }

.room { padding: 44px 0; border-top: 1px solid var(--vp-paper-3); }
.room-head { display: flex; align-items: center; gap: 14px; margin-bottom: 6px; flex-wrap: wrap; }
.room-dot { width: 14px; height: 14px; border-radius: 4px; flex: none; }
.room-name { font-family: var(--vp-font-display); font-size: 24px; margin: 0; white-space: nowrap; }
.room-mq { font-size: 12.5px; color: var(--vp-ink-3); background: var(--vp-paper-2); padding: 4px 10px; border-radius: 999px; font-family: var(--vp-font-mono); }
.room-price { font-size: 13px; font-weight: 600; color: var(--vp-terra-deep); background: var(--vp-terra-soft); padding: 4px 12px; border-radius: 999px; }
.room-free { font-size: 12.5px; color: var(--vp-sage-deep); background: var(--vp-sage-soft); padding: 4px 12px; border-radius: 999px; }
.room-unavail { font-size: 12px; font-weight: 600; color: var(--vp-clay); background: var(--vp-clay-soft); padding: 4px 12px; border-radius: 999px; display: flex; align-items: center; gap: 6px; }
.room.is-unavail .room-name { color: var(--vp-ink-3); }
.room-desc { color: var(--vp-ink-2); font-size: 14.5px; max-width: 640px; margin: 8px 0 20px; }
.room-edit-row { display: flex; align-items: center; gap: 8px; margin-bottom: 16px; font-size: 13px; color: var(--vp-ink-3); }
.room-edit-lbl { font-size: 12px; }
.room-unavail-note { padding: 28px; border-radius: 14px; background: var(--vp-paper-2); color: var(--vp-ink-3); font-size: 13.5px; text-align: center; border: 1px dashed var(--vp-paper-3); }

.pgrid { display: grid; grid-template-columns: repeat(4, 1fr); grid-auto-rows: 150px; gap: 10px; }
.pgrid .ph:nth-child(4n+1) { grid-column: span 2; grid-row: span 2; }
.ph { position: relative; border-radius: 14px; overflow: hidden; }
.ph-add { grid-column: span 1 !important; grid-row: span 1 !important; }

.locate { display: grid; grid-template-columns: 1fr 1fr; gap: 24px; }
.map-slot { width: 100%; height: 340px; }
.info-col { display: flex; flex-direction: column; gap: 16px; }
.info-card { display: flex; gap: 12px; padding: 16px 18px; background: var(--vp-cream); border: 1px solid var(--vp-paper-3); border-radius: 14px; }
.info-ic { width: 36px; height: 36px; border-radius: 10px; background: var(--vp-paper-2); color: var(--vp-terra); display: flex; align-items: center; justify-content: center; flex: none; }
.info-body h4 { margin: 0 0 3px; font-size: 14.5px; font-weight: 600; }
.info-body p { margin: 0; font-size: 13.5px; color: var(--vp-ink-2); line-height: 1.5; }
.chiprow { display: flex; gap: 8px; flex-wrap: wrap; margin-top: 8px; }
.chip { font-size: 12px; padding: 5px 10px; border-radius: 999px; background: var(--vp-paper-2); color: var(--vp-ink-2); }

.gal-footer { padding: 40px 28px 60px; text-align: center; color: var(--vp-ink-3); font-size: 12.5px; }

.lightbox { position: fixed; inset: 0; background: rgba(15,12,9,.92); z-index: 100; display: none; align-items: center; justify-content: center; padding: 40px; }
.lightbox.open { display: flex; }
.lightbox img { max-width: 100%; max-height: 100%; border-radius: 8px; }
.lightbox-close { position: absolute; top: 24px; right: 28px; width: 40px; height: 40px; border-radius: 50%; border: none; background: rgba(255,255,255,.12); color: #fff; cursor: pointer; font-size: 18px; }

.gal-err { position: fixed; bottom: 12px; left: 12px; right: 12px; z-index: 120; background: var(--vp-clay-soft); color: var(--vp-clay); border-radius: 12px; }

@media (max-width: 860px) {
  .plan-grid { grid-template-columns: 1fr; }
  .locate { grid-template-columns: 1fr; }
  .pgrid { grid-template-columns: repeat(2, 1fr); }
  .pgrid .ph:nth-child(4n+1) { grid-column: span 2; grid-row: span 1; }
  .hero-cta { right: 16px; bottom: 20px; }
}
</style>
