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
//   zoom            Ken Burns lento (default attivo, vedi `zoomPredefinito`);
//                   false per disattivarlo, oppure { da, a, origine }
//   sezione         se presente, cartello di sezione di ~2 s prima della scena
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
};

export type Manifest = {
  readonly apertura: {
    readonly durata: number;
    readonly titolo: string;
    readonly sottotitolo: string;
  };
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
    {
      id: "07",
      titolo: "Spese e conto economico",
      clip: "07-spese-conto-economico.mp4",
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
      id: "08",
      titolo: "Saldi proprietari",
      clip: "08-saldi-proprietari.mp4",
      inizio: 0.3,
      fine: 9.8,
      didascalie: [
        { testo: "Più proprietari? Chi ha anticipato cosa, e chi deve a chi.", da: 0.5, a: 9.3 },
      ],
    },
    {
      id: "09",
      titolo: "Annuncio pubblico",
      clip: "09-annuncio-pubblico.mp4",
      sezione: "Trovare inquilini",
      inizio: 0.3,
      fine: 17.5,
      velocita: 1.35,
      didascalie: [{ testo: "Un annuncio pronto da condividere.", da: 0.5, a: 10.5 }],
    },
    {
      id: "10",
      titolo: "Cerca inquilini",
      clip: "10-cerca-inquilini.mp4",
      inizio: 0.2,
      fine: 10.4,
      velocita: 1.1,
      didascalie: [
        { testo: "I contatti da Facebook e Subito, già riassunti.", da: 0.5, a: 9.9 },
      ],
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
