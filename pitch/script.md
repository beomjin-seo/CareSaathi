# CareSaathi: 2 minutes 30 seconds

Slides: https://claude.ai/artifact/8waEfmGVjfvEjiKGbwcf9e (2 slides). App: the Databricks Apps URL (backup: https://claude.ai/artifact/NVRcCmn2JAqG9x8MLREs6x).

Before you start: open the app in a second tab, English, on the first screen. Close every other tab. Zoom the browser to 110%.

---

## 0:00 to 0:10. Slide 1, the coin (hold up two fingers)

> In 2007, India put hands on its coins. A thumb on the one-rupee coin, two fingers on the two-rupee coin. A value you can read without reading.
> That is our design rule. In rural Bihar only about half of women can read, and a mother there still has to find the right hospital tonight. CareSaathi is built for her.

## 0:10 to 0:30. Slide 2, how we decide

> We had 9,989 hospital records and no ground truth. So we don't predict. We grade evidence.
> One, read every sentence about the service. Two, grade it: a named procedure counts almost five times a loose mention, equipment nine times, and finding what the service needs, like an operating theatre for a C-section, up to twenty-six times.
> Three, check the record is one real place. Four, safety rules: a dental clinic claiming dialysis is out. Five, rank: in an emergency the nearest, otherwise the most trusted near you.
> The weights were fitted on 605 labelled claims, not chosen by us. Let me show you.

Switch to the app tab.

---

## 0:30 to 1:10. Scene 1: a mother in Araria, Bihar, in labour

| Do | Say |
|---|---|
| Tap the **Childbirth** picture | "No reading needed. Pictures first." |
| Tap **Yes, right now** | "It's an emergency." |
| Tap **Village or town**, type `Araria`, pick it from the list | "She lives in Araria, one of the hardest-to-reach districts in India." |
| Point at the red bar | "First, free help: 108 ambulance, 102 free transport for pregnancy." |
| Point at the amber bar | "The nearest place with real evidence is 81 kilometres away. We say so, and tell her to call 108 and go to the government hospital first. We never invent a closer answer." |
| Scroll to **About this area** | "Public hospitals here do C-sections for only 4.9% of births, private ones for 45%. So she should ask before she travels." |
| Tap **Open the health worker list** | "No phone? Her village health worker prints this list or has it read aloud." |

## 1:10 to 2:15. Scene 2: a father in Chennai who needs bone surgery

| Do | Say |
|---|---|
| Tap **Start again**, **Accident / injury**, **Bone and joint surgery**, **No, I can plan**, then the **Chennai** picture | "Now a planned case: bone surgery in Chennai." |
| Point at card 1 (SPOT Hospital) and its first line | "Why number one: highest trust within 25 kilometres. Scores within 2 points count as a tie, because that is how much the score moves when we refit it, so the nearer one wins." |
| Point at **Who will treat you** | "Not just the hospital: the doctor. We read about 4,000 hospital websites and match doctors to the need. Here, an orthopaedic surgeon with 30 years of experience, from the hospital's own site." |
| Point at the four green and red steps | "Why we believe it, in the record's own words: department, procedure, equipment, this place. Green, the record says it. Red, the record is silent, which is not a no." |
| Point at **How this place compares** | "Like Medicare's Care Compare: this hospital against its state and India." |
| Tap a 🔊 button | "And every line can be read aloud." |

Backup for scene 2 if Chennai looks different on the day: **Heart → Angiography / stent → No, I can plan → Lucknow**. Card 1 (Mirus Critical Care Centre) names Dr. Mukul Misra, MBBS, MD (Medicine), DM (Cardiology).

## 2:15 to 2:30. Close

| Do | Say |
|---|---|
| Open **Show the math** on the card | "Every number traces back to a sentence in the record and a fitted weight. Nobody visited these hospitals, so we never say 'verified'. We say what to ask on the phone." |
| Look at the judges | "CareSaathi. Proof before you travel. Thank you." |

---

## If something breaks

- Map does not load: keep going, the list and cards do not need the map.
- Databricks app is asleep: use the backup link above; it is the same page.
- Araria not in the list: type the PIN `854311`.
- A judge asks "how do you know it is real": "We don't, for any single hospital. On 605 claims we could label from facility names and an independent reader, 98% of 'strong' were likely real, held out from fitting, AUC 0.88. The card always ends with what to confirm by phone."
- A judge asks about the doctors: "Read from each hospital's own website on 22 November, matched by specialty, not verified and not used in the score. We did not copy directory sites like Practo: their terms forbid it."

## Numbers used, and where they come from

| Number | Source |
|---|---|
| 2007 hand coins (₹1 thumb, ₹2 two fingers) | RBI Currency Museum, "Nritya Mudra" series |
| About half of rural Bihar women literate (54.5%) | NFHS-5 state factsheet, Bihar, rural |
| 9,989 records, 19 services | `pipeline/common.py`, `pipeline/ontology.py` |
| ×4.8, ×9.2, up to ×26, ×0.13, base 0.74 | `pipeline/trust.py` output, `pipeline/out/weights.json` |
| 605 labelled claims, AUC 0.88, 98% of strong | `analysis/FINDINGS.md` sections 11 and 13 |
| 2-point tie, 3.6 km tie | `analysis/FINDINGS.md` section 13 |
| Araria: nearest 81 km, public C-section 4.9%, private 45.2% | `app/data.json`, NFHS-5 district table (checked 22 Nov 11:20) |
| About 4,000 websites read; 1,685 hospitals with named doctors, 10,182 doctors | `pipeline/scrape_doctors.py`, `pipeline/external/doctors_web.json` |
| Chennai bone surgery card 1 SPOT Hospital, orthopaedic doctor, 30 years | `app/data.json` (checked 22 Nov 11:20) |
