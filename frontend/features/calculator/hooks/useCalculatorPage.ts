import { useState, useEffect, useCallback, useRef } from 'react';
import {
  Platform,
  Alert,
  Share,
  Linking,
  Dimensions,
} from 'react-native';
import { useRouter, useLocalSearchParams } from 'expo-router';
import axios from 'axios';
import AsyncStorage from '@react-native-async-storage/async-storage';
import * as Print from 'expo-print';
import * as FileSystem from 'expo-file-system';
import * as Sharing from 'expo-sharing';
import html2canvas from 'html2canvas';

import { Language, saveLanguage, loadLanguage } from '../../../utils/i18n';
import { useAuth } from '../../../contexts/AuthContext';
import frTranslations from '../../../locales/fr.json';
import enTranslations from '../../../locales/en.json';
import { useCalculator, getRateForTerm, formatCurrency, formatCurrencyDecimal } from '../../../hooks/useCalculator';
import {
  computeLeasePayment, computeLeaseForGrid,
  findResidualVehicle, findRateEntry, getKmAdjustment,
  LeaseInputs,
} from '../../../utils/leaseCalculator';
import type { FinancingRates, VehicleProgram, CalculationResult, LocalResult } from '../../../types/calculator';
import { API_URL } from '../../../utils/api';

// ─── Constants ───────────────────────────────────────────────
const SUBMISSIONS_KEY = 'calcauto_submissions';

export const translations = {
  fr: frTranslations,
  en: enTranslations,
};

export const monthNames = {
  fr: frTranslations.months,
  en: enTranslations.months,
};

export const FINANCE_TERMS = [36, 48, 60, 72, 84, 96];
export const LEASE_TERMS = [24, 27, 36, 39, 42, 48, 51, 54, 60];
export const LEASE_KM_OPTIONS = [12000, 18000, 24000];

export const frequencyLabels = {
  monthly: { fr: 'Mensuel', en: 'Monthly', factor: 1 },
  biweekly: { fr: 'Aux 2 sem.', en: 'Bi-weekly', factor: 12 / 26 },
  weekly: { fr: 'Hebdo', en: 'Weekly', factor: 12 / 52 },
};

