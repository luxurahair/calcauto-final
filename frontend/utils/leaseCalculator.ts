/**
 * Moteur de calcul Location SCI Québec
 * Méthode: Annuité en avance (paiement début de période)
 * Validé le 2 mars 2026 — match parfait avec formules SCI
 */

// Constantes fiscales Québec
const TPS = 0.05;
const TVQ = 0.09975;
const TAUX_TAXE = TPS + TVQ; // 14.975%

// === Types ===

export interface LeaseInputs {
  price: number;            // Prix de vente
  pdsf: number;             // PDSF (MSRP) pour calcul résiduel
  leaseCash: number;        // Lease cash (rabais location)
  rate: number;             // Taux annuel en %
  term: number;             // Terme en mois
  residualPct: number;      // % résiduel ajusté (incluant km adjustment)
  fraisDossier: number;     // Frais de dossier
  totalAccessoires: number; // Total accessoires
  rabaisConcess: number;    // Rabais concessionnaire
  soldeReporte: number;     // Solde reporté (négatif = dette)
  tradeValue: number;       // Valeur échange
  tradeOwed: number;        // Montant dû sur échange
  comptant: number;         // Comptant taxes incluses
  bonusCash: number;        // Bonus cash
}

export interface LeaseResult {
  monthly: number;
  biweekly: number;
  weekly: number;
  monthlyBeforeTax: number;
  weeklyBeforeTax: number;
  biweeklyBeforeTax: number;
  total: number;
  rate: number;
  netCapCost: number;
  residualValue: number;
  leaseCash: number;
  capCost: number;
  tpsOnPayment: number;
  tvqOnPayment: number;
  creditTaxeParMois: number;
  creditPerdu: number;
  pdsf: number;
  rabaisConcess: number;
  coutEmprunt: number;
  fraisDossierOnly: number;
}

// === Fonctions de calcul ===

/** 1. Coût capitalisé = prix vente + accessoires - rabais concess. + frais dossier - lease cash */
export function computeCapCost(inputs: LeaseInputs): number {
  const sellingPrice = inputs.price + inputs.totalAccessoires - inputs.rabaisConcess;
  return sellingPrice + inputs.fraisDossier - inputs.leaseCash;
}

/** 2. Solde reporté net (positif = ajouter, négatif = dette avec taxes) */
export function computeSoldeNet(soldeReporte: number): number {
  if (soldeReporte < 0) return Math.abs(soldeReporte) * (1 + TAUX_TAXE);
  if (soldeReporte > 0) return soldeReporte;
  return 0;
}

/** 3. Net cap cost = cap + solde + dû échange - valeur échange - comptant - bonus */
export function computeNetCapCost(inputs: LeaseInputs): number {
  const capCost = computeCapCost(inputs);
  const soldeNet = computeSoldeNet(inputs.soldeReporte);
  return capCost + soldeNet + inputs.tradeOwed - inputs.tradeValue - inputs.comptant - inputs.bonusCash;
}

/** 4. Valeur résiduelle = PDSF × (% résiduel ajusté / 100) */
export function computeResidual(pdsf: number, adjustedResidualPct: number): number {
  return pdsf * (adjustedResidualPct / 100);
}

/** 5. PMT en avance (formule SCI exacte) */
export function computePMTAdvance(netCapCost: number, residualValue: number, rate: number, term: number): { monthlyBeforeTax: number; financeCharge: number } {
  const monthlyRate = rate / 100 / 12;

  if (monthlyRate === 0) {
    return {
      monthlyBeforeTax: (netCapCost - residualValue) / term,
      financeCharge: 0,
    };
  }

  const factor = Math.pow(1 + monthlyRate, term);
  const pmtArrears = (netCapCost * monthlyRate * factor - residualValue * monthlyRate) / (factor - 1);
  const monthlyBeforeTax = pmtArrears / (1 + monthlyRate);
  const financeCharge = monthlyBeforeTax - (netCapCost - residualValue) / term;

  return { monthlyBeforeTax, financeCharge };
}

/** 6. Taxes QC sur le paiement mensuel */
export function computeTaxesQC(monthlyBeforeTax: number): { tps: number; tvq: number; total: number } {
  const tps = monthlyBeforeTax * TPS;
  const tvq = monthlyBeforeTax * TVQ;
  return { tps, tvq, total: tps + tvq };
}

