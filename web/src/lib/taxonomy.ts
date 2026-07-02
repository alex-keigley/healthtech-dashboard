// The fixed 18-category tech-tag taxonomy (METHODOLOGY/PLAN). Human tags
// (origin='human') outrank machine tags and are never overwritten by the
// pipeline.
export const TAXONOMY = [
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
] as const;

export type TaxonomyCategory = (typeof TAXONOMY)[number];