// ─── Hook ────────────────────────────────────────────────────
export function useCalculatorPage() {
  const router = useRouter();
  const { user, logout, getToken } = useAuth();
  const params = useLocalSearchParams<{
    clientName?: string;
    clientEmail?: string;
    clientPhone?: string;
    contactId?: string;
  }>();

  // ── Language ──
  const [lang, setLang] = useState<Language>('fr');
  const t = translations[lang];

  const handleLanguageChange = useCallback((newLang: Language) => {
    setLang(newLang);
    saveLanguage(newLang);
  }, []);

  useEffect(() => {
    loadLanguage().then((savedLang) => setLang(savedLang));
  }, []);

  // ── Programs ──
  const [programs, setPrograms] = useState<VehicleProgram[]>([]);
  const [filteredPrograms, setFilteredPrograms] = useState<VehicleProgram[]>([]);
  const [selectedProgram, setSelectedProgram] = useState<VehicleProgram | null>(null);
  const [vehiclePrice, setVehiclePrice] = useState('');
  const [results, setResults] = useState<CalculationResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const [programsLoading, setProgramsLoading] = useState(true);
  const [showSplash, setShowSplash] = useState(true);

  // ── Filters ──
  const [selectedYear, setSelectedYear] = useState<number | null>(null);
  const [selectedBrand, setSelectedBrand] = useState<string | null>(null);

  // ── Import modal ──
  const [showImportModal, setShowImportModal] = useState(false);
  const [importPassword, setImportPassword] = useState('');

  // ── Email modal ──
  const [showEmailModal, setShowEmailModal] = useState(false);
  const [clientEmail, setClientEmail] = useState('');
  const [clientName, setClientName] = useState('');
  const [clientPhone, setClientPhone] = useState('');
  const [sendingEmail, setSendingEmail] = useState(false);

  // ── SMS Preview modal ──
  const [showSmsPreview, setShowSmsPreview] = useState(false);
  const [smsPreviewText, setSmsPreviewText] = useState('');

  // ── Period ──
  const [currentPeriod, setCurrentPeriod] = useState<{ month: number; year: number } | null>(null);
  const [availablePeriods, setAvailablePeriods] = useState<{ month: number; year: number; count: number }[]>([]);
  const [showPeriodSelector, setShowPeriodSelector] = useState(false);

  // ── Program event metadata ──
  const [programMeta, setProgramMeta] = useState<{
    event_names: string[];
    program_period: string;
    program_month: string;
    loyalty_rate: number;
    no_payments_days: number;
    featured_rate: number | null;
    featured_term: number | null;
    key_message: string;
    brands?: string[];
  } | null>(null);

  const [loyaltyChecked, setLoyaltyChecked] = useState(false);
  const [deferredPayment, setDeferredPayment] = useState(false);

  // ── Term & frequency ──
  const [selectedTerm, setSelectedTerm] = useState<number>(72);
  const [paymentFrequency, setPaymentFrequency] = useState<'monthly' | 'biweekly' | 'weekly'>('monthly');
  const [selectedOption, setSelectedOption] = useState<'1' | '2' | null>(null);

  // ── Inventory ──
  const [inventoryList, setInventoryList] = useState<any[]>([]);
  const [selectedInventory, setSelectedInventory] = useState<any>(null);
  const [showInventoryPicker, setShowInventoryPicker] = useState(false);
  const [manualVin, setManualVin] = useState<string>('');

  // ── Auto-financing ──
  const [autoFinancing, setAutoFinancing] = useState<{
    consumer_cash: number;
    bonus_cash: number;
    option1_rates: Record<string, number | null>;
    option2_rates: Record<string, number | null>;
    programme_source: string;
  } | null>(null);

  // ── Pricing inputs ──
  const [customBonusCash, setCustomBonusCash] = useState('');
  const [comptantTxInclus, setComptantTxInclus] = useState('');
  const [accessories, setAccessories] = useState<Array<{ description: string; price: string }>>([]);
  const [fraisDossier, setFraisDossier] = useState('259.95');
  const [taxePneus, setTaxePneus] = useState('15');
  const [fraisRDPRM, setFraisRDPRM] = useState('100');
  const [prixEchange, setPrixEchange] = useState('');
  const [montantDuEchange, setMontantDuEchange] = useState('');

  // ── Lease SCI ──
  const [showLease, setShowLease] = useState(false);
  const [leaseKmPerYear, setLeaseKmPerYear] = useState<number>(24000);
  const [leaseTerm, setLeaseTerm] = useState<number>(48);
  const [leaseResiduals, setLeaseResiduals] = useState<any>(null);
  const [leaseRates, setLeaseRates] = useState<any>(null);
  const [leaseResult, setLeaseResult] = useState<any>(null);
  const [leaseLoading, setLeaseLoading] = useState(false);
  const [leasePdsf, setLeasePdsf] = useState('');
  const [leaseSoldeReporte, setLeaseSoldeReporte] = useState('');
  const [leaseRabaisConcess, setLeaseRabaisConcess] = useState('');
  const [bestLeaseOption, setBestLeaseOption] = useState<any>(null);
  const [leaseAnalysisGrid, setLeaseAnalysisGrid] = useState<any[]>([]);

  // ── useCalculator (finance calculation) ──
  const activeLoyaltyRate = loyaltyChecked && programMeta?.loyalty_rate ? programMeta.loyalty_rate : 0;
  const { localResult } = useCalculator({
    selectedProgram,
    vehiclePrice,
    selectedTerm,
    customBonusCash,
    comptantTxInclus,
    fraisDossier,
    taxePneus,
    fraisRDPRM,
    prixEchange,
    montantDuEchange,
    accessories,
    rabaisConcess: leaseRabaisConcess,
    loyaltyRate: activeLoyaltyRate,
    deferredPayment,
  });

  // ── Derived values ──
  const years = [...new Set(programs.map(p => p.year))].sort((a, b) => b - a);
  const brands = [...new Set(programs.map(p => p.brand))].sort();

  // ─── Effects ───────────────────────────────────────────────

  // Pre-fill from contact params
  useEffect(() => {
    if (params.clientName) setClientName(params.clientName);
    if (params.clientEmail) setClientEmail(params.clientEmail);
    if (params.clientPhone) setClientPhone(params.clientPhone);
  }, [params]);

  // Load programs
  const loadPrograms = useCallback(async (month?: number, year?: number) => {
    const startTime = Date.now();
    const MIN_LOADING_TIME = 2000;

    try {
      try {
        const periodsRes = await axios.get(`${API_URL}/api/periods`);
        setAvailablePeriods(periodsRes.data);
      } catch (e) {
        console.log('Could not load periods');
      }

      try {
        const token = await getToken();
        if (token) {
          const invRes = await axios.get(`${API_URL}/api/inventory`, {
            headers: { Authorization: `Bearer ${token}` },
          });
          setInventoryList(invRes.data.filter((v: any) => v.status === 'disponible'));
        }
      } catch (e) {
        console.log('Could not load inventory');
      }

      let url = `${API_URL}/api/programs`;
      if (month && year) {
        url += `?month=${month}&year=${year}`;
      }

      const response = await axios.get(url, {
        headers: { 'Cache-Control': 'no-cache' },
      });
      setPrograms(response.data);
      const sorted = [...response.data].sort((a: any, b: any) => (a.sort_order || 0) - (b.sort_order || 0));
      setFilteredPrograms(sorted);

      if (response.data.length > 0) {
        const periodMonth = month || response.data[0].program_month;
        const periodYear = year || response.data[0].program_year;
        setCurrentPeriod({ month: periodMonth, year: periodYear });

        try {
          const metaRes = await axios.get(`${API_URL}/api/program-meta`, {
            params: { month: periodMonth, year: periodYear },
          });
          if (metaRes.data && metaRes.data.event_names) {
            setProgramMeta(metaRes.data);
            setLoyaltyChecked(false);
            setDeferredPayment(false);
          }
        } catch (e) {
          console.log('Could not load program meta');
          setProgramMeta(null);
        }
      }

      const elapsed = Date.now() - startTime;
      if (elapsed < MIN_LOADING_TIME) {
        await new Promise(resolve => setTimeout(resolve, MIN_LOADING_TIME - elapsed));
      }
    } catch (error) {
      console.error('Error loading programs:', error);
    } finally {
      setProgramsLoading(false);
    }
  }, []);

  useEffect(() => {
    loadPrograms();
  }, [loadPrograms]);

  // Load inventory separately
  useEffect(() => {
    const loadInventory = async () => {
      try {
        const token = await getToken();
        if (token) {
          const invRes = await axios.get(`${API_URL}/api/inventory`, {
            headers: { Authorization: `Bearer ${token}` },
          });
          const disponible = invRes.data.filter((v: any) => v.status === 'disponible');
          setInventoryList(disponible);
        }
      } catch (e) {
        console.log('Could not load inventory:', e);
      }
    };
    loadInventory();
  }, []);

  // Load auto-financing when inventory vehicle selected
  useEffect(() => {
    const loadAutoFinancing = async () => {
      if (!selectedInventory?.model_code) {
        setAutoFinancing(null);
        return;
      }
      try {
        const response = await axios.get(
          `${API_URL}/api/product-codes/${selectedInventory.model_code}/financing`
        );
        if (response.data.success && response.data.financing) {
          setAutoFinancing(response.data.financing);
        } else {
          setAutoFinancing(null);
        }
      } catch (e) {
        console.log('Could not load auto-financing:', e);
        setAutoFinancing(null);
      }
    };
    loadAutoFinancing();
  }, [selectedInventory?.model_code]);

  // Load SCI lease data
  useEffect(() => {
    const loadLeaseData = async () => {
      try {
        const [residualsRes, ratesRes] = await Promise.all([
          axios.get(`${API_URL}/api/sci/residuals`),
          axios.get(`${API_URL}/api/sci/lease-rates`),
        ]);
        setLeaseResiduals(residualsRes.data);
        setLeaseRates(ratesRes.data);
      } catch (e) {
        console.log('Could not load SCI lease data:', e);
      }
    };
    loadLeaseData();
  }, []);

  // Restore calculator state from CRM
  useEffect(() => {
    const checkForRestore = async () => {
      try {
        const stateJson = await AsyncStorage.getItem('calcauto_restore_state');
        if (!stateJson) return;
        await AsyncStorage.removeItem('calcauto_restore_state');
        const s = JSON.parse(stateJson);

        if (s.selectedProgram) setSelectedProgram(s.selectedProgram);
        if (s.vehiclePrice !== undefined) setVehiclePrice(s.vehiclePrice);
        if (s.selectedTerm) setSelectedTerm(s.selectedTerm);
        if (s.selectedOption) setSelectedOption(s.selectedOption);
        if (s.paymentFrequency) setPaymentFrequency(s.paymentFrequency);
        if (s.customBonusCash !== undefined) setCustomBonusCash(s.customBonusCash);
        if (s.comptantTxInclus !== undefined) setComptantTxInclus(s.comptantTxInclus);
        if (s.fraisDossier !== undefined) setFraisDossier(s.fraisDossier);
        if (s.taxePneus !== undefined) setTaxePneus(s.taxePneus);
        if (s.fraisRDPRM !== undefined) setFraisRDPRM(s.fraisRDPRM);
        if (s.prixEchange !== undefined) setPrixEchange(s.prixEchange);
        if (s.montantDuEchange !== undefined) setMontantDuEchange(s.montantDuEchange);
        if (s.accessories) setAccessories(s.accessories);
        if (s.leaseRabaisConcess !== undefined) setLeaseRabaisConcess(s.leaseRabaisConcess);
        if (s.leasePdsf !== undefined) setLeasePdsf(s.leasePdsf);
        if (s.leaseSoldeReporte !== undefined) setLeaseSoldeReporte(s.leaseSoldeReporte);
        if (s.leaseTerm) setLeaseTerm(s.leaseTerm);
        if (s.leaseKmPerYear) setLeaseKmPerYear(s.leaseKmPerYear);
        if (s.showLease !== undefined) setShowLease(s.showLease);
        if (s.manualVin !== undefined) setManualVin(s.manualVin);
        if (s.selectedYear) setSelectedYear(s.selectedYear);
        if (s.selectedBrand) setSelectedBrand(s.selectedBrand);
        if (s.selectedInventory) setSelectedInventory(s.selectedInventory);

        console.log('Calculator state restored from submission');
      } catch (e) {
        console.log('Error restoring calculator state:', e);
      }
    };
    checkForRestore();
  }, []);

  // Calculate lease when parameters change
  useEffect(() => {
    if (!showLease || !selectedProgram || !vehiclePrice || !leaseResiduals || !leaseRates) {
      setLeaseResult(null);
      return;
    }

    const price = parseFloat(vehiclePrice);
    if (isNaN(price) || price <= 0) return;

    const residualVehicle = findResidualVehicle(
      leaseResiduals.vehicles || [],
      selectedProgram.brand,
      selectedProgram.model,
      selectedProgram.trim || '',
      selectedInventory?.body_style
    );
    if (!residualVehicle) { setLeaseResult(null); return; }

    const residualPct = residualVehicle.residual_percentages?.[String(leaseTerm)] || 0;
    if (residualPct === 0) { setLeaseResult(null); return; }

    const yr = selectedProgram.year;
    const vehicleList = yr === 2025 ? leaseRates.vehicles_2025 : leaseRates.vehicles_2026;
    const rateEntry = findRateEntry(vehicleList || [], selectedProgram.brand, selectedProgram.model, selectedProgram.trim || '');

    const termKey = String(leaseTerm);
    const standardRate = rateEntry?.standard_rates?.[termKey] ?? null;
    const alternativeRate = rateEntry?.alternative_rates?.[termKey] ?? null;
    const leaseCashVal = rateEntry?.lease_cash || 0;

    const kmAdj = leaseResiduals.km_adjustments?.adjustments;
    const kmAdjustment = getKmAdjustment(kmAdj, leaseKmPerYear, leaseTerm);
    const adjustedResidualPct = residualPct + kmAdjustment;
    const pdsf = parseFloat(leasePdsf) || parseFloat(vehiclePrice);

    const bonusCash = parseFloat(customBonusCash) || selectedProgram.bonus_cash || 0;
    const comptant = parseFloat(comptantTxInclus) || 0;
    const tradeVal = parseFloat(prixEchange) || 0;
    const tradeOwed = parseFloat(montantDuEchange) || 0;
    const soldeReporte = parseFloat(leaseSoldeReporte) || 0;
    const totalAccessoires = accessories.reduce((sum, acc) => sum + (parseFloat(acc.price) || 0), 0);

    const baseInputs: Omit<LeaseInputs, 'rate' | 'leaseCash'> = {
      price,
      pdsf,
      term: leaseTerm,
      residualPct: adjustedResidualPct,
      fraisDossier: parseFloat(fraisDossier) || 0,
      totalAccessoires,
      rabaisConcess: parseFloat(leaseRabaisConcess) || 0,
      soldeReporte,
      tradeValue: tradeVal,
      tradeOwed,
      comptant,
      bonusCash,
    };

    const results: any = {
      vehicleName: `${residualVehicle.brand} ${residualVehicle.model_name} ${residualVehicle.trim}`,
      residualPct: adjustedResidualPct,
      residualValue: pdsf * (adjustedResidualPct / 100),
      kmAdjustment,
      term: leaseTerm,
      kmPerYear: leaseKmPerYear,
    };

    if (standardRate !== null) {
      results.standard = computeLeasePayment({ ...baseInputs, rate: standardRate, leaseCash: leaseCashVal });
    }
    if (alternativeRate !== null) {
      results.alternative = computeLeasePayment({ ...baseInputs, rate: alternativeRate, leaseCash: 0 });
    }

    if (results.standard && results.alternative) {
      results.bestLease = results.standard.total < results.alternative.total ? 'standard' : 'alternative';
      results.leaseSavings = Math.abs(results.standard.total - results.alternative.total);
    } else if (results.standard) {
      results.bestLease = 'standard';
    } else if (results.alternative) {
      results.bestLease = 'alternative';
    }

    setLeaseResult(results);

    // === Best lease analysis grid (all terms × all km) ===
    let bestOption: any = null;
    const grid: any[] = [];

    for (const km of [12000, 18000, 24000]) {
      for (const tt of LEASE_TERMS) {
        const resPct = residualVehicle.residual_percentages?.[String(tt)] || 0;
        if (resPct === 0) continue;

        const kmAdj2 = getKmAdjustment(kmAdj, km, tt);
        const adjResPct = resPct + kmAdj2;

        const stdRate = rateEntry?.standard_rates?.[String(tt)] ?? null;
        const altRate = rateEntry?.alternative_rates?.[String(tt)] ?? null;

        const gridInputs: Omit<LeaseInputs, 'rate' | 'leaseCash' | 'term' | 'residualPct'> = {
          price, pdsf,
          fraisDossier: parseFloat(fraisDossier) || 0,
          totalAccessoires,
          rabaisConcess: parseFloat(leaseRabaisConcess) || 0,
          soldeReporte,
          tradeValue: tradeVal,
          tradeOwed,
          comptant,
          bonusCash,
        };

        if (altRate !== null) {
          const r = computeLeaseForGrid({ ...gridInputs, rate: altRate, leaseCash: 0, term: tt, residualPct: adjResPct });
          const entry = { ...r, kmPerYear: km, option: 'alt', optionLabel: 'Alt' };
          grid.push(entry);
          if (!bestOption || r.monthly < bestOption.monthly) {
            bestOption = { ...entry, option: 'alternative', optionLabel: 'Taux Alternatif' };
          }
        }
        if (stdRate !== null) {
          const r = computeLeaseForGrid({ ...gridInputs, rate: stdRate, leaseCash: leaseCashVal, term: tt, residualPct: adjResPct });
          const entry = { ...r, kmPerYear: km, option: 'std', optionLabel: 'Std' };
          grid.push(entry);
          if (!bestOption || r.monthly < bestOption.monthly) {
            bestOption = { ...entry, option: 'standard', optionLabel: 'Std + Lease Cash' };
          }
        }
      }
    }

    setBestLeaseOption(bestOption);
    setLeaseAnalysisGrid(grid);
  }, [showLease, selectedProgram, vehiclePrice, leaseTerm, leaseKmPerYear, leaseResiduals, leaseRates,
    customBonusCash, comptantTxInclus, fraisDossier, taxePneus, fraisRDPRM, prixEchange, montantDuEchange, accessories, leasePdsf, leaseSoldeReporte, leaseRabaisConcess, selectedInventory?.body_style]);

  // Filter programs when year or brand changes
  useEffect(() => {
    let filtered = [...programs];
    if (selectedYear) {
      filtered = filtered.filter(p => p.year === selectedYear);
    }
    if (selectedBrand) {
      filtered = filtered.filter(p => p.brand === selectedBrand);
    }
    filtered.sort((a, b) => (a.sort_order || 0) - (b.sort_order || 0));
    setFilteredPrograms(filtered);
  }, [programs, selectedYear, selectedBrand]);

  // ─── Callbacks ─────────────────────────────────────────────

  const handleLogout = useCallback(() => {
    if (Platform.OS === 'web') {
      if (window.confirm('Voulez-vous vous déconnecter?')) {
        logout();
      }
    } else {
      Alert.alert(
        'Déconnexion',
        'Voulez-vous vous déconnecter?',
        [
          { text: 'Annuler', style: 'cancel' },
          { text: 'Déconnexion', style: 'destructive', onPress: () => logout() },
        ]
      );
    }
  }, [logout]);

  const onRefresh = useCallback(async () => {
    setRefreshing(true);
    await loadPrograms();
    setRefreshing(false);
  }, [loadPrograms]);

  const selectProgram = useCallback((program: VehicleProgram) => {
    setSelectedProgram(program);
    setResults(null);
  }, []);

  const clearSelection = useCallback(() => {
    setSelectedProgram(null);
    setResults(null);
  }, []);

  const handlePeriodSelect = useCallback((month: number, year: number) => {
    setProgramsLoading(true);
    loadPrograms(month, year);
    setShowPeriodSelector(false);
  }, [loadPrograms]);

  const handleImportConfirm = useCallback(() => {
    if (importPassword === 'Admin') {
      setShowImportModal(false);
      setImportPassword('');
      router.push('/import');
    } else {
      if (Platform.OS === 'web') {
        alert(t.import.incorrectPassword);
      } else {
        Alert.alert('Erreur', t.import.incorrectPassword);
      }
    }
  }, [importPassword, router, t]);

  const clearInventorySelection = useCallback(() => {
    setSelectedInventory(null);
    setVehiclePrice('');
    setAutoFinancing(null);
  }, []);

  const selectInventoryVehicle = useCallback((vehicle: any) => {
    setSelectedInventory(vehicle);
    setManualVin('');
    setVehiclePrice(String(vehicle.asking_price || vehicle.msrp || ''));
  }, []);

  // ── Generate submission text ──
  const generateSubmissionText = useCallback(() => {
    if (!selectedProgram || !localResult || !vehiclePrice) return '';

    const vehicle = `${selectedProgram.brand} ${selectedProgram.model} ${selectedProgram.trim || ''} ${selectedProgram.year}`.trim();
    const option = selectedOption === '2' ? '2' : '1';
    const rate = option === '1' ? localResult.option1Rate : localResult.option2Rate;

    let payment: number;
    if (paymentFrequency === 'biweekly') {
      payment = option === '1' ? localResult.option1Biweekly : (localResult.option2Biweekly || 0);
    } else if (paymentFrequency === 'weekly') {
      payment = option === '1' ? localResult.option1Weekly : (localResult.option2Weekly || 0);
    } else {
      payment = option === '1' ? localResult.option1Monthly : (localResult.option2Monthly || 0);
    }

    const frequencyText = paymentFrequency === 'biweekly'
      ? (lang === 'fr' ? 'aux 2 sem.' : 'bi-weekly')
      : paymentFrequency === 'weekly'
        ? (lang === 'fr' ? 'hebdo' : 'weekly')
        : (lang === 'fr' ? 'mensuel' : 'monthly');

    const vin = selectedInventory?.vin || (manualVin && manualVin.length === 17 ? manualVin : '');

    let leaseSection = '';
    if (showLease && leaseResult && (leaseResult.standard || leaseResult.alternative)) {
      const bestLease = leaseResult.bestLease === 'standard' ? leaseResult.standard : leaseResult.alternative;
      const bestLeaseLabel = leaseResult.bestLease === 'standard'
        ? 'Std + Lease Cash'
        : (lang === 'fr' ? 'Taux Alternatif' : 'Alt. Rate');
      const bestLeasePayment = paymentFrequency === 'biweekly' ? bestLease.biweekly :
        paymentFrequency === 'weekly' ? bestLease.weekly : bestLease.monthly;

      leaseSection = lang === 'fr'
        ? `\n\nLOCATION SCI (${bestLeaseLabel})\n` +
          `Terme: ${leaseTerm} mois | ${leaseKmPerYear / 1000}k km/an\n` +
          `Residuel: ${leaseResult.residualPct}% (${formatCurrency(leaseResult.residualValue)})\n` +
          `Taux: ${bestLease.rate}%\n` +
          `Paiement ${frequencyText}: ${formatCurrencyDecimal(bestLeasePayment)}`
        : `\n\nSCI LEASE (${bestLeaseLabel})\n` +
          `Term: ${leaseTerm} mo | ${leaseKmPerYear / 1000}k km/yr\n` +
          `Residual: ${leaseResult.residualPct}% (${formatCurrency(leaseResult.residualValue)})\n` +
          `Rate: ${bestLease.rate}%\n` +
          `${frequencyText} payment: ${formatCurrencyDecimal(bestLeasePayment)}`;
    }

    const rebateForOption = option === '2' ? (selectedProgram.alternative_consumer_cash || 0) : (selectedProgram.consumer_cash || 0);

    const text = lang === 'fr'
      ? `SOUMISSION CalcAuto AiPro\n\n` +
        `Vehicule: ${vehicle}\n` +
        `Prix: ${formatCurrency(parseFloat(vehiclePrice))}\n` +
        (vin ? `VIN: ${vin}\n` : '') +
        `\nFINANCEMENT Option ${option}\n` +
        `Terme: ${selectedTerm} mois\n` +
        `Taux: ${rate}%\n` +
        `Paiement ${frequencyText}: ${formatCurrencyDecimal(payment)}\n` +
        (rebateForOption > 0 ? `Rabais: ${formatCurrency(rebateForOption)}\n` : '') +
        leaseSection +
        `\n\nEnvoye via CalcAuto AiPro`
      : `CalcAuto AiPro SUBMISSION\n\n` +
        `Vehicle: ${vehicle}\n` +
        `Price: ${formatCurrency(parseFloat(vehiclePrice))}\n` +
        (vin ? `VIN: ${vin}\n` : '') +
        `\nFINANCING Option ${option}\n` +
        `Term: ${selectedTerm} months\n` +
        `Rate: ${rate}%\n` +
        `${frequencyText} payment: ${formatCurrencyDecimal(payment)}\n` +
        (rebateForOption > 0 ? `Rebate: ${formatCurrency(rebateForOption)}\n` : '') +
        leaseSection +
        `\n\nSent via CalcAuto AiPro`;

    return text;
  }, [selectedProgram, localResult, vehiclePrice, selectedOption, paymentFrequency, lang, selectedInventory, manualVin, showLease, leaseResult, leaseTerm, leaseKmPerYear, selectedTerm]);

  // ── Handle Share via SMS ──
  const handleShareSMS = useCallback(async () => {
    if (!selectedProgram || !localResult || !vehiclePrice) {
      if (Platform.OS === 'web') {
        alert(lang === 'fr' ? 'Aucune soumission a partager' : 'No submission to share');
      } else {
        Alert.alert('Erreur', lang === 'fr' ? 'Aucune soumission a partager' : 'No submission to share');
      }
      return;
    }

    try {
      setSmsPreviewText(lang === 'fr' ? 'Generation de la soumission...' : 'Generating submission...');
      setShowSmsPreview(true);

      const vehicle = `${selectedProgram.brand} ${selectedProgram.model} ${selectedProgram.trim || ''} ${selectedProgram.year}`.trim();
      const vin = selectedInventory?.vin || (manualVin && manualVin.length === 17 ? manualVin : '');
      const price = parseFloat(vehiclePrice) || 0;
      const fmt = (v: number) => v.toLocaleString('fr-CA', { maximumFractionDigits: 0 });
      const fmt2 = (v: number) => v.toLocaleString('fr-CA', { minimumFractionDigits: 2, maximumFractionDigits: 2 });

      const brand = selectedProgram.brand?.toLowerCase() || '';
      const stickerBaseUrls: Record<string, string> = {
        chrysler: 'https://www.chrysler.com/hostd/windowsticker/getWindowStickerPdf.do?vin=',
        jeep: 'https://www.jeep.com/hostd/windowsticker/getWindowStickerPdf.do?vin=',
        dodge: 'https://www.dodge.com/hostd/windowsticker/getWindowStickerPdf.do?vin=',
        ram: 'https://www.ramtrucks.com/hostd/windowsticker/getWindowStickerPdf.do?vin=',
        fiat: 'https://www.fiatusa.com/hostd/windowsticker/getWindowStickerPdf.do?vin=',
      };
      const stickerUrl = vin ? (stickerBaseUrls[brand] || stickerBaseUrls['ram']) + vin : '';

      let stickerImageUrl = '';
      if (vin) {
        try {
          const stickerResp = await axios.get(`${API_URL}/api/window-sticker/${vin}`);
          if (stickerResp.data?.images?.length > 0) {
            stickerImageUrl = stickerResp.data.images[0];
          }
        } catch (e) {
          console.log('Window sticker not available');
        }
      }

      const consumerCash = selectedProgram.consumer_cash || 0;
      const bonusCash2 = parseFloat(customBonusCash) || selectedProgram.bonus_cash || 0;
      const dossier = parseFloat(fraisDossier) || 0;
      const pneus = parseFloat(taxePneus) || 0;
      const rdprm = parseFloat(fraisRDPRM) || 0;
      const valeurEchange = parseFloat(prixEchange) || 0;
      const comptant = parseFloat(comptantTxInclus) || 0;
      const altConsumerCash = selectedProgram.alternative_consumer_cash || 0;
      const hasOption2 = selectedProgram.option2_rates !== null && localResult.option2Monthly !== null;
      const payLabel = paymentFrequency === 'biweekly' ? (lang === 'fr' ? 'Aux 2 sem.' : 'Bi-weekly') : paymentFrequency === 'weekly' ? (lang === 'fr' ? 'Hebdo' : 'Weekly') : (lang === 'fr' ? 'Mensuel' : 'Monthly');

      const o1Pay = paymentFrequency === 'biweekly' ? localResult.option1Biweekly : paymentFrequency === 'weekly' ? localResult.option1Weekly : localResult.option1Monthly;
      const o2Pay = paymentFrequency === 'biweekly' ? (localResult.option2Biweekly || 0) : paymentFrequency === 'weekly' ? (localResult.option2Weekly || 0) : (localResult.option2Monthly || 0);

      // Build screenshot HTML (same as original)
      const screenshotHtml = buildSmsScreenshotHtml({
        selectedProgram, localResult, lang, vin, price, fmt, fmt2,
        consumerCash, bonusCash2, dossier, pneus, rdprm, valeurEchange, comptant,
        altConsumerCash, hasOption2, payLabel, o1Pay, o2Pay, selectedTerm,
        showLease, leaseResult, leaseTerm, leaseKmPerYear, paymentFrequency,
        stickerImageUrl, stickerUrl,
      });

      // Render HTML in hidden div, capture with html2canvas
      const container = document.createElement('div');
      container.style.position = 'fixed';
      container.style.left = '-9999px';
      container.style.top = '0';
      container.innerHTML = screenshotHtml;
      document.body.appendChild(container);

      const images = container.querySelectorAll('img');
      if (images.length > 0) {
        await Promise.all(Array.from(images).map(img =>
          new Promise<void>((resolve) => {
            if (img.complete) resolve();
            else { img.onload = () => resolve(); img.onerror = () => resolve(); }
          })
        ));
      }

      const captureDiv = container.querySelector('#capture') as HTMLElement;
      const canvas = await html2canvas(captureDiv, {
        scale: 3,
        useCORS: true,
        allowTaint: true,
        backgroundColor: '#ffffff',
      });
      document.body.removeChild(container);

      const blob: Blob = await new Promise((resolve) => canvas.toBlob((b: any) => resolve(b), 'image/png'));
      const file = new File([blob], `soumission_${vehicle.replace(/\s+/g, '_')}.png`, { type: 'image/png' });
      const filesToShare: File[] = [file];

      let shareText = `${vehicle} - ${fmt(price)} $\n`;
      shareText += `${payLabel}: Option 1 = ${fmt2(o1Pay)} $ (${selectedTerm}m)`;
      if (hasOption2) shareText += ` | Option 2 = ${fmt2(o2Pay)} $`;
      if (showLease && leaseResult) {
        const bestLease = leaseResult.bestLease === 'standard' ? leaseResult.standard : leaseResult.alternative;
        if (bestLease) {
          const leasePayment = paymentFrequency === 'weekly' ? bestLease.weekly : paymentFrequency === 'biweekly' ? bestLease.biweekly : bestLease.monthly;
          const freqSuffix = paymentFrequency === 'weekly' ? '/sem' : paymentFrequency === 'biweekly' ? '/2sem' : '/mois';
          shareText += `\nLocation ${leaseTerm}m: ${fmt2(leasePayment)} $${freqSuffix}`;
        }
      }
      if (stickerUrl) shareText += `\n\nWindow Sticker: ${stickerUrl}`;
      shareText += `\n\n---\nAVIS: Montants a titre indicatif seulement. Sujet a l'approbation du credit. Le concessionnaire ne peut etre tenu responsable d'erreurs de calcul.`;
      shareText += `\n- CalcAuto AiPro`;

      if (navigator.share && navigator.canShare && navigator.canShare({ files: filesToShare })) {
        await navigator.share({ text: shareText, files: filesToShare });
      } else {
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = file.name;
        a.click();
        URL.revokeObjectURL(url);
        try {
          await navigator.clipboard.writeText(shareText);
          alert(lang === 'fr' ? 'Image telechargee et texte copie!' : 'Image downloaded and text copied!');
        } catch {
          alert(lang === 'fr' ? 'Image telechargee!' : 'Image downloaded!');
        }
      }

      setShowSmsPreview(false);
    } catch (error: any) {
      console.error('Share error:', error);
      setShowSmsPreview(false);
      const message = generateSubmissionText();
      setSmsPreviewText(message);
      setShowSmsPreview(true);
    }
  }, [selectedProgram, localResult, vehiclePrice, selectedInventory, manualVin, lang, paymentFrequency,
    customBonusCash, fraisDossier, taxePneus, fraisRDPRM, prixEchange, comptantTxInclus, selectedTerm,
    showLease, leaseResult, leaseTerm, leaseKmPerYear, generateSubmissionText]);

  // ── Send SMS message ──
  const handleSendSms = useCallback(async () => {
    try {
      if (Platform.OS === 'web') {
        if (navigator.share) {
          await navigator.share({ title: 'CalcAuto AiPro - Soumission', text: smsPreviewText });
        } else {
          const smsBody = encodeURIComponent(smsPreviewText);
          window.open(`sms:?body=${smsBody}`, '_blank');
        }
      } else {
        const result = await Share.share({ message: smsPreviewText });
        if (result.action === Share.sharedAction && result.activityType) {
          console.log('Shared with activity type:', result.activityType);
        }
      }
      setShowSmsPreview(false);
    } catch (error: any) {
      console.error('Share error:', error);
      if (error.message !== 'User did not share') {
        if (Platform.OS === 'web') {
          alert(lang === 'fr' ? 'Erreur lors du partage' : 'Error sharing');
        } else {
          Alert.alert('Erreur', lang === 'fr' ? 'Erreur lors du partage' : 'Error sharing');
        }
      }
    }
  }, [smsPreviewText, lang]);

  // ── Handle Print ──
  const handlePrint = useCallback(async () => {
    if (!selectedProgram || !localResult || !vehiclePrice) {
      if (Platform.OS === 'web') {
        alert(lang === 'fr' ? 'Aucune soumission a imprimer' : 'No submission to print');
      } else {
        Alert.alert('Erreur', lang === 'fr' ? 'Aucune soumission a imprimer' : 'No submission to print');
      }
      return;
    }

    const printContent = buildPrintHtml({
      selectedProgram, localResult, vehiclePrice, selectedTerm, selectedOption,
      paymentFrequency, lang, selectedInventory, manualVin,
      customBonusCash, fraisDossier, taxePneus, fraisRDPRM,
      prixEchange, montantDuEchange, comptantTxInclus,
      showLease, leaseResult, leaseTerm, leaseKmPerYear,
    });

    if (Platform.OS === 'web') {
      const printWindow = window.open('', '_blank');
      if (printWindow) {
        printWindow.document.write(printContent);
        printWindow.document.close();
        printWindow.focus();
        setTimeout(() => { printWindow.print(); }, 250);
      }
    } else {
      try {
        await Print.printAsync({ html: printContent });
      } catch (e) {
        console.log('Print cancelled or error:', e);
      }
    }
  }, [selectedProgram, localResult, vehiclePrice, selectedTerm, selectedOption, paymentFrequency, lang,
    selectedInventory, manualVin, customBonusCash, fraisDossier, taxePneus, fraisRDPRM,
    prixEchange, montantDuEchange, comptantTxInclus, showLease, leaseResult, leaseTerm, leaseKmPerYear]);

  // ── Handle Export Excel ──
  const handleExportExcel = useCallback(async () => {
    if (!selectedInventory && !selectedProgram) {
      if (Platform.OS === 'web') {
        alert(lang === 'fr' ? 'Aucune donnee a exporter' : 'No data to export');
      } else {
        Alert.alert('Erreur', lang === 'fr' ? 'Aucune donnee a exporter' : 'No data to export');
      }
      return;
    }

    try {
      const token = await getToken();
      const exportData = {
        vin: selectedInventory?.vin || manualVin || '',
        model_code: selectedInventory?.model_code || selectedProgram?.code || '',
        brand: selectedInventory?.brand || selectedProgram?.brand || '',
        model: selectedInventory?.model || selectedProgram?.model || '',
        trim: selectedInventory?.trim || selectedProgram?.trim || '',
        year: selectedInventory?.year?.toString() || selectedProgram?.year || '',
        stock_no: selectedInventory?.stock_no || '',
        ep_cost: selectedInventory?.ep_cost || 0,
        pdco: selectedInventory?.pdco || selectedInventory?.msrp || 0,
        pref: selectedInventory?.pref || 0,
        holdback: selectedInventory?.holdback || 0,
        subtotal: selectedInventory?.subtotal || 0,
        total: selectedInventory?.total || 0,
        options: selectedInventory?.options || [],
      };

      const response = await fetch(`${API_URL}/api/invoice/export-excel`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(token ? { 'Authorization': `Bearer ${token}` } : {}),
        },
        body: JSON.stringify(exportData),
      });

      const result = await response.json();

      if (result.success && result.excel_base64) {
        if (Platform.OS === 'web') {
          const byteCharacters = atob(result.excel_base64);
          const byteNumbers = new Array(byteCharacters.length);
          for (let i = 0; i < byteCharacters.length; i++) {
            byteNumbers[i] = byteCharacters.charCodeAt(i);
          }
          const byteArray = new Uint8Array(byteNumbers);
          const blob = new Blob([byteArray], { type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' });
          const url = window.URL.createObjectURL(blob);
          const a = document.createElement('a');
          a.href = url;
          a.download = result.filename;
          document.body.appendChild(a);
          a.click();
          window.URL.revokeObjectURL(url);
          document.body.removeChild(a);
          alert(lang === 'fr' ? `Fichier telecharge: ${result.filename}` : `File downloaded: ${result.filename}`);
        } else {
          const filename = result.filename || 'facture_export.xlsx';
          const fileUri = FileSystem.documentDirectory + filename;
          await FileSystem.writeAsStringAsync(fileUri, result.excel_base64, {
            encoding: FileSystem.EncodingType.Base64,
          });
          await Sharing.shareAsync(fileUri, {
            mimeType: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            dialogTitle: lang === 'fr' ? 'Exporter Excel' : 'Export Excel',
          });
        }
      } else {
        throw new Error(result.detail || 'Export failed');
      }
    } catch (error: any) {
      console.error('Excel export error:', error);
      if (Platform.OS === 'web') {
        alert(lang === 'fr' ? `Erreur export: ${error.message}` : `Export error: ${error.message}`);
      } else {
        Alert.alert('Erreur', error.message);
      }
    }
  }, [selectedInventory, selectedProgram, manualVin, lang, getToken]);

  // ── Handle Send Email ──
  const handleSendEmail = useCallback(async () => {
    if (!clientPhone || clientPhone.trim().length < 7) {
      if (Platform.OS === 'web') {
        alert(t.email.invalidPhone);
      } else {
        Alert.alert('Erreur', t.email.invalidPhone);
      }
      return;
    }
    if (!clientEmail || !clientEmail.includes('@')) {
      if (Platform.OS === 'web') {
        alert(t.email.invalidEmail);
      } else {
        Alert.alert('Erreur', t.email.invalidEmail);
      }
      return;
    }
    if (!selectedProgram || !localResult) return;

    setSendingEmail(true);
    try {
      const response = await fetch(`${API_URL}/api/send-calculation-email`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          client_email: clientEmail,
          client_name: clientName,
          client_phone: clientPhone,
          vehicle_info: {
            brand: selectedProgram.brand,
            model: selectedProgram.model,
            trim: selectedProgram.trim,
            year: selectedProgram.year,
            vin: selectedInventory?.vin || (manualVin && manualVin.length === 17 ? manualVin : ''),
          },
          calculation_results: {
            consumer_cash: selectedProgram.consumer_cash,
            bonus_cash: parseFloat(customBonusCash) || selectedProgram.bonus_cash,
            comparisons: [{
              term_months: selectedTerm,
              option1_rate: localResult.option1Rate,
              option1_monthly: localResult.option1Monthly,
              option1_biweekly: localResult.option1Biweekly,
              option1_weekly: localResult.option1Weekly,
              option1_total: localResult.option1Total,
              option2_rate: localResult.option2Rate,
              option2_monthly: localResult.option2Monthly,
              option2_biweekly: localResult.option2Biweekly,
              option2_weekly: localResult.option2Weekly,
              option2_total: localResult.option2Total,
              best_option: localResult.bestOption,
              savings: localResult.savings,
              principal_option1: localResult.principalOption1,
              principal_option2: localResult.principalOption2,
            }],
          },
          selected_term: selectedTerm,
          selected_option: selectedOption || '1',
          vehicle_price: parseFloat(vehiclePrice),
          payment_frequency: paymentFrequency,
          dealer_name: 'CalcAuto AiPro',
          include_window_sticker: !!(selectedInventory?.vin || (manualVin && manualVin.length === 17)),
          vin: selectedInventory?.vin || (manualVin && manualVin.length === 17 ? manualVin : ''),
          fees: {
            frais_dossier: parseFloat(fraisDossier) || 0,
            taxe_pneus: parseFloat(taxePneus) || 0,
            frais_rdprm: parseFloat(fraisRDPRM) || 0,
          },
          trade_in: {
            valeur_echange: parseFloat(prixEchange) || 0,
            montant_du: parseFloat(montantDuEchange) || 0,
          },
          rates_table: {
            option1_rates: selectedProgram.option1_rates,
            option2_rates: selectedProgram.option2_rates,
          },
          lease_data: showLease && leaseResult && (leaseResult.standard || leaseResult.alternative) ? {
            term: leaseTerm,
            km_per_year: leaseKmPerYear,
            residual_pct: leaseResult.residualPct,
            residual_value: leaseResult.residualValue,
            km_adjustment: leaseResult.kmAdjustment || 0,
            best_lease: leaseResult.bestLease,
            lease_savings: leaseResult.leaseSavings || 0,
            standard: leaseResult.standard ? {
              rate: leaseResult.standard.rate,
              lease_cash: leaseResult.standard.leaseCash,
              monthly: leaseResult.standard.monthly,
              biweekly: leaseResult.standard.biweekly,
              weekly: leaseResult.standard.weekly,
              total: leaseResult.standard.total,
            } : null,
            alternative: leaseResult.alternative ? {
              rate: leaseResult.alternative.rate,
              monthly: leaseResult.alternative.monthly,
              biweekly: leaseResult.alternative.biweekly,
              weekly: leaseResult.alternative.weekly,
              total: leaseResult.alternative.total,
            } : null,
          } : null,
        }),
      });

      const data = await response.json();

      if (data.success) {
        const token = await getToken();
        const authHeaders: Record<string, string> = token
          ? { 'Authorization': `Bearer ${token}`, 'Content-Type': 'application/json' }
          : { 'Content-Type': 'application/json' };

        let contactStatus = '';

        // Check/create contact
        try {
          const contactsResponse = await fetch(`${API_URL}/api/contacts`, { headers: authHeaders });
          const existingContacts = await contactsResponse.json();
          const existingContact = existingContacts.find((c: any) =>
            c.name?.toLowerCase() === (clientName || '').toLowerCase() ||
            (c.phone && c.phone === clientPhone) ||
            (c.email && c.email === clientEmail)
          );

          if (existingContact) {
            const updateData: any = {};
            if (clientEmail && clientEmail !== existingContact.email) updateData.email = clientEmail;
            if (clientPhone && clientPhone !== existingContact.phone) updateData.phone = clientPhone;
            if (clientName && clientName !== existingContact.name) updateData.name = clientName;

            if (Object.keys(updateData).length > 0) {
              await fetch(`${API_URL}/api/contacts/${existingContact.id}`, {
                method: 'PUT', headers: authHeaders, body: JSON.stringify(updateData),
              });
              contactStatus = `Contact "${clientName || existingContact.name}" mis a jour`;
            } else {
              contactStatus = `Contact "${clientName || existingContact.name}" existant`;
            }
          } else {
            await fetch(`${API_URL}/api/contacts`, {
              method: 'POST', headers: authHeaders,
              body: JSON.stringify({ name: clientName || 'Client', phone: clientPhone, email: clientEmail, source: 'submission' }),
            });
            contactStatus = `Nouveau contact "${clientName || 'Client'}" cree`;
          }
        } catch (contactErr) {
          console.log('Error managing contact:', contactErr);
          contactStatus = 'Contact non gere';
        }

        // Save submission to server
        let submissionSaved = false;
        try {
          const activeOption = selectedOption || '1';
          const subResponse = await fetch(`${API_URL}/api/submissions`, {
            method: 'POST', headers: authHeaders,
            body: JSON.stringify({
              client_name: clientName || 'Client',
              client_email: clientEmail,
              client_phone: clientPhone,
              vehicle_brand: selectedProgram.brand,
              vehicle_model: selectedProgram.model,
              vehicle_year: selectedProgram.year,
              vehicle_price: parseFloat(vehiclePrice) || 0,
              term: selectedTerm,
              payment_monthly: activeOption === '2' ? localResult.option2Monthly : localResult.option1Monthly,
              payment_biweekly: activeOption === '2' ? localResult.option2Biweekly : localResult.option1Biweekly,
              payment_weekly: activeOption === '2' ? localResult.option2Weekly : localResult.option1Weekly,
              selected_option: activeOption,
              rate: activeOption === '2' ? localResult.option2Rate : localResult.option1Rate,
              program_month: currentPeriod?.month || new Date().getMonth() + 1,
              program_year: currentPeriod?.year || new Date().getFullYear(),
              calculator_state: {
                selectedProgram, vehiclePrice, selectedTerm, selectedOption, paymentFrequency,
                customBonusCash, comptantTxInclus, fraisDossier, taxePneus, fraisRDPRM,
                prixEchange, montantDuEchange, accessories, leaseRabaisConcess, leasePdsf,
                leaseSoldeReporte, leaseTerm, leaseKmPerYear, showLease, manualVin,
                selectedYear, selectedBrand,
                selectedInventory: selectedInventory ? {
                  id: selectedInventory.id, vin: selectedInventory.vin, brand: selectedInventory.brand,
                  model: selectedInventory.model, trim: selectedInventory.trim, year: selectedInventory.year,
                  body_style: selectedInventory.body_style, asking_price: selectedInventory.asking_price,
                  msrp: selectedInventory.msrp, pdco: selectedInventory.pdco,
                } : null,
              },
            }),
          });
          if (subResponse.ok) {
            submissionSaved = true;
          } else {
            const errData = await subResponse.json().catch(() => ({}));
            console.error('Submission save failed:', subResponse.status, errData);
          }
        } catch (subErr) {
          console.error('Error saving submission to server:', subErr);
        }

        // Save locally
        try {
          const payment = paymentFrequency === 'monthly' ? localResult.option1Monthly :
            paymentFrequency === 'biweekly' ? localResult.option1Biweekly : localResult.option1Weekly;
          const submission = {
            id: Date.now().toString(),
            clientName: clientName || 'Client',
            clientEmail, clientPhone,
            vehicle: `${selectedProgram.brand} ${selectedProgram.model} ${selectedProgram.year}`,
            price: parseFloat(vehiclePrice) || 0,
            term: selectedTerm,
            payment,
            date: new Date().toISOString(),
            contactId: params.contactId,
          };
          const storedSubmissions = await AsyncStorage.getItem(SUBMISSIONS_KEY);
          const existingSubmissions = storedSubmissions ? JSON.parse(storedSubmissions) : [];
          existingSubmissions.unshift(submission);
          await AsyncStorage.setItem(SUBMISSIONS_KEY, JSON.stringify(existingSubmissions.slice(0, 100)));
        } catch (e) {
          console.log('Error saving submission locally:', e);
        }

        setShowEmailModal(false);
        setClientEmail('');
        setClientName('');
        setClientPhone('');

        const successMsg = lang === 'fr'
          ? `Email envoye!\n\n${contactStatus}\n${submissionSaved ? 'Soumission enregistree' : 'ATTENTION: Soumission non enregistree dans l\'historique'}`
          : `Email sent!\n\n${contactStatus}\n${submissionSaved ? 'Submission saved' : 'WARNING: Submission not saved to history'}`;

        if (Platform.OS === 'web') {
          alert(successMsg);
        } else {
          Alert.alert('Succes', successMsg);
        }
      } else {
        throw new Error(data.detail || 'Erreur');
      }
    } catch (error: any) {
      if (Platform.OS === 'web') {
        alert(lang === 'fr' ? "Erreur lors de l'envoi" : 'Error sending email');
      } else {
        Alert.alert('Erreur', lang === 'fr' ? "Erreur lors de l'envoi" : 'Error sending email');
      }
    } finally {
      setSendingEmail(false);
    }
  }, [clientPhone, clientEmail, clientName, selectedProgram, localResult, vehiclePrice, selectedTerm, selectedOption,
    paymentFrequency, selectedInventory, manualVin, customBonusCash, fraisDossier, taxePneus, fraisRDPRM,
    prixEchange, montantDuEchange, showLease, leaseResult, leaseTerm, leaseKmPerYear, accessories,
    leaseRabaisConcess, leasePdsf, leaseSoldeReporte, currentPeriod, selectedYear, selectedBrand,
    comptantTxInclus, t, lang, getToken, params.contactId]);

  // ─── Return ────────────────────────────────────────────────
  return {
    // Language
    lang, t, handleLanguageChange,
    // Router
    router,
    // Programs
    programs, filteredPrograms, selectedProgram, selectProgram, clearSelection,
    programsLoading, setProgramsLoading, refreshing, onRefresh, loadPrograms,
    loading, results,
    // Splash
    showSplash, setShowSplash,
    // Filters
    selectedYear, setSelectedYear, selectedBrand, setSelectedBrand, years, brands,
    // Period
    currentPeriod, availablePeriods, showPeriodSelector, setShowPeriodSelector,
    handlePeriodSelect, programMeta,
    // Loyalty & Deferred
    loyaltyChecked, setLoyaltyChecked, deferredPayment, setDeferredPayment,
    // Term & frequency
    selectedTerm, setSelectedTerm, paymentFrequency, setPaymentFrequency,
    selectedOption, setSelectedOption,
    // Pricing inputs
    vehiclePrice, setVehiclePrice,
    customBonusCash, setCustomBonusCash,
    comptantTxInclus, setComptantTxInclus,
    accessories, setAccessories,
    fraisDossier, setFraisDossier,
    taxePneus, setTaxePneus,
    fraisRDPRM, setFraisRDPRM,
    prixEchange, setPrixEchange,
    montantDuEchange, setMontantDuEchange,
    leaseRabaisConcess, setLeaseRabaisConcess,
    // Inventory
    inventoryList, selectedInventory, setSelectedInventory, selectInventoryVehicle, clearInventorySelection,
    manualVin, setManualVin, autoFinancing, setAutoFinancing,
    // Lease SCI
    showLease, setShowLease, leaseKmPerYear, setLeaseKmPerYear,
    leaseTerm, setLeaseTerm, leaseResiduals, leaseRates,
    leaseResult, leaseLoading, leasePdsf, setLeasePdsf,
    leaseSoldeReporte, setLeaseSoldeReporte,
    bestLeaseOption, leaseAnalysisGrid,
    // Finance calculation
    localResult, activeLoyaltyRate,
    // Actions
    handleLogout, handleShareSMS, handleSendSms, handlePrint, handleExportExcel,
    handleSendEmail,
    // Import modal
    showImportModal, setShowImportModal, importPassword, setImportPassword, handleImportConfirm,
    // Email modal
    showEmailModal, setShowEmailModal, clientEmail, setClientEmail,
    clientName, setClientName, clientPhone, setClientPhone, sendingEmail,
    // SMS Preview modal
    showSmsPreview, setShowSmsPreview, smsPreviewText, setSmsPreviewText,
    // Params
    params,
  };
}

