<template>
  <q-page padding class="vp-i-privacy">
    <div class="vp-eyebrow">Profilo</div>
    <h1 class="vp-display vp-i-privacy__titolo">Informativa privacy</h1>
    <p class="vp-i-privacy__sotto">
      Trattamento dei dati personali ai sensi degli artt. 13 e 14 del
      Regolamento (UE) 2016/679 ("GDPR").
    </p>

    <q-banner v-if="errore" class="bg-negative text-white" rounded>
      {{ errore }}
    </q-banner>

    <template v-else>
      <section>
        <h2>1. Titolare del trattamento</h2>
        <p v-if="dati">
          Titolare del trattamento è il locatore dell'immobile
          <strong>{{ dati.immobile.nome }}</strong><template v-if="dati.immobile.indirizzo"> ({{ dati.immobile.indirizzo }})</template>.
          <template v-if="dati.titolari.length > 1">
            I comproprietari operano quali contitolari del trattamento
            (art. 26 GDPR):
          </template>
        </p>
        <ul v-if="dati">
          <li v-for="t in dati.titolari" :key="t.nominativo">
            <strong>{{ t.nominativo }}</strong>
            <template v-if="t.email"> — {{ t.email }}</template>
          </li>
        </ul>
        <p v-if="dati">
          La piattaforma software utilizzata ("Viapal") è gestita da
          <strong>{{ dati.gestore.nome }}</strong> ({{ dati.gestore.email }}),
          che opera quale responsabile del trattamento ai sensi dell'art. 28
          GDPR per conto del titolare.
        </p>
      </section>

      <section>
        <h2>2. Dati trattati</h2>
        <ul>
          <li>dati anagrafici e di contatto: nome, cognome, codice fiscale, telefono, e-mail, credenziali di accesso;</li>
          <li>documenti caricati nell'app: documento d'identità, tessera del codice fiscale, permesso di soggiorno (se applicabile), contratto ed eventuali altri documenti;</li>
          <li>documentazione reddituale (es. contratto di lavoro), solo in fase precontrattuale;</li>
          <li>dati contabili: canoni e oneri dovuti, pagamenti ricevuti e dati dei bonifici (data, importo, causale, IBAN ordinante), deposito cauzionale, conguagli utenze;</li>
          <li>dati tecnici: log di accesso; se attivi le notifiche push, il token di sottoscrizione del browser.</li>
        </ul>
      </section>

      <section>
        <h2>3. Finalità e basi giuridiche</h2>
        <ul>
          <li><strong>Gestione del rapporto di locazione</strong> (contratto, canoni, utenze, deposito, comunicazioni): esecuzione del contratto, art. 6.1.b.</li>
          <li><strong>Obblighi di legge</strong>: registrazione del contratto presso l'Agenzia delle Entrate, obblighi fiscali, comunicazione di cessione di fabbricato / ospitalità di cittadini extra-UE all'autorità di pubblica sicurezza: art. 6.1.c.</li>
          <li><strong>Valutazione precontrattuale</strong> dell'affidabilità economica (documentazione reddituale): misure precontrattuali, art. 6.1.b, e legittimo interesse, art. 6.1.f.</li>
          <li><strong>Notifiche push</strong>: consenso, revocabile in ogni momento dal profilo (art. 6.1.a).</li>
          <li><strong>Difesa di un diritto</strong> in sede giudiziale o stragiudiziale: legittimo interesse, art. 6.1.f.</li>
        </ul>
        <p>
          Il conferimento dei dati richiesti per obblighi legali o per il
          contratto è necessario: in mancanza non è possibile costituire o
          proseguire il rapporto di locazione.
        </p>
      </section>

      <section>
        <h2>4. Destinatari</h2>
        <p>
          I dati possono essere comunicati esclusivamente a: Agenzia delle
          Entrate e autorità di pubblica sicurezza (obblighi di legge);
          eventuali professionisti incaricati; fornitori tecnici della
          piattaforma in qualità di (sub-)responsabili — hosting Contabo GmbH
          (Germania, UE). I dati non sono diffusi né trasferiti fuori
          dall'Unione Europea.
        </p>
      </section>

      <section>
        <h2>5. Conservazione</h2>
        <ul>
          <li>dati contrattuali e contabili: durata del rapporto + 10 anni (prescrizione ordinaria e obblighi fiscali);</li>
          <li>copie di documenti d'identità, codice fiscale, permesso di soggiorno: durata del rapporto + 5 anni;</li>
          <li>documentazione reddituale: cancellata entro 12 mesi dalla firma del contratto (entro 30 giorni se il contratto non si conclude);</li>
          <li>token notifiche push: fino a revoca o chiusura dell'account.</li>
        </ul>
      </section>

      <section>
        <h2>6. Sicurezza</h2>
        <p>
          I dati sono trattati con strumenti informatici su server ubicati
          nell'Unione Europea, con misure adeguate: cifratura del canale,
          autenticazione, accesso ai documenti limitato all'interessato e al
          titolare. I file caricati sono scaricabili solo previa
          autenticazione.
        </p>
      </section>

      <section>
        <h2>7. Cookie e archiviazione locale</h2>
        <p>
          L'app usa esclusivamente cookie tecnici, necessari al
          funzionamento: <code>sessionid</code> (sessione di accesso) e
          <code>csrftoken</code> (protezione dei moduli). Usa inoltre la
          memoria locale del browser (localStorage) per il token di accesso
          e alcune preferenze, e — se installi l'app — la cache
          dell'applicazione. Non sono usati cookie di profilazione, di
          statistica o di terze parti, né strumenti di tracciamento: per
          questo non è richiesto alcun banner di consenso.
        </p>
      </section>

      <section>
        <h2>8. I tuoi diritti</h2>
        <p>
          Puoi esercitare in ogni momento i diritti previsti dagli artt.
          15–22 GDPR (accesso, rettifica, cancellazione, limitazione,
          portabilità, opposizione) scrivendo al titolare ai recapiti sopra.
          Puoi inoltre proporre reclamo al Garante per la protezione dei dati
          personali (<a href="https://www.garanteprivacy.it" target="_blank" rel="noopener">garanteprivacy.it</a>).
          Molti dati sono direttamente consultabili e aggiornabili dalle
          sezioni <router-link to="/i/profilo">Profilo</router-link> e
          <router-link to="/i/documenti">Documenti</router-link>.
        </p>
      </section>

      <p v-if="dati" class="vp-i-privacy__aggiornamento">
        Ultimo aggiornamento: {{ dati.aggiornata_il }}
      </p>
    </template>

    <div class="vp-i-privacy__back">
      <q-btn flat color="primary" icon="arrow_back" label="Torna ai documenti" no-caps to="/i/documenti" />
    </div>
  </q-page>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue';
