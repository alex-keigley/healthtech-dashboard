"""Curated seed list of well-known US healthtech companies.

The repository's news-attachment rate for brand-new Form D filers is low —
trade press covers large incumbents more than just-funded startups. This
seed list bridges the gap: well-known digital-health names are pre-populated
in the repo so the RSS collector has something to match against when it
scans recent articles.

Seeded companies get a historical `first_surfaced_at` so they don't pollute
the weekly "newly surfaced" count, and no filing is attached — they enter
the repo via this module alone. If a seeded company later files a Form D,
the upsert merges the two records by canonical name.

1.0 behavior change: seeded companies still enter as `pending_review` (the
schema's fail-closed default) and each gets a 'new_record' review_items row
(source 'seed') just like any other newly-created company — there's no
special-cased auto-publish for the seed list.

Sources: publicly known healthtech companies from Rock Health and other
well-covered trade press. Kept distinctive-names-only so the entity
resolver doesn't over-match.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass
class SeedRecord:
    name: str
    state: Optional[str]
    focus: str
    industry_group: str = "Seed – digital health"
    entity_type: Optional[str] = None
    year_of_inc: Optional[str] = None


# Historical timestamp used for all seed rows. Chosen as a clearly-backfill
# date so it never shows up in "surfaced this week" counts.
SEED_OBSERVED_AT = "2020-01-01T00:00:00+00:00"


# Curated list. Kept to distinctive names (no generic "Health" standalone).
# Updated cautiously — every addition is a name-collision risk against the
# news feed, so prefer well-known + distinctive over merely-relevant.
SEEDS: list[SeedRecord] = [
    # Virtual care & telehealth
    SeedRecord("Teladoc Health", "NY", "Telehealth / virtual care"),
    SeedRecord("Amwell", "MA", "Telehealth / virtual care"),
    SeedRecord("MDLive", "FL", "Telehealth / virtual care"),
    SeedRecord("Doctor On Demand", "CA", "Telehealth / virtual care"),
    SeedRecord("Included Health", "CA", "Telehealth / virtual care"),
    # Digital front door / consumer health
    SeedRecord("Hims & Hers Health", "CA", "Patient engagement / consumer health"),
    SeedRecord("Ro Health", "NY", "Patient engagement / consumer health"),
    SeedRecord("K Health", "NY", "AI-enabled primary care"),
    SeedRecord("Carbon Health", "CA", "Primary care / clinic operator"),
    SeedRecord("Forward Health", "CA", "Primary care / membership"),
    SeedRecord("Maven Clinic", "NY", "Women's health / virtual care"),
    SeedRecord("Kindbody", "NY", "Fertility / women's health"),
    SeedRecord("Tia Clinic", "NY", "Women's health / clinic operator"),
    # Behavioral health
    SeedRecord("Lyra Health", "CA", "Behavioral / mental health"),
    SeedRecord("Spring Health", "NY", "Behavioral / mental health"),
    SeedRecord("Headspace Health", "CA", "Behavioral / mental health"),
    SeedRecord("Talkspace", "NY", "Behavioral / mental health"),
    SeedRecord("Modern Health", "CA", "Behavioral / mental health"),
    SeedRecord("Tava Health", "UT", "Behavioral / mental health"),
    SeedRecord("Alma", "NY", "Behavioral / mental health"),
    SeedRecord("BetterHelp", "CA", "Behavioral / mental health"),
    # Chronic care / RPM
    SeedRecord("Hinge Health", "CA", "Digital MSK / RPM"),
    SeedRecord("Sword Health", "NY", "Digital MSK / RPM"),
    SeedRecord("Omada Health", "CA", "Chronic care management"),
    SeedRecord("Livongo Health", "CA", "Chronic care / diabetes"),
    SeedRecord("Virta Health", "CA", "Chronic care / metabolic"),
    # Insurance / payer tech
    SeedRecord("Oscar Health", "NY", "Health insurance / payer tech"),
    SeedRecord("Clover Health", "NJ", "Health insurance / payer tech"),
    SeedRecord("Devoted Health", "MA", "Medicare Advantage"),
    SeedRecord("Bright Health Group", "MN", "Health insurance / payer tech"),
    SeedRecord("Alignment Healthcare", "CA", "Medicare Advantage"),
    # Clinical IT / EHR / interop
    SeedRecord("Innovaccer", "CA", "Healthcare data platform"),
    SeedRecord("Health Catalyst", "UT", "Healthcare analytics"),
    SeedRecord("Komodo Health", "CA", "Real-world data platform"),
    SeedRecord("Flatiron Health", "NY", "Oncology clinical data"),
    SeedRecord("Notable Health", "CA", "Patient intake / clinical AI"),
    SeedRecord("Suki AI", "CA", "Ambient clinical AI"),
    SeedRecord("Abridge", "PA", "Ambient clinical AI"),
    SeedRecord("Ambience Healthcare", "CA", "Ambient clinical AI"),
    SeedRecord("DeepScribe", "CA", "Ambient clinical AI"),
    SeedRecord("Nuance Communications", "MA", "Clinical documentation AI"),
    SeedRecord("Olive AI", "OH", "Healthcare operations AI"),
    # Diagnostics / genomics / imaging
    SeedRecord("Tempus Labs", "IL", "Oncology data / diagnostics"),
    SeedRecord("Guardant Health", "CA", "Oncology diagnostics"),
    SeedRecord("10x Genomics", "CA", "Genomics"),
    SeedRecord("Natera", "CA", "Genomics / diagnostics"),
    SeedRecord("Everly Health", "TX", "Consumer diagnostics"),
    # Digital therapeutics
    SeedRecord("Akili Interactive", "MA", "Digital therapeutics"),
    SeedRecord("Pear Therapeutics", "MA", "Digital therapeutics"),
    SeedRecord("Big Health", "CA", "Digital therapeutics"),
    # Care coordination / SDoH
    SeedRecord("Unite Us", "NY", "SDoH / care coordination"),
    SeedRecord("Rightway Healthcare", "NY", "Care navigation"),
    # Ops / scheduling / staffing
    SeedRecord("Clipboard Health", "CA", "Healthcare staffing"),
    SeedRecord("ShiftKey", "TX", "Healthcare staffing"),
    SeedRecord("Trusted Health", "CA", "Healthcare staffing"),
    # Medical devices / monitoring
    SeedRecord("Dexcom", "CA", "Continuous glucose monitoring"),
    SeedRecord("Butterfly Network", "CT", "Medical imaging / point of care"),
    SeedRecord("iRhythm Technologies", "CA", "Cardiac monitoring"),
    # Employer benefits / transparency
    SeedRecord("Transcarent", "CA", "Employer healthcare platform"),
    SeedRecord("Nava Benefits", "NY", "Employer benefits"),
    # Primary-care / clinic operators in the news cycle
    SeedRecord("One Medical", "CA", "Primary care / membership"),
    SeedRecord("Cityblock Health", "NY", "Community health / Medicaid"),
    SeedRecord("Zocdoc", "NY", "Appointment booking / patient engagement"),
    # Recently-funded healthtechs that show up in 2026 trade press
    SeedRecord("Courier Health", "NY", "Biopharma patient CRM"),
    SeedRecord("Amperos Health", "CA", "AI denial management / RCM"),
]


def collect() -> list[SeedRecord]:
    """Return the curated seed list. No network I/O."""
    return list(SEEDS)
