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
//   notifiche       { titolo, corpo, da, a } notifica push simulata in alto a
//                   destra (componente NotificaPush), tempi come le didascalie;
//                   testo da tenere fedele a billing/_notifiche.py
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

export type Notifica = {
  readonly titolo: string;
  readonly corpo: string;
  readonly da: number;
  readonly a: number;
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
    contatto: "viapal.e-den.it", // segnaposto, da confermare
  },
  durataSezione: 2,
  transizioneFotogrammi: 12,
  zoomPredefinito: { da: 1, a: 1.04, origine: "50% 40%" },
  musica: {
    file: "musica.mp3",
    volume: 0.35,
    dissolvenzaEntrata: 1.5,
    dissolvenzaUscita: 3,
  },
  // Tempi ricavati dai provini delle riprese del 17/10/2026: `inizio`/`fine`
  // tolgono attese e lampi bianchi dei ricaricamenti (scene spezzate in a/b),
  // le didascalie cadono sui momenti chiave (secondi sorgente da `inizio`).
  scene: [
    {
      id: "01",
      titolo: "Cruscotto",
      clip: "01-cruscotto.mp4",
      sezione: "Il quadro",
      inizio: 0.8,
      fine: 10,
      velocita: 1.1,
      didascalie: [
        // prima dello scroll: dopo, in basso compare la tabella dei flussi
        { testo: "Tutto l'anno a colpo d'occhio: incassi, spese, ritardi.", da: 0.4, a: 5.8 },
      ],
    },
    {
      id: "02",
      titolo: "Inquilini",
      clip: "02-inquilini.mp4",
      inizio: 0.3,
      fine: 18.5,
      velocita: 1.4,
      didascalie: [
        // finisce prima del tab Documenti, la cui lista sta in basso a sinistra
        { testo: "Ogni inquilino: contratto, pagamenti, documenti.", da: 0.9, a: 11.2 },
      ],
    },
    {
      id: "03a",
      titolo: "Utenze",
      clip: "03-utenze.mp4",
      sezione: "Le bollette",
      inizio: 0.3,
      // a 26,3 un fotogramma vuoto mentre carica il tab Andamento
      fine: 26.2,
      velocita: 1.4,
      didascalie: [
        { testo: "Carichi la bolletta: importi e periodo letti in automatico.", da: 0.4, a: 6.1 },
        { testo: "Divisa per i giorni di presenza di ciascuno.", da: 7.0, a: 13.0 },
        { testo: "Ognuno riceve il suo conto.", da: 14.0, a: 24.8 },
      ],
    },
    {
      id: "03b",
      titolo: "Utenze",
      clip: "03-utenze.mp4",
      inizio: 26.4,
      fine: 32.4,
      didascalie: [],
    },
    {
      id: "04",
      titolo: "Lato inquilino",
      clip: "04-lato-inquilino.mp4",
      // fuori i lampi bianchi dell'impersonation (~2,7) e di "Torna a te" (~21,3)
      inizio: 3.3,
      fine: 21.2,
      velocita: 1.3,
      didascalie: [
        // in alto a destra: in basso c'è il totale da versare; esce prima del QR
        {
          testo: "L'inquilino vede quanto deve\ne paga con un QR.",
          da: 0.3,
          a: 5.0,
          // sotto la barra "Torna a te" dell'impersonation
          posizione: { right: 96, top: 140 },
        },
      ],
    },
    {
      id: "05",
      titolo: "Riconciliazione",
      clip: "05-riconciliazione.mp4",
      sezione: "I soldi",
      inizio: 0.8,
      fine: 16,
      velocita: 1.3,
      didascalie: [
        // in basso a sinistra c'è la tabella delle allocazioni
        {
          testo: "Bonifici abbinati agli addebiti in due clic.",
          da: 0.3,
          a: 12.8,
          posizione: { right: 96, top: 60 },
        },
      ],
    },
    {
      id: "06a",
      titolo: "Ritardi e solleciti",
      clip: "06-ritardi-solleciti.mp4",
      inizio: 0.2,
      // da 6,2 a 6,6 l'anteprima delle notifiche è vuota mentre carica
      fine: 6.15,
      velocita: 1.2,
      didascalie: [{ testo: "Chi è in ritardo,", da: 0.4, a: 5.9 }],
    },
    {
      id: "06b",
      titolo: "Ritardi e solleciti",
      clip: "06-ritardi-solleciti.mp4",
      inizio: 6.65,
      fine: 15.2,
      velocita: 1.2,
      didascalie: [{ testo: "e un sollecito pronto da inviare.", da: 0.6, a: 8.4 }],
    },
    // Notifiche: l'addebito dichiarato da Karthik Pillai (cura_demo_video) nei
    // ritardi, con sopra la push che il proprietario riceverebbe; poi chi la
    // riceve (Immobile → Avvisi) e il dispositivo (Area personale). Tagliato il
    // giro dal menu utente (17,6–22,5). La clip finisce sul registro degli
    // inviati (da 30,9): fuori montaggio per stare nei 2'50", rimontabile come
    // terzo taglio con `inizio: 30.9`.
    {
      id: "07a",
      titolo: "Notifiche",
      clip: "07-notifiche.mp4",
      inizio: 0.3,
      fine: 17.5,
      velocita: 1.6,
      notifiche: [
        {
          // billing/_notifiche.py: "{nominativo} dichiara di aver pagato" /
          // "{addebito}: {importo} €. Tocca per confermare l'incasso."
          titolo: "Karthik Pillai dichiara di aver pagato",
          corpo: "Utenze Ago 2026: 39,26 €. Tocca per confermare l'incasso.",
          da: 1.6,
          a: 7.0,
        },
      ],
      didascalie: [
        // la tabella dei ritardi sta in alto: in basso a sinistra c'è posto
        {
          testo: "L'inquilino segnala il pagamento:\nti arriva una notifica.",
          da: 2.2,
          a: 9.3,
        },
        // a destra sotto le stanze: a sinistra in basso c'è il menu "Avvisa"
        {
          testo: "Decidi chi riceve\nle notifiche,",
          da: 11.0,
          a: 17.2,
          posizione: { right: 60, bottom: 190 },
        },
      ],
    },
    {
      id: "07b",
      titolo: "Notifiche",
      clip: "07-notifiche.mp4",
      inizio: 22.5,
      fine: 26.5,
      velocita: 1.25,
      didascalie: [{ testo: "e su quale dispositivo.", da: 0.3, a: 3.9 }],
    },
    {
      id: "08",
      titolo: "Spese e conto economico",
      clip: "08-spese-conto-economico.mp4",
      inizio: 0.3,
      fine: 22,
      velocita: 1.5,
      didascalie: [
        // solo sul conto economico: prima il dialog arriva fino in basso
        {
          testo: "Spese e conto economico,\nper cassa o per competenza.",
          da: 12.1,
          a: 21.6,
        },
      ],
    },
    {
      id: "09",
      titolo: "Saldi proprietari",
      clip: "09-saldi-proprietari.mp4",
      inizio: 0.3,
      fine: 9.8,
      didascalie: [
        { testo: "Più proprietari? Chi ha anticipato cosa, e chi deve a chi.", da: 0.5, a: 9.3 },
      ],
    },
    {
      id: "10",
      titolo: "Annuncio pubblico",
      clip: "10-annuncio-pubblico.mp4",
      sezione: "La casa",
      inizio: 0.3,
      fine: 17.5,
      velocita: 1.35,
      didascalie: [{ testo: "Un annuncio pronto da condividere.", da: 0.5, a: 10.5 }],
    },
    {
      id: "11",
      titolo: "Documenti generati",
      clip: "11-documenti-generati.mp4",
      inizio: 0.3,
      fine: 11,
      velocita: 1.1,
      didascalie: [
        {
          testo: "Atto di subentro e cessione di fabbricato,\ncompilati dai dati.",
          da: 0.5,
          a: 10.3,
        },
      ],
    },
    {
      id: "12a",
      titolo: "Più immobili",
      clip: "12-piu-immobili.mp4",
      inizio: 0.3,
      // a 5,3 il cambio immobile ricarica l'app (lampo bianco)
      fine: 5.2,
      didascalie: [],
    },
    {
      id: "12b",
      titolo: "Più immobili",
      clip: "12-piu-immobili.mp4",
      inizio: 5.65,
      fine: 14.8,
      didascalie: [
        { testo: "A stanze o appartamento intero, anche più d'uno.", da: 0.4, a: 8.9 },
      ],
    },
  ],
};
