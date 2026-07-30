<template>
  <q-page padding class="vp-privacy-pub">
    <div class="vp-eyebrow">Viapal</div>
    <h1 class="vp-display vp-privacy-pub__titolo">Privacy e cookie</h1>

    <section>
      <h2>Visitatori delle pagine pubbliche</h2>
      <p>
        Le pagine pubbliche di questo sito (gli annunci degli immobili) non
        raccolgono dati personali dei visitatori: nessun modulo, nessuna
        registrazione, nessuno strumento di analisi o tracciamento.
      </p>
    </section>

    <section>
      <h2>Cookie</h2>
      <p>
        Il sito usa esclusivamente cookie tecnici, strettamente necessari al
        funzionamento (<code>sessionid</code> per la sessione degli utenti
        registrati, <code>csrftoken</code> per la protezione dei moduli).
        Non sono usati cookie di profilazione, di statistica o di terze
        parti: per questo, ai sensi dell'art. 122 del Codice Privacy e delle
        Linee guida cookie del Garante (10 giugno 2021), non è richiesto
        alcun banner di consenso.
      </p>
    </section>

    <section>
      <h2>Utenti registrati</h2>
      <p>
        Gli inquilini che accedono all'app trovano l'informativa completa
        sul trattamento dei dati personali (artt. 13 e 14 GDPR) nella
        sezione <em>Documenti</em> del proprio profilo.
      </p>
    </section>

    <section>
      <h2>Contatti</h2>
      <p>
        La piattaforma è gestita da Sandro Dentella
        (<a href="mailto:sandro.dentella@gmail.com">sandro.dentella@gmail.com</a>).
        Per ogni richiesta relativa alla privacy puoi scrivere a questo
        indirizzo.
      </p>
    </section>
  </q-page>
</template>

<style scoped>
.vp-privacy-pub {
  max-width: 640px;
  margin: 0 auto;
}
.vp-privacy-pub__titolo {
  font-size: var(--vp-text-2xl);
  margin: var(--vp-gap-1) 0 var(--vp-gap-4);
}
section {
  margin-bottom: var(--vp-gap-4);
}
section h2 {
  font-size: var(--vp-text-lg);
  font-weight: 600;
  margin: 0 0 var(--vp-gap-2);
}
section p {
  font-size: var(--vp-text-sm);
  line-height: 1.55;
}
</style>
