// Manifest del montaggio: l'unico file da toccare per aggiungere, ritagliare o
// riordinare le scene. Tutti i tempi sono in SECONDI.
//
// Scena:
//   clip            nome del file in public/clips (es. "03-utenze.mp4")
//   inizio / fine   taglio nella clip sorgente (default: 0 / fine della clip)
//   velocita        moltiplicatore di riproduzione (1.5 = accelera i tratti morti)
//   durataPrevista  durata del segnaposto finché la clip non esiste
//   didascalie      { testo, da, a } in secondi della clip TAGLIATA, cioè
//                   contati da `inizio` sul tempo della sorgente: restano
//                   agganciate a ciò che si vede anche se cambi `velocita`.
//                   "\n" nel testo forza un a capo. `posizione` (default
//                   "basso-sx") sposta la card dove non copre l'azione:
//                   "alto-dx", "alto-sx", "basso-dx" o { left/right/top/bottom } in px.
//   notifiche       notifiche push simulate sopra la clip, tempi come le
//                   didascalie (da/a = quanto resta in scena il telefono, con
//                   entrata e uscita). Campi: { titolo, corpo, da, a } più
//                     stile      "telefono" (default): telefono con schermata
//                                di blocco che entra dal basso, la notifica
//                                arriva ~1 s dopo con una vibrazione
//                                (TelefonoNotifica); "desktop": card in alto
//                                (NotificaPush)
//                     etichetta  cartellino accanto al telefono, es. «Sul
//                                telefono del proprietario»
//                     ora, data  ora grande e data della schermata di blocco
//                     lato       "destra" (default) o "sinistra"
//                     alto       px fra il bordo alto del video e il telefono
//                                a riposo (default 300; oltre ~480 si vede
//                                solo la metà alta)
//                   Titolo e corpo vanno tenuti fedeli al codice che manda la
//                   push (billing/_notifiche.py, billing/calc/avvisi.py,
//                   billing/calc/riepilogo.py); il telefono tronca come
//                   Android: titolo a 2 righe, corpo a 3, con "…".
//   zoom            Ken Burns lento (default attivo, vedi `zoomPredefinito`);
//                   false per disattivarlo, oppure { da, a, origine }
//   sezione         se presente, cartello di sezione di ~2 s prima della scena
//
// Introduzione (fra l'apertura e la prima sezione), tre cartelli in fila:
//   cheCose         che cos'è Viapal: titolo (serif grande, "\n" = a capo) e
//                   sottotitolo facoltativo
//   viste           le due viste affiancate: a sinistra il proprietario su un
//                   portatile, a destra l'inquilino su un tablet; per ciascuna
//                   titolo, voci (3-4, compaiono una alla volta) e immagine
//                   (percorso in public/, fotogrammi estratti dalle clip)
//   passaggio       frase-ponte che sfuma nel cartello della prima sezione
//
// Una stessa clip può comparire in più scene con tagli diversi (es. per
// saltare un tratto in mezzo o accelerarne solo una parte).

export type Posizione =
  | "basso-sx"
  | "basso-dx"
  | "alto-sx"
  | "alto-dx"
  | {
      readonly left?: number;
      readonly right?: number;
      readonly top?: number;
      readonly bottom?: number;
    };

export type Didascalia = {
  readonly testo: string;
  readonly da: number;
  readonly a: number;
  readonly posizione?: Posizione;
};

export type StileNotifica = "telefono" | "desktop";
export type LatoNotifica = "destra" | "sinistra";

export type Notifica = {
  readonly titolo: string;
  readonly corpo: string;
  readonly da: number;
  readonly a: number;
  /** default "telefono" */
  readonly stile?: StileNotifica;
  readonly etichetta?: string;
  /** ora della schermata di blocco, es. "10:42" */
  readonly ora?: string;
  /** data della schermata di blocco, es. "sabato 17 ottobre" */
  readonly data?: string;
  /** default "destra" */
  readonly lato?: LatoNotifica;
  /** solo telefono: px dal bordo alto del video al telefono a riposo */
  readonly alto?: number;
};

export type Zoom = {
  readonly da?: number;
  readonly a?: number;
  /** transform-origin CSS, es. "50% 30%" per zoomare verso l'alto */
  readonly origine?: string;
};

