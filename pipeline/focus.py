"""Heuristic 'focus' tag derived from a company's name and Form D industry group.

This is a Phase 1.5 placeholder: a keyword ladder that gives readers a rough
sense of what the company *might* do. It is deliberately coarse — real natural-
language descriptions arrive in Phase 2 via SBIR award abstracts and news RSS.

The function always returns a non-empty string; when nothing matches, it falls
back to a cleaned-up version of the industry group.
"""

from __future__ import annotations

import re

_RULES: list[tuple[re.Pattern, str]] = [
    # Therapeutics / drug development
    (re.compile(r"\b(therapeutics?|therapy|therapies|rx)\b", re.I), "Therapeutic drug development"),
    (re.compile(r"\b(pharma|pharmaceutical|pharmaceuticals)\b", re.I), "Pharmaceutical development"),
    (re.compile(r"\b(biotech|bio|biosciences?|biopharma)\b", re.I), "Biotech R&D"),
    (re.compile(r"\b(gene|genomic|genomics|genetic)\b", re.I), "Genomics / precision medicine"),
    (re.compile(r"\b(oncolog\w*|cancer|tumor)\b", re.I), "Oncology"),
    (re.compile(r"\b(vaccin\w*|immunotherapy|immune)\b", re.I), "Immunotherapy / vaccines"),

    # Diagnostics / labs
    (re.compile(r"\b(diagnostics?|diagnostic|assay|labcorp|labs?)\b", re.I), "Diagnostics / lab testing"),
    (re.compile(r"\b(imaging|radiology|radiolog\w+|mri|ct\b|ultrasound)\b", re.I), "Medical imaging"),

    # Devices / hardware
    (re.compile(r"\b(neurolog\w*|neurosci\w*|neuro)\b", re.I), "Neurology / neuroscience"),
    (re.compile(r"\b(cardio\w*|cardiac)\b", re.I), "Cardiology"),
    (re.compile(r"\b(surgical|surgery|spine|orthoped\w+)\b", re.I), "Clinical device / surgical"),
    (re.compile(r"\b(device|devices|implant|implantable|wearable|sensor)\b", re.I), "Medical device / hardware"),

    # Digital health / IT
    (re.compile(r"\b(tele(health|medicine)?|virtual care|remote)\b", re.I), "Telehealth / virtual care"),
    (re.compile(r"\b(ehr|emr|clinical ?(it|software)?|workflow|scribe)\b", re.I), "Clinical IT / EHR workflow"),
    (re.compile(r"\b(ai|artificial intelligence|machine learning|ml\b|neural|analytic\w*|data)\b", re.I),
     "AI / analytics in healthcare"),
    (re.compile(r"\b(patient|engagement|portal)\b", re.I), "Patient engagement"),
    (re.compile(r"\b(rcm|billing|claims|revenue ?cycle|prior ?auth)\b", re.I), "Revenue cycle / payer tech"),
    (re.compile(r"\b(insurance|insur\w+|benefits|payer)\b", re.I), "Payer / insurance"),
    (re.compile(r"\b(mental|behavioral|psych\w+|wellness|mind)\b", re.I), "Behavioral / mental health"),
    (re.compile(r"\b(dental|orthodont\w+)\b", re.I), "Dental"),
    (re.compile(r"\b(vision|ophthalmology|optical|optomet\w+)\b", re.I), "Vision / eye care"),
    (re.compile(r"\b(home ?health|hospice|aging|senior|elder)\b", re.I), "Home health / senior care"),
    (re.compile(r"\b(pediatric|maternal|fertility|women)\b", re.I), "Women's / maternal / pediatric"),
    (re.compile(r"\b(nutrition|diet|food|obesity)\b", re.I), "Nutrition / metabolic"),

    # Generic fallbacks (coarse)
    (re.compile(r"\b(clinic\w*|practice|physician|doctors?)\b", re.I), "Care delivery / clinical service"),
    (re.compile(r"\b(hospital|health ?system)\b", re.I), "Hospital / health system operator"),
    (re.compile(r"\b(care|health|med(ical)?|patient)\b", re.I), "Healthcare service"),
]


def infer_focus(company_name: str, industry_group: str | None) -> str:
    """Return a short coarse-grained 'focus' label for a healthtech company.

    The rules are heuristic — they match on name keywords. When nothing hits,
    we fall back to the Form D industry group so the cell is never empty.
    """
    name = company_name or ""
    for pattern, label in _RULES:
        if pattern.search(name):
            return label
    return (industry_group or "").strip() or "Healthcare (unclassified)"
