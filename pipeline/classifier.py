"""Healthtech technology taxonomy classifier.

Rule-based, multi-label. For each company we tag 0+ technology categories
by matching keyword patterns over any text we have: company name, Form D
industry group, heuristic focus label, and (if attached) news article
titles and abstracts.

Each tag carries a confidence score (0.0-1.0) derived from the rule that
matched and how specific the signal was. Multiple matches stack.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

# Full technology-category list, matching widely used industry groupings.
CATEGORIES = [
    "Clinical IT / EHR / workflow",
    "Interoperability & data exchange",
    "Patient engagement",
    "Telehealth / virtual care",
    "Remote patient monitoring",
    "AI/ML in healthcare",
    "Medical imaging / radiology AI",
    "Clinical decision support",
    "Revenue cycle / payer tech",
    "Population health / SDoH",
    "Cybersecurity & privacy",
    "Precision medicine / genomics",
    "Digital therapeutics",
    "Healthcare operations",
    "Therapeutics / drug development",
    "Medical devices",
    "Diagnostics",
    "Behavioral / mental health",
]

# Each rule: (compiled pattern, category, base_confidence).
# Patterns are matched case-insensitively across any available text blob.
_RULES: list[tuple[re.Pattern, str, float]] = [
    # Clinical IT / EHR / workflow
    (re.compile(r"\b(ehr|emr|clinical\s+(workflow|documentation)|scribe|charting)\b", re.I),
     "Clinical IT / EHR / workflow", 0.9),
    (re.compile(r"\b(practice\s+management|clinical\s+software|care\s+coordination)\b", re.I),
     "Clinical IT / EHR / workflow", 0.7),

    # Interoperability
    (re.compile(r"\b(fhir|hl7|tefca|interoperab\w+|data\s+exchange|health\s+information\s+exchange|hie)\b", re.I),
     "Interoperability & data exchange", 0.95),

    # Patient engagement
    (re.compile(r"\b(patient\s+(engagement|portal|experience)|digital\s+front\s+door|appointment\s+booking)\b", re.I),
     "Patient engagement", 0.9),

    # Telehealth / virtual care
    (re.compile(r"\b(tele(health|medicine)|virtual\s+care|virtual\s+visit|remote\s+visit)\b", re.I),
     "Telehealth / virtual care", 0.95),

    # Remote patient monitoring
    (re.compile(r"\b(rpm|remote\s+patient\s+monitoring|hospital[\s-]at[\s-]home|continuous\s+monitoring)\b", re.I),
     "Remote patient monitoring", 0.95),
    (re.compile(r"\b(wearable|biosensor|continuous\s+glucose)\b", re.I),
     "Remote patient monitoring", 0.7),

    # AI / ML
    (re.compile(r"\b(artificial\s+intelligence|machine\s+learning|deep\s+learning|generative\s+ai|llm|ambient\s+ai)\b", re.I),
     "AI/ML in healthcare", 0.9),
    (re.compile(r"\bai[-\s]*(powered|driven|based|enabled)\b", re.I),
     "AI/ML in healthcare", 0.85),

    # Medical imaging
    (re.compile(r"\b(radiology|imaging|mri|ct\s*scan|ultrasound|x[-\s]?ray|mammogra\w+|pathology\s+image)\b", re.I),
     "Medical imaging / radiology AI", 0.9),

    # Clinical decision support
    (re.compile(r"\b(clinical\s+decision\s+support|cds\b|diagnostic\s+support)\b", re.I),
     "Clinical decision support", 0.95),

    # Revenue cycle / payer
    (re.compile(r"\b(revenue\s+cycle|rcm\b|prior\s+auth\w*|claims\s+(management|processing)|medical\s+billing|payer\s+tech)\b", re.I),
     "Revenue cycle / payer tech", 0.95),
    (re.compile(r"\b(health\s+insurance|insurer|payer)\b", re.I),
     "Revenue cycle / payer tech", 0.55),

    # Population health / SDoH
    (re.compile(r"\b(population\s+health|social\s+determinants|sdoh|public\s+health|community\s+health)\b", re.I),
     "Population health / SDoH", 0.9),

    # Cybersecurity
    (re.compile(r"\b(cybersecurity|hipaa\s+compliance|data\s+security|healthcare\s+security|phi\s+protection)\b", re.I),
     "Cybersecurity & privacy", 0.95),

    # Precision medicine / genomics
    (re.compile(r"\b(genomic\w*|genom\w+|precision\s+medicine|sequencing|crispr|gene\s+(therapy|editing))\b", re.I),
     "Precision medicine / genomics", 0.9),

    # Digital therapeutics
    (re.compile(r"\b(digital\s+therapeutic|dtx\b|prescription\s+digital)\b", re.I),
     "Digital therapeutics", 0.95),

    # Healthcare operations
    (re.compile(r"\b(staffing|scheduling|supply\s+chain|nurse\s+scheduling|workforce)\b", re.I),
     "Healthcare operations", 0.8),

    # Therapeutics / drugs. Deliberately NO catch-all on "biotech" or
    # "bioscience" alone — the Form D industry group "Biotechnology" over-tags
    # every biotech filer as drug-development, most of which is wrong.
    # If a company genuinely does drug development, it says so in the name,
    # focus label, or attached news text.
    (re.compile(r"\b(therapeutics?|therapy|therapies|drug\s+(development|discovery)|biopharma|pharmaceutical\w*)\b", re.I),
     "Therapeutics / drug development", 0.85),

    # Medical devices
    (re.compile(r"\b(medical\s+device|implant\w*|surgical\s+(device|robot)|catheter|pacemaker|stent)\b", re.I),
     "Medical devices", 0.9),
    (re.compile(r"\b(spine|orthoped\w+|cardiac\s+device|endoscop\w+)\b", re.I),
     "Medical devices", 0.75),

    # Diagnostics
    (re.compile(r"\b(diagnostic\w*|in[-\s]?vitro|ivd\b|lab\s+test|assay|biomarker)\b", re.I),
     "Diagnostics", 0.85),

    # Behavioral / mental health
    (re.compile(r"\b(behavioral\s+health|mental\s+health|psychiat\w+|addiction|substance\s+use|wellbeing)\b", re.I),
     "Behavioral / mental health", 0.9),
]


@dataclass
class Tag:
    category: str
    confidence: float


def classify(texts: list[str]) -> list[Tag]:
    """Classify a company given any text we know about it.

    `texts` should be a list of strings (name, industry group, focus label,
    news titles, abstracts, ...). Empty strings and None are OK.
    Returns a list of Tag, one per matching category (dedup'd, max confidence
    per category). Order is by descending confidence.
    """
    blob = " \n ".join(t for t in texts if t)
    if not blob.strip():
        return []
    best: dict[str, float] = {}
    for pattern, category, conf in _RULES:
        if pattern.search(blob):
            if conf > best.get(category, 0.0):
                best[category] = conf
    return sorted(
        (Tag(category=c, confidence=conf) for c, conf in best.items()),
        key=lambda t: t.confidence,
        reverse=True,
    )