import { api } from 'boot/axios';

interface DatiInformativa {
  immobile: { nome: string; indirizzo: string };
  titolari: { nominativo: string; email: string | null }[];
  gestore: { nome: string; email: string };
  aggiornata_il: string;
}

const dati = ref<DatiInformativa | null>(null);
const errore = ref('');

onMounted(async () => {
  try {
    const { data } = await api.get<DatiInformativa>('/api/v1/privacy/informativa/');
    dati.value = data;
  } catch {
    errore.value = "Impossibile caricare i dati dell'informativa.";
  }
});
</script>

<style scoped>
.vp-i-privacy {
  max-width: 640px;
  margin: 0 auto;
}
.vp-i-privacy__titolo {
  font-size: var(--vp-text-2xl);
  margin: var(--vp-gap-1) 0 var(--vp-gap-2);
}
.vp-i-privacy__sotto {
  color: var(--vp-ink-3);
  font-size: var(--vp-text-sm);
  margin-bottom: var(--vp-gap-4);
}
section {
  margin-bottom: var(--vp-gap-4);
}
section h2 {
  font-size: var(--vp-text-lg);
  font-weight: 600;
  margin: 0 0 var(--vp-gap-2);
}
section p,
section li {
  font-size: var(--vp-text-sm);
  line-height: 1.55;
}
section ul {
  padding-left: 1.2em;
  margin: 0 0 var(--vp-gap-2);
}
.vp-i-privacy__aggiornamento {
  color: var(--vp-ink-3);
  font-size: var(--vp-text-xs);
}
.vp-i-privacy__back {
  margin-top: var(--vp-gap-4);
}
</style>
