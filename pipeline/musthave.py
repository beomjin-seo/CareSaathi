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
The shares were re-measured after the co-requirement regexes were tightened (2026-11-22): bedside monitors for an ICU
fell to 26% once Holter, fetal and glucose monitors stopped counting, and heart surgeon to 30% once the bare "M.Ch"
match was removed, so both left the list.
Not reviewed by a clinician.
"""

MUST = {
    "emergency_obstetric": [
        {"keys": ["operation_theatre"],
         "why": "A C-section cannot be done outside an operating theatre. Staff and blood can be brought in; a theatre cannot.",
         "src": "https://www.unfpa.org/resources/setting-standards-emergency-obstetric-and-newborn-care"},
    ],
    "cardiac_surgery": [
        {"keys": ["cardiac_OT", "heart_lung_machine"],
         "why": "Heart surgery needs an operating theatre, with a heart-lung machine ready even when the surgeon plans not to use one.",
         "src": "https://cdnbbsr.s3waas.gov.in/s3169779d3852b32ce8b1a1724dbf5217d/uploads/2024/08/20240828153687657.pdf"},
        {"keys": ["cardiac_ICU", "ventilator"],
         "why": "After heart surgery every patient needs intensive care with a breathing machine ready.",
         "src": "https://cdnbbsr.s3waas.gov.in/s3169779d3852b32ce8b1a1724dbf5217d/uploads/2024/08/20240828153687657.pdf"},
    ],
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
}

# passed the medical test, failed the data test (share of strong-evidence records that mention it)
DROPPED = {
    "icu": {"oxygen": 0.14, "monitors": 0.26},
    "nicu": {"warmer_or_incubator": 0.17},
    "cardiac_surgery": {"cardiac_surgeon": 0.30},
}

# share of strong-evidence records that mention each must-have in use (the data test, threshold 0.33)
SHARE = {"emergency_obstetric": [0.66], "cardiac_surgery": [0.87, 0.56], "burn_care": [0.81], "trauma_emergency": [0.66, 0.86], "cath_lab": [0.89]}

# proposed, then refuted by the second pass
REFUTED = {
    "dialysis": "RO water plant: peritoneal and bedside dialysis need none. Nephrologist: many public and chain units run with trained doctors and a visiting specialist",
    "emergency_obstetric": "anaesthesia and blood bank: commonly a visiting anaesthetist and blood from a linked bank",
    "nicu": "ventilator and specialist: Level II newborn units legitimately run without them and refer",
    "mri": "radiologist: scans are commonly reported off-site by tele-radiology",
    "burn_care": "skin graft or plastic surgeon: general surgeons graft skin in an ordinary theatre",
    "trauma_emergency": "blood bank: many hospitals operate with blood fetched from a nearby licensed bank",
    "icu": "ventilator: a Level I ICU (ISCCM 2020) may run on non-invasive support and transfer",
}

CAP = 89.9   # highest trust a claim can show when a must-have is not on the record
