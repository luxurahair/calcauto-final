// Types partagés pour le calculateur de financement

export interface FinancingRates {
  rate_36: number;
  rate_48: number;
  rate_60: number;
  rate_72: number;
  rate_84: number;
  rate_96: number;
}

export interface VehicleProgram {
  id: string;
  brand: string;
  model: string;
  trim: string | null;
  year: number;
  consumer_cash: number;
  alternative_consumer_cash: number;
  option1_rates: FinancingRates;
  option2_rates: FinancingRates | null;
  bonus_cash: number;
  program_month: number;
  program_year: number;
  sort_order: number;
}

export interface PaymentComparison {
  term_months: number;
  option1_rate: number;
  option1_monthly: number;
  option1_total: number;
  option1_rebate: number;
  option2_rate: number | null;
  option2_monthly: number | null;
  option2_total: number | null;
  best_option: string | null;
  savings: number | null;
}

export interface CalculationResult {
  vehicle_price: number;
  consumer_cash: number;
  bonus_cash: number;
  brand: string;
  model: string;
  trim: string | null;
  year: number;
  comparisons: PaymentComparison[];
}

export interface LocalResult {
  option1Monthly: number;
  option1Biweekly: number;
  option1Weekly: number;
  option1Total: number;
  option1Rate: number;
  option2Monthly: number | null;
  option2Biweekly: number | null;
  option2Weekly: number | null;
  option2Total: number | null;
  option2Rate: number | null;
  bestOption: string | null;
  savings: number | null;
  principalOption1: number;
  principalOption2: number;
  fraisTaxables: number;
  taxes: number;
  echangeNet: number;
  comptant: number;
  bonusCash: number;
}

export interface ProgramPeriod {
  month: number;
  year: number;
  count: number;
}

export type PaymentFrequency = 'monthly' | 'biweekly' | 'weekly';
export type Language = 'fr' | 'en';