export type Scena = {
  readonly id: string;
  readonly titolo: string;
  readonly clip: string;
  readonly inizio?: number;
  readonly fine?: number;
  readonly velocita?: number;
  readonly durataPrevista?: number;
  readonly zoom?: boolean | Zoom;
  readonly sezione?: string;
  /** promemoria mostrato solo nel segnaposto */
  readonly nota?: string;
  readonly didascalie: readonly Didascalia[];
  readonly notifiche?: readonly Notifica[];
};

export type Vista = {
  readonly titolo: string;
  readonly voci: readonly string[];
  /** percorso in public/, es. "intro/proprietario-cruscotto.jpg" */
  readonly immagine: string;
};

export type Introduzione = {
  readonly cheCose: {
    readonly durata: number;
    readonly titolo: string;
    readonly sottotitolo?: string;
  };
  readonly viste: {
    readonly durata: number;
    readonly proprietario: Vista;
    readonly inquilino: Vista;
  };
  readonly passaggio: {
    readonly durata: number;
    readonly testo: string;
  };
};

export type Manifest = {
  readonly apertura: {
    readonly durata: number;
    readonly titolo: string;
    readonly sottotitolo: string;
  };
  readonly introduzione: Introduzione;
  readonly chiusura: {
    readonly durata: number;
    readonly titolo: string;
    readonly contatto: string;
  };
  readonly durataSezione: number;
  /** durata delle dissolvenze fra un blocco e l'altro, in fotogrammi */
  readonly transizioneFotogrammi: number;
  readonly zoomPredefinito: Zoom | false;
  /** usata solo se public/musica.mp3 esiste */
  readonly musica: {
    readonly file: string;
    readonly volume: number;
    readonly dissolvenzaEntrata: number;
    readonly dissolvenzaUscita: number;
  };
  readonly scene: readonly Scena[];
};

