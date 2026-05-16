# Klinika Test Prompts

Copy-paste these into the chat at [http://localhost:9000](http://localhost:9000) in order.

## 1. Data Import (run these first)

```
Lade die Patientendaten aus data/samples/sample_clinic_bootstrap.bdt
```

```
Synchronisiere den Kalender aus data/samples/sample_doctolib_calendar.json
```

```
Lade Laborergebnisse aus data/samples/sample_lab_results.ldt
```

## 2. Schedule Queries

```
Wer kommt heute?
```

```
Wer kommt als nächstes?
```

## 3. Patient Queries

```
Welche Medikamente nimmt Herr Schmidt?
```

```
Welche Diagnosen hat Frau Müller?
```

```
Ist Herr Schmidt allergisch gegen etwas?
```

```
Zeig mir die letzten Begegnungen von Herrn Becker
```

## 4. Lab Queries

```
Gibt es auffällige Laborwerte?
```

```
Zeig mir Schmidts HbA1c-Wert
```

```
Wie sind Beckers Nierenwerte?
```

## 5. Search Queries

```
Welche Patienten haben Diabetes?
```

```
Wer nimmt Metformin?
```

## 6. Memory

```
Merke dir: Frau Müller bevorzugt Nachmittagstermine
```

```
Was weißt du über Frau Müllers Präferenzen?
```

## 7. Drafting

```
Erstelle eine Überweisung an Kardiologie für Herrn Schmidt wegen V.a. KHK
```

```
Erstelle einen Arztbrief für Frau Müller über die Diabetes-Kontrolle
```

```
Erstelle einen Rezeptvorschlag für Herrn Becker: Torasemid erhöhen auf 20mg
```

```
Erstelle eine SOAP-Notiz für Herrn Weber: COPD-Kontrolle, FEV1 stabil
```

```
Zeig mir die letzten Entwürfe
```

## 8. Device Results (GDT)

```
Lade Geraetedaten aus data/samples/gdt/gdt_6310_ekg1_00042.gdt
```

```
Lade Geraetedaten aus data/samples/gdt/gdt_6310_spir_00044.gdt
```

```
Lade Geraetedaten aus data/samples/gdt/gdt_6310_rr01_00046.gdt
```

```
Gibt es neue Untersuchungsergebnisse?
```

```
Zeig mir das EKG von Herrn Schmidt
```

## 9. Voice Input (click mic button, speak in German)

Click the microphone button (left of text input), speak, click again to stop.
First use downloads Whisper model (~140MB). Subsequent uses are faster.

- "Wer kommt heute?"
- "Welche Medikamente nimmt Herr Schmidt?"
- "Gibt es auffaellige Laborwerte?"
- "Wie spaet ist es?"

## 10. Skills (after doing some queries first)

```
Speichere das als Skill 'Labor-Triage'
```

```
Zeig mir alle gespeicherten Skills
```

```
Fuehre den Skill 'Labor-Triage' aus
```

```
Loesche den Skill 'Labor-Triage'
```

## 11. Clinical Reasoning

```
Fasse die wichtigsten Befunde für Herrn Becker zusammen
```

```
Welche Patienten brauchen heute besondere Aufmerksamkeit?
```

## 12. Incremental Import

```
Lade die inkrementellen Daten aus data/samples/sample_clinic_incremental.bdt
```

```
Wie viele Patienten haben wir jetzt?
```

