"""Must-have items per service.

A must-have is something the service cannot be delivered without. It is not a sign of quality.
Each entry is a group of co-requirement keys from ontology.py. Finding ANY key of the group in the record satisfies it.

Rule applied in export_app.py: if a must-have group is not found in the record, the claim cannot be shown as
"strong evidence" (trust stops at CAP, just under the strong threshold) and the card tells the user to confirm
the item by phone first. The facility is never removed for this reason: a silent record is not a "no".

An item is on this list only if it passed two tests:
  (a) medical: a web-research pass proposed it from Indian and international standards, and a second pass that
      tried to refute it ("is there a common, legitimate way to deliver the service without it?") failed to;
  (b) data: at least one in three strong-evidence records for the service mention it. If almost no record
      mentions an item (oxygen for an ICU, the water plant for dialysis), silence is the norm and tells us nothing.

Items that passed (a) but not (b) are listed in DROPPED so the decision can be audited.
Not reviewed by a clinician.
"""

MUST = {
    "burn_care": [
        {"keys": ["operation_theatre"],
         "why": "Deep burns need surgery under anaesthesia; the national burn guideline tells hospitals without a theatre to refer the patient on.",
         "src": "https://www.dghs.mohfw.gov.in/uploads/assets/S1Ipab4025VceQpFs7Qa6THwh07NLmggStsg1cDD.pdf"},
    ],
    "trauma_emergency": [
        {"keys": ["operation_theatre"],
         "why": "A badly bleeding patient can only be saved by immediate surgery; without a theatre a hospital can only stabilise and transfer.",
         "src": "https://www.dghs.mohfw.gov.in/uploads/assets/SwQ7pJMiJepMtqfUQNUJrGOROd584XHIgipqf7gI.pdf"},
        {"keys": ["surgeon_ortho_or_neuro"],
         "why": "Injuries need a general, bone or brain surgeon to operate; a visiting or on-call surgeon counts.",
         "src": "https://www.dghs.mohfw.gov.in/uploads/assets/SwQ7pJMiJepMtqfUQNUJrGOROd584XHIgipqf7gI.pdf"},
    ],
    "cath_lab": [
        {"keys": ["cardiologist"],
         "why": "Angiography and angioplasty are done by a heart doctor in person; a visiting cardiologist counts.",
         "src": "https://pmc.ncbi.nlm.nih.gov/articles/PMC11307489"},
    ],
    "icu": [
        {"keys": ["monitors"],
         "why": "Continuous bedside monitoring is what makes a ward an intensive care unit.",
         "src": "https://pmc.ncbi.nlm.nih.gov/articles/PMC7085818"},
    ],
}

# passed the medical test, failed the data test (share of strong-evidence records that mention it)
DROPPED = {
    "icu": {"oxygen": 0.14},
}

# proposed, then refuted by the second pass
REFUTED = {
    "burn_care": "skin graft or plastic surgeon: general surgeons graft skin in an ordinary theatre",
    "trauma_emergency": "blood bank: many hospitals operate with blood fetched from a nearby licensed bank",
    "icu": "ventilator: a Level I ICU (ISCCM 2020) may run on non-invasive support and transfer",
}

CAP = 89.9   # highest trust a claim can show when a must-have is not on the record