// ─── HTML Template Builders (extracted for readability) ─────

function buildSmsScreenshotHtml(d: {
  selectedProgram: VehicleProgram; localResult: LocalResult; lang: Language;
  vin: string; price: number; fmt: (v: number) => string; fmt2: (v: number) => string;
  consumerCash: number; bonusCash2: number; dossier: number; pneus: number; rdprm: number;
  valeurEchange: number; comptant: number; altConsumerCash: number; hasOption2: boolean;
  payLabel: string; o1Pay: number; o2Pay: number; selectedTerm: number;
  showLease: boolean; leaseResult: any; leaseTerm: number; leaseKmPerYear: number;
  paymentFrequency: string; stickerImageUrl: string; stickerUrl: string;
}): string {
  const { selectedProgram: sp, localResult: lr, lang, vin, price, fmt, fmt2,
    consumerCash, bonusCash2, dossier, pneus, rdprm, valeurEchange, comptant,
    altConsumerCash, hasOption2, payLabel, o1Pay, o2Pay, selectedTerm,
    showLease, leaseResult, leaseTerm, leaseKmPerYear, paymentFrequency,
    stickerImageUrl, stickerUrl } = d;

  return `
    <div id="capture" style="width:800px;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;background:#fff;color:#333;">
      <div style="background:linear-gradient(135deg,#1a1a2e,#16213e);padding:24px;text-align:center;">
        <div style="color:#fff;font-size:28px;font-weight:700;">CalcAuto <span style="color:#4ECDC4;">AiPro</span></div>
        <div style="color:rgba(255,255,255,0.7);font-size:14px;margin-top:4px;">${lang === 'fr' ? 'Soumission de financement' : 'Financing Submission'}</div>
      </div>
      <div style="padding:20px;">
        <div style="background:#f8f9fa;border-radius:10px;padding:16px;border-left:4px solid #4ECDC4;margin-bottom:16px;">
          <div style="font-size:14px;color:#666;text-transform:uppercase;letter-spacing:1px;">${sp.brand}</div>
          <div style="font-size:24px;font-weight:700;color:#1a1a2e;margin:6px 0;">${sp.model} ${sp.trim || ''} ${sp.year}</div>
          <div style="font-size:22px;color:#4ECDC4;font-weight:700;">${fmt(price)} $</div>
          ${vin ? `<div style="font-size:10px;color:#888;font-family:monospace;margin-top:4px;">VIN: ${vin}</div>` : ''}
        </div>
        <div style="margin-bottom:14px;">
          <div style="font-size:11px;color:#666;text-transform:uppercase;letter-spacing:1px;margin-bottom:6px;">Tableau des taux</div>
          <table style="width:100%;border-collapse:collapse;font-size:12px;">
            <thead><tr style="background:#1a1a2e;color:#fff;">
              <th style="padding:6px 8px;text-align:left;">Terme</th>
              <th style="padding:6px 8px;text-align:center;">Option 1</th>
              ${hasOption2 ? '<th style="padding:6px 8px;text-align:center;">Option 2</th>' : ''}
            </tr></thead>
            <tbody>
              ${[36, 48, 60, 72, 84, 96].map(t => {
                const opt1 = sp.option1_rates?.['rate_' + String(t) as keyof typeof sp.option1_rates];
                const opt2 = sp.option2_rates?.['rate_' + String(t) as keyof typeof sp.option2_rates];
                const isSelected = t === selectedTerm;
                return `<tr style="background:${isSelected ? '#e8f5e9' : (t % 2 === 0 ? '#f8f9fa' : '#fff')};${isSelected ? 'font-weight:700;' : ''}">
                  <td style="padding:5px 8px;">${t} mois</td>
                  <td style="padding:5px 8px;text-align:center;color:#c0392b;">${opt1 != null ? String(opt1).replace('.', ',') + '%' : '-'}</td>
                  ${hasOption2 ? `<td style="padding:5px 8px;text-align:center;color:#1565C0;">${opt2 != null ? String(opt2).replace('.', ',') + '%' : '-'}</td>` : ''}
                </tr>`;
              }).join('')}
            </tbody>
          </table>
        </div>
        <div style="font-size:11px;color:#666;text-transform:uppercase;letter-spacing:1px;margin-bottom:6px;">Comparaison</div>
        <div style="display:flex;gap:8px;margin-bottom:14px;">
          <div style="flex:1;border:2px solid ${lr.bestOption === '1' ? '#4CAF50' : '#ddd'};border-radius:10px;padding:12px;">
            <div style="font-size:14px;font-weight:700;color:#c0392b;margin-bottom:6px;">Option 1 ${lr.bestOption === '1' ? '<span style="background:#4CAF50;color:#fff;font-size:10px;padding:2px 6px;border-radius:8px;">&#10003;</span>' : ''}</div>
            <div style="font-size:11px;color:#666;margin-bottom:4px;">${lang === 'fr' ? 'Rabais:' : 'Rebate:'} ${consumerCash > 0 ? '-' + fmt(consumerCash) + ' $' : '$0'}</div>
            <div style="font-size:11px;color:#666;margin-bottom:4px;">${lang === 'fr' ? 'Capital:' : 'Principal:'} ${fmt(lr.principalOption1)} $</div>
            <div style="font-size:11px;color:#666;margin-bottom:4px;">${lang === 'fr' ? 'Taux:' : 'Rate:'} <span style="color:#c0392b;">${lr.option1Rate}%</span></div>
            <div style="background:#f8f9fa;border-radius:6px;padding:8px;text-align:center;border-top:3px solid #c0392b;margin-top:6px;">
              <div style="font-size:10px;color:#666;">${payLabel}</div>
              <div style="font-size:22px;font-weight:700;color:#c0392b;">${fmt2(o1Pay)} $</div>
              <div style="font-size:10px;color:#666;">Total (${selectedTerm}m): ${fmt(lr.option1Total)} $</div>
            </div>
          </div>
          ${hasOption2 ? `
          <div style="flex:1;border:2px solid ${lr.bestOption === '2' ? '#4CAF50' : '#ddd'};border-radius:10px;padding:12px;">
            <div style="font-size:14px;font-weight:700;color:#1565C0;margin-bottom:6px;">Option 2 ${lr.bestOption === '2' ? '<span style="background:#4CAF50;color:#fff;font-size:10px;padding:2px 6px;border-radius:8px;">&#10003;</span>' : ''}</div>
            <div style="font-size:11px;color:#666;margin-bottom:4px;">${lang === 'fr' ? 'Rabais:' : 'Rebate:'} ${altConsumerCash > 0 ? '-' + fmt(altConsumerCash) + ' $' : '$0'}</div>
            <div style="font-size:11px;color:#666;margin-bottom:4px;">${lang === 'fr' ? 'Capital:' : 'Principal:'} ${fmt(lr.principalOption2)} $</div>
            <div style="font-size:11px;color:#666;margin-bottom:4px;">${lang === 'fr' ? 'Taux:' : 'Rate:'} <span style="color:#1565C0;">${lr.option2Rate}%</span></div>
            <div style="background:#f8f9fa;border-radius:6px;padding:8px;text-align:center;border-top:3px solid #1565C0;margin-top:6px;">
              <div style="font-size:10px;color:#666;">${payLabel}</div>
              <div style="font-size:22px;font-weight:700;color:#1565C0;">${fmt2(o2Pay)} $</div>
              <div style="font-size:10px;color:#666;">Total (${selectedTerm}m): ${fmt(lr.option2Total || 0)} $</div>
            </div>
          </div>` : ''}
        </div>
        ${showLease && leaseResult && (leaseResult.standard || leaseResult.alternative) ? `
        <div style="border-top:2px solid #FFD700;padding-top:12px;margin-bottom:14px;">
          <div style="font-size:13px;font-weight:700;color:#F57F17;margin-bottom:10px;">LOCATION SCI - ${leaseTerm} mois / ${(leaseKmPerYear / 1000).toFixed(0)}k km</div>
          <div style="font-size:11px;color:#666;margin-bottom:8px;">Residuel: ${leaseResult.residualPct}% = ${fmt(Math.round(leaseResult.residualValue))} $</div>
          <div style="display:flex;gap:8px;">
            ${leaseResult.standard ? `
            <div style="flex:1;border:2px solid ${leaseResult.bestLease === 'standard' ? '#FFD700' : '#ddd'};border-radius:10px;padding:10px;">
              <div style="font-size:12px;font-weight:700;color:#E65100;">Std + Lease Cash ${leaseResult.bestLease === 'standard' ? '<span style="background:#FFD700;color:#000;font-size:9px;padding:1px 5px;border-radius:6px;">&#10003;</span>' : ''}</div>
              <div style="font-size:10px;color:#666;">Taux: ${leaseResult.standard.rate}% | Cash: -${fmt(leaseResult.standard.leaseCash)} $</div>
              <div style="background:#fff8e1;border-radius:6px;padding:8px;text-align:center;margin-top:6px;">
                <div style="font-size:10px;color:#666;">Avant taxes: ${fmt2(paymentFrequency === 'weekly' ? leaseResult.standard.weeklyBeforeTax : paymentFrequency === 'biweekly' ? leaseResult.standard.biweeklyBeforeTax : leaseResult.standard.monthlyBeforeTax)} $</div>
                <div style="font-size:20px;font-weight:700;color:#E65100;">${fmt2(paymentFrequency === 'weekly' ? leaseResult.standard.weekly : paymentFrequency === 'biweekly' ? leaseResult.standard.biweekly : leaseResult.standard.monthly)} $</div>
                <div style="font-size:10px;color:#c00;">Cout emprunt: ${fmt2(leaseResult.standard.coutEmprunt)} $</div>
              </div>
            </div>` : ''}
            ${leaseResult.alternative ? `
            <div style="flex:1;border:2px solid ${leaseResult.bestLease === 'alternative' ? '#FFD700' : '#ddd'};border-radius:10px;padding:10px;">
              <div style="font-size:12px;font-weight:700;color:#0277BD;">Taux Alternatif ${leaseResult.bestLease === 'alternative' ? '<span style="background:#FFD700;color:#000;font-size:9px;padding:1px 5px;border-radius:6px;">&#10003;</span>' : ''}</div>
              <div style="font-size:10px;color:#666;">Taux: ${leaseResult.alternative.rate}% | Cash: $0</div>
              <div style="background:#e3f2fd;border-radius:6px;padding:8px;text-align:center;margin-top:6px;">
                <div style="font-size:10px;color:#666;">Avant taxes: ${fmt2(paymentFrequency === 'weekly' ? leaseResult.alternative.weeklyBeforeTax : paymentFrequency === 'biweekly' ? leaseResult.alternative.biweeklyBeforeTax : leaseResult.alternative.monthlyBeforeTax)} $</div>
                <div style="font-size:20px;font-weight:700;color:#0277BD;">${fmt2(paymentFrequency === 'weekly' ? leaseResult.alternative.weekly : paymentFrequency === 'biweekly' ? leaseResult.alternative.biweekly : leaseResult.alternative.monthly)} $</div>
                <div style="font-size:10px;color:#c00;">Cout emprunt: ${fmt2(leaseResult.alternative.coutEmprunt)} $</div>
              </div>
            </div>` : ''}
          </div>
        </div>` : ''}
        ${stickerImageUrl ? `
        <div style="margin-top:10px;text-align:center;">
          <div style="font-size:11px;font-weight:700;color:#666;margin-bottom:6px;">WINDOW STICKER</div>
          <img src="${stickerImageUrl}" style="max-width:100%;border-radius:8px;border:1px solid #ddd;" crossorigin="anonymous" />
        </div>` : ''}
        ${stickerUrl ? `
        <div style="text-align:center;margin-top:8px;">
          <a href="${stickerUrl}" style="font-size:11px;color:#4ECDC4;">Window Sticker PDF</a>
        </div>` : ''}
        <div style="text-align:center;margin-top:14px;padding-top:10px;border-top:1px solid #eee;">
          <div style="font-size:10px;color:#999;">Genere le ${new Date().toLocaleDateString('fr-CA')} - CalcAuto AiPro</div>
          <div style="font-size:8px;color:#999;margin-top:6px;line-height:1.3;text-align:justify;padding:0 8px;">
            ${lang === 'fr'
              ? "AVIS IMPORTANT: Les montants presentes sont a titre indicatif seulement et ne constituent pas une offre officielle. Les versements reels peuvent differer selon l'evaluation de credit, les programmes en vigueur et les frais applicables. Le concessionnaire ne peut etre tenu responsable de toute erreur de calcul. Sujet a l'approbation du credit."
              : 'IMPORTANT: Amounts shown are for informational purposes only and do not constitute an official offer. Actual payments may differ. Subject to credit approval.'}
          </div>
        </div>
      </div>
    </div>`;
}

