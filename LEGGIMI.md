# Rassegna eventi attorno a Parma

Web app installabile sul telefono che raccoglie gli eventi in un raggio di 100 km da Parma.

## Cosa c'è nella cartella

| File | A cosa serve |
|---|---|
| `raccogli.py` | Scarica gli eventi dalle fonti, tiene quelli nel raggio e nei prossimi 60 giorni, toglie i doppioni, scrive `app/eventi.json` |
| `config.json` | Centro, raggio, quanti giorni in avanti guardare |
| `segnalazioni.json` | Eventi inseriti a mano (c'è un esempio da copiare) |
| `Aggiorna-eventi.bat` | Doppio clic: aggiorna gli eventi e apre l'app nel browser del computer |
| `app/` | L'app vera e propria (pagina, icone, file per l'installazione sul telefono) |

## Fonti

1. **Emilia-Romagna Turismo**, open data ufficiale della Regione: attiva, gratuita, senza chiave.
   Copre solo l'Emilia-Romagna e pubblica soprattutto eventi di richiamo (mostre, fiere, sagre principali).
2. **Il Tacco di Bacco** (iltaccodibacco.it): attiva. Legge i dati strutturati degli eventi pubblicati
   nelle pagine di 11 province (Parma, Reggio Emilia, Piacenza, Modena, Cremona, Mantova, Brescia, Lodi,
   Bologna, La Spezia, Lucca). Le sue condizioni ammettono solo l'uso personale e non commerciale:
   se l'app diventasse pubblica o commerciale, va chiesto il permesso al sito.
   Le coordinate dei paesi vengono da OpenStreetMap e restano in `geocache.json`.
3. **Segnalazioni a mano**: attiva, si compila `segnalazioni.json`.
4. **Ticketmaster**: pronta ma spenta. Si accende impostando la variabile d'ambiente `TICKETMASTER_KEY`
   con una chiave gratuita presa da developer.ticketmaster.com. Copertura dell'Italia da verificare.

## Fonti verificate il 05/11/2026, non ancora collegate

| Sito | Stato |
|---|---|
| Teatro Due, Parma | Calendario leggibile (WordPress, plugin EventON) |
| Teatro al Parco / Solares, Parma | Calendario leggibile (WordPress, voce "appuntamenti") |
| Teatro Comunale Pavarotti-Freni, Modena | Calendario leggibile (WordPress, plugin MEC), da approfondire |
| ParmaToday eventi | Feed RSS presente ma rifiuta i programmi automatici (errore 403): escluso |
| DICE, TicketOne, Eventbrite | Nessun accesso pubblico: esclusi |
| Arci Taun Fidenza, Vibra Club Modena | Indirizzo del sito da trovare |