/** 7. Crédit taxe échange réparti sur les paiements */
export function computeTradeTaxCredit(tradeValue: number, term: number, taxesMensuelles: number): { creditParMois: number; creditPerdu: number } {
  if (tradeValue <= 0) return { creditParMois: 0, creditPerdu: 0 };
  const depreciation = tradeValue / term;
  const creditPotentiel = depreciation * TAUX_TAXE;
  const creditParMois = Math.min(creditPotentiel, taxesMensuelles);
  const creditPerdu = Math.max(0, creditPotentiel - taxesMensuelles);
  return { creditParMois, creditPerdu };
}

/** Calcul complet d'une location SCI (version détaillée) */
export function computeLeasePayment(inputs: LeaseInputs): LeaseResult {
  const capCost = computeCapCost(inputs);
  const netCapCost = computeNetCapCost(inputs);
  const residualValue = computeResidual(inputs.pdsf, inputs.residualPct);
  const { monthlyBeforeTax, financeCharge } = computePMTAdvance(netCapCost, residualValue, inputs.rate, inputs.term);
  const taxes = computeTaxesQC(monthlyBeforeTax);
  const tradeTaxCredit = computeTradeTaxCredit(inputs.tradeValue, inputs.term, taxes.total);

  const monthlyAfterTax = monthlyBeforeTax + taxes.total - tradeTaxCredit.creditParMois;

  return {
    monthly: Math.max(0, monthlyAfterTax),
    biweekly: Math.max(0, monthlyAfterTax * 12 / 26),
    weekly: Math.max(0, monthlyAfterTax * 12 / 52),
    monthlyBeforeTax: Math.max(0, monthlyBeforeTax),
    weeklyBeforeTax: Math.max(0, monthlyBeforeTax * 12 / 52),
    biweeklyBeforeTax: Math.max(0, monthlyBeforeTax * 12 / 26),
    total: Math.max(0, monthlyAfterTax * inputs.term),
    rate: inputs.rate,
    netCapCost: Math.max(0, netCapCost),
    residualValue,
    leaseCash: inputs.leaseCash,
    capCost,
    tpsOnPayment: Math.round(taxes.tps * 100) / 100,
    tvqOnPayment: Math.round(taxes.tvq * 100) / 100,
    creditTaxeParMois: Math.round(tradeTaxCredit.creditParMois * 100) / 100,
    creditPerdu: Math.round(tradeTaxCredit.creditPerdu * 100) / 100,
    pdsf: inputs.pdsf,
    rabaisConcess: inputs.rabaisConcess,
    coutEmprunt: Math.round(financeCharge * inputs.term * 100) / 100,
    fraisDossierOnly: inputs.fraisDossier,
  };
}

/** Calcul simplifié pour la grille meilleur choix (même formule, retour réduit) */
export function computeLeaseForGrid(inputs: LeaseInputs): {
  monthly: number;
  monthlyBeforeTax: number;
  rate: number;
  term: number;
  residualPct: number;
  residualValue: number;
  coutEmprunt: number;
  leaseCash: number;
  kmPerYear: number;
} & { kmPerYear: number } {
  const netCapCost = computeNetCapCost(inputs);
  const residualValue = computeResidual(inputs.pdsf, inputs.residualPct);
  const { monthlyBeforeTax, financeCharge } = computePMTAdvance(netCapCost, residualValue, inputs.rate, inputs.term);
  const taxes = computeTaxesQC(monthlyBeforeTax);
  const tradeTaxCredit = computeTradeTaxCredit(inputs.tradeValue, inputs.term, taxes.total);
  const monthly = monthlyBeforeTax + taxes.total - tradeTaxCredit.creditParMois;

  return {
    monthly: Math.max(0, monthly),
    monthlyBeforeTax: Math.max(0, monthlyBeforeTax),
    rate: inputs.rate,
    term: inputs.term,
    residualPct: inputs.residualPct,
    residualValue,
    coutEmprunt: financeCharge * inputs.term,
    leaseCash: inputs.leaseCash,
    kmPerYear: 0, // sera set par l'appelant
  };
}

// === Matching vehicule ===