function buildPrintHtml(d: {
  selectedProgram: VehicleProgram; localResult: LocalResult; vehiclePrice: string;
  selectedTerm: number; selectedOption: '1' | '2' | null; paymentFrequency: 'monthly' | 'biweekly' | 'weekly';
  lang: Language; selectedInventory: any; manualVin: string;
  customBonusCash: string; fraisDossier: string; taxePneus: string; fraisRDPRM: string;
  prixEchange: string; montantDuEchange: string; comptantTxInclus: string;
  showLease: boolean; leaseResult: any; leaseTerm: number; leaseKmPerYear: number;
}): string {
  const { selectedProgram: sp, localResult: lr, vehiclePrice, selectedTerm, selectedOption,
    paymentFrequency, lang, selectedInventory, manualVin,
    customBonusCash, fraisDossier, taxePneus, fraisRDPRM,
    prixEchange, montantDuEchange, comptantTxInclus,
    showLease, leaseResult, leaseTerm, leaseKmPerYear } = d;

  const option = selectedOption === '2' ? '2' : '1';
  const vin = selectedInventory?.vin || (manualVin && manualVin.length === 17 ? manualVin : '');
  const price = parseFloat(vehiclePrice) || 0;
  const consumerCash = sp.consumer_cash;
  const bonusCash = parseFloat(customBonusCash) || sp.bonus_cash || 0;
  const dossier = parseFloat(fraisDossier) || 0;
  const pneus = parseFloat(taxePneus) || 0;
  const rdprm = parseFloat(fraisRDPRM) || 0;
  const valeurEchange = parseFloat(prixEchange) || 0;
  const comptant = parseFloat(comptantTxInclus) || 0;
  const altConsumerCashPrint = sp.alternative_consumer_cash || 0;
  const hasOption2 = sp.option2_rates !== null && lr.option2Monthly !== null;
  const bestOpt = lr.bestOption;
  const savingsAmt = lr.savings || 0;

  const fmt = (v: number) => v.toLocaleString('fr-CA', { maximumFractionDigits: 0 });
  const fmt2 = (v: number) => v.toLocaleString('fr-CA', { minimumFractionDigits: 2, maximumFractionDigits: 2 });

  let paymentLabel: string;
  if (paymentFrequency === 'biweekly') {
    paymentLabel = lang === 'fr' ? 'Aux 2 semaines' : 'Bi-weekly';
  } else if (paymentFrequency === 'weekly') {
    paymentLabel = lang === 'fr' ? 'Hebdomadaire' : 'Weekly';
  } else {
    paymentLabel = lang === 'fr' ? 'Mensuel' : 'Monthly';
  }

  const terms = [36, 48, 60, 72, 84, 96];
  const ratesRows = terms.map(t => {
    const r1 = getRateForTerm(sp.option1_rates, t);
    const r2 = sp.option2_rates ? getRateForTerm(sp.option2_rates, t) : null;
    const isSelected = t === selectedTerm;
    return `<tr style="${isSelected ? 'background:#e8f5e9; font-weight:bold;' : ''}">
      <td style="text-align:left; padding:8px; border-bottom:1px solid #eee;">${t} ${lang === 'fr' ? 'mois' : 'mo'}${isSelected ? ' &#10003;' : ''}</td>
      <td style="text-align:center; padding:8px; border-bottom:1px solid #eee; color:#c0392b;">${r1.toFixed(2)}%</td>
      ${hasOption2 ? `<td style="text-align:center; padding:8px; border-bottom:1px solid #eee; color:#1565C0;">${r2 !== null ? r2.toFixed(2) + '%' : '-'}</td>` : ''}
    </tr>`;
  }).join('');

  const o1Payment = paymentFrequency === 'biweekly' ? lr.option1Biweekly : paymentFrequency === 'weekly' ? lr.option1Weekly : lr.option1Monthly;
  const o2Payment = paymentFrequency === 'biweekly' ? (lr.option2Biweekly || 0) : paymentFrequency === 'weekly' ? (lr.option2Weekly || 0) : (lr.option2Monthly || 0);

  // Build lease section HTML
  let leaseHtml = '';
  if (showLease && leaseResult && (leaseResult.standard || leaseResult.alternative)) {
    leaseHtml = `
    <div class="section" style="margin-top:20px;">
      <div class="section-title" style="border-color:#FFD700;">${lang === 'fr' ? 'Location SCI' : 'SCI Lease'}</div>
      <table class="info-table" style="margin-bottom:12px;">
        <tr><td>${lang === 'fr' ? 'Kilometrage / an' : 'Km / year'}</td><td><strong>${(leaseKmPerYear / 1000).toFixed(0)}k km</strong></td></tr>
        <tr><td>${lang === 'fr' ? 'Terme location' : 'Lease term'}</td><td><strong>${leaseTerm} ${lang === 'fr' ? 'mois' : 'months'}</strong></td></tr>
        <tr><td>${lang === 'fr' ? 'Residuel' : 'Residual'}</td><td><strong>${leaseResult.residualPct}%${leaseResult.kmAdjustment ? ` (+${leaseResult.kmAdjustment}%)` : ''} = ${fmt(Math.round(leaseResult.residualValue))} $</strong></td></tr>
      </table>
      <div class="options-grid">
        ${leaseResult.standard ? `
        <div class="option-card ${leaseResult.bestLease === 'standard' ? 'winner' : ''}">
          <div class="option-title" style="color:#E65100;">Std + Lease Cash</div>
          <div class="payment-box" style="border-top:3px solid #E65100;">
            <div class="payment-label">${paymentLabel}</div>
            <div class="payment-amount" style="color:#E65100;">${fmt2(paymentFrequency === 'biweekly' ? leaseResult.standard.biweekly : paymentFrequency === 'weekly' ? leaseResult.standard.weekly : leaseResult.standard.monthly)} $</div>
            <div class="payment-total">Total: ${fmt(Math.round(leaseResult.standard.total))} $</div>
          </div>
        </div>` : ''}
        ${leaseResult.alternative ? `
        <div class="option-card ${leaseResult.bestLease === 'alternative' ? 'winner' : ''}">
          <div class="option-title" style="color:#0277BD;">${lang === 'fr' ? 'Taux Alternatif' : 'Alt. Rate'}</div>
          <div class="payment-box" style="border-top:3px solid #0277BD;">
            <div class="payment-label">${paymentLabel}</div>
            <div class="payment-amount" style="color:#0277BD;">${fmt2(paymentFrequency === 'biweekly' ? leaseResult.alternative.biweekly : paymentFrequency === 'weekly' ? leaseResult.alternative.weekly : leaseResult.alternative.monthly)} $</div>
            <div class="payment-total">Total: ${fmt(Math.round(leaseResult.alternative.total))} $</div>
          </div>
        </div>` : ''}
      </div>
    </div>`;
  }

  return `<!DOCTYPE html><html><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"><title>CalcAuto AiPro</title>
<style>
*{box-sizing:border-box;margin:0;padding:0}body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;background:#f5f5f5;color:#333}
.container{max-width:640px;margin:0 auto;background:#fff}.header{background:linear-gradient(135deg,#1a1a2e 0%,#16213e 100%);padding:25px 20px;text-align:center}
.header h1{color:#fff;font-size:26px;margin:0}.header h1 span{color:#4ECDC4}.header p{color:rgba(255,255,255,0.7);font-size:13px;margin-top:4px}
.content{padding:20px}.section{margin-bottom:20px}.section-title{font-size:13px;font-weight:700;color:#666;text-transform:uppercase;letter-spacing:0.5px;margin-bottom:10px;border-bottom:2px solid #4ECDC4;padding-bottom:5px;display:inline-block}
.vehicle-box{background:#f8f9fa;border-radius:10px;padding:15px;border-left:4px solid #4ECDC4}.vehicle-brand{font-size:13px;color:#666;text-transform:uppercase;letter-spacing:1px}
.vehicle-model{font-size:22px;font-weight:700;color:#1a1a2e;margin:4px 0}.vehicle-price{font-size:20px;color:#4ECDC4;font-weight:700}.vehicle-vin{font-size:11px;color:#888;font-family:monospace;margin-top:4px}
.rates-table{width:100%;border-collapse:collapse;font-size:13px}.rates-table th{background:#1a1a2e;color:#fff;padding:10px;font-size:12px}.rates-table td{padding:8px;border-bottom:1px solid #eee}
.info-table{width:100%;font-size:13px}.info-table td{padding:8px 4px;border-bottom:1px solid #f0f0f0}.info-table td:last-child{text-align:right;font-weight:600}
.best-choice{background:#e8f5e9;border:2px solid #4CAF50;border-radius:10px;padding:12px;text-align:center;margin-bottom:20px}.best-choice-title{font-size:16px;font-weight:700;color:#2E7D32}
.options-grid{display:flex;gap:10px}.option-card{flex:1;border-radius:10px;padding:15px;border:2px solid #ddd}.option-card.winner{border-color:#4CAF50;background:#f0fff4}
.option-title{font-size:15px;font-weight:700;margin-bottom:8px}.option-detail{display:flex;justify-content:space-between;font-size:12px;margin-bottom:4px;color:#555}
.payment-box{background:#f8f9fa;border-radius:8px;padding:12px;margin-top:10px;text-align:center}.payment-label{font-size:11px;color:#666}
.payment-amount{font-size:24px;font-weight:700;margin:4px 0}.payment-total{font-size:11px;color:#666}
.footer{background:#f8f9fa;padding:20px;text-align:center;border-top:1px solid #eee;margin-top:20px}.footer .disclaimer{font-size:10px;color:#999;margin-top:8px;line-height:1.4}
.back-btn{display:block;margin:10px auto 15px;padding:12px 30px;background:#1a1a2e;color:#4ECDC4;border:2px solid #4ECDC4;border-radius:8px;font-size:16px;font-weight:700;cursor:pointer;text-align:center}
@media print{body{background:#fff}.no-print{display:none !important}}
</style></head><body><div class="container">
<div class="header"><h1>CalcAuto <span>AiPro</span></h1><p>${lang === 'fr' ? 'Soumission de financement' : 'Financing Submission'}</p></div>
<div class="content">
  <div class="section"><div class="section-title">${lang === 'fr' ? 'Vehicule' : 'Vehicle'}</div>
    <div class="vehicle-box"><div class="vehicle-brand">${sp.brand}</div><div class="vehicle-model">${sp.model} ${sp.trim || ''} ${sp.year}</div>
    <div class="vehicle-price">${fmt(price)} $</div>${vin ? `<div class="vehicle-vin">VIN: ${vin}</div>` : ''}</div></div>
  <div class="section"><div class="section-title">${lang === 'fr' ? 'Tableau des taux' : 'Rate Table'}</div>
    <table class="rates-table"><thead><tr><th style="text-align:left;">${lang === 'fr' ? 'Terme' : 'Term'}</th><th>Option 1</th>${hasOption2 ? '<th>Option 2</th>' : ''}</tr></thead><tbody>${ratesRows}</tbody></table></div>
  <div class="section"><div class="section-title">${lang === 'fr' ? 'Details du financement' : 'Financing Details'}</div>
    <table class="info-table">
      <tr><td>${lang === 'fr' ? 'Prix du vehicule' : 'Vehicle price'}</td><td>${fmt(price)} $</td></tr>
      ${consumerCash > 0 ? `<tr><td>${lang === 'fr' ? 'Rabais' : 'Rebate'}</td><td style="color:#2E7D32;">-${fmt(consumerCash)} $</td></tr>` : ''}
      ${bonusCash > 0 ? `<tr><td>Bonus Cash</td><td style="color:#2E7D32;">-${fmt(bonusCash)} $</td></tr>` : ''}
      ${dossier > 0 ? `<tr><td>${lang === 'fr' ? 'Frais dossier' : 'Admin fees'}</td><td>${fmt2(dossier)} $</td></tr>` : ''}
      ${pneus > 0 ? `<tr><td>${lang === 'fr' ? 'Taxe pneus' : 'Tire tax'}</td><td>${fmt(pneus)} $</td></tr>` : ''}
      ${rdprm > 0 ? `<tr><td>RDPRM</td><td>${fmt(rdprm)} $</td></tr>` : ''}
      ${valeurEchange > 0 ? `<tr><td>${lang === 'fr' ? 'Valeur echange' : 'Trade-in'}</td><td style="color:#2E7D32;">-${fmt(valeurEchange)} $</td></tr>` : ''}
      ${comptant > 0 ? `<tr><td>${lang === 'fr' ? 'Comptant' : 'Down payment'}</td><td>-${fmt(comptant)} $</td></tr>` : ''}
      <tr><td>${lang === 'fr' ? 'Terme' : 'Term'}</td><td><strong>${selectedTerm} ${lang === 'fr' ? 'mois' : 'months'}</strong></td></tr>
      <tr><td>${lang === 'fr' ? 'Frequence' : 'Frequency'}</td><td><strong>${paymentLabel}</strong></td></tr>
    </table></div>
  ${hasOption2 && savingsAmt > 0 ? `<div class="best-choice"><div class="best-choice-title">Option ${bestOpt} = ${lang === 'fr' ? 'Meilleur choix!' : 'Best choice!'}</div></div>` : ''}
  <div class="section"><div class="section-title">${lang === 'fr' ? 'Comparaison' : 'Comparison'}</div>
    <div class="options-grid">
      <div class="option-card ${bestOpt === '1' ? 'winner' : ''}">
        <div class="option-title" style="color:#c0392b;">Option 1</div>
        <div class="option-detail"><span>${lang === 'fr' ? 'Taux:' : 'Rate:'}</span><span style="color:#c0392b;">${lr.option1Rate}%</span></div>
        <div class="payment-box" style="border-top:3px solid #c0392b;"><div class="payment-label">${paymentLabel}</div>
          <div class="payment-amount" style="color:#c0392b;">${fmt2(o1Payment)} $</div>
          <div class="payment-total">Total: ${fmt(lr.option1Total)} $</div></div>
      </div>
      ${hasOption2 ? `<div class="option-card ${bestOpt === '2' ? 'winner' : ''}">
        <div class="option-title" style="color:#1565C0;">Option 2</div>
        <div class="option-detail"><span>${lang === 'fr' ? 'Taux:' : 'Rate:'}</span><span style="color:#1565C0;">${lr.option2Rate}%</span></div>
        <div class="payment-box" style="border-top:3px solid #1565C0;"><div class="payment-label">${paymentLabel}</div>
          <div class="payment-amount" style="color:#1565C0;">${fmt2(o2Payment)} $</div>
          <div class="payment-total">Total: ${fmt(lr.option2Total || 0)} $</div></div>
      </div>` : ''}
    </div></div>
  ${leaseHtml}
</div>
<div class="footer"><button class="back-btn no-print" onclick="window.close();if(!window.closed)history.back();">${lang === 'fr' ? 'Retour au calculateur' : 'Back to calculator'}</button>
  <div style="font-size:12px;color:#666;">${lang === 'fr' ? 'Genere le' : 'Generated on'} ${new Date().toLocaleDateString(lang === 'fr' ? 'fr-CA' : 'en-CA')}</div>
  <div class="disclaimer">${lang === 'fr'
    ? "AVIS IMPORTANT: Les montants de paiements presentes dans cette soumission sont fournis a titre indicatif seulement et ne constituent en aucun cas une offre de financement ou de location officielle. Les versements reels peuvent differer en fonction de l'evaluation de credit, des programmes en vigueur au moment de la transaction, des ajustements de residuel et des frais applicables. Le concessionnaire et ses representants ne peuvent etre tenus responsables de toute erreur de calcul ou d'ecart entre la presente estimation et les conditions finales du contrat. Toute transaction est sujette a l'approbation du credit par l'institution financiere."
    : 'IMPORTANT NOTICE: Payment amounts shown in this submission are provided for informational purposes only and do not constitute an official financing or lease offer. Actual payments may differ. Subject to credit approval.'}</div>
</div></div></body></html>`;
}

// Re-export utilities for components
export { getRateForTerm, formatCurrency, formatCurrencyDecimal };