export const manifest: Manifest = {
  apertura: {
    durata: 6,
    titolo: "Affitti a stanze, senza fogli Excel.",
    sottotitolo: "Viapal — il gestionale per chi affitta camere",
  },
  // Testi provvisori: da rifinire.
  introduzione: {
    cheCose: {
      durata: 4,
      titolo: "Viapal gestisce l'affitto di una casa:\nintera, o divisa in stanze.",
      sottotitolo: "Per chi la possiede e per chi ci abita.",
    },
    viste: {
      durata: 7,
      proprietario: {
        titolo: "Per chi affitta",
        voci: ["Incassi e ritardi", "Bollette divise per presenza", "Spese e conti fra comproprietari"],
        // 01-cruscotto.mp4 a 1,0 s: indicatori in vista, nessun cursore
        immagine: "intro/proprietario-cruscotto.jpg",
      },
      inquilino: {
        titolo: "Per chi abita",
        voci: ["Quanto deve e perché", "Paga con un QR", "I suoi documenti"],
        // 04-lato-inquilino.mp4 a 3,5 s, senza la barra "Torna a te"
        // dell'impersonation e ritagliata a 16:10 (cursore fuori campo)
        immagine: "intro/inquilino-home.jpg",
      },
    },
    passaggio: {
      durata: 2,
      testo: "Vediamo come funziona.",
    },
  },
  chiusura: {
    durata: 6,
    titolo: "Prova Viapal gratis.",
    contatto: "viapal.e-den.it",
  },
  durataSezione: 2,
  transizioneFotogrammi: 12,
  zoomPredefinito: { da: 1, a: 1.04, origine: "50% 40%" },
  musica: {
    file: "musica.mp3",
    volume: 0.25,
    dissolvenzaEntrata: 1.5,
    dissolvenzaUscita: 3,
  },
  // Tempi ricavati dai provini delle riprese del 18/10/2026 (nomi italiani):
  // `inizio`/`fine` tolgono attese, fotogrammi vuoti e lampi bianchi dei
  // ricaricamenti (scene spezzate in a/b), le didascalie cadono sui momenti
  // chiave (secondi sorgente da `inizio`).
  scene: [
    {
      id: "01",
      titolo: "Cruscotto",
      clip: "01-cruscotto.mp4",
      sezione: "Il quadro",
      // incasso 1,5–2,8, spese ~3,5–5, ritardi ~6–7,5, scroll 8,6–10,5
      inizio: 0.8,
      fine: 11,
      velocita: 1.1,
      didascalie: [
        // prima dello scroll: dopo, in basso compare la tabella dei flussi
        { testo: "Tutto l'anno a colpo d'occhio: incassi, spese, ritardi.", da: 0.4, a: 7.6 },
      ],
    },
    // Inquilini: fuori il fotogramma quasi vuoto (2,83–3,00) fra la lista e la
    // scheda di Diego Palmieri.
    {
      id: "02a",
      titolo: "Inquilini",
      clip: "02-inquilini.mp4",
      inizio: 0.3,
      fine: 2.8,
      didascalie: [],
    },
    {
      id: "02b",
      titolo: "Inquilini",
      clip: "02-inquilini.mp4",
      // scheda da 3,0, badge 4,5–6,5, Profilo & contratto 8,5–9, Documenti 11–12,8,
      // atto aperto 16–18,7
      inizio: 3.05,
      fine: 18.5,
      velocita: 1.4,
      didascalie: [
        // finisce prima del tab Documenti, la cui lista sta in basso a sinistra
        { testo: "Ogni inquilino: contratto, pagamenti, documenti.", da: 0.5, a: 7.9 },
      ],
    },
    // Utenze: bollette 0–7, Ripartizione 7,3, grafico ~13,5, Invio 15,5. Tolto
    // il giro fra le pagine dell'invio (16,6–19,1, riga di Rossella Stefania
    // Foti aperta e chiusa); l'anteprima di Diego (20,5) va a velocità piena
    // per lasciare leggere il telefono.
    {
      id: "03a",
      titolo: "Utenze",
      clip: "03-utenze.mp4",
      sezione: "Le bollette",
      inizio: 0.3,
      fine: 16.6,
      velocita: 1.4,
      didascalie: [
        { testo: "Carichi la bolletta: importi e periodo letti in automatico.", da: 0.3, a: 6.7 },
        // cella di Diego 9–12, grafico ~13,5
        { testo: "Divisa per i giorni di presenza di ciascuno.", da: 7.4, a: 14.4 },
      ],
    },
    {
      id: "03b",
      titolo: "Utenze",
      clip: "03-utenze.mp4",
      // anteprima di Diego 20,5, «Giorni di presenza: 10» 21,5–24,5, clic
      // Andamento 25,6; a 26,2–26,37 il tab Andamento è vuoto mentre carica
      inizio: 19.1,
      fine: 26.15,
      didascalie: [{ testo: "Ognuno riceve il suo conto,\nanche sul telefono.", da: 0.3, a: 6.5 }],
      notifiche: [
        {
          // billing/calc/avvisi.py, push dell'avviso utenze: titolo = oggetto
          // dell'email ("Viapal — conguaglio utenze {{periodo}}", periodo
          // gg/mm/aaaa – gg/mm/aaaa), corpo "Il tuo importo è di {importo} €.
          // Tocca per vedere il dettaglio e pagare." Il telefono tronca il
          // titolo a 2 righe con "…", come Android. Importo: quello di Diego
          // Palmieri nell'anteprima della clip (luglio 2026, 14,72 €). Il
          // telefono entra quando l'anteprima è aperta (20,5 sorgente), la
          // notifica arriva ~1 s dopo.
          etichetta: "Sul telefono dell'inquilino",
          titolo: "Viapal — conguaglio utenze 01/07/2026 – 31/07/2026",
          corpo: "Il tuo importo è di 14,72 €. Tocca per vedere il dettaglio e pagare.",
          ora: "9:15",
          data: "lunedì 3 agosto",
          da: 1.45,
          a: 6.85,
          alto: 300,
        },
      ],
    },
    {
      id: "03c",
      titolo: "Utenze",
      clip: "03-utenze.mp4",
      inizio: 26.45,
      fine: 32.4,
      velocita: 1.2,
      didascalie: [],
    },
    // Lato inquilino: fuori i lampi bianchi dell'impersonation (2,57–2,77) e di
    // "Torna a te" (21,37–21,50), e la pagina Utenze vuota mentre carica
    // (13,97–14,13).
    {
      id: "04a",
      titolo: "Lato inquilino",
      clip: "04-lato-inquilino.mp4",
      // «Ciao, Diego» da 2,8, Utenze agosto 4,5–7, QR 8,7–11,3, Esc 11,5, Utenze 13
      inizio: 3.3,
      fine: 13.95,
      velocita: 1.3,
      didascalie: [
        // in alto a destra: in basso c'è il totale da versare; esce prima del QR
        {
          testo: "L'inquilino vede quanto deve\ne paga con un QR.",
          da: 0.3,
          a: 5.2,
          // sotto la barra "Torna a te" dell'impersonation
          posizione: { right: 96, top: 140 },
        },
      ],
    },
    {
      id: "04b",
      titolo: "Lato inquilino",
      clip: "04-lato-inquilino.mp4",
      // scroll 14,8–16, Torna a te ~19,5–20
      inizio: 14.2,
      fine: 21.2,
      velocita: 1.3,
      didascalie: [],
    },
    {
      id: "05",
      titolo: "Riconciliazione",
      clip: "05-riconciliazione.mp4",
      sezione: "I soldi",
      // clic bonifico 2,5, «Inquilino: Christian Brambilla» 4–6, spunta
      // deposito 8,5–9,6, «residuo 0,00» 11–14, Annulla 15,5
      inizio: 0.8,
      fine: 16.8,
      velocita: 1.3,
      didascalie: [
        // in basso a sinistra c'è la tabella delle allocazioni
        {
          testo: "Bonifici abbinati agli addebiti in due clic.",
          da: 0.3,
          a: 13.2,
          posizione: { right: 96, top: 60 },
        },
      ],
    },
    {
      id: "06a",
      titolo: "Ritardi e solleciti",
      clip: "06-ritardi-solleciti.mp4",
      // ritardi 1–4,5, clic Notifiche 5,5; da 6,2 a 6,65 l'anteprima delle
      // notifiche è vuota mentre carica
      inizio: 0.2,
      fine: 6.15,
      velocita: 1.2,
      didascalie: [{ testo: "Chi è in ritardo,", da: 0.4, a: 5.9 }],
    },
    {
      id: "06b",
      titolo: "Ritardi e solleciti",
      clip: "06-ritardi-solleciti.mp4",
      // Diego si apre 8,5, importi 10–11,5, «Invia 2 riepiloghi» 12,8–14,3
      inizio: 6.7,
      fine: 15.2,
      velocita: 1.2,
      didascalie: [{ testo: "e un sollecito pronto da inviare.", da: 0.6, a: 8.3 }],
    },
    // Notifiche: l'addebito dichiarato da Luigi Cirillo (cura_demo_video) nei
    // ritardi, con sopra la push che il proprietario riceverebbe; poi chi la
    // riceve (Immobile → Avvisi) e il dispositivo (Area personale). Fuori la
    // pagina Immobile vuota mentre carica (10,13–10,17) e il giro dal menu
    // utente (17,0–21,8). La clip finisce sul registro degli inviati (da 29,5):
    // fuori montaggio, rimontabile come ulteriore taglio con `inizio: 29.5`.
    {
      id: "07a",
      titolo: "Notifiche",
      clip: "07-notifiche.mp4",
      // «Da confermare» 1,5–5, Conferma 6–7,5, clic Immobile 9,5. Più lenta
      // delle altre perché la notifica resti leggibile ~3,7 s.
      inizio: 0.3,
      fine: 10.1,
      velocita: 1.2,
      notifiche: [
        {
          // billing/_notifiche.py: "{nominativo} dichiara di aver pagato" /
          // "{addebito}: {importo} €. Tocca per confermare l'incasso."
          // Nominativo, etichetta e importo dell'addebito "Da confermare"
          // preparato da cura_demo_video (Luigi Cirillo, Utenze Ago 2026).
          etichetta: "Sul telefono del proprietario",
          titolo: "Luigi Cirillo dichiara di aver pagato",
          corpo: "Utenze Ago 2026: 39,26 €. Tocca per confermare l'incasso.",
          ora: "10:42",
          data: "sabato 17 ottobre",
          // il telefono sta sotto la tabella, a destra, accanto alla riga
          // "Da confermare"; la notifica arriva a ~2,1 s sorgente
          da: 0.7,
          a: 6.9,
          alto: 500,
        },
      ],
      didascalie: [
        // la tabella dei ritardi sta in alto: in basso a sinistra c'è posto
        {
          testo: "L'inquilino segnala il pagamento:\nti arriva sul telefono.",
          da: 1.6,
          a: 8.6,
        },
      ],
    },
    {
      id: "07b",
      titolo: "Notifiche",
      clip: "07-notifiche.mp4",
      // menu Avvisi 13–15,5, Esc ~16,5
      inizio: 10.25,
      fine: 17,
      velocita: 1.6,
      didascalie: [
        // a destra sotto le stanze: a sinistra in basso c'è il menu "Avvisa"
        {
          testo: "Decidi chi riceve\nle notifiche,",
          da: 0.4,
          a: 6.6,
          posizione: { right: 60, bottom: 190 },
        },
      ],
    },
    {
      id: "07c",
      titolo: "Notifiche",
      clip: "07-notifiche.mp4",
      // Area personale 21,9, interruttore 23,5–25,5, Notifiche addebiti 26,5
      inizio: 21.8,
      fine: 26.2,
      velocita: 1.25,
      didascalie: [{ testo: "e su quale dispositivo.", da: 0.3, a: 4.2 }],
    },
    // Spese e conto economico: fuori la pagina vuota del conto economico
    // mentre carica (12,60–12,70).
    {
      id: "08a",
      titolo: "Spese e conto economico",
      clip: "08-spese-conto-economico.mp4",
      // grafico 0–4, Aggiungi 4,5 (dialog 5–9), Annulla 9,5, Conto economico 11,5
      inizio: 0.3,
      fine: 12.55,
      velocita: 1.5,
      didascalie: [],
    },
    {
      id: "08b",
      titolo: "Spese e conto economico",
      clip: "08-spese-conto-economico.mp4",
      // Competenza 15,5–16, Camera 3 19,5–21,7
      inizio: 12.75,
      fine: 22.5,
      velocita: 1.5,
      didascalie: [
        // solo sul conto economico: prima il dialog arriva fino in basso
        {
          testo: "Spese e conto economico,\nper cassa o per competenza.",
          da: 0.2,
          a: 9.4,
        },
      ],
    },
    {
      id: "09",
      titolo: "Saldi proprietari",
      clip: "09-saldi-proprietari.mp4",
      // saldi da 1,6, anticipi 5,2, chi deve a chi 7,4–9,8
      inizio: 0.3,
      fine: 10.5,
      didascalie: [
        { testo: "Più proprietari? Chi ha anticipato cosa, e chi deve a chi.", da: 1.0, a: 9.9 },
      ],
    },
    {
      id: "10",
      titolo: "Annuncio pubblico",
      clip: "10-annuncio-pubblico.mp4",
      sezione: "La casa",
      // copertina 1,3, planimetria 5,3, camera 5 a 10,0, foto grande 12,6–16,5
      inizio: 0.3,
      fine: 17.3,
      velocita: 1.35,
      didascalie: [{ testo: "Un annuncio pronto da condividere.", da: 0.6, a: 9.8 }],
    },
    {
      id: "11",
      titolo: "Documenti generati",
      clip: "11-documenti-generati.mp4",
      // Genera 2,4 (pannello 3,0–5,5), voce 5,8, riepilogo 6,3–9,9, Annulla 10,2
      inizio: 0.3,
      fine: 10.8,
      velocita: 1.1,
      didascalie: [
        {
          testo: "Atto di subentro e cessione di fabbricato,\ncompilati dai dati.",
          da: 0.5,
          a: 9.7,
        },
      ],
    },
    {
      id: "12a",
      titolo: "Più immobili",
      clip: "12-piu-immobili.mp4",
      // menu immobili 2,4–3,9, Gelsomini 4,5; a 5,33–5,60 il cambio immobile
      // ricarica l'app (lampo bianco)
      inizio: 0.3,
      fine: 5.25,
      didascalie: [],
    },
    {
      id: "12b",
      titolo: "Più immobili",
      clip: "12-piu-immobili.mp4",
      // dashboard 5,7–9, Nuova proprietà 10,4, form 11,3, «Appartamento intero» 13–15
      inizio: 5.7,
      fine: 15,
      didascalie: [
        { testo: "A stanze o appartamento intero, anche più d'uno.", da: 0.4, a: 9.0 },
      ],
    },
  ],
};