export function findResidualVehicle(
  vehicles: any[],
  brand: string,
  model: string,
  trim: string,
  bodyStyle?: string
): any | null {
  const brandLower = brand.toLowerCase();
  const modelLower = model.toLowerCase();
  const trimLower = (trim || '').toLowerCase();
  const bodyStyleLower = (bodyStyle || '').toLowerCase();

  // Priorité 1: match avec body_style
  if (bodyStyleLower) {
    const match = vehicles.find((v: any) => {
      const vBrand = v.brand.toLowerCase();
      const vModel = v.model_name.toLowerCase();
      const vTrim = (v.trim || '').toLowerCase();
      const vBody = (v.body_style || '').toLowerCase();
      return vBrand === brandLower &&
        (vModel.includes(modelLower) || modelLower.includes(vModel)) &&
        (vTrim.includes(trimLower) || trimLower.includes(vTrim) || !trimLower) &&
        vBody === bodyStyleLower;
    });
    if (match) return match;
  }

  // Priorité 2: sans body_style
  return vehicles.find((v: any) => {
    const vBrand = v.brand.toLowerCase();
    const vModel = v.model_name.toLowerCase();
    const vTrim = (v.trim || '').toLowerCase();
    return vBrand === brandLower &&
      (vModel.includes(modelLower) || modelLower.includes(vModel)) &&
      (vTrim.includes(trimLower) || trimLower.includes(vTrim) || !trimLower);
  }) || null;
}

export function findRateEntry(
  vehicleList: any[],
  brand: string,
  model: string,
  trim: string
): any | null {
  const brandLower = brand.toLowerCase();
  const modelLower = model.toLowerCase().trim();
  const trimLower = (trim || '').toLowerCase().trim();

  // Strict model matching: prevent "Cherokee" from matching "Grand Cherokee"
  // and "Grand Cherokee L" from matching "Grand Cherokee Laredo"
  const isStrictMatch = (vModel: string, searchModel: string): boolean => {
    // Cherokee vs Grand Cherokee
    if (searchModel === 'cherokee' && vModel.includes('grand cherokee')) return false;
    // Grand Cherokee L vs Grand Cherokee Laredo/etc
    if (searchModel === 'grand cherokee l') {
      // Must contain "grand cherokee l " (with space after L) or end with "grand cherokee l"
      const hasGCL = vModel.includes('grand cherokee l ') || vModel.endsWith('grand cherokee l');
      // But NOT just "grand cherokee la..." (Laredo etc) without being a true L model  
      if (!hasGCL) return false;
      return true;
    }
    // Grand Cherokee (no L) - match Grand Cherokee but also Grand Cherokee/Grand Cherokee L
    if (searchModel === 'grand cherokee') {
      // Match "grand cherokee" entries but not "grand cherokee l " entries (those are the L variant)
      if (vModel.includes('grand cherokee l ') && !vModel.includes('/')) return false;
      return vModel.includes('grand cherokee');
    }
    // Combined "Grand Cherokee/Grand Cherokee L" - match all GC entries  
    if (searchModel.includes('grand cherokee/grand cherokee l')) {
      return vModel.includes('grand cherokee');
    }
    return vModel.includes(searchModel) || searchModel.includes(vModel);
  };

  // Get ALL entries that match brand + model (strict)
  const candidates = (vehicleList || []).filter((v: any) => {
    const vModel = v.model.toLowerCase();
    const vBrand = v.brand.toLowerCase();
    if (vBrand !== brandLower) return false;
    return isStrictMatch(vModel, modelLower);
  });

  if (candidates.length === 0) return null;
  if (candidates.length === 1) return candidates[0];

  // Multiple matches — pick the best one based on trim
  // 1. Exact trim match (e.g., trim="Base" -> "Cherokee Base")
  if (trimLower) {
    const trimMatch = candidates.find((v: any) => {
      const vModel = v.model.toLowerCase();
      return vModel.includes(trimLower) || trimLower.split(',').some((t: string) => vModel.includes(t.trim()));
    });
    if (trimMatch) return trimMatch;
  }

  // 2. Prefer "(excluding ...)" entries as the generic/default match
  const excludingEntry = candidates.find((v: any) => v.model.toLowerCase().includes('excluding'));
  if (excludingEntry) return excludingEntry;

  // 3. Fallback to first match
  return candidates[0];
}

/** Calcule l'ajustement km pour un terme donné */
export function getKmAdjustment(
  kmAdjustments: any,
  kmPerYear: number,
  term: number
): number {
  if (kmPerYear === 24000 || !kmAdjustments) return 0;
  return kmAdjustments[String(kmPerYear)]?.[String(term)] || 0;
}
