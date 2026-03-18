import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import axios from 'axios';
import { API_URL } from '../../../utils/api';
import { ProgramPeriod, VehicleProgram } from '../../../types/calculator';

type ProgramMeta = {
  event_names: string[];
  program_period: string;
  program_month: string;
  loyalty_rate: number;
  no_payments_days: number;
  featured_rate: number | null;
  featured_term: number | null;
  key_message: string;
  brands?: string[];
};

function sameProgram(a: VehicleProgram | null, b: VehicleProgram) {
  if (!a) return false;
  return (
    a.brand === b.brand &&
    a.model === b.model &&
    (a.trim || '') === (b.trim || '') &&
    a.year === b.year
  );
}

function findMatchingProgram(
  list: VehicleProgram[],
  previous: VehicleProgram | null
): VehicleProgram | null {
  if (!previous || list.length === 0) return null;

  const byId = list.find((p) => p.id === previous.id);
  if (byId) return byId;

  const byLogicalKey = list.find((p) => sameProgram(previous, p));
  return byLogicalKey || null;
}

export function useProgramsData({
  onProgramMetaLoaded,
}: {
  onProgramMetaLoaded?: (meta: ProgramMeta | null) => void;
}) {
  const [programs, setPrograms] = useState<VehicleProgram[]>([]);
  const [selectedProgram, setSelectedProgram] = useState<VehicleProgram | null>(null);

  const [selectedYear, setSelectedYear] = useState<number | null>(null);
  const [selectedBrand, setSelectedBrand] = useState<string | null>(null);

  const [programsLoading, setProgramsLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  const [currentPeriod, setCurrentPeriod] = useState<{ month: number; year: number } | null>(null);
  const [availablePeriods, setAvailablePeriods] = useState<ProgramPeriod[]>([]);
  const [showPeriodSelector, setShowPeriodSelector] = useState(false);

  const [programMeta, setProgramMeta] = useState<ProgramMeta | null>(null);

  const years = useMemo(
    () => [...new Set(programs.map((p) => p.year))].sort((a, b) => b - a),
    [programs]
  );

  const brands = useMemo(
    () => [...new Set(programs.map((p) => p.brand))].sort((a, b) => a.localeCompare(b)),
    [programs]
  );

  const filteredPrograms = useMemo(() => {
    let filtered = [...programs];
    if (selectedYear) filtered = filtered.filter((p) => p.year === selectedYear);
    if (selectedBrand) filtered = filtered.filter((p) => p.brand === selectedBrand);
    filtered.sort((a, b) => (a.sort_order || 0) - (b.sort_order || 0));
    return filtered;
  }, [programs, selectedYear, selectedBrand]);

  const currentPeriodRef = useRef<{ month: number; year: number } | null>(null);
  const onMetaLoadedRef = useRef(onProgramMetaLoaded);
  onMetaLoadedRef.current = onProgramMetaLoaded;

  const loadPeriods = useCallback(async () => {
    try {
      const res = await axios.get(`${API_URL}/api/periods`);
      const periods = Array.isArray(res.data) ? res.data : [];
      setAvailablePeriods(periods);

      if (!currentPeriodRef.current && periods.length > 0) {
        const initial = { month: periods[0].month, year: periods[0].year };
        currentPeriodRef.current = initial;
        setCurrentPeriod(initial);
      }
    } catch (error) {
      console.log('Could not load periods:', error);
    }
  }, []);

  const loadProgramMeta = useCallback(
    async (month: number, year: number) => {
      try {
        const res = await axios.get(`${API_URL}/api/program-meta`, {
          params: { month, year },
        });
        const meta = res.data && res.data.event_names ? res.data : null;
        setProgramMeta(meta);
        onMetaLoadedRef.current?.(meta);
      } catch (error) {
        console.log('Could not load program meta:', error);
        setProgramMeta(null);
        onMetaLoadedRef.current?.(null);
      }
    },
    []
  );

  const loadPrograms = useCallback(
    async (month?: number, year?: number) => {
      const startTime = Date.now();
      const MIN_LOADING_TIME = 1200;

      setProgramsLoading(true);

      try {
        await loadPeriods();

        let url = `${API_URL}/api/programs`;
        if (month && year) {
          url += `?month=${month}&year=${year}`;
        }

        const res = await axios.get(url, {
          headers: { 'Cache-Control': 'no-cache' },
        });

        const raw = Array.isArray(res.data) ? res.data : [];
        const sorted = [...raw].sort(
          (a: VehicleProgram, b: VehicleProgram) => (a.sort_order || 0) - (b.sort_order || 0)
        );

        const periodMonth = month || sorted[0]?.program_month;
        const periodYear = year || sorted[0]?.program_year;

        setPrograms(sorted);

        if (periodMonth && periodYear) {
          const newPeriod = { month: periodMonth, year: periodYear };
          currentPeriodRef.current = newPeriod;
          setCurrentPeriod(newPeriod);
          await loadProgramMeta(periodMonth, periodYear);
        } else {
          setProgramMeta(null);
          onMetaLoadedRef.current?.(null);
        }

        setSelectedProgram((previous) => findMatchingProgram(sorted, previous));
      } catch (error) {
        console.error('Error loading programs:', error);
        setPrograms([]);
        setSelectedProgram(null);
      } finally {
        const elapsed = Date.now() - startTime;
        if (elapsed < MIN_LOADING_TIME) {
          await new Promise((resolve) => setTimeout(resolve, MIN_LOADING_TIME - elapsed));
        }
        setProgramsLoading(false);
      }
    },
    [loadPeriods, loadProgramMeta]
  );

  useEffect(() => {
    loadPrograms();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const onRefresh = useCallback(async () => {
    setRefreshing(true);
    try {
      await loadPrograms(currentPeriod?.month, currentPeriod?.year);
    } finally {
      setRefreshing(false);
    }
  }, [loadPrograms, currentPeriod]);

  const handlePeriodSelect = useCallback(
    async (month: number, year: number) => {
      setShowPeriodSelector(false);
      await loadPrograms(month, year);
    },
    [loadPrograms]
  );

  const selectProgram = useCallback((program: VehicleProgram) => {
    setSelectedProgram(program);
  }, []);

  const clearSelection = useCallback(() => {
    setSelectedProgram(null);
  }, []);

  return {
    programs,
    filteredPrograms,
    selectedProgram,
    setSelectedProgram,
    selectProgram,
    clearSelection,

    selectedYear,
    setSelectedYear,
    selectedBrand,
    setSelectedBrand,
    years,
    brands,

    currentPeriod,
    availablePeriods,
    showPeriodSelector,
    setShowPeriodSelector,
    handlePeriodSelect,
    programMeta,

    programsLoading,
    setProgramsLoading,
    refreshing,
    onRefresh,
    loadPrograms,
  };
}
