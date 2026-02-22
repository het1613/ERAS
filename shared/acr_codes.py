"""
Ontario Ambulance Call Report (ACR) Problem Codes with keyword mappings and MPDS priorities.

Source: https://www.ontario.ca/page/ambulance-call-report-codes

Each code entry contains:
  - code: Ontario ACR Problem Code number
  - description: Official descriptor
  - category: Grouping category
  - default_priority: Default MPDS dispatch priority (Purple/Red/Orange/Yellow/Green)
  - keywords: List of keywords/phrases used to match transcript text.
              Multi-word phrases are weighted higher during matching.
"""

ACR_PROBLEM_CODES = [
    # ── VSA (Vital Signs Absent) ─────────────────────────────────────────
    {
        "code": "1",
        "description": "VSA - Cardiac / Medical",
        "category": "VSA",
        "default_priority": "Purple",
        "keywords": [
            "no pulse", "not breathing", "no heartbeat", "vital signs absent",
            "cardiac arrest", "cpr", "flatline", "clinically dead",
            "no signs of life", "pulseless", "unresponsive not breathing",
            "agonal breathing", "death", "dead",
        ],
    },
    {
        "code": "2",
        "description": "VSA - Traumatic",
        "category": "VSA",
        "default_priority": "Purple",
        "keywords": [
            "traumatic arrest", "traumatic cardiac arrest",
            "no pulse after trauma", "no pulse after accident",
            "vital signs absent trauma", "crush injury no pulse",
        ],
    },

    # ── Airway ────────────────────────────────────────────────────────────
    {
        "code": "11",
        "description": "Obstruction (Partial/Complete)",
        "category": "Airway",
        "default_priority": "Red",
        "keywords": [
            "choking", "can't breathe", "cannot breathe", "airway obstruction",
            "something stuck in throat", "swallowed something",
            "food stuck", "gagging", "throat blocked", "can't swallow",
            "blocked airway", "object in throat", "aspirating",
        ],
    },

    # ── Breathing ─────────────────────────────────────────────────────────
    {
        "code": "21",
        "description": "Dyspnea",
        "category": "Breathing",
        "default_priority": "Orange",
        "keywords": [
            "difficulty breathing", "short of breath", "shortness of breath",
            "hard to breathe", "trouble breathing", "labored breathing",
            "wheezing", "asthma", "asthma attack", "can't catch breath",
            "hyperventilating", "hyperventilation", "breathing fast",
            "breathing problem", "respiratory distress", "dyspnea",
            "copd", "emphysema", "bronchitis",
        ],
    },
    {
        "code": "24",
        "description": "Respiratory Arrest",
        "category": "Breathing",
        "default_priority": "Purple",
        "keywords": [
            "stopped breathing", "not breathing", "respiratory arrest",
            "no breathing", "breathing stopped", "apnea",
            "lips turning blue", "cyanotic", "blue lips",
        ],
    },

    # ── Circulation ───────────────────────────────────────────────────────
    {
        "code": "31",
        "description": "Hemorrhage",
        "category": "Circulation",
        "default_priority": "Red",
        "keywords": [
            "bleeding", "hemorrhage", "heavy bleeding", "severe bleeding",
            "blood everywhere", "losing blood", "blood loss",
            "bleeding won't stop", "uncontrolled bleeding", "hemorrhaging",
            "arterial bleeding", "bleeding out", "pool of blood",
        ],
    },
    {
        "code": "32",
        "description": "Hypertension",
        "category": "Circulation",
        "default_priority": "Yellow",
        "keywords": [
            "high blood pressure", "hypertension", "blood pressure high",
            "hypertensive", "blood pressure spike",
        ],
    },
    {
        "code": "33",
        "description": "Hypotension",
        "category": "Circulation",
        "default_priority": "Orange",
        "keywords": [
            "low blood pressure", "hypotension", "blood pressure low",
            "blood pressure dropping", "hypotensive", "feeling faint low bp",
        ],
    },
    {
        "code": "34",
        "description": "Suspected Sepsis",
        "category": "Circulation",
        "default_priority": "Red",
        "keywords": [
            "sepsis", "septic", "infection spreading", "blood infection",
            "fever and confusion", "high fever and chills",
            "infected wound spreading", "systemic infection",
        ],
    },

    # ── Neurological ──────────────────────────────────────────────────────
    {
        "code": "40",
        "description": "Traumatic Brain Injury",
        "category": "Neurological",
        "default_priority": "Red",
        "keywords": [
            "head injury", "head trauma", "hit head", "traumatic brain injury",
            "skull fracture", "concussion", "brain injury",
            "blow to the head", "head wound", "cracked skull",
        ],
    },
    {
        "code": "41",
        "description": "Stroke / TIA",
        "category": "Neurological",
        "default_priority": "Red",
        "keywords": [
            "stroke", "face drooping", "arm weakness", "speech difficulty",
            "slurred speech", "can't move one side", "paralysis one side",
            "tia", "transient ischemic", "mini stroke",
            "face is drooping", "one side numb", "sudden numbness",
            "vision loss sudden", "sudden confusion",
        ],
    },
    {
        "code": "42",
        "description": "Temp. Loss of Consciousness",
        "category": "Neurological",
        "default_priority": "Orange",
        "keywords": [
            "fainted", "passed out", "lost consciousness", "syncope",
            "blacked out", "collapsed", "went limp", "fainting",
            "temporarily unconscious", "briefly unconscious",
        ],
    },
    {
        "code": "43",
        "description": "Altered Level of Consciousness",
        "category": "Neurological",
        "default_priority": "Orange",
        "keywords": [
            "altered consciousness", "not fully conscious",
            "drowsy and confused", "not responding normally",
            "altered mental status", "semi conscious", "barely responsive",
            "in and out of consciousness", "altered loc",
        ],
    },
    {
        "code": "44",
        "description": "Headache",
        "category": "Neurological",
        "default_priority": "Yellow",
        "keywords": [
            "headache", "severe headache", "worst headache",
            "thunderclap headache", "migraine", "head pain",
            "head is pounding", "splitting headache",
        ],
    },
    {
        "code": "45",
        "description": "Behaviour / Psychiatric",
        "category": "Neurological",
        "default_priority": "Orange",
        "keywords": [
            "psychiatric", "mental health crisis", "suicidal",
            "self harm", "behavioral emergency", "psychotic",
            "hallucinating", "hearing voices", "threatening",
            "agitated", "violent behavior", "mental breakdown",
            "anxiety attack", "panic attack", "psychiatric emergency",
        ],
    },
    {
        "code": "46",
        "description": "Active Seizure",
        "category": "Neurological",
        "default_priority": "Red",
        "keywords": [
            "seizure", "convulsions", "convulsing", "fitting",
            "having a seizure", "shaking uncontrollably", "epilepsy",
            "epileptic", "grand mal", "tonic clonic",
            "eyes rolling back", "body stiffening",
        ],
    },
    {
        "code": "47",
        "description": "Paralysis / Spinal Trauma",
        "category": "Neurological",
        "default_priority": "Red",
        "keywords": [
            "paralysis", "paralyzed", "can't move legs", "can't feel legs",
            "spinal injury", "spinal cord", "neck injury", "back broken",
            "spine injury", "quadriplegic", "paraplegic",
            "can't move arms", "can't feel anything below",
        ],
    },
    {
        "code": "48",
        "description": "Confusion / Disorientation",
        "category": "Neurological",
        "default_priority": "Yellow",
        "keywords": [
            "confused", "disoriented", "doesn't know where",
            "confusion", "not making sense", "incoherent",
            "doesn't recognize", "lost and confused",
        ],
    },
    {
        "code": "49",
        "description": "Unconscious",
        "category": "Neurological",
        "default_priority": "Red",
        "keywords": [
            "unconscious", "unresponsive", "won't wake up",
            "not waking up", "knocked out", "comatose",
            "not responding", "out cold", "completely unresponsive",
        ],
    },
    {
        "code": "50",
        "description": "Post-ictal",
        "category": "Neurological",
        "default_priority": "Orange",
        "keywords": [
            "post seizure", "after seizure", "post ictal",
            "had a seizure", "seizure ended", "confused after seizure",
            "just had a seizure", "recovering from seizure",
        ],
    },

    # ── Cardiac ───────────────────────────────────────────────────────────
    {
        "code": "51",
        "description": "Ischemic",
        "category": "Cardiac",
        "default_priority": "Red",
        "keywords": [
            "heart attack", "myocardial infarction", "chest pain",
            "crushing chest pain", "chest tightness", "pressure in chest",
            "chest pain radiating", "pain down left arm",
            "angina", "ischemic", "heart pain",
            "elephant on chest", "squeezing chest",
        ],
    },
    {
        "code": "53",
        "description": "Palpitations",
        "category": "Cardiac",
        "default_priority": "Yellow",
        "keywords": [
            "palpitations", "heart racing", "heart fluttering",
            "irregular heartbeat", "heart skipping beats",
            "rapid heart rate", "heart pounding", "tachycardia",
            "heart beating fast", "arrhythmia", "afib",
            "atrial fibrillation",
        ],
    },
    {
        "code": "54",
        "description": "Pulmonary Edema",
        "category": "Cardiac",
        "default_priority": "Red",
        "keywords": [
            "pulmonary edema", "fluid in lungs", "lungs filling with fluid",
            "drowning in own fluid", "frothy sputum", "pink frothy",
            "can't breathe lying down", "heart failure breathing",
        ],
    },
    {
        "code": "55",
        "description": "Post Arrest",
        "category": "Cardiac",
        "default_priority": "Purple",
        "keywords": [
            "post arrest", "after cardiac arrest", "rosc",
            "return of spontaneous circulation", "revived",
            "heart started again", "pulse came back",
        ],
    },
    {
        "code": "56",
        "description": "Cardiogenic Shock",
        "category": "Cardiac",
        "default_priority": "Purple",
        "keywords": [
            "cardiogenic shock", "heart failing", "heart not pumping",
            "cardiac shock", "pump failure",
        ],
    },
    {
        "code": "57",
        "description": "STEMI",
        "category": "Cardiac",
        "default_priority": "Purple",
        "keywords": [
            "stemi", "st elevation", "massive heart attack",
            "widowmaker", "acute mi", "st segment elevation",
        ],
    },
    {
        "code": "58",
        "description": "Hyperkalemia",
        "category": "Cardiac",
        "default_priority": "Red",
        "keywords": [
            "hyperkalemia", "high potassium", "potassium level high",
            "dialysis missed potassium",
        ],
    },

    # ── Non-Traumatic ─────────────────────────────────────────────────────
    {
        "code": "60",
        "description": "Non-Ischemic Chest Pain",
        "category": "Non-Traumatic",
        "default_priority": "Orange",
        "keywords": [
            "chest pain non cardiac", "chest wall pain",
            "pleurisy", "pleuritic chest pain", "sharp chest pain",
            "chest pain when breathing", "rib pain",
            "costochondritis", "chest discomfort",
        ],
    },
    {
        "code": "61",
        "description": "Abdominal / Pelvic Pain",
        "category": "Non-Traumatic",
        "default_priority": "Orange",
        "keywords": [
            "abdominal pain", "stomach pain", "belly pain",
            "stomach ache", "pelvic pain", "lower abdomen pain",
            "cramping", "severe cramps", "abdomen hurts",
            "appendicitis", "appendix", "peritonitis",
            "rectal pain", "groin pain",
        ],
    },
    {
        "code": "61.1",
        "description": "Renal Colic",
        "category": "Non-Traumatic",
        "default_priority": "Orange",
        "keywords": [
            "kidney stone", "renal colic", "kidney pain",
            "flank pain", "stone passing",
        ],
    },
    {
        "code": "62",
        "description": "Back Pain",
        "category": "Non-Traumatic",
        "default_priority": "Yellow",
        "keywords": [
            "back pain", "lower back pain", "upper back pain",
            "back spasm", "sciatica", "back went out",
            "slipped disc", "herniated disc", "back hurts",
        ],
    },

    # ── Gastrointestinal ──────────────────────────────────────────────────
    {
        "code": "63",
        "description": "Nausea / Vomiting / Diarrhea",
        "category": "Gastrointestinal",
        "default_priority": "Yellow",
        "keywords": [
            "vomiting", "nausea", "throwing up", "diarrhea",
            "nauseous", "vomiting blood", "blood in stool",
            "can't stop vomiting", "gastroenteritis",
            "food poisoning", "stomach flu", "sick to stomach",
        ],
    },

    # ── Integumentary ─────────────────────────────────────────────────────
    {
        "code": "65",
        "description": "Integumentary",
        "category": "Integumentary",
        "default_priority": "Yellow",
        "keywords": [
            "skin condition", "rash", "severe rash", "skin issue",
            "skin infection", "cellulitis", "abscess",
        ],
    },

    # ── Musculoskeletal / Trauma ──────────────────────────────────────────
    {
        "code": "66",
        "description": "Musculoskeletal",
        "category": "Musculoskeletal/Trauma",
        "default_priority": "Yellow",
        "keywords": [
            "broken bone", "fracture", "sprain", "dislocation",
            "twisted ankle", "broken arm", "broken leg",
            "broken hip", "hip fracture", "wrist broken",
            "dislocated shoulder", "joint injury", "muscle injury",
        ],
    },
    {
        "code": "67",
        "description": "Trauma / Injury",
        "category": "Musculoskeletal/Trauma",
        "default_priority": "Orange",
        "keywords": [
            "car accident", "vehicle accident", "collision", "crash",
            "pedestrian hit", "pedestrian struck", "hit by car",
            "motorcycle accident", "bicycle accident", "fall",
            "fell from height", "fell down stairs", "assault",
            "stabbing", "stabbed", "gunshot", "shot", "explosion",
            "blunt trauma", "injury", "injured", "trauma",
            "multiple injuries", "mva", "mvc", "motor vehicle",
        ],
    },

    # ── Obstetrical / Gynecological ───────────────────────────────────────
    {
        "code": "71",
        "description": "Obstetrical Emergency",
        "category": "Obstetrical/Gynecological",
        "default_priority": "Red",
        "keywords": [
            "labor", "contractions", "water broke", "giving birth",
            "delivering", "baby coming", "pregnancy complication",
            "pregnant bleeding", "miscarriage", "placenta",
            "umbilical cord", "breech", "premature labor",
            "crowning", "birth",
        ],
    },
    {
        "code": "72",
        "description": "Gynecological Emergency",
        "category": "Obstetrical/Gynecological",
        "default_priority": "Orange",
        "keywords": [
            "vaginal bleeding", "gynecological", "ectopic pregnancy",
            "ovarian", "severe menstrual",
        ],
    },
    {
        "code": "73",
        "description": "Newborn / Neonatal",
        "category": "Obstetrical/Gynecological",
        "default_priority": "Red",
        "keywords": [
            "newborn", "neonate", "baby not breathing",
            "infant not breathing", "baby blue", "newborn emergency",
            "just born", "baby limp", "neonatal",
        ],
    },

    # ── Endocrine / Toxicological ─────────────────────────────────────────
    {
        "code": "81",
        "description": "Drug / Alcohol Overdose",
        "category": "Endocrine/Toxicological",
        "default_priority": "Red",
        "keywords": [
            "overdose", "od", "drug overdose", "too many pills",
            "alcohol poisoning", "intoxicated unresponsive",
            "took too much", "pills", "substance abuse",
            "drunk and unconscious", "binge drinking",
        ],
    },
    {
        "code": "81.1",
        "description": "Suspected Opioid Overdose",
        "category": "Endocrine/Toxicological",
        "default_priority": "Purple",
        "keywords": [
            "opioid overdose", "fentanyl", "heroin", "narcan",
            "naloxone", "opioid", "needle in arm",
            "pinpoint pupils", "not breathing opioid",
            "blue lips drugs", "fentanyl overdose",
        ],
    },
    {
        "code": "82",
        "description": "Poisoning / Toxic Exposure",
        "category": "Endocrine/Toxicological",
        "default_priority": "Orange",
        "keywords": [
            "poisoning", "poisoned", "toxic exposure", "chemical exposure",
            "ingested poison", "drank bleach", "carbon monoxide",
            "co poisoning", "gas leak", "fumes", "chemical spill",
            "hazmat", "toxic fumes", "swallowed chemicals",
        ],
    },
    {
        "code": "83",
        "description": "Diabetic Emergency",
        "category": "Endocrine/Toxicological",
        "default_priority": "Red",
        "keywords": [
            "diabetic emergency", "low blood sugar", "high blood sugar",
            "hypoglycemia", "hyperglycemia", "diabetes",
            "insulin reaction", "diabetic shock", "sugar too low",
            "sugar too high", "diabetic coma", "diabetic",
        ],
    },
    {
        "code": "84",
        "description": "Allergic Reaction",
        "category": "Endocrine/Toxicological",
        "default_priority": "Orange",
        "keywords": [
            "allergic reaction", "allergy", "hives", "swelling",
            "face swelling", "tongue swelling", "lips swelling",
            "itching all over", "allergic", "reaction to food",
            "bee sting reaction", "peanut allergy",
        ],
    },
    {
        "code": "85",
        "description": "Anaphylaxis",
        "category": "Endocrine/Toxicological",
        "default_priority": "Purple",
        "keywords": [
            "anaphylaxis", "anaphylactic", "epipen", "epi pen",
            "throat closing", "throat swelling shut",
            "can't breathe allergic", "severe allergic reaction",
            "anaphylactic shock", "tongue swelling can't breathe",
        ],
    },
    {
        "code": "86",
        "description": "Adrenal Crisis",
        "category": "Endocrine/Toxicological",
        "default_priority": "Red",
        "keywords": [
            "adrenal crisis", "addison", "adrenal insufficiency",
            "missed cortisol", "steroid dependent",
        ],
    },

    # ── General and Minor ─────────────────────────────────────────────────
    {
        "code": "89",
        "description": "Lift Assist",
        "category": "General",
        "default_priority": "Green",
        "keywords": [
            "lift assist", "fallen can't get up", "can't get up",
            "fell and can't get up", "needs help getting up",
            "on the floor can't get up",
        ],
    },
    {
        "code": "91",
        "description": "Environmental Emergency",
        "category": "General",
        "default_priority": "Orange",
        "keywords": [
            "hypothermia", "heat stroke", "heat exhaustion",
            "drowning", "near drowning", "cold exposure",
            "frostbite", "lightning strike", "electrocution",
            "submersion", "frozen", "overheating",
        ],
    },
    {
        "code": "92",
        "description": "Weakness / Dizziness / Unwell",
        "category": "General",
        "default_priority": "Yellow",
        "keywords": [
            "weak", "weakness", "dizzy", "dizziness", "lightheaded",
            "unwell", "not feeling well", "generally unwell",
            "malaise", "fatigue", "lethargic", "feeling faint",
            "vertigo", "room spinning",
        ],
    },
    {
        "code": "95",
        "description": "Infectious Disease",
        "category": "General",
        "default_priority": "Yellow",
        "keywords": [
            "fever", "high fever", "infection", "flu symptoms",
            "covid", "infectious", "contagious",
            "fever and chills", "body aches and fever",
        ],
    },
    {
        "code": "99",
        "description": "Other Medical / Trauma",
        "category": "General",
        "default_priority": "Yellow",
        "keywords": [
            "medical emergency", "emergency", "ambulance",
            "need help", "urgent", "unknown medical",
        ],
    },
]


def get_acr_codes_for_api():
    """Return ACR codes in a format suitable for the REST API (without keywords)."""
    return [
        {
            "code": entry["code"],
            "description": entry["description"],
            "category": entry["category"],
            "default_priority": entry["default_priority"],
        }
        for entry in ACR_PROBLEM_CODES
    ]
