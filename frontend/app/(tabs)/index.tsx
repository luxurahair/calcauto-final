import React from 'react';
import {
  View, Text, ScrollView, TouchableOpacity, TextInput,
  ActivityIndicator, RefreshControl, Platform, KeyboardAvoidingView,
  Modal, Alert, Dimensions,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';

// Components
import { AnimatedSplashScreen } from '../../components/AnimatedSplashScreen';
import { LanguageSelector } from '../../components/LanguageSelector';
import { LoadingBorderAnimation } from '../../components/LoadingBorderAnimation';
import { EventBanner } from '../../components/EventBanner';
import { styles, loadingStyles } from './styles/homeStyles';
// Calculator hook & utilities
import {
  useCalculatorPage,
  monthNames,
  FINANCE_TERMS, LEASE_TERMS, LEASE_KM_OPTIONS,
  frequencyLabels,
} from '../../features/calculator';
import { getRateForTerm, formatCurrency, formatCurrencyDecimal } from '../../hooks/useCalculator';
import { findResidualVehicle } from '../../utils/leaseCalculator';

export default function HomeScreen() {
  // All state, effects, and callbacks are in the hook
  const {
    lang, t, handleLanguageChange, router,
    programs, filteredPrograms, selectedProgram, selectProgram, clearSelection,
    programsLoading, setProgramsLoading, refreshing, onRefresh, loadPrograms,
    showSplash, setShowSplash,
    selectedYear, setSelectedYear, selectedBrand, setSelectedBrand, years, brands,
    currentPeriod, availablePeriods, showPeriodSelector, setShowPeriodSelector,
    handlePeriodSelect, programMeta,
    loyaltyChecked, setLoyaltyChecked, deferredPayment, setDeferredPayment,
    selectedTerm, setSelectedTerm, paymentFrequency, setPaymentFrequency,
    selectedOption, setSelectedOption,
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
    inventoryList, selectedInventory, setSelectedInventory, selectInventoryVehicle, clearInventorySelection,
    manualVin, setManualVin, autoFinancing, setAutoFinancing,
    showLease, setShowLease, leaseKmPerYear, setLeaseKmPerYear,
    leaseTerm, setLeaseTerm, leaseResiduals, leaseRates,
    leaseResult, leasePdsf, setLeasePdsf,
    leaseSoldeReporte, setLeaseSoldeReporte,
    bestLeaseOption, leaseAnalysisGrid,
    localResult, activeLoyaltyRate,
    handleLogout, handleShareSMS, handleSendSms, handlePrint, handleExportExcel,
    handleSendEmail,
    showImportModal, setShowImportModal, importPassword, setImportPassword, handleImportConfirm,
    showEmailModal, setShowEmailModal, clientEmail, setClientEmail,
    clientName, setClientName, clientPhone, setClientPhone, sendingEmail,
    showSmsPreview, setShowSmsPreview, smsPreviewText, setSmsPreviewText,
    params,
  } = useCalculatorPage();

  // Constants used in JSX
  const availableTerms = FINANCE_TERMS;
  const leaseTerms = LEASE_TERMS;
  const leaseKmOptions = LEASE_KM_OPTIONS;

  // Handle year/brand filter press
  const handleYearPress = (year: number | null) => setSelectedYear(year);
  const handleBrandPress = (brand: string | null) => setSelectedBrand(brand);

  // Filter button component
  const FilterButton = ({ active, onPress, label }: { active: boolean; onPress: () => void; label: string }) => (
    <TouchableOpacity
      style={[styles.filterChip, active && styles.filterChipActive]}
      onPress={onPress}
      activeOpacity={0.7}
    >
      <Text style={[styles.filterChipText, active && styles.filterChipTextActive]}>
        {label}
      </Text>
    </TouchableOpacity>
  );


  return (
    <SafeAreaView style={styles.container}>
      {/* Animated Splash Screen */}
      <AnimatedSplashScreen 
        visible={showSplash} 
        onFinish={() => setShowSplash(false)} 
      />
      
      {/* Loading Animation */}
      <LoadingBorderAnimation loading={programsLoading && !showSplash} />
      
      <KeyboardAvoidingView
        style={styles.flex}
        behavior={Platform.OS === 'ios' ? 'padding' : 'height'}
      >
        {/* Header */}
        <View style={styles.header}>
          <View style={{flex: 1}}>
            <Text style={styles.headerTitle}>{t.title}</Text>
            <TouchableOpacity 
              style={{flexDirection: 'row', alignItems: 'center', backgroundColor: '#2d2d44', paddingHorizontal: 12, paddingVertical: 6, borderRadius: 20, marginTop: 4}}
              onPress={() => setShowPeriodSelector(true)}
            >
              <Ionicons name="calendar-outline" size={14} color="#4ECDC4" />
              <Text style={{color: '#4ECDC4', fontSize: 13, fontWeight: '600', marginLeft: 6}}>
                {currentPeriod ? `${monthNames[lang][currentPeriod.month]} ${currentPeriod.year}` : 'Période'}
              </Text>
              <Ionicons name="chevron-down" size={14} color="#4ECDC4" style={{marginLeft: 4}} />
            </TouchableOpacity>
          </View>
          <View style={styles.headerActions}>
            <LanguageSelector
              currentLanguage={lang}
              onLanguageChange={handleLanguageChange}
            />
            <TouchableOpacity
              style={styles.importButton}
              onPress={() => setShowImportModal(true)}
            >
              <Ionicons name="cloud-upload-outline" size={20} color="#fff" />
            </TouchableOpacity>
            <TouchableOpacity
              style={[styles.importButton, {backgroundColor: '#e74c3c', marginLeft: 8}]}
              onPress={handleLogout}
            >
              <Ionicons name="log-out-outline" size={20} color="#fff" />
            </TouchableOpacity>
          </View>
        </View>
        
        {/* Period Selector Modal */}
        <Modal
          visible={showPeriodSelector}
          transparent
          animationType="fade"
          onRequestClose={() => setShowPeriodSelector(false)}
        >
          <View style={styles.modalOverlay}>
            <View style={styles.periodModal}>
              <View style={styles.periodModalHeader}>
                <Text style={styles.periodModalTitle}>
                  {lang === 'fr' ? 'Choisir la période' : 'Select Period'}
                </Text>
                <TouchableOpacity onPress={() => setShowPeriodSelector(false)}>
                  <Ionicons name="close" size={24} color="#fff" />
                </TouchableOpacity>
              </View>
              <ScrollView style={styles.periodList}>
                {availablePeriods.map((period, index) => (
                  <TouchableOpacity
                    key={`${period.month}-${period.year}`}
                    style={[
                      styles.periodItem,
                      currentPeriod?.month === period.month && currentPeriod?.year === period.year && styles.periodItemActive
                    ]}
                    onPress={() => {
                      setProgramsLoading(true);
                      loadPrograms(period.month, period.year);
                      setShowPeriodSelector(false);
                    }}
                  >
                    <Text style={[
                      styles.periodItemText,
                      currentPeriod?.month === period.month && currentPeriod?.year === period.year && styles.periodItemTextActive
                    ]}>
                      {monthNames[lang][period.month]} {period.year}
                    </Text>
                    <Text style={styles.periodItemCount}>
                      {period.count} {lang === 'fr' ? 'véhicules' : 'vehicles'}
                    </Text>
                  </TouchableOpacity>
                ))}
              </ScrollView>
            </View>
          </View>
        </Modal>

        <ScrollView
          style={styles.scrollView}
          contentContainerStyle={styles.scrollContent}
          refreshControl={
            <RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor="#4ECDC4" />
          }
          keyboardShouldPersistTaps="handled"
        >
          {/* Event Banner - Dynamic from PDF cover page */}
          {programMeta && programMeta.event_names?.length > 0 && programMeta.event_names[0] && (
            <EventBanner
              meta={programMeta}
              lang={lang}
              loyaltyChecked={loyaltyChecked}
              onToggleLoyalty={() => setLoyaltyChecked(prev => !prev)}
              deferredChecked={deferredPayment}
              onToggleDeferred={() => setDeferredPayment(prev => !prev)}
              selectedTerm={selectedTerm}
            />
          )}

          {/* Year Filter */}
          <View style={styles.filterSection}>
            <Text style={styles.filterLabel}>{t.filters.year}</Text>
            <ScrollView horizontal showsHorizontalScrollIndicator={false} style={styles.filterScroll}>
              <View style={styles.filterRow}>
                <FilterButton 
                  active={selectedYear === null} 
                  onPress={() => handleYearPress(null)} 
                  label={t.filters.all} 
                />
                {years.map(year => (
                  <FilterButton 
                    key={year}
                    active={selectedYear === year} 
                    onPress={() => handleYearPress(year)} 
                    label={String(year)} 
                  />
                ))}
              </View>
            </ScrollView>
          </View>

          {/* Brand Filter */}
          <View style={styles.filterSection}>
            <Text style={styles.filterLabel}>{t.filters.brand}</Text>
            <ScrollView horizontal showsHorizontalScrollIndicator={false} style={styles.filterScroll}>
              <View style={styles.filterRow}>
                <FilterButton 
                  active={selectedBrand === null} 
                  onPress={() => handleBrandPress(null)} 
                  label={t.filters.all} 
                />
                {brands.map(brand => (
                  <FilterButton 
                    key={brand}
                    active={selectedBrand === brand} 
                    onPress={() => handleBrandPress(brand)} 
                    label={brand} 
                  />
                ))}
              </View>
            </ScrollView>
          </View>

          {/* Vehicle Selection */}
          <View style={styles.section}>
            <Text style={styles.sectionTitle}>
              {t.vehicle.selectVehicle} ({filteredPrograms.length})
            </Text>
            {programsLoading ? (
              <View style={styles.loadingContainer}>
                <ActivityIndicator size="small" color="#4ECDC4" />
                <Text style={styles.loadingText}>{t.loadingPrograms}</Text>
              </View>
            ) : filteredPrograms.length === 0 ? (
              <Text style={styles.noDataText}>{t.vehicle.noPrograms}</Text>
            ) : (
              <ScrollView horizontal showsHorizontalScrollIndicator={false} style={styles.programsScroll}>
                {filteredPrograms.map((program) => (
                  <TouchableOpacity
                    key={program.id}
                    style={[
                      styles.programCard,
                      selectedProgram?.id === program.id && styles.programCardSelected,
                    ]}
                    onPress={() => selectProgram(program)}
                    activeOpacity={0.7}
                  >
                    <View style={styles.programHeader}>
                      <Text style={styles.programBrand}>{program.brand}</Text>
                      <Text style={styles.programYear}>{program.year}</Text>
                    </View>
                    <Text style={styles.programModel}>{program.model}</Text>
                    {program.trim && (
                      <Text style={styles.programTrim} numberOfLines={2}>{program.trim}</Text>
                    )}
                    <View style={styles.badgeRow}>
                      {program.consumer_cash > 0 && (
                        <View style={styles.cashBadge}>
                          <Text style={styles.cashBadgeText}>
                            {formatCurrency(program.consumer_cash)}
                          </Text>
                        </View>
                      )}
                      {program.bonus_cash > 0 && (
                        <View style={styles.bonusBadge}>
                          <Text style={styles.bonusBadgeText}>
                            +{formatCurrency(program.bonus_cash)}
                          </Text>
                        </View>
                      )}
                    </View>
                    {program.option2_rates && (
                      <View style={styles.option2Badge}>
                        <Text style={styles.option2BadgeText}>
                          {program.option2_rates.rate_36}%
                        </Text>
                      </View>
                    )}
                  </TouchableOpacity>
                ))}
              </ScrollView>
            )}

            {selectedProgram && (
              <View style={styles.selectedInfo}>
                <View style={styles.selectedHeader}>
                  <View style={styles.selectedTitleContainer}>
                    <Text style={styles.selectedBrand}>{selectedProgram.brand}</Text>
                    <Text style={styles.selectedTitle}>
                      {selectedProgram.model} {selectedProgram.year}
                    </Text>
                    {selectedProgram.trim && (
                      <Text style={styles.selectedTrim}>{selectedProgram.trim}</Text>
                    )}
                  </View>
                  <TouchableOpacity onPress={clearSelection} hitSlop={{top: 10, bottom: 10, left: 10, right: 10}}>
                    <Ionicons name="close-circle" size={28} color="#FF6B6B" />
                  </TouchableOpacity>
                </View>
                
                {/* Rates table by term */}
                <View style={styles.ratesTable}>
                  <View style={styles.ratesHeader}>
                    <Text style={styles.ratesHeaderCell}>{t.term.selectTerm}</Text>
                    <Text style={styles.ratesHeaderCell}>{t.options.option1}</Text>
                    {selectedProgram.option2_rates && (
                      <Text style={styles.ratesHeaderCell}>{t.options.option2}</Text>
                    )}
                  </View>
                  {availableTerms.map(term => (
                    <TouchableOpacity 
                      key={term} 
                      style={[
                        styles.ratesRow,
                        selectedTerm === term && styles.ratesRowSelected
                      ]}
                      onPress={() => setSelectedTerm(term)}
                    >
                      <Text style={[styles.ratesCell, selectedTerm === term && styles.ratesCellSelected]}>
                        {term} {t.term.months}
                      </Text>
                      <Text style={[styles.ratesCell, styles.ratesCellOption1, selectedTerm === term && styles.ratesCellSelected]}>
                        {getRateForTerm(selectedProgram.option1_rates, term)}%
                      </Text>
                      {selectedProgram.option2_rates && (
                        <Text style={[styles.ratesCell, styles.ratesCellOption2, selectedTerm === term && styles.ratesCellSelected]}>
                          {getRateForTerm(selectedProgram.option2_rates, term)}%
                        </Text>
                      )}
                    </TouchableOpacity>
                  ))}
                </View>

                {/* Rebates summary */}
                <View style={styles.rebatesSummary}>
                  {selectedProgram.consumer_cash > 0 && (
                    <View style={styles.rebateItem}>
                      <Text style={styles.rebateLabel}>{t.results.rebate} Opt.1 ({t.results.beforeTax}):</Text>
                      <Text style={styles.rebateValue}>{formatCurrency(selectedProgram.consumer_cash)}</Text>
                    </View>
                  )}
                  {selectedProgram.alternative_consumer_cash > 0 && (
                    <View style={styles.rebateItem}>
                      <Text style={styles.rebateLabel}>{t.results.rebate} Opt.2 ({t.results.beforeTax}):</Text>
                      <Text style={styles.rebateValue}>{formatCurrency(selectedProgram.alternative_consumer_cash)}</Text>
                    </View>
                  )}
                  {selectedProgram.bonus_cash > 0 && (
                    <View style={styles.rebateItem}>
                      <Ionicons name="gift-outline" size={14} color="#FFD700" />
                      <Text style={styles.rebateLabelBonus}>{t.results.bonusCash} ({t.results.afterTax}):</Text>
                      <Text style={styles.rebateValueBonus}>{formatCurrency(selectedProgram.bonus_cash)}</Text>
                    </View>
                  )}
                </View>
              </View>
            )}
            
            {/* Section Accessoires */}
            <View style={styles.section}>
              <View style={styles.sectionHeader}>
                <Ionicons name="add-circle-outline" size={20} color="#4CAF50" />
                <Text style={styles.sectionTitle}>
                  {lang === 'fr' ? 'Accessoires' : 'Accessories'}
                </Text>
              </View>
              
              {accessories.map((acc, index) => (
                <View key={index} style={styles.accessoryRow}>
                  <TextInput
                    style={[styles.input, styles.accessoryDescInput]}
                    placeholder={lang === 'fr' ? 'Description' : 'Description'}
                    placeholderTextColor="#666"
                    value={acc.description}
                    onChangeText={(text) => {
                      const newAcc = [...accessories];
                      newAcc[index].description = text;
                      setAccessories(newAcc);
                    }}
                  />
                  <TextInput
                    style={[styles.input, styles.accessoryPriceInput]}
                    placeholder="$"
                    placeholderTextColor="#666"
                    keyboardType="numeric"
                    value={acc.price}
                    onChangeText={(text) => {
                      const newAcc = [...accessories];
                      newAcc[index].price = text;
                      setAccessories(newAcc);
                    }}
                  />
                  <TouchableOpacity
                    style={styles.removeAccessoryBtn}
                    onPress={() => {
                      const newAcc = accessories.filter((_, i) => i !== index);
                      setAccessories(newAcc);
                    }}
                  >
                    <Ionicons name="close-circle" size={24} color="#FF5252" />
                  </TouchableOpacity>
                </View>
              ))}
              
              <TouchableOpacity
                style={styles.addAccessoryBtn}
                onPress={() => setAccessories([...accessories, { description: '', price: '' }])}
              >
                <Ionicons name="add" size={20} color="#4CAF50" />
                <Text style={styles.addAccessoryText}>
                  {lang === 'fr' ? 'Ajouter un accessoire' : 'Add accessory'}
                </Text>
              </TouchableOpacity>
              
              {accessories.length > 0 && (
                <View style={styles.accessoriesTotalRow}>
                  <Text style={styles.accessoriesTotalLabel}>
                    {lang === 'fr' ? 'Total accessoires:' : 'Total accessories:'}
                  </Text>
                  <Text style={styles.accessoriesTotalValue}>
                    {formatCurrency(accessories.reduce((sum, acc) => sum + (parseFloat(acc.price) || 0), 0))}
                  </Text>
                </View>
              )}
            </View>
          </View>

          {/* Inventory Selection - Filtered by selected brand */}
          {selectedProgram && (
            <View style={styles.section}>
              <Text style={styles.sectionTitle}>
                {lang === 'fr' ? '📦 Inventaire disponible' : '📦 Available Inventory'} ({inventoryList.filter(v => v.brand?.toLowerCase() === selectedProgram.brand?.toLowerCase() && String(v.year) === String(selectedProgram.year) && v.model?.toLowerCase() === selectedProgram.model?.toLowerCase()).length})
              </Text>
              <Text style={styles.inventorySubtitle}>
                {lang === 'fr' 
                  ? `${selectedProgram.brand} ${selectedProgram.model} ${selectedProgram.year} en stock`
                  : `${selectedProgram.brand} ${selectedProgram.model} ${selectedProgram.year} in stock`}
              </Text>
              {inventoryList.length > 0 ? (
                <ScrollView horizontal showsHorizontalScrollIndicator={false} style={styles.inventoryScroll}>
                  {inventoryList
                    .filter(v => v.brand?.toLowerCase() === selectedProgram.brand?.toLowerCase() && String(v.year) === String(selectedProgram.year) && v.model?.toLowerCase() === selectedProgram.model?.toLowerCase())
                    .map((vehicle) => (
                      <TouchableOpacity
                        key={vehicle.id}
                        style={[
                          styles.inventoryCard,
                          selectedInventory?.id === vehicle.id && styles.inventoryCardSelected
                        ]}
                        onPress={() => {
                          setSelectedInventory(vehicle);
                          setManualVin('');  // Clear manual VIN when selecting from inventory
                          setVehiclePrice(String(vehicle.asking_price || vehicle.msrp || ''));
                        }}
                      >
                        <Text style={styles.inventoryStock}>#{vehicle.stock_no}</Text>
                        <Text style={styles.inventoryModel}>
                          {vehicle.year} {vehicle.model}
                        </Text>
                        <Text style={styles.inventoryTrim}>{vehicle.trim}</Text>
                        {vehicle.vin && (
                          <Text style={styles.inventoryVin}>VIN: {vehicle.vin}</Text>
                        )}
                        <Text style={styles.inventoryPrice}>
                          {formatCurrency(vehicle.asking_price || vehicle.msrp)}
                        </Text>
                        {vehicle.net_cost && (
                          <Text style={styles.inventoryProfit}>
                            Profit: {formatCurrency((vehicle.asking_price || vehicle.msrp) - vehicle.net_cost)}
                          </Text>
                        )}
                      </TouchableOpacity>
                    ))}
                  {inventoryList.filter(v => v.brand?.toLowerCase() === selectedProgram.brand?.toLowerCase() && String(v.year) === String(selectedProgram.year) && v.model?.toLowerCase() === selectedProgram.model?.toLowerCase()).length === 0 && (
                    <View style={styles.noInventoryContainer}>
                      <Text style={styles.noInventoryText}>
                        {lang === 'fr' 
                          ? `Aucun ${selectedProgram.brand} ${selectedProgram.model} ${selectedProgram.year} en inventaire`
                          : `No ${selectedProgram.brand} ${selectedProgram.model} ${selectedProgram.year} vehicles in inventory`}
                      </Text>
                      <View style={styles.manualVinContainer}>
                        <Text style={styles.manualVinLabel}>
                          {lang === 'fr' ? 'VIN manuel (optionnel):' : 'Manual VIN (optional):'}
                        </Text>
                        <TextInput
                          style={styles.manualVinInput}
                          value={manualVin}
                          onChangeText={(text) => setManualVin(text.toUpperCase().replace(/[^A-Z0-9]/g, ''))}
                          placeholder="Ex: 1C4RJKBG5S8806267"
                          placeholderTextColor="#666"
                          maxLength={17}
                          autoCapitalize="characters"
                        />
                        {manualVin.length > 0 && manualVin.length !== 17 && (
                          <Text style={styles.manualVinError}>
                            {lang === 'fr' ? `${manualVin.length}/17 caractères` : `${manualVin.length}/17 characters`}
                          </Text>
                        )}
                        {manualVin.length === 17 && (
                          <Text style={styles.manualVinSuccess}>
                            ✓ {lang === 'fr' ? 'VIN valide - Window Sticker sera inclus' : 'Valid VIN - Window Sticker will be included'}
                          </Text>
                        )}
                      </View>
                    </View>
                  )}
                </ScrollView>
              ) : (
                <Text style={styles.noInventoryText}>
                  {lang === 'fr' ? 'Chargement de l\'inventaire...' : 'Loading inventory...'}
                </Text>
              )}
            </View>
          )}

          {/* Price Input and Calculation */}
          {selectedProgram && (
            <View style={styles.section}>
              <Text style={styles.sectionTitle}>{t.vehicle.vehiclePrice}</Text>
              
              {/* Selected inventory info */}
              {selectedInventory && (
                <View style={styles.selectedInventoryBanner}>
                  <View style={styles.selectedInventoryInfo}>
                    <Ionicons name="car-sport" size={20} color="#4ECDC4" />
                    <Text style={styles.selectedInventoryText}>
                      Stock #{selectedInventory.stock_no} - {selectedInventory.year} {selectedInventory.brand} {selectedInventory.model} {selectedInventory.trim}
                    </Text>
                  </View>
                  {selectedInventory.vin && (
                    <Text style={styles.selectedInventoryVin}>VIN: {selectedInventory.vin}</Text>
                  )}
                  <TouchableOpacity onPress={() => { setSelectedInventory(null); setVehiclePrice(''); setAutoFinancing(null); }}>
                    <Ionicons name="close-circle" size={22} color="#FF6B6B" />
                  </TouchableOpacity>
                </View>
              )}
              
              {/* Promotions automatiques détectées */}
              {autoFinancing && (selectedInventory || selectedProgram) && (
                <View style={styles.autoFinancingBanner}>
                  <View style={styles.autoFinancingHeader}>
                    <Ionicons name="flash" size={18} color="#FFD700" />
                    <Text style={styles.autoFinancingTitle}>
                      {lang === 'fr' ? 'Promotions détectées automatiquement' : 'Auto-detected Promotions'}
                    </Text>
                  </View>
                  <View style={styles.autoFinancingContent}>
                    {autoFinancing.consumer_cash > 0 && (
                      <View style={styles.autoFinancingItem}>
                        <Text style={styles.autoFinancingLabel}>Consumer Cash:</Text>
                        <Text style={styles.autoFinancingValue}>{formatCurrency(autoFinancing.consumer_cash)}</Text>
                      </View>
                    )}
                    {autoFinancing.bonus_cash > 0 && (
                      <View style={styles.autoFinancingItem}>
                        <Text style={styles.autoFinancingLabel}>Bonus Cash:</Text>
                        <Text style={styles.autoFinancingValueBonus}>+{formatCurrency(autoFinancing.bonus_cash)}</Text>
                      </View>
                    )}
                    {(autoFinancing.consumer_cash > 0 || autoFinancing.bonus_cash > 0) && (
                      <View style={styles.autoFinancingItem}>
                        <Text style={styles.autoFinancingLabelTotal}>
                          {lang === 'fr' ? 'Total rabais:' : 'Total rebates:'}
                        </Text>
                        <Text style={styles.autoFinancingValueTotal}>
                          {formatCurrency(autoFinancing.consumer_cash + autoFinancing.bonus_cash)}
                        </Text>
                      </View>
                    )}
                    {autoFinancing.option2_rates && Object.values(autoFinancing.option2_rates).some(v => v !== null && v < 5) && (
                      <View style={styles.autoFinancingItem}>
                        <Text style={styles.autoFinancingLabel}>Option 2:</Text>
                        <Text style={styles.autoFinancingValueRate}>
                          {lang === 'fr' ? 'Taux réduits disponibles' : 'Reduced rates available'}
                        </Text>
                      </View>
                    )}
                  </View>
                  {autoFinancing.programme_source && (
                    <Text style={styles.autoFinancingSource}>
                      Source: {autoFinancing.programme_source}
                    </Text>
                  )}
                </View>
              )}
              
              {/* Prix du véhicule */}
              <View style={styles.inputRow}>
                <Text style={styles.inputLabel}>{t.vehicle.vehiclePrice}</Text>
                <View style={styles.inputContainer}>
                  <Text style={styles.currencySymbol}>$</Text>
                  <TextInput
                    style={styles.priceInput}
                    placeholder="55000"
                    placeholderTextColor="#666"
                    keyboardType="numeric"
                    value={vehiclePrice}
                    onChangeText={setVehiclePrice}
                  />
                </View>
              </View>

              {/* Rabais concessionnaire (partagé financement + location) */}
              <View style={styles.inputRow}>
                <Text style={styles.inputLabel}>{lang === 'fr' ? 'Rabais concess.' : 'Dealer discount'}</Text>
                <View style={styles.inputContainer}>
                  <Text style={styles.currencySymbol}>$</Text>
                  <TextInput
                    style={styles.priceInput}
                    placeholder="0"
                    placeholderTextColor="#666"
                    keyboardType="numeric"
                    value={leaseRabaisConcess}
                    onChangeText={setLeaseRabaisConcess}
                    data-testid="rabais-concess-input"
                  />
                </View>
              </View>
              
              {/* Bonus Cash optionnel */}
              <View style={styles.inputRow}>
                <Text style={styles.inputLabel}>{t.results.bonusCash} ({t.results.afterTax})</Text>
                <View style={styles.inputContainer}>
                  <Text style={styles.currencySymbol}>$</Text>
                  <TextInput
                    style={styles.priceInput}
                    placeholder={String(selectedProgram.bonus_cash || 0)}
                    placeholderTextColor="#666"
                    keyboardType="numeric"
                    value={customBonusCash}
                    onChangeText={setCustomBonusCash}
                  />
                </View>
              </View>

              {/* Comptant (tx inclus) */}
              <View style={styles.inputRow}>
                <Text style={styles.inputLabel}>{lang === 'fr' ? 'Comptant (tx inclus)' : 'Cash Down (tax incl.)'}</Text>
                <View style={styles.inputContainer}>
                  <Text style={styles.currencySymbol}>$</Text>
                  <TextInput
                    style={styles.priceInput}
                    placeholder="0"
                    placeholderTextColor="#666"
                    keyboardType="numeric"
                    value={comptantTxInclus}
                    onChangeText={setComptantTxInclus}
                  />
                </View>
              </View>

              {/* Frais additionnels (taxables) */}
              <View style={styles.feesSection}>
                <Text style={styles.feesSectionTitle}>{t.fees.title}</Text>
                <View style={styles.feesRow}>
                  <View style={styles.feeField}>
                    <Text style={styles.feeLabel}>{t.fees.dossier}</Text>
                    <View style={styles.feeInputContainer}>
                      <Text style={styles.feeSymbol}>$</Text>
                      <TextInput
                        style={styles.feeInput}
                        placeholder="259.95"
                        placeholderTextColor="#666"
                        keyboardType="decimal-pad"
                        value={fraisDossier}
                        onChangeText={setFraisDossier}
                      />
                    </View>
                  </View>
                  <View style={styles.feeField}>
                    <Text style={styles.feeLabel}>{t.fees.tires}</Text>
                    <View style={styles.feeInputContainer}>
                      <Text style={styles.feeSymbol}>$</Text>
                      <TextInput
                        style={styles.feeInput}
                        placeholder="15"
                        placeholderTextColor="#666"
                        keyboardType="decimal-pad"
                        value={taxePneus}
                        onChangeText={setTaxePneus}
                      />
                    </View>
                  </View>
                  <View style={styles.feeField}>
                    <Text style={styles.feeLabel}>{t.fees.rdprm}</Text>
                    <View style={styles.feeInputContainer}>
                      <Text style={styles.feeSymbol}>$</Text>
                      <TextInput
                        style={styles.feeInput}
                        placeholder="100"
                        placeholderTextColor="#666"
                        keyboardType="decimal-pad"
                        value={fraisRDPRM}
                        onChangeText={setFraisRDPRM}
                      />
                    </View>
                  </View>
                </View>
              </View>

              {/* Échange */}
              <View style={styles.feesSection}>
                <Text style={styles.feesSectionTitle}>{t.exchange.title}</Text>
                <View style={styles.exchangeRow}>
                  <View style={styles.exchangeField}>
                    <Text style={styles.feeLabel}>{t.exchange.value}</Text>
                    <View style={styles.feeInputContainer}>
                      <Text style={styles.feeSymbol}>$</Text>
                      <TextInput
                        style={styles.feeInput}
                        placeholder="0"
                        placeholderTextColor="#666"
                        keyboardType="numeric"
                        value={prixEchange}
                        onChangeText={setPrixEchange}
                      />
                    </View>
                    <Text style={styles.feeNote}>{t.exchange.reducesAmount}</Text>
                  </View>
                  <View style={styles.exchangeField}>
                    <Text style={styles.feeLabel}>{t.exchange.owed}</Text>
                    <View style={styles.feeInputContainer}>
                      <Text style={styles.feeSymbol}>$</Text>
                      <TextInput
                        style={styles.feeInput}
                        placeholder="0"
                        placeholderTextColor="#666"
                        keyboardType="numeric"
                        value={montantDuEchange}
                        onChangeText={setMontantDuEchange}
                      />
                    </View>
                    <Text style={styles.feeNote}>{t.exchange.addedToFinancing}</Text>
                  </View>
                </View>
              </View>

              {/* Sélection du terme */}
              <View style={styles.termSection}>
                <Text style={styles.inputLabel}>{t.term.selectTerm}</Text>
                <View style={styles.termButtons}>
                  {availableTerms.map(term => (
                    <TouchableOpacity
                      key={term}
                      style={[
                        styles.termButton,
                        selectedTerm === term && styles.termButtonActive
                      ]}
                      onPress={() => setSelectedTerm(term)}
                    >
                      <Text style={[
                        styles.termButtonText,
                        selectedTerm === term && styles.termButtonTextActive
                      ]}>
                        {term} {t.term.months}
                      </Text>
                    </TouchableOpacity>
                  ))}
                </View>
              </View>

              {/* Fréquence de paiement */}
              <View style={styles.termSection}>
                <Text style={styles.inputLabel}>{t.frequency.title}</Text>
                <View style={styles.frequencyButtons}>
                  <TouchableOpacity
                    style={[
                      styles.frequencyButton,
                      paymentFrequency === 'monthly' && styles.frequencyButtonActive
                    ]}
                    onPress={() => setPaymentFrequency('monthly')}
                  >
                    <Text style={[
                      styles.frequencyButtonText,
                      paymentFrequency === 'monthly' && styles.frequencyButtonTextActive
                    ]}>
                      {frequencyLabels.monthly[lang]}
                    </Text>
                  </TouchableOpacity>
                  <TouchableOpacity
                    style={[
                      styles.frequencyButton,
                      paymentFrequency === 'biweekly' && styles.frequencyButtonActive
                    ]}
                    onPress={() => setPaymentFrequency('biweekly')}
                  >
                    <Text style={[
                      styles.frequencyButtonText,
                      paymentFrequency === 'biweekly' && styles.frequencyButtonTextActive
                    ]}>
                      {frequencyLabels.biweekly[lang]}
                    </Text>
                  </TouchableOpacity>
                  <TouchableOpacity
                    style={[
                      styles.frequencyButton,
                      paymentFrequency === 'weekly' && styles.frequencyButtonActive
                    ]}
                    onPress={() => setPaymentFrequency('weekly')}
                  >
                    <Text style={[
                      styles.frequencyButtonText,
                      paymentFrequency === 'weekly' && styles.frequencyButtonTextActive
                    ]}>
                      {frequencyLabels.weekly[lang]}
                    </Text>
                  </TouchableOpacity>
                </View>
              </View>

              {/* Sélection de l'option */}
              <View style={styles.termSection}>
                <Text style={styles.inputLabel}>{t.options.chooseOption}</Text>
                <View style={styles.optionButtons}>
                  <TouchableOpacity
                    style={[
                      styles.optionButton,
                      styles.optionButton1,
                      selectedOption === '1' && styles.optionButtonActive1
                    ]}
                    onPress={() => setSelectedOption(selectedOption === '1' ? null : '1')}
                  >
                    <Text style={[
                      styles.optionButtonText,
                      selectedOption === '1' && styles.optionButtonTextActive
                    ]}>
                      {t.options.option1}
                    </Text>
                    <Text style={[
                      styles.optionButtonSubtext,
                      selectedOption === '1' && styles.optionButtonTextActive
                    ]}>
                      {selectedProgram.consumer_cash > 0 ? formatCurrency(selectedProgram.consumer_cash) : '$0'} + {localResult?.option1Rate || getRateForTerm(selectedProgram.option1_rates, selectedTerm)}%
                    </Text>
                  </TouchableOpacity>
                  
                  {selectedProgram.option2_rates ? (
                    <TouchableOpacity
                      style={[
                        styles.optionButton,
                        styles.optionButton2,
                        selectedOption === '2' && styles.optionButtonActive2
                      ]}
                      onPress={() => setSelectedOption(selectedOption === '2' ? null : '2')}
                    >
                      <Text style={[
                        styles.optionButtonText,
                        selectedOption === '2' && styles.optionButtonTextActive
                      ]}>
                        {t.options.option2}
                      </Text>
                      <Text style={[
                        styles.optionButtonSubtext,
                        selectedOption === '2' && styles.optionButtonTextActive
                      ]}>
                        {selectedProgram.alternative_consumer_cash > 0 ? formatCurrency(selectedProgram.alternative_consumer_cash) : '$0'} + {localResult?.option2Rate || getRateForTerm(selectedProgram.option2_rates, selectedTerm)}%
                      </Text>
                    </TouchableOpacity>
                  ) : (
                    <View style={[styles.optionButton, styles.optionButtonDisabled]}>
                      <Text style={styles.optionButtonTextDisabled}>{t.options.option2}</Text>
                      <Text style={styles.optionButtonTextDisabled}>{t.options.notAvailable}</Text>
                    </View>
                  )}
                </View>
              </View>
            </View>
          )}

          {/* Results - Real-time calculation */}
          {selectedProgram && localResult && vehiclePrice && (
            <View style={styles.section}>
              <Text style={styles.sectionTitle}>
                {t.results.title} - {selectedTerm} {t.term.months}
              </Text>
              
              {/* Summary */}
              <View style={styles.resultsSummary}>
                <Text style={styles.summaryTitle}>
                  {selectedProgram.brand} {selectedProgram.model} {selectedProgram.trim || ''} {selectedProgram.year}
                </Text>
                <Text style={styles.summaryPrice}>
                  {formatCurrency(parseFloat(vehiclePrice))}
                </Text>
              </View>

              {/* Best Option Banner */}
              {localResult.bestOption && (
                <View style={[
                  styles.bestOptionBanner,
                  localResult.bestOption === '1' ? styles.bestOptionBanner1 : styles.bestOptionBanner2
                ]}>
                  <Ionicons name="trophy" size={20} color="#1a1a2e" />
                  <Text style={styles.bestOptionText}>
                    {localResult.bestOption === '1' ? t.options.option1 : t.options.option2} = {t.results.bestChoice}
                  </Text>
                  {localResult.savings > 0 && (
                    <Text style={styles.bestOptionSavings}>
                      {t.results.savings}: {formatCurrency(localResult.savings)}
                    </Text>
                  )}
                </View>
              )}

              {/* Options comparison */}
              <View style={styles.optionsGrid}>
                {/* Option 1 */}
                <View style={[
                  styles.optionCard,
                  styles.optionCard1,
                  localResult.bestOption === '1' && styles.optionCardBest
                ]}>
                  <View style={styles.optionHeader}>
                    <Text style={styles.optionCardTitle}>{t.options.option1}</Text>
                    {localResult.bestOption === '1' && (
                      <Ionicons name="checkmark-circle" size={18} color="#4ECDC4" />
                    )}
                  </View>
                  <Text style={styles.optionSubtitle}>{t.options.option1Desc}</Text>
                  
                  {selectedProgram.consumer_cash > 0 && (
                    <View style={styles.optionDetail}>
                      <Text style={styles.optionDetailLabel}>{t.results.rebate}:</Text>
                      <Text style={styles.optionDetailValue}>{formatCurrency(selectedProgram.consumer_cash)}</Text>
                    </View>
                  )}
                  <View style={styles.optionDetail}>
                    <Text style={styles.optionDetailLabel}>{t.results.financedCapital}:</Text>
                    <Text style={styles.optionDetailValue}>{formatCurrency(localResult.principalOption1)}</Text>
                  </View>
                  <View style={styles.optionDetail}>
                    <Text style={styles.optionDetailLabel}>{t.results.rate}:</Text>
                    <Text style={styles.optionRateValue}>{localResult.option1Rate}%</Text>
                  </View>
                  <View style={styles.optionMainResult}>
                    <Text style={styles.optionMonthlyLabel}>
                      {paymentFrequency === 'monthly' ? 'Mensuel' : paymentFrequency === 'biweekly' ? 'Aux 2 sem.' : 'Hebdo'}
                    </Text>
                    <Text style={styles.optionMonthlyValue}>
                      {formatCurrencyDecimal(
                        paymentFrequency === 'monthly' ? localResult.option1Monthly :
                        paymentFrequency === 'biweekly' ? localResult.option1Biweekly :
                        localResult.option1Weekly
                      )}
                    </Text>
                  </View>
                  <View style={styles.optionDetail}>
                    <Text style={styles.optionDetailLabel}>{t.results.total} ({selectedTerm} {t.term.months}):</Text>
                    <Text style={styles.optionTotalValue}>{formatCurrency(localResult.option1Total)}</Text>
                  </View>
                </View>

                {/* Option 2 */}
                <View style={[
                  styles.optionCard,
                  styles.optionCard2,
                  localResult.bestOption === '2' && styles.optionCardBest
                ]}>
                  <View style={styles.optionHeader}>
                    <Text style={styles.optionCardTitle}>{t.options.option2}</Text>
                    {localResult.bestOption === '2' && (
                      <Ionicons name="checkmark-circle" size={18} color="#4ECDC4" />
                    )}
                  </View>
                  <Text style={styles.optionSubtitle}>{t.options.option2Desc}</Text>
                  
                  {localResult.option2Rate !== null ? (
                    <>
                      <View style={styles.optionDetail}>
                        <Text style={styles.optionDetailLabel}>{t.results.rebate}:</Text>
                        <Text style={styles.optionDetailValue}>{selectedProgram.alternative_consumer_cash > 0 ? formatCurrency(selectedProgram.alternative_consumer_cash) : '$0'}</Text>
                      </View>
                      <View style={styles.optionDetail}>
                        <Text style={styles.optionDetailLabel}>{t.results.financedCapital}:</Text>
                        <Text style={styles.optionDetailValue}>{formatCurrency(localResult.principalOption2)}</Text>
                      </View>
                      <View style={styles.optionDetail}>
                        <Text style={styles.optionDetailLabel}>{t.results.rate}:</Text>
                        <Text style={styles.optionRateValue}>{localResult.option2Rate}%</Text>
                      </View>
                      <View style={styles.optionMainResult}>
                        <Text style={styles.optionMonthlyLabel}>
                          {paymentFrequency === 'monthly' ? t.frequency.monthly : paymentFrequency === 'biweekly' ? t.frequency.biweekly : t.frequency.weekly}
                        </Text>
                        <Text style={styles.optionMonthlyValue}>
                          {formatCurrencyDecimal(
                            paymentFrequency === 'monthly' ? localResult.option2Monthly! :
                            paymentFrequency === 'biweekly' ? localResult.option2Biweekly! :
                            localResult.option2Weekly!
                          )}
                        </Text>
                      </View>
                      <View style={styles.optionDetail}>
                        <Text style={styles.optionDetailLabel}>{t.results.total} ({selectedTerm} {t.term.months}):</Text>
                        <Text style={styles.optionTotalValue}>{formatCurrency(localResult.option2Total!)}</Text>
                      </View>
                    </>
                  ) : (
                    <View style={styles.noOption}>
                      <Ionicons name="close-circle-outline" size={32} color="#666" />
                      <Text style={styles.noOptionText}>{t.options.notAvailable}</Text>
                      <Text style={styles.noOptionSubtext}>Non disponible pour ce véhicule</Text>
                    </View>
                  )}
                </View>
              </View>

              {/* Bonus Cash Note */}
              {(parseFloat(customBonusCash) > 0 || selectedProgram.bonus_cash > 0) && (
                <View style={styles.bonusCashNote}>
                  <Ionicons name="information-circle" size={16} color="#FFD700" />
                  <Text style={styles.bonusCashNoteText}>
                    {t.results.bonusCash} de {formatCurrency(parseFloat(customBonusCash) || selectedProgram.bonus_cash)} sera déduit après taxes (au comptant)
                  </Text>
                </View>
              )}
              
              {/* Send by Email Button */}
              <TouchableOpacity
                style={styles.sendEmailButton}
                onPress={() => setShowEmailModal(true)}
                data-testid="send-email-btn"
              >
                <Ionicons name="mail-outline" size={20} color="#fff" />
                <Text style={styles.sendEmailButtonText}>
                  {lang === 'fr' ? 'Envoyer par email' : 'Send by email'}
                </Text>
              </TouchableOpacity>
              
              {/* Share Actions Row */}
              <View style={styles.shareActionsRow}>
                {/* Share via SMS Button */}
                <TouchableOpacity
                  style={styles.shareSmsButton}
                  onPress={handleShareSMS}
                  data-testid="share-sms-btn"
                >
                  <Ionicons name="chatbubble-outline" size={18} color="#fff" />
                  <Text style={styles.shareButtonText}>
                    {lang === 'fr' ? 'Texto' : 'SMS'}
                  </Text>
                </TouchableOpacity>
                
                {/* Print Button */}
                <TouchableOpacity
                  style={styles.printButton}
                  onPress={handlePrint}
                  data-testid="print-btn"
                >
                  <Ionicons name="print-outline" size={18} color="#fff" />
                  <Text style={styles.shareButtonText}>
                    {lang === 'fr' ? 'Imprimer' : 'Print'}
                  </Text>
                </TouchableOpacity>
                
                {/* Export Excel Button */}
                <TouchableOpacity
                  style={styles.exportExcelButton}
                  onPress={handleExportExcel}
                  data-testid="export-excel-btn"
                >
                  <Ionicons name="document-outline" size={18} color="#fff" />
                  <Text style={styles.shareButtonText}>
                    Excel
                  </Text>
                </TouchableOpacity>
              </View>
            </View>
          )}

          {/* ============ LOCATION SCI ============ */}
          {selectedProgram && vehiclePrice && (
            <View style={styles.section} data-testid="lease-section">
              {/* Toggle Lease */}
              <TouchableOpacity
                style={[styles.leaseToggle, showLease && styles.leaseToggleActive]}
                onPress={() => setShowLease(!showLease)}
                data-testid="lease-toggle-btn"
              >
                <Ionicons name="car-sport" size={20} color={showLease ? '#fff' : '#4ECDC4'} />
                <Text style={[styles.leaseToggleText, showLease && styles.leaseToggleTextActive]}>
                  {lang === 'fr' ? 'Location SCI' : 'SCI Lease'}
                </Text>
                <Ionicons name={showLease ? 'chevron-up' : 'chevron-down'} size={18} color={showLease ? '#fff' : '#4ECDC4'} />
              </TouchableOpacity>

              {showLease && (
                <View style={styles.leaseContent}>
                  {/* PDSF / PDOC */}
                  <View style={styles.leaseInputRow}>
                    <Text style={styles.leaseInputLabel}>{lang === 'fr' ? 'PDSF / PDOC' : 'MSRP'}</Text>
                    <TextInput
                      style={styles.leaseInput}
                      value={leasePdsf}
                      onChangeText={setLeasePdsf}
                      placeholder={vehiclePrice || '71580'}
                      placeholderTextColor="#555"
                      keyboardType="numeric"
                      data-testid="lease-pdsf-input"
                    />
                  </View>
                  
                  {/* Solde reporté */}
                  <View style={styles.leaseInputRow}>
                    <Text style={styles.leaseInputLabel}>{lang === 'fr' ? 'Solde reporté' : 'Carried balance'}</Text>
                    <TextInput
                      style={styles.leaseInput}
                      value={leaseSoldeReporte}
                      onChangeText={setLeaseSoldeReporte}
                      placeholder="0"
                      placeholderTextColor="#555"
                      keyboardType="numeric"
                      data-testid="lease-solde-input"
                    />
                    <Text style={styles.leaseInputHint}>{lang === 'fr' ? '(-) si dette' : '(-) if owed'}</Text>
                  </View>

                  {/* Km per year selection */}
                  <View style={styles.leaseRow}>
                    <Text style={styles.leaseLabel}>{lang === 'fr' ? 'Kilométrage / an' : 'Km / year'}</Text>
                    <View style={styles.leaseKmButtons}>
                      {leaseKmOptions.map(km => (
                        <TouchableOpacity
                          key={km}
                          style={[styles.leaseKmBtn, leaseKmPerYear === km && styles.leaseKmBtnActive]}
                          onPress={() => setLeaseKmPerYear(km)}
                          data-testid={`lease-km-${km}`}
                        >
                          <Text style={[styles.leaseKmBtnText, leaseKmPerYear === km && styles.leaseKmBtnTextActive]}>
                            {(km / 1000).toFixed(0)}k
                          </Text>
                        </TouchableOpacity>
                      ))}
                    </View>
                  </View>

                  {/* Lease term selection */}
                  <View style={styles.leaseRow}>
                    <Text style={styles.leaseLabel}>{lang === 'fr' ? 'Terme location' : 'Lease term'}</Text>
                    <ScrollView horizontal showsHorizontalScrollIndicator={false} style={styles.leaseTermScroll}>
                      {leaseTerms.map(t => (
                        <TouchableOpacity
                          key={t}
                          style={[styles.leaseTermBtn, leaseTerm === t && styles.leaseTermBtnActive]}
                          onPress={() => setLeaseTerm(t)}
                          data-testid={`lease-term-${t}`}
                        >
                          <Text style={[styles.leaseTermBtnText, leaseTerm === t && styles.leaseTermBtnTextActive]}>
                            {t}
                          </Text>
                        </TouchableOpacity>
                      ))}
                    </ScrollView>
                  </View>

                  {/* Residual by km/year table */}
                  {(() => {
                    if (!selectedProgram || !leaseResiduals?.vehicles) return null;
                    const brandL = selectedProgram.brand.toLowerCase();
                    const modelL = selectedProgram.model.toLowerCase();
                    const trimL = (selectedProgram.trim || '').toLowerCase();
                    const bodyL = (selectedInventory?.body_style || '').toLowerCase();
                    // Priority: match with body_style, fallback without
                    let rv = bodyL ? leaseResiduals.vehicles?.find((v: any) => {
                      const vB = v.brand.toLowerCase();
                      const vM = v.model_name.toLowerCase();
                      const vT = (v.trim || '').toLowerCase();
                      const vBS = (v.body_style || '').toLowerCase();
                      return vB === brandL && (vM.includes(modelL) || modelL.includes(vM)) &&
                        (vT.includes(trimL) || trimL.includes(vT) || !trimL) && vBS === bodyL;
                    }) : null;
                    if (!rv) {
                      rv = leaseResiduals.vehicles?.find((v: any) => {
                        const vB = v.brand.toLowerCase();
                        const vM = v.model_name.toLowerCase();
                        const vT = (v.trim || '').toLowerCase();
                        return vB === brandL && (vM.includes(modelL) || modelL.includes(vM)) &&
                          (vT.includes(trimL) || trimL.includes(vT) || !trimL);
                      });
                    }
                    if (!rv) return null;
                    const basePct = rv.residual_percentages?.[String(leaseTerm)] || 0;
                    if (basePct === 0) return null;
                    const kmAdj = leaseResiduals.km_adjustments?.adjustments || {};
                    const pdsf = parseFloat(leasePdsf) || parseFloat(vehiclePrice) || 0;
                    
                    return (
                      <View style={styles.residualKmTable} data-testid="residual-km-table">
                        <Text style={styles.residualKmTitle}>
                          {lang === 'fr' ? 'Résiduel selon kilométrage' : 'Residual by mileage'}
                          {rv.body_style ? ` — ${rv.body_style}` : ''}
                        </Text>
                        <View style={styles.residualKmRow}>
                          <View style={styles.residualKmHeader}>
                            <Text style={styles.residualKmHeaderText}>km/an</Text>
                          </View>
                          <View style={styles.residualKmHeader}>
                            <Text style={styles.residualKmHeaderText}>%</Text>
                          </View>
                          <View style={styles.residualKmHeader}>
                            <Text style={styles.residualKmHeaderText}>$</Text>
                          </View>
                        </View>
                        {[12000, 18000, 24000].map(km => {
                          const adj = km === 24000 ? 0 : (kmAdj[String(km)]?.[String(leaseTerm)] || 0);
                          const pct = basePct + adj;
                          const val = pdsf * (pct / 100);
                          const isSelected = km === leaseKmPerYear;
                          return (
                            <TouchableOpacity
                              key={km}
                              style={[styles.residualKmRow, isSelected && styles.residualKmRowSelected]}
                              onPress={() => setLeaseKmPerYear(km)}
                              data-testid={`residual-km-row-${km}`}
                            >
                              <View style={styles.residualKmCell}>
                                <Text style={[styles.residualKmText, isSelected && styles.residualKmTextSelected]}>
                                  {(km / 1000).toFixed(0)}k
                                </Text>
                              </View>
                              <View style={styles.residualKmCell}>
                                <Text style={[styles.residualKmText, isSelected && styles.residualKmTextSelected]}>
                                  {pct}%{adj !== 0 ? ` (+${adj})` : ''}
                                </Text>
                              </View>
                              <View style={styles.residualKmCell}>
                                <Text style={[styles.residualKmValue, isSelected && styles.residualKmValueSelected]}>
                                  {formatCurrency(val)}
                                </Text>
                              </View>
                            </TouchableOpacity>
                          );
                        })}
                      </View>
                    );
                  })()}

                  {/* Info: only frais de dossier capitalized in lease */}
                  <View style={styles.leaseInfoBar}>
                    <Ionicons name="information-circle" size={14} color="#4ECDC4" />
                    <Text style={styles.leaseInfoText}>
                      {lang === 'fr' 
                        ? `Capitalisé: ${formatCurrency(parseFloat(fraisDossier) || 0)} dossier | Pneus (${formatCurrency(parseFloat(taxePneus) || 0)}) + RDPRM (${formatCurrency(parseFloat(fraisRDPRM) || 0)}) payés à la livraison`
                        : `Capitalized: ${formatCurrency(parseFloat(fraisDossier) || 0)} admin | Tires (${formatCurrency(parseFloat(taxePneus) || 0)}) + RDPRM (${formatCurrency(parseFloat(fraisRDPRM) || 0)}) paid at delivery`}
                    </Text>
                  </View>

                  {/* Lease Results */}
                  {leaseResult ? (
                    <View style={styles.leaseResults}>
                      {/* Residual info */}
                      <View style={styles.leaseResidualInfo}>
                        <View>
                          <Text style={styles.leaseResidualLabel}>
                            {lang === 'fr' ? 'PDSF' : 'MSRP'}: {formatCurrency(leaseResult.standard?.pdsf || leaseResult.alternative?.pdsf || 0)}
                          </Text>
                          <Text style={styles.leaseResidualLabel}>
                            {lang === 'fr' ? 'Résiduel' : 'Residual'}: {leaseResult.residualPct}%
                            {leaseResult.kmAdjustment !== 0 ? ` (${leaseResult.kmAdjustment > 0 ? '+' : ''}${leaseResult.kmAdjustment}%)` : ''}
                          </Text>
                        </View>
                        <Text style={styles.leaseResidualValue}>
                          {formatCurrency(leaseResult.residualValue)}
                        </Text>
                      </View>

                      {/* Tax credit warning for trade-in */}
                      {(leaseResult.standard?.creditPerdu > 0 || leaseResult.alternative?.creditPerdu > 0) && (
                        <View style={styles.leaseWarningBar}>
                          <Ionicons name="warning" size={14} color="#FF6B6B" />
                          <Text style={styles.leaseWarningText}>
                            {lang === 'fr' 
                              ? `Crédit taxe échange: surplus perdu de ${formatCurrency((leaseResult.standard || leaseResult.alternative).creditPerdu)} / mois`
                              : `Trade tax credit: lost surplus of ${formatCurrency((leaseResult.standard || leaseResult.alternative).creditPerdu)} / mo`}
                          </Text>
                        </View>
                      )}

                      {/* Best lease banner */}
                      {leaseResult.bestLease && leaseResult.standard && leaseResult.alternative && (
                        <View style={styles.leaseBestBanner}>
                          <Ionicons name="trophy" size={16} color="#1a1a2e" />
                          <Text style={styles.leaseBestText}>
                            {leaseResult.bestLease === 'standard' 
                              ? (lang === 'fr' ? 'Std + Lease Cash' : 'Std + Lease Cash')
                              : (lang === 'fr' ? 'Taux Alternatif' : 'Alternative Rate')
                            } = {lang === 'fr' ? 'Meilleur choix' : 'Best choice'}
                          </Text>
                          {leaseResult.leaseSavings > 0 && (
                            <Text style={styles.leaseBestSavings}>
                              {lang === 'fr' ? 'Économie' : 'Savings'}: {formatCurrency(leaseResult.leaseSavings)}
                            </Text>
                          )}
                        </View>
                      )}

                      {/* Lease options cards */}
                      <View style={styles.leaseCardsRow}>
                        {/* Standard Rate + Lease Cash */}
                        {leaseResult.standard && (
                          <View style={[
                            styles.leaseCard,
                            leaseResult.bestLease === 'standard' && styles.leaseCardBest
                          ]}>
                            <View style={styles.leaseCardHeader}>
                              <Text style={styles.leaseCardTitle}>
                                {lang === 'fr' ? 'Std + Lease Cash' : 'Std + Lease Cash'}
                              </Text>
                              {leaseResult.bestLease === 'standard' && (
                                <Ionicons name="checkmark-circle" size={16} color="#4ECDC4" />
                              )}
                            </View>
                            {leaseResult.standard.leaseCash > 0 && (
                              <View style={styles.leaseCardDetail}>
                                <Text style={styles.leaseCardDetailLabel}>Lease Cash:</Text>
                                <Text style={styles.leaseCardDetailValue}>{formatCurrency(leaseResult.standard.leaseCash)}</Text>
                              </View>
                            )}
                            <View style={styles.leaseCardDetail}>
                              <Text style={styles.leaseCardDetailLabel}>{lang === 'fr' ? 'Taux' : 'Rate'}:</Text>
                              <Text style={styles.leaseCardRateValue}>{leaseResult.standard.rate}%</Text>
                            </View>
                            <View style={styles.leaseCardMainResult}>
                              <Text style={styles.leaseCardPaymentLabel}>
                                {paymentFrequency === 'monthly' ? (lang === 'fr' ? 'Mensuel' : 'Monthly') : 
                                 paymentFrequency === 'biweekly' ? (lang === 'fr' ? 'Aux 2 sem.' : 'Bi-weekly') : 
                                 (lang === 'fr' ? 'Hebdo' : 'Weekly')}
                              </Text>
                              <Text style={styles.leaseCardPaymentValue}>
                                {formatCurrencyDecimal(
                                  paymentFrequency === 'monthly' ? leaseResult.standard.monthly :
                                  paymentFrequency === 'biweekly' ? leaseResult.standard.biweekly :
                                  leaseResult.standard.weekly
                                )}
                              </Text>
                              <Text style={styles.leaseCardTaxDetail}>
                                {lang === 'fr' ? 'Avant taxes' : 'Before tax'}: {formatCurrencyDecimal(
                                  paymentFrequency === 'monthly' ? leaseResult.standard.monthlyBeforeTax :
                                  paymentFrequency === 'biweekly' ? leaseResult.standard.biweeklyBeforeTax :
                                  leaseResult.standard.weeklyBeforeTax
                                )}
                              </Text>
                              {paymentFrequency === 'monthly' && (
                                <View style={styles.leaseCardTaxBreakdown}>
                                  <Text style={styles.leaseCardTaxLine}>TPS (5%): {formatCurrencyDecimal(leaseResult.standard.tpsOnPayment)}</Text>
                                  <Text style={styles.leaseCardTaxLine}>TVQ (9.975%): {formatCurrencyDecimal(leaseResult.standard.tvqOnPayment)}</Text>
                                </View>
                              )}
                              {leaseResult.standard.rabaisConcess > 0 && (
                                <Text style={styles.leaseCardRabaisLine}>
                                  {lang === 'fr' ? 'Rabais concess.' : 'Dealer disc.'}: -{formatCurrency(leaseResult.standard.rabaisConcess)}
                                </Text>
                              )}
                            </View>
                            <View style={styles.leaseCardDetail}>
                              <Text style={styles.leaseCardDetailLabel}>Total ({leaseTerm} {lang === 'fr' ? 'mois' : 'mo'}):</Text>
                              <Text style={styles.leaseCardTotalValue}>{formatCurrency(leaseResult.standard.total)}</Text>
                            </View>
                            <View style={styles.leaseCardDetail}>
                              <Text style={[styles.leaseCardDetailLabel, { color: '#FF6B6B' }]}>{lang === 'fr' ? "Coût d'emprunt:" : 'Cost of borrowing:'}</Text>
                              <Text style={[styles.leaseCardTotalValue, { color: '#FF6B6B' }]}>{formatCurrencyDecimal(leaseResult.standard.coutEmprunt)}</Text>
                            </View>
                          </View>
                        )}

                        {/* Alternative Rate */}
                        {leaseResult.alternative && (
                          <View style={[
                            styles.leaseCard,
                            styles.leaseCardAlt,
                            leaseResult.bestLease === 'alternative' && styles.leaseCardBest
                          ]}>
                            <View style={styles.leaseCardHeader}>
                              <Text style={styles.leaseCardTitle}>
                                {lang === 'fr' ? 'Taux Alternatif' : 'Alt. Rate'}
                              </Text>
                              {leaseResult.bestLease === 'alternative' && (
                                <Ionicons name="checkmark-circle" size={16} color="#4ECDC4" />
                              )}
                            </View>
                            <View style={styles.leaseCardDetail}>
                              <Text style={styles.leaseCardDetailLabel}>Lease Cash:</Text>
                              <Text style={styles.leaseCardDetailValue}>$0</Text>
                            </View>
                            <View style={styles.leaseCardDetail}>
                              <Text style={styles.leaseCardDetailLabel}>{lang === 'fr' ? 'Taux' : 'Rate'}:</Text>
                              <Text style={styles.leaseCardRateValue}>{leaseResult.alternative.rate}%</Text>
                            </View>
                            <View style={styles.leaseCardMainResult}>
                              <Text style={styles.leaseCardPaymentLabel}>
                                {paymentFrequency === 'monthly' ? (lang === 'fr' ? 'Mensuel' : 'Monthly') : 
                                 paymentFrequency === 'biweekly' ? (lang === 'fr' ? 'Aux 2 sem.' : 'Bi-weekly') : 
                                 (lang === 'fr' ? 'Hebdo' : 'Weekly')}
                              </Text>
                              <Text style={styles.leaseCardPaymentValue}>
                                {formatCurrencyDecimal(
                                  paymentFrequency === 'monthly' ? leaseResult.alternative.monthly :
                                  paymentFrequency === 'biweekly' ? leaseResult.alternative.biweekly :
                                  leaseResult.alternative.weekly
                                )}
                              </Text>
                              <Text style={styles.leaseCardTaxDetail}>
                                {lang === 'fr' ? 'Avant taxes' : 'Before tax'}: {formatCurrencyDecimal(
                                  paymentFrequency === 'monthly' ? leaseResult.alternative.monthlyBeforeTax :
                                  paymentFrequency === 'biweekly' ? leaseResult.alternative.biweeklyBeforeTax :
                                  leaseResult.alternative.weeklyBeforeTax
                                )}
                              </Text>
                              {paymentFrequency === 'monthly' && (
                                <View style={styles.leaseCardTaxBreakdown}>
                                  <Text style={styles.leaseCardTaxLine}>TPS (5%): {formatCurrencyDecimal(leaseResult.alternative.tpsOnPayment)}</Text>
                                  <Text style={styles.leaseCardTaxLine}>TVQ (9.975%): {formatCurrencyDecimal(leaseResult.alternative.tvqOnPayment)}</Text>
                                </View>
                              )}
                              {leaseResult.alternative.rabaisConcess > 0 && (
                                <Text style={styles.leaseCardRabaisLine}>
                                  {lang === 'fr' ? 'Rabais concess.' : 'Dealer disc.'}: -{formatCurrency(leaseResult.alternative.rabaisConcess)}
                                </Text>
                              )}
                            </View>
                            <View style={styles.leaseCardDetail}>
                              <Text style={styles.leaseCardDetailLabel}>Total ({leaseTerm} {lang === 'fr' ? 'mois' : 'mo'}):</Text>
                              <Text style={styles.leaseCardTotalValue}>{formatCurrency(leaseResult.alternative.total)}</Text>
                            </View>
                            <View style={styles.leaseCardDetail}>
                              <Text style={[styles.leaseCardDetailLabel, { color: '#FF6B6B' }]}>{lang === 'fr' ? "Coût d'emprunt:" : 'Cost of borrowing:'}</Text>
                              <Text style={[styles.leaseCardTotalValue, { color: '#FF6B6B' }]}>{formatCurrencyDecimal(leaseResult.alternative.coutEmprunt)}</Text>
                            </View>
                          </View>
                        )}
                      </View>

                      {/* No lease options available */}
                      {!leaseResult.standard && !leaseResult.alternative && (
                        <View style={styles.leaseNoOption}>
                          <Ionicons name="information-circle" size={24} color="#666" />
                          <Text style={styles.leaseNoOptionText}>
                            {lang === 'fr' ? 'Aucun taux de location disponible pour ce véhicule' : 'No lease rates available for this vehicle'}
                          </Text>
                        </View>
                      )}

                      {/* Comparison with financing */}
                      {localResult && (leaseResult.standard || leaseResult.alternative) && (
                        <View style={styles.leaseVsFinance}>
                          <Text style={styles.leaseVsFinanceTitle}>
                            {lang === 'fr' ? 'Location vs Financement' : 'Lease vs Finance'}
                          </Text>
                          <View style={styles.leaseVsFinanceRow}>
                            <View style={styles.leaseVsFinanceCol}>
                              <Text style={styles.leaseVsFinanceLabel}>
                                {lang === 'fr' ? 'Meilleure Location' : 'Best Lease'}
                              </Text>
                              <Text style={styles.leaseVsFinanceValue}>
                                {formatCurrencyDecimal(
                                  paymentFrequency === 'monthly' 
                                    ? (leaseResult.bestLease === 'standard' ? leaseResult.standard?.monthly : leaseResult.alternative?.monthly) || 0
                                    : paymentFrequency === 'biweekly'
                                    ? (leaseResult.bestLease === 'standard' ? leaseResult.standard?.biweekly : leaseResult.alternative?.biweekly) || 0
                                    : (leaseResult.bestLease === 'standard' ? leaseResult.standard?.weekly : leaseResult.alternative?.weekly) || 0
                                )}
                              </Text>
                              <Text style={styles.leaseVsFinanceSub}>{leaseTerm} {lang === 'fr' ? 'mois' : 'mo'}</Text>
                            </View>
                            <View style={styles.leaseVsFinanceDivider} />
                            <View style={styles.leaseVsFinanceCol}>
                              <Text style={styles.leaseVsFinanceLabel}>
                                {lang === 'fr' ? 'Meilleur Financement' : 'Best Finance'}
                              </Text>
                              <Text style={styles.leaseVsFinanceValue}>
                                {formatCurrencyDecimal(
                                  paymentFrequency === 'monthly' 
                                    ? (localResult.bestOption === '2' && localResult.option2Monthly ? localResult.option2Monthly : localResult.option1Monthly)
                                    : paymentFrequency === 'biweekly'
                                    ? (localResult.bestOption === '2' && localResult.option2Biweekly ? localResult.option2Biweekly : localResult.option1Biweekly)
                                    : (localResult.bestOption === '2' && localResult.option2Weekly ? localResult.option2Weekly : localResult.option1Weekly)
                                )}
                              </Text>
                              <Text style={styles.leaseVsFinanceSub}>{selectedTerm} {lang === 'fr' ? 'mois' : 'mo'}</Text>
                            </View>
                          </View>
                        </View>
                      )}

                      {/* ANALYSE COMPLÈTE - Grille de tous les paiements */}
                      {leaseAnalysisGrid.length > 0 && (
                        <View style={styles.analysisSection}>
                          <Text style={styles.analysisSectionTitle}>
                            {lang === 'fr' ? `ANALYSE COMPLÈTE - Paiements ${paymentFrequency === 'weekly' ? 'hebdo' : paymentFrequency === 'biweekly' ? 'aux 2 sem.' : 'mensuels'}` : `FULL ANALYSIS - ${paymentFrequency === 'weekly' ? 'Weekly' : paymentFrequency === 'biweekly' ? 'Bi-weekly' : 'Monthly'} payments`}
                          </Text>
                          {[12000, 18000, 24000].map(km => {
                            const kmRows = leaseAnalysisGrid.filter(r => r.kmPerYear === km);
                            if (kmRows.length === 0) return null;
                            const terms = [...new Set(kmRows.map(r => r.term))].sort((a,b) => a-b);
                            return (
                              <View key={km} style={styles.analysisKmBlock}>
                                <Text style={styles.analysisKmTitle}>{(km/1000).toFixed(0)}k km / {lang === 'fr' ? 'an' : 'yr'}</Text>
                                <ScrollView horizontal showsHorizontalScrollIndicator={true}>
                                  <View>
                                    <View style={styles.analysisHeaderRow}>
                                      <Text style={[styles.analysisCell, styles.analysisCellHeader, { width: 52 }]}>{lang === 'fr' ? 'Terme' : 'Term'}</Text>
                                      <Text style={[styles.analysisCell, styles.analysisCellHeader, { width: 45 }]}>Rés%</Text>
                                      <Text style={[styles.analysisCell, styles.analysisCellHeader, { width: 82, color: '#E65100' }]}>Std</Text>
                                      <Text style={[styles.analysisCell, styles.analysisCellHeader, { width: 82, color: '#0277BD' }]}>Alt</Text>
                                    </View>
                                    {terms.map(t => {
                                      const stdRow = kmRows.find(r => r.term === t && r.option === 'std');
                                      const altRow = kmRows.find(r => r.term === t && r.option === 'alt');
                                      const isBestStd = bestLeaseOption && bestLeaseOption.term === t && bestLeaseOption.kmPerYear === km && bestLeaseOption.option === 'standard';
                                      const isBestAlt = bestLeaseOption && bestLeaseOption.term === t && bestLeaseOption.kmPerYear === km && bestLeaseOption.option === 'alternative';
                                      return (
                                        <TouchableOpacity 
                                          key={t} 
                                          style={[styles.analysisDataRow, (isBestStd || isBestAlt) && styles.analysisBestRow]}
                                          onPress={() => { setLeaseTerm(t); setLeaseKmPerYear(km); }}
                                        >
                                          <Text style={[styles.analysisCell, { width: 52, fontWeight: '600' }]}>{t}m</Text>
                                          <Text style={[styles.analysisCell, { width: 45, color: '#888' }]}>{stdRow?.residualPct || altRow?.residualPct}%</Text>
                                          <Text style={[styles.analysisCell, { width: 82, color: isBestStd ? '#FFD700' : '#E65100', fontWeight: isBestStd ? '800' : '500' }]}>
                                            {stdRow ? `${(paymentFrequency === 'weekly' ? stdRow.monthly * 12/52 : paymentFrequency === 'biweekly' ? stdRow.monthly * 12/26 : stdRow.monthly).toFixed(0)}$` : '-'}
                                          </Text>
                                          <Text style={[styles.analysisCell, { width: 82, color: isBestAlt ? '#FFD700' : '#0277BD', fontWeight: isBestAlt ? '800' : '500' }]}>
                                            {altRow ? `${(paymentFrequency === 'weekly' ? altRow.monthly * 12/52 : paymentFrequency === 'biweekly' ? altRow.monthly * 12/26 : altRow.monthly).toFixed(0)}$` : '-'}
                                          </Text>
                                        </TouchableOpacity>
                                      );
                                    })}
                                  </View>
                                </ScrollView>
                              </View>
                            );
                          })}
                        </View>
                      )}

                      {/* MEILLEUR CHOIX */}
                      {bestLeaseOption && (
                        <TouchableOpacity 
                          style={styles.bestLeaseBox}
                          onPress={() => {
                            setLeaseTerm(bestLeaseOption.term);
                            setLeaseKmPerYear(bestLeaseOption.kmPerYear);
                          }}
                          data-testid="best-lease-option"
                        >
                          <View style={styles.bestLeaseHeader}>
                            <Ionicons name="trophy" size={18} color="#FFD700" />
                            <Text style={styles.bestLeaseTitle}>
                              {lang === 'fr' ? 'MEILLEUR CHOIX LOCATION' : 'BEST LEASE OPTION'}
                            </Text>
                            <Ionicons name="trophy" size={18} color="#FFD700" />
                          </View>
                          <View style={styles.bestLeaseContent}>
                            <View style={styles.bestLeaseRow}>
                              <Text style={styles.bestLeaseLabel}>{lang === 'fr' ? 'Terme:' : 'Term:'}</Text>
                              <Text style={styles.bestLeaseValue}>{bestLeaseOption.term} {lang === 'fr' ? 'mois' : 'mo'}</Text>
                            </View>
                            <View style={styles.bestLeaseRow}>
                              <Text style={styles.bestLeaseLabel}>{lang === 'fr' ? 'Kilométrage:' : 'Mileage:'}</Text>
                              <Text style={styles.bestLeaseValue}>{(bestLeaseOption.kmPerYear / 1000).toFixed(0)}k km / {lang === 'fr' ? 'an' : 'yr'}</Text>
                            </View>
                            <View style={styles.bestLeaseRow}>
                              <Text style={styles.bestLeaseLabel}>Option:</Text>
                              <Text style={[styles.bestLeaseValue, { color: bestLeaseOption.option === 'standard' ? '#E65100' : '#0277BD' }]}>
                                {bestLeaseOption.optionLabel}
                              </Text>
                            </View>
                            <View style={styles.bestLeaseRow}>
                              <Text style={styles.bestLeaseLabel}>{lang === 'fr' ? 'Taux:' : 'Rate:'}</Text>
                              <Text style={styles.bestLeaseValue}>{bestLeaseOption.rate}%</Text>
                            </View>
                            {bestLeaseOption.leaseCash > 0 && (
                              <View style={styles.bestLeaseRow}>
                                <Text style={styles.bestLeaseLabel}>Lease Cash:</Text>
                                <Text style={styles.bestLeaseValue}>{formatCurrency(bestLeaseOption.leaseCash)}</Text>
                              </View>
                            )}
                            <View style={styles.bestLeaseRow}>
                              <Text style={styles.bestLeaseLabel}>{lang === 'fr' ? 'Résiduel:' : 'Residual:'}</Text>
                              <Text style={styles.bestLeaseValue}>{bestLeaseOption.residualPct}% ({formatCurrency(bestLeaseOption.residualValue)})</Text>
                            </View>
                            <View style={[styles.bestLeaseRow, { borderTopWidth: 1, borderTopColor: '#444', paddingTop: 6, marginTop: 4 }]}>
                              <Text style={[styles.bestLeaseLabel, { fontSize: 13 }]}>{lang === 'fr' ? 'Avant taxes:' : 'Before tax:'}</Text>
                              <Text style={[styles.bestLeaseValue, { fontSize: 13 }]}>{formatCurrencyDecimal(
                                paymentFrequency === 'monthly' ? bestLeaseOption.monthlyBeforeTax :
                                paymentFrequency === 'biweekly' ? bestLeaseOption.monthlyBeforeTax * 12 / 26 :
                                bestLeaseOption.monthlyBeforeTax * 12 / 52
                              )} / {paymentFrequency === 'monthly' ? (lang === 'fr' ? 'mois' : 'mo') : paymentFrequency === 'biweekly' ? (lang === 'fr' ? '2 sem.' : 'bi-wk') : (lang === 'fr' ? 'sem.' : 'wk')}</Text>
                            </View>
                            <View style={styles.bestLeaseRow}>
                              <Text style={[styles.bestLeaseLabel, { fontSize: 16, fontWeight: '700' }]}>{paymentFrequency === 'monthly' ? (lang === 'fr' ? 'MENSUEL:' : 'MONTHLY:') : paymentFrequency === 'biweekly' ? (lang === 'fr' ? 'AUX 2 SEM.:' : 'BI-WEEKLY:') : (lang === 'fr' ? 'HEBDO:' : 'WEEKLY:')}</Text>
                              <Text style={[styles.bestLeaseValue, { fontSize: 16, fontWeight: '700', color: '#4ECDC4' }]}>{formatCurrencyDecimal(
                                paymentFrequency === 'monthly' ? bestLeaseOption.monthly :
                                paymentFrequency === 'biweekly' ? bestLeaseOption.monthly * 12 / 26 :
                                bestLeaseOption.monthly * 12 / 52
                              )} / {paymentFrequency === 'monthly' ? (lang === 'fr' ? 'mois' : 'mo') : paymentFrequency === 'biweekly' ? (lang === 'fr' ? '2 sem.' : 'bi-wk') : (lang === 'fr' ? 'sem.' : 'wk')}</Text>
                            </View>
                          </View>
                          <Text style={styles.bestLeaseTap}>
                            {lang === 'fr' ? 'Toucher pour sélectionner ce terme et km' : 'Tap to select this term and km'}
                          </Text>
                        </TouchableOpacity>
                      )}
                      <TouchableOpacity
                        style={styles.sendEmailButton}
                        onPress={() => setShowEmailModal(true)}
                        data-testid="lease-send-email-btn"
                      >
                        <Ionicons name="mail-outline" size={20} color="#fff" />
                        <Text style={styles.sendEmailButtonText}>
                          {lang === 'fr' ? 'Envoyer par email' : 'Send by email'}
                        </Text>
                      </TouchableOpacity>
                      
                      <View style={styles.shareActionsRow}>
                        <TouchableOpacity
                          style={styles.shareSmsButton}
                          onPress={handleShareSMS}
                          data-testid="lease-share-sms-btn"
                        >
                          <Ionicons name="chatbubble-outline" size={18} color="#fff" />
                          <Text style={styles.shareButtonText}>
                            {lang === 'fr' ? 'Texto' : 'SMS'}
                          </Text>
                        </TouchableOpacity>
                        
                        <TouchableOpacity
                          style={styles.printButton}
                          onPress={handlePrint}
                          data-testid="lease-print-btn"
                        >
                          <Ionicons name="print-outline" size={18} color="#fff" />
                          <Text style={styles.shareButtonText}>
                            {lang === 'fr' ? 'Imprimer' : 'Print'}
                          </Text>
                        </TouchableOpacity>
                        
                        <TouchableOpacity
                          style={styles.exportExcelButton}
                          onPress={handleExportExcel}
                          data-testid="lease-export-excel-btn"
                        >
                          <Ionicons name="document-outline" size={18} color="#fff" />
                          <Text style={styles.shareButtonText}>
                            Excel
                          </Text>
                        </TouchableOpacity>
                      </View>
                    </View>
                  ) : showLease ? (
                    <View style={styles.leaseNoOption}>
                      <Ionicons name="alert-circle" size={24} color="#FF6B6B" />
                      <Text style={styles.leaseNoOptionText}>
                        {lang === 'fr' 
                          ? 'Données de location non disponibles pour ce véhicule. Vérifiez la marque/modèle.'
                          : 'Lease data not available for this vehicle. Check brand/model.'}
                      </Text>
                    </View>
                  ) : null}
                </View>
              )}
            </View>
          )}
        </ScrollView>
        <Modal
          visible={showImportModal}
          transparent
          animationType="fade"
          onRequestClose={() => setShowImportModal(false)}
        >
          <View style={styles.modalOverlay}>
            <View style={styles.modalContent}>
              <Text style={styles.modalTitle}>{t.import.title}</Text>
              <Text style={styles.modalSubtitle}>
                {t.import.enterAdminPassword}
              </Text>
              <TextInput
                style={styles.passwordInput}
                placeholder={t.import.password}
                placeholderTextColor="#666"
                secureTextEntry
                value={importPassword}
                onChangeText={setImportPassword}
                autoCapitalize="none"
              />
              <View style={styles.modalButtons}>
                <TouchableOpacity
                  style={styles.modalButtonCancel}
                  onPress={() => {
                    setShowImportModal(false);
                    setImportPassword('');
                  }}
                >
                  <Text style={styles.modalButtonCancelText}>{t.import.cancel}</Text>
                </TouchableOpacity>
                <TouchableOpacity
                  style={styles.modalButtonConfirm}
                  onPress={() => {
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
                  }}
                >
                  <Text style={styles.modalButtonConfirmText}>{t.import.confirm}</Text>
                </TouchableOpacity>
              </View>
            </View>
          </View>
        </Modal>

        {/* SMS Preview Modal */}
        <Modal
          visible={showSmsPreview}
          transparent
          animationType="slide"
          onRequestClose={() => setShowSmsPreview(false)}
        >
          <View style={styles.modalOverlay}>
            <View style={styles.smsPreviewModalContent}>
              <View style={styles.smsPreviewHeader}>
                <View style={styles.smsPreviewIconContainer}>
                  <Ionicons name="chatbubble-ellipses" size={32} color="#4ECDC4" />
                </View>
                <Text style={styles.smsPreviewTitle}>
                  {lang === 'fr' ? 'Aperçu du message' : 'Message Preview'}
                </Text>
                <TouchableOpacity
                  style={styles.smsPreviewClose}
                  onPress={() => setShowSmsPreview(false)}
                >
                  <Ionicons name="close" size={24} color="#888" />
                </TouchableOpacity>
              </View>
              
              <View style={styles.smsPreviewBody}>
                <Text style={styles.smsPreviewLabel}>
                  {lang === 'fr' ? 'Modifiez le message si nécessaire:' : 'Edit the message if needed:'}
                </Text>
                <TextInput
                  style={styles.smsPreviewTextInput}
                  multiline
                  numberOfLines={12}
                  value={smsPreviewText}
                  onChangeText={setSmsPreviewText}
                  placeholder={lang === 'fr' ? 'Message...' : 'Message...'}
                  placeholderTextColor="#666"
                  textAlignVertical="top"
                />
                <Text style={styles.smsPreviewCharCount}>
                  {smsPreviewText.length} {lang === 'fr' ? 'caractères' : 'characters'}
                </Text>
              </View>
              
              <View style={styles.smsPreviewButtons}>
                <TouchableOpacity
                  style={styles.smsPreviewCancelButton}
                  onPress={() => setShowSmsPreview(false)}
                >
                  <Text style={styles.smsPreviewCancelText}>
                    {lang === 'fr' ? 'Annuler' : 'Cancel'}
                  </Text>
                </TouchableOpacity>
                <TouchableOpacity
                  style={styles.smsPreviewSendButton}
                  onPress={handleSendSms}
                  data-testid="sms-preview-send-btn"
                >
                  <Ionicons name="send" size={18} color="#fff" />
                  <Text style={styles.smsPreviewSendText}>
                    {lang === 'fr' ? 'Envoyer' : 'Send'}
                  </Text>
                </TouchableOpacity>
              </View>
            </View>
          </View>
        </Modal>

        {/* Email Modal */}
        <Modal
          visible={showEmailModal}
          transparent
          animationType="fade"
          onRequestClose={() => setShowEmailModal(false)}
        >
          <View style={[styles.modalOverlay, { justifyContent: 'center' }]}>
            <View style={{
              backgroundColor: '#1a1a2e',
              borderRadius: 16,
              width: '90%',
              maxWidth: 420,
              maxHeight: Math.round(Dimensions.get('window').height * 0.6),
              flexDirection: 'column',
              overflow: 'hidden',
            }}>
              <View style={{
                flexDirection: 'row',
                alignItems: 'center',
                paddingVertical: 10,
                paddingHorizontal: 16,
                borderBottomWidth: 1,
                borderBottomColor: '#2d2d44',
              }}>
                <Ionicons name="mail" size={22} color="#4ECDC4" style={{ marginRight: 10 }} />
                <Text style={{ fontSize: 17, fontWeight: 'bold', color: '#fff', flex: 1 }}>
                  {t.email.sendByEmail}
                </Text>
                <TouchableOpacity
                  onPress={() => setShowEmailModal(false)}
                  style={{ padding: 4 }}
                >
                  <Ionicons name="close" size={22} color="#888" />
                </TouchableOpacity>
              </View>
              
              <ScrollView style={{ flex: 1 }} showsVerticalScrollIndicator={true} bounces={false}>
              <View style={styles.emailModalBody}>
                <Text style={styles.emailModalLabel}>
                  {t.email.clientName}
                </Text>
                <TextInput
                  style={styles.emailModalInput}
                  placeholder="Ex: Jean Dupont"
                  placeholderTextColor="#666"
                  value={clientName}
                  onChangeText={setClientName}
                />
                
                <Text style={styles.emailModalLabel}>
                  {t.email.clientPhone} *
                </Text>
                <TextInput
                  style={styles.emailModalInput}
                  placeholder="514-555-1234"
                  placeholderTextColor="#666"
                  value={clientPhone}
                  onChangeText={setClientPhone}
                  keyboardType="phone-pad"
                />
                
                <Text style={styles.emailModalLabel}>
                  {t.email.clientEmail} *
                </Text>
                <TextInput
                  style={styles.emailModalInput}
                  placeholder="client@email.com"
                  placeholderTextColor="#666"
                  value={clientEmail}
                  onChangeText={setClientEmail}
                  keyboardType="email-address"
                  autoCapitalize="none"
                />
                
                {selectedProgram && (
                  <View style={styles.emailPreviewBox}>
                    <Text style={styles.emailPreviewTitle}>
                      {t.email.summaryToSend}
                    </Text>
                    <Text style={styles.emailPreviewText}>
                      {selectedProgram.brand} {selectedProgram.model} {selectedProgram.year}
                    </Text>
                    <Text style={styles.emailPreviewText}>
                      {formatCurrency(parseFloat(vehiclePrice) || 0)} • {selectedTerm} mois
                    </Text>
                    <Text style={styles.emailPreviewPayment}>
                      {localResult ? formatCurrency(
                        paymentFrequency === 'weekly' ? localResult.option1Weekly :
                        paymentFrequency === 'biweekly' ? localResult.option1Biweekly :
                        localResult.option1Monthly || 0
                      ) : formatCurrency(0)}{paymentFrequency === 'weekly' ? '/sem.' : paymentFrequency === 'biweekly' ? '/2 sem.' : '/mois'}
                    </Text>
                    {showLease && leaseResult && (leaseResult.standard || leaseResult.alternative) && (
                      <Text style={[styles.emailPreviewText, {color: '#FFD700', marginTop: 6}]}>
                        + Location SCI: {formatCurrencyDecimal(
                          paymentFrequency === 'monthly' 
                            ? (leaseResult.bestLease === 'standard' ? leaseResult.standard?.monthly : leaseResult.alternative?.monthly) || 0
                            : paymentFrequency === 'biweekly'
                            ? (leaseResult.bestLease === 'standard' ? leaseResult.standard?.biweekly : leaseResult.alternative?.biweekly) || 0
                            : (leaseResult.bestLease === 'standard' ? leaseResult.standard?.weekly : leaseResult.alternative?.weekly) || 0
                        )}{paymentFrequency === 'weekly' ? '/sem.' : paymentFrequency === 'biweekly' ? '/2 sem.' : '/mois'} ({leaseTerm} mois)
                      </Text>
                    )}
                  </View>
                )}
              </View>
              </ScrollView>
              
              <View style={{
                flexDirection: 'row',
                paddingHorizontal: 16,
                paddingVertical: 12,
                gap: 10,
                borderTopWidth: 1,
                borderTopColor: '#2d2d44',
              }}>
                <TouchableOpacity
                  style={styles.emailModalCancelButton}
                  onPress={() => {
                    setShowEmailModal(false);
                    setClientEmail('');
                    setClientName('');
                    setClientPhone('');
                  }}
                >
                  <Text style={styles.emailModalCancelText}>
                    {t.email.cancel}
                  </Text>
                </TouchableOpacity>
                
                <TouchableOpacity
                  style={[styles.emailModalSendButton, sendingEmail && styles.emailModalSendButtonDisabled]}
                  disabled={sendingEmail}
                  onPress={handleSendEmail}
                >
                  {sendingEmail ? (
                    <ActivityIndicator size="small" color="#1a1a2e" />
                  ) : (
                    <>
                      <Ionicons name="send" size={18} color="#1a1a2e" />
                      <Text style={styles.emailModalSendText}>
                        {lang === 'fr' ? 'Envoyer' : 'Send'}
                      </Text>
                    </>
                  )}
                </TouchableOpacity>
              </View>
            </View>
          </View>
        </Modal>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}

