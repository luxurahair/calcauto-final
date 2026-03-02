import { useCallback, useEffect, useState } from 'react';
import { FinancingRates, VehicleProgram, LocalResult } from '../types/calculator';

// Taux de taxe QC: 5% TPS + 9.975% TVQ
const TAUX_TAXE = 0.14975;

/**
 * Calcul du paiement mensuel de financement (formule PMT standard)
 */
export function calculateMonthlyPayment(principal: number, annualRate: number, months: number): number {
  if (principal <= 0 || months <= 0) return 0;
  if (annualRate === 0) return principal / months;
  const monthlyRate = annualRate / 100 / 12;
  return principal * (monthlyRate * Math.pow(1 + monthlyRate, months)) / (Math.pow(1 + monthlyRate, months) - 1);
}

/**
 * Obtenir le taux pour un terme donné
 */
export function getRateForTerm(rates: FinancingRates, term: number): number {
  const rateMap: { [key: number]: number } = {
    36: rates.rate_36,
    48: rates.rate_48,
    60: rates.rate_60,
    72: rates.rate_72,
    84: rates.rate_84,
    96: rates.rate_96,
  };
  return rateMap[term] ?? 4.99;
}

/**
 * Formater en devise canadienne (sans décimales)
 */
export function formatCurrency(value: number): string {
  return new Intl.NumberFormat('fr-CA', {
    style: 'currency',
    currency: 'CAD',
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  }).format(value);
}

/**
 * Formater en devise canadienne (avec décimales)
 */
export function formatCurrencyDecimal(value: number): string {
  return new Intl.NumberFormat('fr-CA', {
    style: 'currency',
    currency: 'CAD',
    minimumFractionDigits: 2,
  }).format(value);
}

interface CalculatorInputs {
  selectedProgram: VehicleProgram | null;
  vehiclePrice: string;
  selectedTerm: number;
  customBonusCash: string;
  comptantTxInclus: string;
  fraisDossier: string;
  taxePneus: string;
  fraisRDPRM: string;
  prixEchange: string;
  montantDuEchange: string;
  accessories: Array<{ description: string; price: string }>;
  rabaisConcess: string;
}

/**
 * Hook principal de calcul de financement
 * Extrait la logique pure de calcul de index.tsx
 */
export function useCalculator(inputs: CalculatorInputs) {
  const [localResult, setLocalResult] = useState<LocalResult | null>(null);

  const {
    selectedProgram, vehiclePrice, selectedTerm, customBonusCash,
    comptantTxInclus, fraisDossier, taxePneus, fraisRDPRM,
    prixEchange, montantDuEchange, accessories, rabaisConcess,
  } = inputs;

  const calculateForTerm = useCallback(() => {
    if (!selectedProgram || !vehiclePrice) {
      setLocalResult(null);
      return;
    }

    const price = parseFloat(vehiclePrice);
    if (isNaN(price) || price <= 0) {
      setLocalResult(null);
      return;
    }

    const bonusCash = parseFloat(customBonusCash) || selectedProgram.bonus_cash || 0;
    const consumerCash = selectedProgram.consumer_cash;
    const comptant = parseFloat(comptantTxInclus) || 0;
    const rabais = parseFloat(rabaisConcess) || 0;

    // Frais taxables
    const dossier = parseFloat(fraisDossier) || 0;
    const pneus = parseFloat(taxePneus) || 0;
    const rdprm = parseFloat(fraisRDPRM) || 0;
    const fraisTaxables = dossier + pneus + rdprm;

    // Echange
    const valeurEchange = parseFloat(prixEchange) || 0;
    const detteSurEchange = parseFloat(montantDuEchange) || 0;
    const echangeNet = valeurEchange - detteSurEchange;

    // Accessoires
    const totalAccessoires = accessories.reduce((sum, acc) => sum + (parseFloat(acc.price) || 0), 0);

    // Option 1: Prix + Accessoires - Consumer Cash - Rabais concess. - valeur echange + frais + dette echange + taxes - comptant - bonus cash
    const montantAvantTaxesO1 = price + totalAccessoires - consumerCash - rabais - valeurEchange + fraisTaxables;
    const taxesO1 = montantAvantTaxesO1 * TAUX_TAXE;
    const principalOption1Brut = montantAvantTaxesO1 + taxesO1 + detteSurEchange;
    const principalOption1 = principalOption1Brut - comptant - bonusCash;
    const rate1 = getRateForTerm(selectedProgram.option1_rates, selectedTerm);
    const monthly1 = calculateMonthlyPayment(Math.max(0, principalOption1), rate1, selectedTerm);
    const biweekly1 = monthly1 * 12 / 26;
    const weekly1 = monthly1 * 12 / 52;
    const total1 = monthly1 * selectedTerm;

    // Option 2: Prix complet - Rabais concess. - valeur echange + frais + dette echange + taxes - comptant (pas de Consumer Cash ni Bonus)
    let monthly2: number | null = null;
    let biweekly2: number | null = null;
    let weekly2: number | null = null;
    let total2: number | null = null;
    let rate2: number | null = null;
    let bestOption: string | null = null;
    let savings = 0;

    // Option 2: Prix - Alternative Consumer Cash - Rabais concess. - valeur echange + frais + dette echange + taxes - comptant
    const altConsumerCash = selectedProgram.alternative_consumer_cash || 0;
    const montantAvantTaxesO2 = price + totalAccessoires - altConsumerCash - rabais - valeurEchange + fraisTaxables;
    const taxesO2 = montantAvantTaxesO2 * TAUX_TAXE;
    const principalOption2Brut = montantAvantTaxesO2 + taxesO2 + detteSurEchange;
    const principalOption2 = principalOption2Brut - comptant;

    if (selectedProgram.option2_rates) {
      rate2 = getRateForTerm(selectedProgram.option2_rates, selectedTerm);
      monthly2 = calculateMonthlyPayment(Math.max(0, principalOption2), rate2, selectedTerm);
      biweekly2 = monthly2 * 12 / 26;
      weekly2 = monthly2 * 12 / 52;
      total2 = monthly2 * selectedTerm;

      if (total1 < total2) {
        bestOption = '1';
        savings = total2 - total1;
      } else if (total2 < total1) {
        bestOption = '2';
        savings = total1 - total2;
      } else {
        bestOption = '1';
        savings = 0;
      }
    }

    setLocalResult({
      option1Monthly: monthly1,
      option1Biweekly: biweekly1,
      option1Weekly: weekly1,
      option1Total: total1,
      option1Rate: rate1,
      option2Monthly: monthly2,
      option2Biweekly: biweekly2,
      option2Weekly: weekly2,
      option2Total: total2,
      option2Rate: rate2,
      bestOption,
      savings,
      principalOption1,
      principalOption2,
      fraisTaxables,
      taxes: taxesO1,
      echangeNet,
      comptant,
      bonusCash,
    });
  }, [selectedProgram, vehiclePrice, selectedTerm, customBonusCash, comptantTxInclus, fraisDossier, taxePneus, fraisRDPRM, prixEchange, montantDuEchange, accessories, rabaisConcess]);

  useEffect(() => {
    calculateForTerm();
  }, [calculateForTerm]);

  return { localResult, calculateForTerm };
}
