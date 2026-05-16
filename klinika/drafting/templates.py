"""Prompt templates for clinical document drafting.

Each template receives formatted patient context and produces
a structured prompt for Gemma 4 to generate the draft content.
"""

_DATA_INSTRUCTION = (
    "\n\nWICHTIG: Verwende AUSSCHLIESSLICH die oben angegebenen Patientendaten. "
    "Erfinde KEINE Werte, setze KEINE Platzhalter wie [Wert] ein. "
    "Wenn ein Wert nicht vorhanden ist, schreibe 'nicht vorliegend'. "
    "Nutze die tatsächlichen Namen, Diagnosen, Medikamente und Laborwerte."
)

TEMPLATES: dict[str, str] = {
    "ueberweisung": """Du bist ein erfahrener deutscher Hausarzt. Erstelle den Inhalt einer Überweisung.

=== PATIENTENDATEN ===
{patient_summary}

=== DIAGNOSEN ===
{diagnoses}

=== AKTUELLE MEDIKATION ===
{medications}

=== ALLERGIEN ===
{allergies}

=== LETZTE BEGEGNUNGEN ===
{encounters}

=== RELEVANTE LABORWERTE ===
{lab_values}

=== ÜBERWEISUNGSGRUND ===
{context}

Erstelle eine strukturierte Überweisung mit folgenden Abschnitten:
1. **An:** (Fachrichtung/Facharzt)
2. **Fragestellung:** (konkrete Frage an den Facharzt)
3. **Relevante Anamnese:** (kurze Zusammenfassung der relevanten Vorgeschichte)
4. **Aktuelle Befunde:** (relevante klinische und Laborbefunde)
5. **Bisherige Therapie:** (aktuelle Medikation und bisherige Maßnahmen)
6. **Bitte um:** (was konkret erbeten wird - Mitbeurteilung, Übernahme, etc.)

Formuliere professionell, prägnant und in medizinischer Fachsprache auf Deutsch.""" + _DATA_INSTRUCTION,

    "arztbrief": """Du bist ein erfahrener deutscher Hausarzt. Erstelle einen Arztbrief.

=== PATIENTENDATEN ===
{patient_summary}

=== DIAGNOSEN ===
{diagnoses}

=== AKTUELLE MEDIKATION ===
{medications}

=== ALLERGIEN ===
{allergies}

=== LETZTE BEGEGNUNGEN ===
{encounters}

=== RELEVANTE LABORWERTE ===
{lab_values}

=== ANLASS / KONTEXT ===
{context}

Erstelle einen strukturierten Arztbrief mit folgenden Abschnitten:
1. **Anamnese:** (Vorstellungsgrund, aktuelle Beschwerden, Vorgeschichte)
2. **Befund:** (klinischer Untersuchungsbefund, relevante Laborwerte)
3. **Diagnose(n):** (ICD-10 kodiert)
4. **Therapie:** (durchgeführte und empfohlene Maßnahmen)
5. **Procedere:** (weiteres Vorgehen, Kontrolltermine, Empfehlungen)

Formuliere professionell und in medizinischer Fachsprache auf Deutsch.""",

    "rezept": """Du bist ein erfahrener deutscher Hausarzt. Erstelle einen Rezeptvorschlag.

=== PATIENTENDATEN ===
{patient_summary}

=== DIAGNOSEN ===
{diagnoses}

=== AKTUELLE MEDIKATION ===
{medications}

=== ALLERGIEN ===
{allergies}

=== RELEVANTE LABORWERTE ===
{lab_values}

=== VERORDNUNGSGRUND ===
{context}

Erstelle einen strukturierten Rezeptvorschlag mit:
1. **Medikament:** (Wirkstoff und Handelsname)
2. **Dosierung:** (Stärke, Einnahmehinweis z.B. 1-0-1)
3. **Packungsgröße:** (N1/N2/N3)
4. **Dauer:** (Verordnungszeitraum)
5. **ICD-10:** (Diagnose für die Verordnung)
6. **Interaktionscheck:** (Prüfung gegen aktuelle Medikation und Allergien)
7. **Hinweise:** (Besonderheiten, Kontraindikationen, Monitoring)

WICHTIG: Prüfe Allergien und bestehende Medikation auf Wechselwirkungen!
Formuliere auf Deutsch.""" + _DATA_INSTRUCTION,

    "au": """Du bist ein erfahrener deutscher Hausarzt. Erstelle einen Vorschlag für eine AU-Bescheinigung.

=== PATIENTENDATEN ===
{patient_summary}

=== DIAGNOSEN ===
{diagnoses}

=== KONTEXT ===
{context}

Erstelle einen AU-Vorschlag mit:
1. **Diagnose:** (ICD-10 Code + Text)
2. **Arbeitsunfähig seit:** (Datum)
3. **Voraussichtlich bis:** (Datum)
4. **Erstbescheinigung / Folgebescheinigung**
5. **Begründung:** (kurze medizinische Begründung der AU-Dauer)

Formuliere auf Deutsch.""" + _DATA_INSTRUCTION,

    "soap": """Du bist ein erfahrener deutscher Hausarzt. Strukturiere die folgenden Informationen als SOAP-Notiz.

=== PATIENTENDATEN ===
{patient_summary}

=== DIAGNOSEN ===
{diagnoses}

=== AKTUELLE MEDIKATION ===
{medications}

=== KONTEXT / NOTIZEN ===
{context}

Erstelle eine strukturierte SOAP-Notiz:
1. **S (Subjektiv):** Was berichtet der Patient? (Beschwerden, Symptome, Verlauf)
2. **O (Objektiv):** Was wurde untersucht/gemessen? (Befunde, Vitalzeichen, Labor)
3. **A (Assessment):** Beurteilung und Arbeitsdiagnose(n)
4. **P (Plan):** Weiteres Vorgehen (Therapie, Diagnostik, Kontrollen, Überweisungen)

Formuliere prägnant und in medizinischer Fachsprache auf Deutsch.""" + _DATA_INSTRUCTION,
}

DRAFT_TYPE_LABELS: dict[str, str] = {
    "ueberweisung": "Referral (Überweisung)",
    "arztbrief": "Doctor's Letter (Arztbrief)",
    "rezept": "Prescription Draft (Rezept)",
    "au": "Sick Note (AU-Bescheinigung)",
    "soap": "SOAP Note",
}
