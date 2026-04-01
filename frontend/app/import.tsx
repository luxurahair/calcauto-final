import React, { useState, useCallback } from 'react';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  TouchableOpacity,
  TextInput,
  ActivityIndicator,
  Platform,
  KeyboardAvoidingView,
  Alert,
  Modal,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { useRouter } from 'expo-router';
import axios from 'axios';
import * as DocumentPicker from 'expo-document-picker';

import { API_URL } from '../utils/api';
import { useAuth } from '../contexts/AuthContext';

interface RatesData {
  rate_36: number;
  rate_48: number;
  rate_60: number;
  rate_72: number;
  rate_84: number;
  rate_96: number;
}

interface ProgramEntry {
  brand: string;
  model: string;
  trim: string | null;
  year: number;
  consumer_cash: number;
  bonus_cash: number;
  option1_rates: RatesData;
  option2_rates: RatesData | null;
}

const months = [
  { value: 1, label: 'Janvier' },
  { value: 2, label: 'Février' },
  { value: 3, label: 'Mars' },
  { value: 4, label: 'Avril' },
  { value: 5, label: 'Mai' },
  { value: 6, label: 'Juin' },
  { value: 7, label: 'Juillet' },
  { value: 8, label: 'Août' },
  { value: 9, label: 'Septembre' },
  { value: 10, label: 'Octobre' },
  { value: 11, label: 'Novembre' },
  { value: 12, label: 'Décembre' },
];

// Steps for the import wizard
type Step = 'login' | 'choose-type' | 'upload' | 'select-pages' | 'preview' | 'email-sent' | 'excel-correction' | 'success' | 'residual-upload' | 'residual-processing' | 'residual-success';

export default function ImportScreen() {
  const router = useRouter();
  const { isDemoUser } = useAuth();
  
  // Wizard state
  const [currentStep, setCurrentStep] = useState<Step>(isDemoUser ? 'choose-type' : 'login');
  const [password, setPassword] = useState(isDemoUser ? 'Liana2018' : '');
  const [isAuthenticated, setIsAuthenticated] = useState(isDemoUser);
  const [docType, setDocType] = useState<'programs' | 'residuals'>('programs');
  
  // Period selection
  const [selectedMonth, setSelectedMonth] = useState(new Date().getMonth() + 1);
  const [selectedYear, setSelectedYear] = useState(new Date().getFullYear());
  
  // PDF file state
  const [pdfFile, setPdfFile] = useState<any>(null);
  const [pdfFileName, setPdfFileName] = useState('');
  const [totalPages, setTotalPages] = useState(0);
  
  // Page selection for PDF extraction
  const [pageStart, setPageStart] = useState('');
  const [pageEnd, setPageEnd] = useState('');
  
  // Page selection for SCI Lease extraction (from same PDF)
  const [leasePageStart, setLeasePageStart] = useState('');
  const [leasePageEnd, setLeasePageEnd] = useState('');
  
  // Auto-detection state
  const [detectedSections, setDetectedSections] = useState<any>(null);
  const [scanning, setScanning] = useState(false);
  
  // Loading states
  const [loading, setLoading] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [extracting, setExtracting] = useState(false);
  const [extractionStatus, setExtractionStatus] = useState('');
  const [saving, setSaving] = useState(false);
  
  // Programs data
  const [programs, setPrograms] = useState<ProgramEntry[]>([]);
  const [editingIndex, setEditingIndex] = useState<number | null>(null);
  
  // Edit modal state
  const [editModalVisible, setEditModalVisible] = useState(false);
  const [editProgram, setEditProgram] = useState<ProgramEntry | null>(null);

  // Residual guide state
  const [residualResult, setResidualResult] = useState<any>(null);

  // Excel correction state
  const [excelImporting, setExcelImporting] = useState(false);
  const [excelResult, setExcelResult] = useState<string | null>(null);
  const excelFileRef = React.useRef<HTMLInputElement | null>(null);

  const showAlert = (title: string, message: string) => {
    if (Platform.OS === 'web') {
      alert(`${title}: ${message}`);
    } else {
      Alert.alert(title, message);
    }
  };

  // Step 1: Login
  const handleLogin = async () => {
    if (!password) {
      showAlert('Erreur', 'Entrez le mot de passe');
      return;
    }
    
    setLoading(true);
    try {
      const formData = new FormData();
      formData.append('password', password);
      
      await axios.post(`${API_URL}/api/verify-password`, formData, {
        headers: { 'Content-Type': 'multipart/form-data' }
      });
      
      setIsAuthenticated(true);
      setCurrentStep('choose-type');
    } catch (error: any) {
      showAlert('Erreur', error.response?.data?.detail || 'Mot de passe incorrect');
    } finally {
      setLoading(false);
    }
  };

  // Step 2: Pick PDF and auto-detect pages
  const handlePickPDF = async () => {
    try {
      const result = await DocumentPicker.getDocumentAsync({
        type: 'application/pdf',
        copyToCacheDirectory: true,
      });
      
      if (result.canceled) {
        return;
      }
      
      const file = result.assets[0];
      if (!file) return;
      
      setUploading(true);
      setScanning(true);
      setPdfFile(file);
      setPdfFileName(file.name);
      
      // Build FormData for scan
      const formData = new FormData();
      if (Platform.OS === 'web') {
        const response = await fetch(file.uri);
        const blob = await response.blob();
        formData.append('file', blob, file.name);
      } else {
        formData.append('file', {
          uri: file.uri,
          type: 'application/pdf',
          name: file.name,
        } as any);
      }
      formData.append('password', password);
      
      // Call scan-pdf to auto-detect pages
      const scanResponse = await axios.post(`${API_URL}/api/scan-pdf`, formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
        timeout: 30000,
      });
      
      if (scanResponse.data.success) {
        const d = scanResponse.data;
        setTotalPages(d.total_pages);
        setDetectedSections(d);
        
        // Auto-fill page ranges from detection
        if (d.retail_start) setPageStart(String(d.retail_start));
        if (d.retail_end) setPageEnd(String(d.retail_end));
        if (d.lease_start) setLeasePageStart(String(d.lease_start));
        if (d.lease_end) setLeasePageEnd(String(d.lease_end));
        
        setCurrentStep('select-pages' as Step);
      } else {
        showAlert('Erreur', 'Impossible de scanner le PDF');
      }
    } catch (error: any) {
      console.error('Upload error:', error);
      showAlert('Erreur', error.response?.data?.detail || 'Erreur lors du téléversement');
    } finally {
      setUploading(false);
      setScanning(false);
    }
  };

  // Step 3: Extract selected pages (async with polling)
  const handleExtractPages = async () => {
    if (!pdfFile) {
      showAlert('Erreur', 'Aucun PDF sélectionné');
      return;
    }
    
    setExtracting(true);
    setExtractionStatus('Envoi du PDF...');
    
    try {
      // Create FormData for upload
      const formData = new FormData();
      
      // Handle file for different platforms
      if (Platform.OS === 'web') {
        const response = await fetch(pdfFile.uri);
        const blob = await response.blob();
        formData.append('file', blob, pdfFile.name);
      } else {
        formData.append('file', {
          uri: pdfFile.uri,
          type: 'application/pdf',
          name: pdfFile.name,
        } as any);
      }
      
      formData.append('password', password);
      formData.append('program_month', String(selectedMonth));
      formData.append('program_year', String(selectedYear));
      if (pageStart) formData.append('start_page', pageStart);
      if (pageEnd) formData.append('end_page', pageEnd);
      if (leasePageStart) formData.append('lease_start_page', leasePageStart);
      if (leasePageEnd) formData.append('lease_end_page', leasePageEnd);
      
      // Use async endpoint - returns immediately with task_id
      const uploadResponse = await axios.post(`${API_URL}/api/extract-pdf-async`, formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
        timeout: 30000, // 30 sec is enough for upload only
      });
      
      const taskId = uploadResponse.data.task_id;
      setExtractionStatus('Extraction en cours...');
      
      // Poll for task completion
      let attempts = 0;
      const maxAttempts = 120; // 120 * 3s = 6 minutes max
      
      while (attempts < maxAttempts) {
        await new Promise(resolve => setTimeout(resolve, 3000)); // Wait 3 seconds
        attempts++;
        
        try {
          const statusResponse = await axios.get(`${API_URL}/api/extract-task/${taskId}`, { timeout: 10000 });
          const task = statusResponse.data;
          
          // Update status message
          if (task.message) {
            setExtractionStatus(task.message);
          }
          
          if (task.status === 'complete') {
            setPrograms(task.programs || []);
            const leaseCount = task.sci_lease_count || 0;
            const leaseMsg = leaseCount > 0 ? `\n+ ${leaseCount} taux SCI Lease sauvegardés!` : '';
            setCurrentStep('preview');
            showAlert('Succès', `${(task.programs || []).length} programmes extraits avec succès!${leaseMsg}\n\n${task.message}`);
            return;
          } else if (task.status === 'error') {
            showAlert('Erreur', task.message || 'Erreur lors de l\'extraction');
            return;
          }
          // Otherwise, keep polling (status is queued/extracting/ai_processing/saving/etc.)
        } catch (pollError) {
          // Network hiccup during polling - just retry
          console.log('Poll retry...', pollError);
        }
      }
      
      // Max attempts reached
      showAlert('Info', 'L\'extraction prend plus de temps que prévu. Vérifiez votre email pour le fichier Excel.');
      
    } catch (error: any) {
      console.error('Upload error:', error);
      if (error.code === 'ECONNABORTED' || error.message?.includes('timeout')) {
        showAlert('Erreur', 'Le téléversement du PDF a pris trop de temps. Réessayez avec une connexion plus rapide.');
      } else if (error.code === 'ERR_NETWORK' || error.message?.includes('Network')) {
        showAlert('Erreur', 'Erreur réseau. Vérifiez votre connexion internet.');
      } else {
        showAlert('Erreur', error.response?.data?.detail || 'Erreur lors du téléversement.');
      }
    } finally {
      setExtracting(false);
      setExtractionStatus('');
    }
  };

  // Edit a program
  const openEditModal = (index: number) => {
    setEditingIndex(index);
    setEditProgram({ ...programs[index] });
    setEditModalVisible(true);
  };

  const saveEditedProgram = () => {
    if (editingIndex !== null && editProgram) {
      const updated = [...programs];
      updated[editingIndex] = editProgram;
      setPrograms(updated);
      setEditModalVisible(false);
      setEditProgram(null);
      setEditingIndex(null);
    }
  };

  const deleteProgram = (index: number) => {
    Alert.alert(
      'Supprimer',
      'Voulez-vous supprimer ce programme?',
      [
        { text: 'Annuler', style: 'cancel' },
        { 
          text: 'Supprimer', 
          style: 'destructive',
          onPress: () => {
            const updated = [...programs];
            updated.splice(index, 1);
            setPrograms(updated);
          }
        },
      ]
    );
  };

  // Step 3: Save programs
  const handleSavePrograms = async () => {
    if (programs.length === 0) {
      showAlert('Erreur', 'Aucun programme à sauvegarder');
      return;
    }
    
    setSaving(true);
    try {
      const response = await axios.post(`${API_URL}/api/save-programs`, {
        password: password,
        programs: programs,
        program_month: selectedMonth,
        program_year: selectedYear,
      });
      
      if (response.data.success) {
        setCurrentStep('success');
      } else {
        showAlert('Erreur', response.data.message);
      }
    } catch (error: any) {
      showAlert('Erreur', error.response?.data?.detail || 'Erreur lors de la sauvegarde');
    } finally {
      setSaving(false);
    }
  };

  const formatCurrency = (value: number) => {
    return new Intl.NumberFormat('fr-CA', {
      style: 'currency',
      currency: 'CAD',
      minimumFractionDigits: 0,
    }).format(value);
  };

  const getMonthLabel = (month: number) => {
    return months.find(m => m.value === month)?.label || '';
  };

  // Render login step
  const renderLoginStep = () => (
    <View style={styles.stepContainer}>
      <View style={styles.iconContainer}>
        <Ionicons name="lock-closed" size={60} color="#4ECDC4" />
      </View>
      <Text style={styles.stepTitle}>Accès Administrateur</Text>
      <Text style={styles.stepDescription}>
        Entrez le mot de passe pour accéder à l'import des programmes
      </Text>
      
      <TextInput
        style={styles.passwordInput}
        placeholder="Mot de passe"
        placeholderTextColor="#666"
        secureTextEntry
        value={password}
        onChangeText={setPassword}
        autoCapitalize="none"
      />
      
      <TouchableOpacity
        style={[styles.primaryButton, loading && styles.buttonDisabled]}
        onPress={handleLogin}
        disabled={loading}
      >
        {loading ? (
          <ActivityIndicator size="small" color="#1a1a2e" />
        ) : (
          <>
            <Ionicons name="log-in" size={20} color="#1a1a2e" />
            <Text style={styles.primaryButtonText}>Se connecter</Text>
          </>
        )}
      </TouchableOpacity>
    </View>
  );

  // Render choose document type step
  const renderChooseTypeStep = () => (
    <View style={styles.stepContainer}>
      <View style={styles.iconContainer}>
        <Ionicons name="folder-open" size={60} color="#4ECDC4" />
      </View>
      <Text style={styles.stepTitle}>Type de document</Text>
      <Text style={styles.stepDescription}>
        Quel document souhaitez-vous importer ce mois-ci ?
      </Text>

      <TouchableOpacity
        style={styles.docTypeCard}
        onPress={() => { setDocType('programs'); setCurrentStep('upload'); }}
        data-testid="choose-programs-btn"
      >
        <View style={styles.docTypeIconWrap}>
          <Ionicons name="calculator" size={32} color="#4ECDC4" />
        </View>
        <View style={styles.docTypeTextWrap}>
          <Text style={styles.docTypeTitle}>Programmes de financement</Text>
          <Text style={styles.docTypeDesc}>Taux Option 1 & 2, Consumer Cash, Bonus Cash</Text>
          <Text style={styles.docTypeHint}>Vous indiquerez les pages Vente et SCI Lease</Text>
        </View>
        <Ionicons name="chevron-forward" size={24} color="#4ECDC4" />
      </TouchableOpacity>

      <TouchableOpacity
        style={styles.docTypeCard}
        onPress={() => { setDocType('residuals'); setCurrentStep('residual-upload'); }}
        data-testid="choose-residuals-btn"
      >
        <View style={styles.docTypeIconWrap}>
          <Ionicons name="car-sport" size={32} color="#FFB347" />
        </View>
        <View style={styles.docTypeTextWrap}>
          <Text style={styles.docTypeTitle}>Guide des valeurs résiduelles</Text>
          <Text style={styles.docTypeDesc}>Résiduels par marque, modèle, trim, carrosserie</Text>
          <Text style={styles.docTypeHint}>Extraction automatique + email de vérification</Text>
        </View>
        <Ionicons name="chevron-forward" size={24} color="#FFB347" />
      </TouchableOpacity>
    </View>
  );

  // Handle residual guide upload
  const handleResidualUpload = async () => {
    try {
      const result = await DocumentPicker.getDocumentAsync({
        type: 'application/pdf',
        copyToCacheDirectory: true,
      });

      if (result.canceled || !result.assets?.[0]) return;

      const file = result.assets[0];
      setCurrentStep('residual-processing');

      const formDataUpload = new FormData();
      
      if (Platform.OS === 'web') {
        const response = await fetch(file.uri);
        const blob = await response.blob();
        formDataUpload.append('file', blob, file.name || 'residual_guide.pdf');
      } else {
        formDataUpload.append('file', {
          uri: file.uri,
          name: file.name || 'residual_guide.pdf',
          type: 'application/pdf',
        } as any);
      }
      
      formDataUpload.append('password', password);
      // Mois/année auto-détectés depuis le contenu du PDF

      const res = await axios.post(`${API_URL}/api/upload-residual-guide`, formDataUpload, {
        headers: { 'Content-Type': 'multipart/form-data' },
        timeout: 120000,
      });

      if (res.data.success) {
        setResidualResult(res.data);
        setCurrentStep('residual-success');
      }
    } catch (error: any) {
      const msg = error.response?.data?.detail || error.message || 'Erreur inconnue';
      Platform.OS === 'web' ? alert(`Erreur: ${msg}`) : Alert.alert('Erreur', msg);
      setCurrentStep('residual-upload');
    }
  };

  // Render residual upload step
  const renderResidualUploadStep = () => (
    <View style={styles.stepContainer}>
      <View style={styles.iconContainer}>
        <Ionicons name="car-sport" size={60} color="#FFB347" />
      </View>
      <Text style={styles.stepTitle}>Guide des résiduels SCI</Text>
      <Text style={styles.stepDescription}>
        Sélectionnez le PDF du guide des valeurs résiduelles Stellantis.
        L'extraction est automatique.
      </Text>

      <TouchableOpacity
        style={[styles.primaryButton, { backgroundColor: '#FFB347' }]}
        onPress={handleResidualUpload}
        data-testid="upload-residual-btn"
      >
        <Ionicons name="cloud-upload" size={20} color="#1a1a2e" />
        <Text style={styles.primaryButtonText}>Choisir le PDF</Text>
      </TouchableOpacity>

      <TouchableOpacity
        style={styles.secondaryButton}
        onPress={() => setCurrentStep('choose-type')}
      >
        <Ionicons name="arrow-back" size={18} color="#888" />
        <Text style={styles.secondaryButtonText}>Retour</Text>
      </TouchableOpacity>
    </View>
  );

  // Render residual processing step
  const renderResidualProcessingStep = () => (
    <View style={styles.stepContainer}>
      <View style={styles.iconContainer}>
        <ActivityIndicator size="large" color="#FFB347" />
      </View>
      <Text style={styles.stepTitle}>Extraction en cours...</Text>
      <Text style={styles.stepDescription}>
        Analyse du PDF et extraction des valeurs résiduelles.
        Cela peut prendre quelques secondes.
      </Text>
    </View>
  );

  // Render residual success step
  const renderResidualSuccessStep = () => (
    <View style={styles.stepContainer}>
      <View style={[styles.iconContainer, { backgroundColor: 'rgba(78, 205, 196, 0.15)' }]}>
        <Ionicons name="checkmark-circle" size={60} color="#4ECDC4" />
      </View>
      <Text style={styles.stepTitle}>Import réussi !</Text>

      {residualResult && (
        <View style={styles.residualSummary}>
          {/* Detected period */}
          {residualResult.detected_period && (
            <Text style={[styles.residualSummaryTitle, { color: '#FFB347', marginBottom: 8 }]}>
              {residualResult.detected_period}
            </Text>
          )}
          
          <Text style={styles.residualSummaryTitle}>
            {residualResult.total_vehicles} véhicules extraits
          </Text>
          
          {/* Changes summary */}
          {residualResult.changes && (
            <View style={{ marginTop: 10, marginBottom: 10, padding: 10, borderRadius: 8, backgroundColor: 'rgba(255,255,255,0.05)' }}>
              <Text style={{ color: '#ccc', fontSize: 13, fontWeight: '600', marginBottom: 6 }}>Comparaison :</Text>
              {residualResult.changes.modified_vehicles > 0 && (
                <Text style={{ color: '#FFB347', fontSize: 13, marginBottom: 2 }}>
                  {residualResult.changes.modified_vehicles} véhicules modifiés
                </Text>
              )}
              {residualResult.changes.new_vehicles > 0 && (
                <Text style={{ color: '#4ECDC4', fontSize: 13, marginBottom: 2 }}>
                  {residualResult.changes.new_vehicles} nouveaux véhicules
                </Text>
              )}
              {residualResult.changes.unchanged_vehicles > 0 && (
                <Text style={{ color: '#888', fontSize: 13, marginBottom: 2 }}>
                  {residualResult.changes.unchanged_vehicles} inchangés
                </Text>
              )}
            </View>
          )}
          
          {/* KM adjustments info */}
          {residualResult.km_adjustments && (
            <View style={{ marginBottom: 10, padding: 8, borderRadius: 8, backgroundColor: 'rgba(78,205,196,0.1)' }}>
              <Text style={{ color: '#4ECDC4', fontSize: 12, fontWeight: '600' }}>
                Ajustements km : 12k/60m = +{residualResult.km_adjustments['12k_60mo']}% | 18k/60m = +{residualResult.km_adjustments['18k_60mo']}%
              </Text>
            </View>
          )}

          {residualResult.brands && Object.entries(residualResult.brands).map(([brand, count]: [string, any]) => (
            <View key={brand} style={styles.residualBrandRow}>
              <Text style={styles.residualBrandName}>{brand}</Text>
              <Text style={styles.residualBrandCount}>{count}</Text>
            </View>
          ))}
          <View style={styles.residualEmailStatus}>
            <Ionicons 
              name={residualResult.email_sent ? "mail" : "mail-unread"} 
              size={18} 
              color={residualResult.email_sent ? "#4ECDC4" : "#888"} 
            />
            <Text style={[styles.residualEmailText, { color: residualResult.email_sent ? "#4ECDC4" : "#888" }]}>
              {residualResult.email_sent 
                ? "Email de vérification envoyé avec fichier Excel" 
                : "Email non envoyé (SMTP non configuré)"}
            </Text>
          </View>
        </View>
      )}

      <TouchableOpacity
        style={styles.primaryButton}
        onPress={() => { setCurrentStep('choose-type'); setResidualResult(null); }}
      >
        <Ionicons name="add-circle" size={20} color="#1a1a2e" />
        <Text style={styles.primaryButtonText}>Importer un autre document</Text>
      </TouchableOpacity>

      <TouchableOpacity
        style={styles.secondaryButton}
        onPress={() => router.back()}
      >
        <Ionicons name="home" size={18} color="#888" />
        <Text style={styles.secondaryButtonText}>Retour au calculateur</Text>
      </TouchableOpacity>
    </View>
  );

  // Render upload step
  const renderUploadStep = () => (
    <View style={styles.stepContainer}>
      <View style={styles.iconContainer}>
        <Ionicons name="document-text" size={60} color="#4ECDC4" />
      </View>
      <Text style={styles.stepTitle}>Importer le PDF</Text>
      <Text style={styles.stepDescription}>
        Sélectionnez la période et uploadez le PDF des programmes de financement
      </Text>
      
      {/* Period Selection */}
      <View style={styles.periodSection}>
        <Text style={styles.periodLabel}>Période du programme</Text>
        <View style={styles.periodRow}>
          <ScrollView horizontal showsHorizontalScrollIndicator={false} style={styles.monthScroll}>
            <View style={styles.monthButtons}>
              {months.map(m => (
                <TouchableOpacity
                  key={m.value}
                  style={[
                    styles.monthButton,
                    selectedMonth === m.value && styles.monthButtonActive
                  ]}
                  onPress={() => setSelectedMonth(m.value)}
                >
                  <Text style={[
                    styles.monthButtonText,
                    selectedMonth === m.value && styles.monthButtonTextActive
                  ]}>
                    {m.label.substring(0, 3)}
                  </Text>
                </TouchableOpacity>
              ))}
            </View>
          </ScrollView>
        </View>
        
        <View style={styles.yearRow}>
          <Text style={styles.yearLabel}>Année:</Text>
          <TextInput
            style={styles.yearInput}
            value={String(selectedYear)}
            onChangeText={(v) => setSelectedYear(parseInt(v) || new Date().getFullYear())}
            keyboardType="numeric"
          />
        </View>
      </View>
      
      <TouchableOpacity
        style={[styles.uploadButton, uploading && styles.buttonDisabled]}
        onPress={handlePickPDF}
        disabled={uploading}
      >
        {uploading ? (
          <View style={styles.extractingContainer}>
            <ActivityIndicator size="large" color="#4ECDC4" />
            <Text style={styles.extractingText}>Chargement du PDF...</Text>
          </View>
        ) : (
          <>
            <Ionicons name="document" size={40} color="#1a1a2e" />
            <Text style={styles.uploadButtonText}>Sélectionner le PDF</Text>
            <Text style={styles.uploadButtonSubtext}>Cliquez pour choisir un fichier</Text>
          </>
        )}
      </TouchableOpacity>
    </View>
  );

  // Render Step: Select Pages
  const renderSelectPagesStep = () => (
    <View style={styles.stepContainer}>
      <Text style={styles.stepTitle}>Sélectionner les pages</Text>
      <Text style={styles.stepDescription}>
        Le PDF "{pdfFileName}" contient {totalPages} pages
      </Text>
      
      {/* Auto-detection banner */}
      {detectedSections && (
        <View style={{ backgroundColor: '#1a3a2a', borderRadius: 12, padding: 16, marginBottom: 16, borderWidth: 1, borderColor: '#4ECDC4' }}>
          <View style={{ flexDirection: 'row', alignItems: 'center', marginBottom: 8 }}>
            <Ionicons name="checkmark-circle" size={20} color="#4ECDC4" />
            <Text style={{ color: '#4ECDC4', fontWeight: '700', fontSize: 14, marginLeft: 8 }}>
              Sections auto-detectees
            </Text>
          </View>
          <Text style={{ color: '#ccc', fontSize: 12, lineHeight: 18 }}>
            {detectedSections.retail_start ? `Finance Prime: pages ${detectedSections.retail_start}-${detectedSections.retail_end}` : 'Finance Prime: non detecte'}
            {'\n'}
            {detectedSections.lease_start ? `SCI Lease: pages ${detectedSections.lease_start}-${detectedSections.lease_end}` : 'SCI Lease: non detecte'}
            {detectedSections.non_prime_start ? `\nNon-Prime: pages ${detectedSections.non_prime_start}-${detectedSections.non_prime_end}` : ''}
            {detectedSections.key_incentive_pages?.length ? `\nKey Incentives: pages ${detectedSections.key_incentive_pages.join(', ')}` : ''}
          </Text>
        </View>
      )}
      
      {/* Page Selection - Retail */}
      <View style={styles.periodSection}>
        <Text style={styles.periodLabel}>Programme Retail (Financement)</Text>
        <Text style={styles.pageHint}>Pages contenant les taux Option 1 & 2 + Consumer Cash</Text>
        <View style={styles.pageRow}>
          <View style={styles.pageField}>
            <Text style={styles.pageLabel}>De la page:</Text>
            <TextInput
              style={styles.pageInput}
              value={pageStart}
              onChangeText={setPageStart}
              keyboardType="numeric"
              placeholder="auto"
              placeholderTextColor="#666"
            />
          </View>
          <View style={styles.pageField}>
            <Text style={styles.pageLabel}>A la page:</Text>
            <TextInput
              style={styles.pageInput}
              value={pageEnd}
              onChangeText={setPageEnd}
              keyboardType="numeric"
              placeholder="auto"
              placeholderTextColor="#666"
            />
          </View>
        </View>
      </View>
      
      {/* Page Selection - SCI Lease */}
      <View style={[styles.periodSection, { borderColor: '#FFB347' }]}>
        <Text style={[styles.periodLabel, { color: '#FFB347' }]}>Programme SCI Lease (Location)</Text>
        <Text style={styles.pageHint}>Pages contenant les taux location + Lease Cash / Bonus Cash</Text>
        <View style={styles.pageRow}>
          <View style={styles.pageField}>
            <Text style={styles.pageLabel}>De la page:</Text>
            <TextInput
              style={[styles.pageInput, { borderColor: '#FFB347' }]}
              value={leasePageStart}
              onChangeText={setLeasePageStart}
              keyboardType="numeric"
              placeholder="auto"
              placeholderTextColor="#666"
            />
          </View>
          <View style={styles.pageField}>
            <Text style={styles.pageLabel}>A la page:</Text>
            <TextInput
              style={[styles.pageInput, { borderColor: '#FFB347' }]}
              value={leasePageEnd}
              onChangeText={setLeasePageEnd}
              keyboardType="numeric"
              placeholder="auto"
              placeholderTextColor="#666"
            />
          </View>
        </View>
      </View>
      
      <Text style={styles.pageValidation}>
        Retail: pages {pageStart || 'auto'}-{pageEnd || 'auto'}  |  SCI Lease: pages {leasePageStart || 'auto'}-{leasePageEnd || 'auto'}
      </Text>
      
      <TouchableOpacity
        style={[styles.extractButton, extracting && styles.buttonDisabled]}
        onPress={handleExtractPages}
        disabled={extracting}
      >
        {extracting ? (
          <View style={styles.extractingContainer}>
            <ActivityIndicator size="large" color="#4ECDC4" />
            <Text style={styles.extractingText}>{extractionStatus || 'Extraction en cours...'}</Text>
            <Text style={styles.extractingSubtext}>Retail: pages {pageStart}-{pageEnd} | SCI Lease: pages {leasePageStart}-{leasePageEnd}</Text>
            <Text style={styles.extractingWait}>Veuillez patienter (2-4 minutes)</Text>
          </View>
        ) : (
          <>
            <Ionicons name="analytics" size={24} color="#fff" />
            <Text style={styles.extractButtonText}>
              Extraire les programmes
            </Text>
          </>
        )}
      </TouchableOpacity>
      
      {/* Change PDF button */}
      <TouchableOpacity
        style={styles.changePdfButton}
        onPress={() => {
          setPdfFile(null);
          setPdfFileName('');
          setTotalPages(0);
          setCurrentStep('upload');
        }}
        disabled={extracting}
      >
        <Text style={styles.changePdfButtonText}>← Changer de PDF</Text>
      </TouchableOpacity>
    </View>
  );

  // Original upload step render (now simplified)
  const renderUploadStepOld = () => (
    <View style={styles.stepContainer}>
      <Text style={styles.stepTitle}>Importer le PDF</Text>
      <Text style={styles.stepDescription}>
        Sélectionnez la période et uploadez le PDF des programmes de financement
      </Text>
      
      {/* Period Selection */}
      <View style={styles.periodSection}>
        <Text style={styles.periodLabel}>Période du programme</Text>
        <View style={styles.periodRow}>
          <ScrollView horizontal showsHorizontalScrollIndicator={false} style={styles.monthScroll}>
            <View style={styles.monthButtons}>
              {months.map(m => (
                <TouchableOpacity
                  key={m.value}
                  style={[
                    styles.monthButton,
                    selectedMonth === m.value && styles.monthButtonActive
                  ]}
                  onPress={() => setSelectedMonth(m.value)}
                >
                  <Text style={[
                    styles.monthButtonText,
                    selectedMonth === m.value && styles.monthButtonTextActive
                  ]}>
                    {m.label.substring(0, 3)}
                  </Text>
                </TouchableOpacity>
              ))}
            </View>
          </ScrollView>
        </View>
        
        <View style={styles.yearRow}>
          <Text style={styles.yearLabel}>Année:</Text>
          <TextInput
            style={styles.yearInput}
            value={String(selectedYear)}
            onChangeText={(v) => setSelectedYear(parseInt(v) || new Date().getFullYear())}
            keyboardType="numeric"
          />
        </View>
      </View>
      
      {/* Page Selection */}
      <View style={styles.periodSection}>
        <Text style={styles.periodLabel}>Pages du PDF à extraire</Text>
        <Text style={styles.pageHint}>Ex: Pages 20-21 pour les programmes Retail</Text>
        <View style={styles.pageRow}>
          <View style={styles.pageField}>
            <Text style={styles.pageLabel}>De la page:</Text>
            <TextInput
              style={styles.pageInput}
              value={pageStart}
              onChangeText={setPageStart}
              keyboardType="numeric"
              placeholder="20"
              placeholderTextColor="#666"
            />
          </View>
          <View style={styles.pageField}>
            <Text style={styles.pageLabel}>À la page:</Text>
            <TextInput
              style={styles.pageInput}
              value={pageEnd}
              onChangeText={setPageEnd}
              keyboardType="numeric"
              placeholder="21"
              placeholderTextColor="#666"
            />
          </View>
        </View>
      </View>
      
      <TouchableOpacity
        style={[styles.uploadButton, extracting && styles.buttonDisabled]}
        onPress={handlePickPDF}
        disabled={extracting}
      >
        {extracting ? (
          <View style={styles.extractingContainer}>
            <ActivityIndicator size="large" color="#4ECDC4" />
            <Text style={styles.extractingText}>{extractionStatus || 'Extraction en cours...'}</Text>
            <Text style={styles.extractingSubtext}>Pages {pageStart} à {pageEnd}</Text>
            <Text style={styles.extractingWait}>Veuillez patienter (2-4 minutes)</Text>
          </View>
        ) : (
          <>
            <Ionicons name="cloud-upload" size={40} color="#1a1a2e" />
            <Text style={styles.uploadButtonText}>Sélectionner le PDF</Text>
            <Text style={styles.uploadButtonSubtext}>Pages {pageStart} à {pageEnd} seront analysées</Text>
          </>
        )}
      </TouchableOpacity>
    </View>
  );

  // Render preview step
  const renderPreviewStep = () => (
    <View style={styles.previewContainer}>
      <View style={styles.previewHeader}>
        <Text style={styles.previewTitle}>
          Programmes extraits ({programs.length})
        </Text>
        <Text style={styles.previewPeriod}>
          {getMonthLabel(selectedMonth)} {selectedYear}
        </Text>
      </View>
      
      <Text style={styles.previewInstructions}>
        Vérifiez et modifiez les données ci-dessous avant de sauvegarder
      </Text>
      
      <ScrollView style={styles.programsList}>
        {programs.map((prog, index) => (
          <View key={index} style={styles.programCard}>
            <View style={styles.programCardHeader}>
              <View style={styles.programCardInfo}>
                <Text style={styles.programBrand}>{prog.brand}</Text>
                <Text style={styles.programModel}>
                  {prog.model} {prog.trim || ''} {prog.year}
                </Text>
              </View>
              <View style={styles.programCardActions}>
                <TouchableOpacity 
                  style={styles.editButton}
                  onPress={() => openEditModal(index)}
                >
                  <Ionicons name="pencil" size={18} color="#4ECDC4" />
                </TouchableOpacity>
                <TouchableOpacity 
                  style={styles.deleteButton}
                  onPress={() => deleteProgram(index)}
                >
                  <Ionicons name="trash" size={18} color="#FF6B6B" />
                </TouchableOpacity>
              </View>
            </View>
            
            <View style={styles.programCardDetails}>
              <View style={styles.programDetailRow}>
                <Text style={styles.programDetailLabel}>Consumer Cash:</Text>
                <Text style={styles.programDetailValue}>
                  {formatCurrency(prog.consumer_cash)}
                </Text>
              </View>
              <View style={styles.programDetailRow}>
                <Text style={styles.programDetailLabel}>Bonus Cash:</Text>
                <Text style={styles.programDetailValue}>
                  {formatCurrency(prog.bonus_cash)}
                </Text>
              </View>
              <View style={styles.programDetailRow}>
                <Text style={styles.programDetailLabel}>Option 1:</Text>
                <Text style={prog.option1_rates ? styles.programDetailValue : styles.programDetailNA}>
                  {prog.option1_rates 
                    ? `${prog.option1_rates.rate_36}% - ${prog.option1_rates.rate_96}%`
                    : 'N/A'}
                </Text>
              </View>
              <View style={styles.programDetailRow}>
                <Text style={styles.programDetailLabel}>Option 2:</Text>
                <Text style={prog.option2_rates ? styles.programDetailValue : styles.programDetailNA}>
                  {prog.option2_rates 
                    ? `${prog.option2_rates.rate_36}% - ${prog.option2_rates.rate_96}%`
                    : 'N/A'}
                </Text>
              </View>
            </View>
          </View>
        ))}
      </ScrollView>
      
      <View style={styles.previewActions}>
        <TouchableOpacity
          style={styles.backButton}
          onPress={() => setCurrentStep('upload')}
        >
          <Ionicons name="arrow-back" size={20} color="#fff" />
          <Text style={styles.backButtonText}>Retour</Text>
        </TouchableOpacity>
        
        <TouchableOpacity
          style={[styles.saveButton, saving && styles.buttonDisabled]}
          onPress={handleSavePrograms}
          disabled={saving}
        >
          {saving ? (
            <ActivityIndicator size="small" color="#1a1a2e" />
          ) : (
            <>
              <Ionicons name="checkmark-circle" size={20} color="#1a1a2e" />
              <Text style={styles.saveButtonText}>Approuver et Sauvegarder</Text>
            </>
          )}
        </TouchableOpacity>
      </View>
    </View>
  );

  // Render success step
  const renderSuccessStep = () => (
    <View style={styles.stepContainer}>
      <View style={[styles.iconContainer, styles.successIcon]}>
        <Ionicons name="checkmark-circle" size={80} color="#4ECDC4" />
      </View>
      <Text style={styles.stepTitle}>Programmes sauvegardés!</Text>
      <Text style={styles.stepDescription}>
        {programs.length} programmes ont été ajoutés pour {getMonthLabel(selectedMonth)} {selectedYear}
      </Text>
      <Text style={styles.successNote}>
        Les utilisateurs de l'application verront automatiquement les nouveaux programmes.
      </Text>
      
      <TouchableOpacity
        style={styles.primaryButton}
        onPress={() => router.replace('/')}
      >
        <Ionicons name="home" size={20} color="#1a1a2e" />
        <Text style={styles.primaryButtonText}>Retour à l'accueil</Text>
      </TouchableOpacity>
    </View>
  );

  // Render email sent step (when timeout but email was likely sent)
  const renderEmailSentStep = () => (
    <View style={styles.stepContainer}>
      <View style={[styles.iconContainer, styles.successIcon]}>
        <Ionicons name="checkmark-circle" size={80} color="#4ECDC4" />
      </View>
      <Text style={styles.stepTitle}>Importation reussie!</Text>
      <Text style={styles.stepDescription}>
        Les pages {pageStart || '1'} a {pageEnd || totalPages} ont ete extraites et sauvegardees.
      </Text>
      <Text style={styles.successNote}>
        {'\u2705'} Programmes sauvegardes dans la base de donnees
      </Text>
      <Text style={styles.successNote}>
        {'\uD83D\uDCE7'} Fichier Excel envoye a votre email pour verification
      </Text>
      <Text style={styles.emailSentNote}>
        Verifiez l'Excel recu par email. Si des corrections sont necessaires, passez a l'etape suivante.
      </Text>
      
      <TouchableOpacity
        style={[styles.primaryButton, { backgroundColor: '#FFD700' }]}
        onPress={() => setCurrentStep('excel-correction')}
      >
        <Ionicons name="document-text" size={20} color="#1a1a2e" />
        <Text style={styles.primaryButtonText}>Corriger et importer l'Excel final</Text>
      </TouchableOpacity>

      <TouchableOpacity
        style={[styles.primaryButton, { backgroundColor: '#4ECDC4', marginTop: 12 }]}
        onPress={() => {
          if (Platform.OS === 'web') {
            window.open(`${API_URL}/api/programs/export-excel`, '_blank');
          }
        }}
      >
        <Ionicons name="download" size={20} color="#1a1a2e" />
        <Text style={styles.primaryButtonText}>Telecharger l'Excel</Text>
      </TouchableOpacity>
      
      <TouchableOpacity
        style={[styles.primaryButton, { backgroundColor: '#2d2d44', marginTop: 12 }]}
        onPress={() => router.replace('/')}
      >
        <Ionicons name="home" size={20} color="#fff" />
        <Text style={[styles.primaryButtonText, { color: '#fff' }]}>Retour a l'accueil</Text>
      </TouchableOpacity>
    </View>
  );

  // Excel correction handler
  const handleExcelCorrection = async (event: any) => {
    const file = event?.target?.files?.[0];
    if (!file) return;
    
    setExcelImporting(true);
    setExcelResult(null);
    try {
      const formData = new FormData();
      formData.append('file', file);
      formData.append('password', password);

      const response = await axios.post(`${API_URL}/api/programs/import-excel`, formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
        timeout: 60000,
      });

      const data = response.data;
      setExcelResult(`${data.updated} programmes mis a jour, ${data.corrections_saved} corrections memorisees`);
    } catch (e: any) {
      setExcelResult('Erreur: ' + (e.response?.data?.detail || e.message || 'inconnu'));
    } finally {
      setExcelImporting(false);
      if (excelFileRef.current) excelFileRef.current.value = '';
    }
  };

  // Render Excel correction step
  const renderExcelCorrectionStep = () => (
    <View style={styles.stepContainer}>
      <View style={[styles.iconContainer, { backgroundColor: 'rgba(255,215,0,0.15)' }]}>
        <Ionicons name="create" size={60} color="#FFD700" />
      </View>
      <Text style={styles.stepTitle}>Excel final - Source de verite</Text>
      <Text style={styles.stepDescription}>
        Importez le fichier Excel corrige. Les valeurs corrigees remplaceront les donnees actuelles
        et seront memorisees pour les prochains imports PDF.
      </Text>

      <TouchableOpacity
        style={[styles.primaryButton, { backgroundColor: '#4ECDC4', marginBottom: 20 }]}
        onPress={() => {
          if (Platform.OS === 'web') {
            window.open(`${API_URL}/api/programs/export-excel`, '_blank');
          }
        }}
      >
        <Ionicons name="download" size={20} color="#1a1a2e" />
        <Text style={styles.primaryButtonText}>Telecharger l'Excel actuel</Text>
      </TouchableOpacity>

      <View style={{ backgroundColor: '#2d2d44', borderRadius: 12, padding: 20, width: '100%', marginBottom: 20 }}>
        <Text style={{ color: '#FFD700', fontSize: 16, fontWeight: '700', marginBottom: 12, textAlign: 'center' }}>
          Importer le fichier corrige
        </Text>

        {Platform.OS === 'web' && (
          <input
            ref={(el: any) => { excelFileRef.current = el; }}
            type="file"
            accept=".xlsx,.xls"
            style={{ display: 'none' }}
            onChange={handleExcelCorrection}
          />
        )}

        <TouchableOpacity
          style={{
            backgroundColor: excelImporting ? '#555' : '#FFD700',
            borderRadius: 8, paddingVertical: 16, alignItems: 'center',
            opacity: excelImporting ? 0.7 : 1,
          }}
          onPress={() => {
            if (Platform.OS === 'web' && excelFileRef.current) {
              excelFileRef.current.click();
            }
          }}
          disabled={excelImporting}
        >
          {excelImporting ? (
            <ActivityIndicator size="small" color="#1a1a2e" />
          ) : (
            <View style={{ flexDirection: 'row', alignItems: 'center' }}>
              <Ionicons name="cloud-upload" size={20} color="#1a1a2e" />
              <Text style={{ color: '#1a1a2e', fontWeight: '700', fontSize: 16, marginLeft: 8 }}>
                Choisir le fichier Excel
              </Text>
            </View>
          )}
        </TouchableOpacity>
      </View>

      {excelResult && (
        <View style={{
          backgroundColor: excelResult.startsWith('Erreur') ? 'rgba(255,107,107,0.15)' : 'rgba(78,205,196,0.15)',
          borderRadius: 8, padding: 16, width: '100%', marginBottom: 16,
          borderWidth: 1, borderColor: excelResult.startsWith('Erreur') ? '#FF6B6B' : '#4ECDC4',
        }}>
          <Text style={{ color: excelResult.startsWith('Erreur') ? '#FF6B6B' : '#4ECDC4', fontSize: 14, textAlign: 'center' }}>
            {excelResult}
          </Text>
        </View>
      )}

      <View style={{ backgroundColor: '#2d2d44', borderRadius: 8, padding: 14, width: '100%', marginBottom: 16 }}>
        <Text style={{ color: '#aaa', fontSize: 12, lineHeight: 18 }}>
          {'\u2022'} NE PAS modifier la colonne ID{'\n'}
          {'\u2022'} Col F: Consumer Cash (Opt 1, avant taxes){'\n'}
          {'\u2022'} Col N: Rabais Alt. Cash (Opt 2, avant taxes){'\n'}
          {'\u2022'} Bonus Cash = 0 sauf Fiat 500e ($5,000){'\n'}
          {'\u2022'} Les corrections sont memorisees pour les futurs PDF
        </Text>
      </View>

      {/* ============ LEASE SCI SECTION ============ */}
      <View style={{ backgroundColor: '#2d2d44', borderRadius: 12, padding: 20, width: '100%', marginBottom: 20 }}>
        <View style={{ flexDirection: 'row', alignItems: 'center', marginBottom: 12 }}>
          <Ionicons name="car-sport" size={24} color="#FF6B6B" />
          <Text style={{ color: '#fff', fontSize: 18, fontWeight: '700', marginLeft: 10 }}>
            Taux Location SCI
          </Text>
        </View>

        <TouchableOpacity
          style={{ backgroundColor: '#FF6B6B', borderRadius: 8, paddingVertical: 14, alignItems: 'center', marginBottom: 10 }}
          onPress={() => {
            if (Platform.OS === 'web') {
              window.open(`${API_URL}/api/sci/export-excel`, '_blank');
            }
          }}
        >
          <Text style={{ color: '#fff', fontWeight: '700', fontSize: 15 }}>Telecharger Excel Lease SCI</Text>
        </TouchableOpacity>

        {Platform.OS === 'web' && (
          <input
            ref={(el: any) => { (window as any).__sciImportRef = el; }}
            type="file"
            accept=".xlsx,.xls"
            style={{ display: 'none' }}
            onChange={async (event: any) => {
              const file = event?.target?.files?.[0];
              if (!file) return;
              setExcelImporting(true);
              setExcelResult(null);
              try {
                const formData = new FormData();
                formData.append('file', file);
                formData.append('password', password);
                const response = await axios.post(`${API_URL}/api/sci/import-excel`, formData, {
                  headers: { 'Content-Type': 'multipart/form-data' },
                  timeout: 60000,
                });
                setExcelResult(`SCI: ${response.data.message}`);
              } catch (e: any) {
                setExcelResult('Erreur SCI: ' + (e.response?.data?.detail || e.message));
              } finally {
                setExcelImporting(false);
                if ((window as any).__sciImportRef) (window as any).__sciImportRef.value = '';
              }
            }}
          />
        )}

        <TouchableOpacity
          style={{
            backgroundColor: excelImporting ? '#555' : '#FFD700', borderRadius: 8,
            paddingVertical: 14, alignItems: 'center', opacity: excelImporting ? 0.7 : 1,
          }}
          onPress={() => {
            if (Platform.OS === 'web' && (window as any).__sciImportRef) (window as any).__sciImportRef.click();
          }}
          disabled={excelImporting}
        >
          {excelImporting ? (
            <ActivityIndicator size="small" color="#1a1a2e" />
          ) : (
            <Text style={{ color: '#1a1a2e', fontWeight: '700', fontSize: 15 }}>Importer Excel Lease corrige</Text>
          )}
        </TouchableOpacity>
      </View>

      <TouchableOpacity
        style={[styles.primaryButton, { backgroundColor: '#2d2d44' }]}
        onPress={() => router.replace('/')}
      >
        <Ionicons name="home" size={20} color="#fff" />
        <Text style={[styles.primaryButtonText, { color: '#fff' }]}>Retour a l'accueil</Text>
      </TouchableOpacity>
    </View>
  );

  // Edit modal
  const renderEditModal = () => (
    <Modal
      visible={editModalVisible}
      transparent
      animationType="slide"
      onRequestClose={() => setEditModalVisible(false)}
    >
      <View style={styles.modalOverlay}>
        <View style={styles.modalContent}>
          <View style={styles.modalHeader}>
            <Text style={styles.modalTitle}>Modifier le programme</Text>
            <TouchableOpacity onPress={() => setEditModalVisible(false)}>
              <Ionicons name="close" size={24} color="#aaa" />
            </TouchableOpacity>
          </View>
          
          {editProgram && (
            <ScrollView style={styles.modalBody}>
              <View style={styles.formRow}>
                <View style={styles.formField}>
                  <Text style={styles.formLabel}>Marque</Text>
                  <TextInput
                    style={styles.formInput}
                    value={editProgram.brand}
                    onChangeText={(v) => setEditProgram({...editProgram, brand: v})}
                  />
                </View>
                <View style={styles.formField}>
                  <Text style={styles.formLabel}>Modèle</Text>
                  <TextInput
                    style={styles.formInput}
                    value={editProgram.model}
                    onChangeText={(v) => setEditProgram({...editProgram, model: v})}
                  />
                </View>
              </View>
              
              <View style={styles.formRow}>
                <View style={styles.formField}>
                  <Text style={styles.formLabel}>Trim</Text>
                  <TextInput
                    style={styles.formInput}
                    value={editProgram.trim || ''}
                    onChangeText={(v) => setEditProgram({...editProgram, trim: v || null})}
                  />
                </View>
                <View style={styles.formFieldSmall}>
                  <Text style={styles.formLabel}>Année</Text>
                  <TextInput
                    style={styles.formInput}
                    value={String(editProgram.year)}
                    onChangeText={(v) => setEditProgram({...editProgram, year: parseInt(v) || 2026})}
                    keyboardType="numeric"
                  />
                </View>
              </View>
              
              <View style={styles.formRow}>
                <View style={styles.formField}>
                  <Text style={styles.formLabel}>Consumer Cash ($)</Text>
                  <TextInput
                    style={styles.formInput}
                    value={String(editProgram.consumer_cash)}
                    onChangeText={(v) => setEditProgram({...editProgram, consumer_cash: parseFloat(v) || 0})}
                    keyboardType="numeric"
                  />
                </View>
                <View style={styles.formField}>
                  <Text style={styles.formLabel}>Bonus Cash ($)</Text>
                  <TextInput
                    style={styles.formInput}
                    value={String(editProgram.bonus_cash)}
                    onChangeText={(v) => setEditProgram({...editProgram, bonus_cash: parseFloat(v) || 0})}
                    keyboardType="numeric"
                  />
                </View>
              </View>
              
              <Text style={styles.ratesTitle}>Taux Option 1 (%)</Text>
              {editProgram.option1_rates ? (
              <View style={styles.ratesGrid}>
                {['36', '48', '60', '72', '84', '96'].map((term) => (
                  <View key={`o1-${term}`} style={styles.rateField}>
                    <Text style={styles.rateLabel}>{term}m</Text>
                    <TextInput
                      style={styles.rateInput}
                      value={String(editProgram.option1_rates![`rate_${term}` as keyof RatesData])}
                      onChangeText={(v) => setEditProgram({
                        ...editProgram,
                        option1_rates: {
                          ...editProgram.option1_rates!,
                          [`rate_${term}`]: parseFloat(v) || 0
                        }
                      })}
                      keyboardType="decimal-pad"
                    />
                  </View>
                ))}
              </View>
              ) : (
                <Text style={styles.programDetailNA}>Option 1 non disponible</Text>
              )}
              
              <View style={styles.option2Toggle}>
                <TouchableOpacity
                  style={styles.option2ToggleBtn}
                  onPress={() => setEditProgram({
                    ...editProgram,
                    option2_rates: editProgram.option2_rates 
                      ? null 
                      : { rate_36: 0, rate_48: 0, rate_60: 0, rate_72: 1.49, rate_84: 1.99, rate_96: 3.49 }
                  })}
                >
                  <Ionicons
                    name={editProgram.option2_rates ? 'checkbox' : 'square-outline'}
                    size={24}
                    color="#4ECDC4"
                  />
                  <Text style={styles.option2ToggleText}>Option 2 disponible</Text>
                </TouchableOpacity>
              </View>
              
              {editProgram.option2_rates && (
                <>
                  <Text style={styles.ratesTitle}>Taux Option 2 (%)</Text>
                  <View style={styles.ratesGrid}>
                    {['36', '48', '60', '72', '84', '96'].map((term) => (
                      <View key={`o2-${term}`} style={styles.rateField}>
                        <Text style={styles.rateLabel}>{term}m</Text>
                        <TextInput
                          style={styles.rateInput}
                          value={String(editProgram.option2_rates![`rate_${term}` as keyof RatesData])}
                          onChangeText={(v) => setEditProgram({
                            ...editProgram,
                            option2_rates: {
                              ...editProgram.option2_rates!,
                              [`rate_${term}`]: parseFloat(v) || 0
                            }
                          })}
                          keyboardType="decimal-pad"
                        />
                      </View>
                    ))}
                  </View>
                </>
              )}
            </ScrollView>
          )}
          
          <TouchableOpacity
            style={styles.modalSaveButton}
            onPress={saveEditedProgram}
          >
            <Ionicons name="checkmark" size={20} color="#1a1a2e" />
            <Text style={styles.modalSaveButtonText}>Sauvegarder les modifications</Text>
          </TouchableOpacity>
        </View>
      </View>
    </Modal>
  );

  return (
    <SafeAreaView style={styles.container}>
      <KeyboardAvoidingView
        style={styles.flex}
        behavior={Platform.OS === 'ios' ? 'padding' : 'height'}
      >
        {/* Header */}
        <View style={styles.header}>
          <TouchableOpacity onPress={() => router.back()} style={styles.headerBackButton}>
            <Ionicons name="arrow-back" size={24} color="#fff" />
          </TouchableOpacity>
          <View>
            <Text style={styles.headerTitle}>Import PDF</Text>
            <Text style={styles.headerSubtitle}>
              {currentStep === 'login' ? 'Authentification' : 
               currentStep === 'choose-type' ? 'Type de document' :
               currentStep === 'upload' ? 'Programmes de financement' :
               currentStep === 'select-pages' ? 'Choix des pages' :
               currentStep === 'preview' ? 'Verification des donnees' :
               currentStep === 'email-sent' ? 'Extraction terminee' :
               currentStep === 'excel-correction' ? 'Excel final - Verite' :
               currentStep === 'success' ? 'Termine' :
               currentStep === 'residual-upload' ? 'Guide des residuels' :
               currentStep === 'residual-processing' ? 'Traitement en cours...' :
               currentStep === 'residual-success' ? 'Termine' : ''}
            </Text>
          </View>
        </View>

        {/* Progress Steps - adapts to flow */}
        <View style={styles.progressContainer}>
          {(docType === 'residuals' 
            ? ['login', 'choose-type', 'residual-upload', 'residual-success']
            : ['login', 'choose-type', 'upload', 'email-sent', 'excel-correction']
          ).map((step, index) => {
            const allSteps = docType === 'residuals'
              ? ['login', 'choose-type', 'residual-upload', 'residual-processing', 'residual-success']
              : ['login', 'choose-type', 'upload', 'select-pages', 'preview', 'email-sent', 'excel-correction', 'success'];
            const currentIndex = allSteps.indexOf(currentStep);
            const stepIndex = allSteps.indexOf(step);
            const isActive = currentStep === step || (step === 'residual-upload' && currentStep === 'residual-processing');
            const isCompleted = currentIndex > stepIndex;
            
            return (
              <View key={step} style={styles.progressStep}>
                <View style={[
                  styles.progressDot,
                  isActive && styles.progressDotActive,
                  isCompleted && styles.progressDotCompleted
                ]} />
                {index < 4 ? <View style={[
                  styles.progressLine,
                  isCompleted && styles.progressLineCompleted
                ]} /> : null}
              </View>
            );
          })}
        </View>

        <ScrollView
          style={styles.scrollView}
          contentContainerStyle={styles.scrollContent}
          keyboardShouldPersistTaps="handled"
        >
          {currentStep === 'login' ? renderLoginStep() : null}
          {currentStep === 'choose-type' ? renderChooseTypeStep() : null}
          {currentStep === 'upload' ? renderUploadStep() : null}
          {currentStep === 'select-pages' ? renderSelectPagesStep() : null}
          {currentStep === 'preview' ? renderPreviewStep() : null}
          {currentStep === 'email-sent' ? renderEmailSentStep() : null}
          {currentStep === 'excel-correction' ? renderExcelCorrectionStep() : null}
          {currentStep === 'success' ? renderSuccessStep() : null}
          {currentStep === 'residual-upload' ? renderResidualUploadStep() : null}
          {currentStep === 'residual-processing' ? renderResidualProcessingStep() : null}
          {currentStep === 'residual-success' ? renderResidualSuccessStep() : null}
        </ScrollView>
        
        {renderEditModal()}
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#1a1a2e',
  },
  flex: {
    flex: 1,
  },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: 16,
    paddingVertical: 12,
    borderBottomWidth: 1,
    borderBottomColor: '#2d2d44',
    gap: 12,
  },
  headerBackButton: {
    padding: 4,
  },
  headerTitle: {
    fontSize: 18,
    fontWeight: 'bold',
    color: '#fff',
  },
  headerSubtitle: {
    fontSize: 12,
    color: '#4ECDC4',
    marginTop: 2,
  },
  progressContainer: {
    flexDirection: 'row',
    justifyContent: 'center',
    alignItems: 'center',
    paddingVertical: 16,
    paddingHorizontal: 40,
  },
  progressStep: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  progressDot: {
    width: 12,
    height: 12,
    borderRadius: 6,
    backgroundColor: '#2d2d44',
  },
  progressDotActive: {
    backgroundColor: '#4ECDC4',
    transform: [{ scale: 1.3 }],
  },
  progressDotCompleted: {
    backgroundColor: '#4ECDC4',
  },
  progressLine: {
    width: 60,
    height: 2,
    backgroundColor: '#2d2d44',
  },
  progressLineCompleted: {
    backgroundColor: '#4ECDC4',
  },
  scrollView: {
    flex: 1,
  },
  scrollContent: {
    padding: 16,
    paddingBottom: 40,
  },
  stepContainer: {
    alignItems: 'center',
    paddingVertical: 20,
  },
  iconContainer: {
    width: 120,
    height: 120,
    borderRadius: 60,
    backgroundColor: '#2d2d44',
    alignItems: 'center',
    justifyContent: 'center',
    marginBottom: 24,
  },
  successIcon: {
    backgroundColor: 'rgba(78, 205, 196, 0.2)',
  },
  stepTitle: {
    fontSize: 24,
    fontWeight: 'bold',
    color: '#fff',
    marginBottom: 12,
    textAlign: 'center',
  },
  stepDescription: {
    fontSize: 14,
    color: '#888',
    textAlign: 'center',
    marginBottom: 24,
    paddingHorizontal: 20,
  },
  passwordInput: {
    backgroundColor: '#2d2d44',
    borderRadius: 12,
    padding: 16,
    fontSize: 16,
    color: '#fff',
    width: '100%',
    marginBottom: 16,
    textAlign: 'center',
  },
  primaryButton: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: '#4ECDC4',
    borderRadius: 12,
    padding: 16,
    width: '100%',
    gap: 8,
  },
  primaryButtonText: {
    fontSize: 16,
    fontWeight: '600',
    color: '#1a1a2e',
  },
  buttonDisabled: {
    opacity: 0.6,
  },
  periodSection: {
    width: '100%',
    marginBottom: 24,
  },
  periodLabel: {
    fontSize: 14,
    color: '#fff',
    marginBottom: 12,
    fontWeight: '600',
  },
  periodRow: {
    marginBottom: 12,
  },
  pageRow: {
    flexDirection: 'row',
    gap: 16,
    marginTop: 8,
  },
  pageField: {
    flex: 1,
  },
  pageLabel: {
    fontSize: 14,
    color: '#4ECDC4',
    marginBottom: 8,
    fontWeight: '600',
  },
  pageInput: {
    backgroundColor: '#2d2d44',
    borderRadius: 10,
    padding: 14,
    fontSize: 18,
    color: '#fff',
    textAlign: 'center',
    fontWeight: '600',
    borderWidth: 2,
    borderColor: '#3d3d54',
  },
  pageHint: {
    fontSize: 13,
    color: '#4ECDC4',
    marginTop: 4,
    marginBottom: 8,
  },
  monthScroll: {
    flexGrow: 0,
  },
  monthButtons: {
    flexDirection: 'row',
    gap: 8,
  },
  monthButton: {
    backgroundColor: '#2d2d44',
    paddingHorizontal: 14,
    paddingVertical: 10,
    borderRadius: 8,
  },
  monthButtonActive: {
    backgroundColor: '#4ECDC4',
  },
  monthButtonText: {
    fontSize: 12,
    color: '#aaa',
    fontWeight: '500',
  },
  monthButtonTextActive: {
    color: '#1a1a2e',
  },
  yearRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
  },
  yearLabel: {
    fontSize: 14,
    color: '#888',
  },
  yearInput: {
    backgroundColor: '#2d2d44',
    borderRadius: 8,
    padding: 10,
    fontSize: 14,
    color: '#fff',
    width: 100,
    textAlign: 'center',
  },
  uploadButton: {
    backgroundColor: '#4ECDC4',
    borderRadius: 16,
    padding: 30,
    width: '100%',
    alignItems: 'center',
    borderWidth: 2,
    borderColor: '#4ECDC4',
    borderStyle: 'dashed',
  },
  uploadButtonText: {
    fontSize: 18,
    fontWeight: '600',
    color: '#1a1a2e',
    marginTop: 12,
  },
  uploadButtonSubtext: {
    fontSize: 12,
    color: '#1a1a2e',
    opacity: 0.7,
    marginTop: 4,
  },
  extractingContainer: {
    alignItems: 'center',
    paddingVertical: 10,
  },
  extractingText: {
    fontSize: 18,
    fontWeight: '700',
    color: '#1a1a2e',
    marginTop: 16,
  },
  extractingSubtext: {
    fontSize: 14,
    color: '#1a1a2e',
    marginTop: 8,
  },
  extractingWait: {
    fontSize: 12,
    color: '#666',
    marginTop: 12,
    fontStyle: 'italic',
  },
  pdfInfoCard: {
    backgroundColor: '#2d2d44',
    borderRadius: 16,
    padding: 20,
    flexDirection: 'row',
    alignItems: 'center',
    marginBottom: 24,
    gap: 16,
  },
  pdfInfoText: {
    flex: 1,
  },
  pdfInfoTitle: {
    fontSize: 16,
    fontWeight: '600',
    color: '#fff',
    marginBottom: 4,
  },
  pdfInfoPages: {
    fontSize: 14,
    color: '#4ECDC4',
    fontWeight: '500',
  },
  pageValidation: {
    fontSize: 13,
    color: '#4ECDC4',
    marginTop: 12,
    textAlign: 'center',
    fontWeight: '500',
  },
  extractButton: {
    backgroundColor: '#4ECDC4',
    borderRadius: 12,
    padding: 18,
    width: '100%',
    alignItems: 'center',
    flexDirection: 'row',
    justifyContent: 'center',
    gap: 10,
  },
  extractButtonText: {
    fontSize: 16,
    fontWeight: '600',
    color: '#1a1a2e',
  },
  changePdfButton: {
    marginTop: 16,
    padding: 12,
    alignItems: 'center',
  },
  changePdfButtonText: {
    fontSize: 14,
    color: '#888',
  },
  previewContainer: {
    flex: 1,
  },
  previewHeader: {
    marginBottom: 8,
  },
  previewTitle: {
    fontSize: 20,
    fontWeight: 'bold',
    color: '#fff',
  },
  previewPeriod: {
    fontSize: 14,
    color: '#4ECDC4',
    marginTop: 4,
  },
  previewInstructions: {
    fontSize: 12,
    color: '#888',
    marginBottom: 16,
  },
  programsList: {
    flex: 1,
    marginBottom: 16,
  },
  programCard: {
    backgroundColor: '#2d2d44',
    borderRadius: 12,
    padding: 14,
    marginBottom: 10,
  },
  programCardHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'flex-start',
  },
  programCardInfo: {
    flex: 1,
  },
  programBrand: {
    fontSize: 11,
    color: '#4ECDC4',
    fontWeight: '600',
  },
  programModel: {
    fontSize: 14,
    color: '#fff',
    fontWeight: 'bold',
    marginTop: 2,
  },
  programCardActions: {
    flexDirection: 'row',
    gap: 8,
  },
  editButton: {
    padding: 6,
    backgroundColor: 'rgba(78, 205, 196, 0.2)',
    borderRadius: 6,
  },
  deleteButton: {
    padding: 6,
    backgroundColor: 'rgba(255, 107, 107, 0.2)',
    borderRadius: 6,
  },
  programCardDetails: {
    marginTop: 10,
    paddingTop: 10,
    borderTopWidth: 1,
    borderTopColor: '#3d3d54',
  },
  programDetailRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    marginBottom: 4,
  },
  programDetailLabel: {
    fontSize: 11,
    color: '#888',
  },
  programDetailValue: {
    fontSize: 11,
    color: '#fff',
    fontWeight: '500',
  },
  programDetailNA: {
    fontSize: 11,
    color: '#666',
    fontStyle: 'italic',
  },
  previewActions: {
    flexDirection: 'row',
    gap: 12,
  },
  backButton: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: '#2d2d44',
    borderRadius: 12,
    padding: 14,
    gap: 8,
    flex: 0.4,
  },
  backButtonText: {
    fontSize: 14,
    color: '#fff',
  },
  saveButton: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: '#4ECDC4',
    borderRadius: 12,
    padding: 14,
    gap: 8,
    flex: 0.6,
  },
  saveButtonText: {
    fontSize: 14,
    fontWeight: '600',
    color: '#1a1a2e',
  },
  successNote: {
    fontSize: 12,
    color: '#4ECDC4',
    textAlign: 'center',
    marginBottom: 24,
    paddingHorizontal: 20,
  },
  emailSentNote: {
    fontSize: 13,
    color: '#888',
    textAlign: 'center',
    marginBottom: 32,
    paddingHorizontal: 20,
    lineHeight: 20,
  },
  // Modal styles
  modalOverlay: {
    flex: 1,
    backgroundColor: 'rgba(0, 0, 0, 0.8)',
    justifyContent: 'flex-end',
  },
  modalContent: {
    backgroundColor: '#1a1a2e',
    borderTopLeftRadius: 24,
    borderTopRightRadius: 24,
    maxHeight: '90%',
  },
  modalHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    padding: 16,
    borderBottomWidth: 1,
    borderBottomColor: '#2d2d44',
  },
  modalTitle: {
    fontSize: 18,
    fontWeight: 'bold',
    color: '#fff',
  },
  modalBody: {
    padding: 16,
    maxHeight: 500,
  },
  formRow: {
    flexDirection: 'row',
    gap: 12,
    marginBottom: 12,
  },
  formField: {
    flex: 1,
  },
  formFieldSmall: {
    width: 100,
  },
  formLabel: {
    fontSize: 12,
    color: '#888',
    marginBottom: 6,
  },
  formInput: {
    backgroundColor: '#2d2d44',
    borderRadius: 8,
    padding: 12,
    fontSize: 14,
    color: '#fff',
  },
  ratesTitle: {
    fontSize: 14,
    color: '#FF6B6B',
    fontWeight: '600',
    marginTop: 8,
    marginBottom: 10,
  },
  ratesGrid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 8,
    marginBottom: 12,
  },
  rateField: {
    width: '30%',
  },
  rateLabel: {
    fontSize: 10,
    color: '#888',
    marginBottom: 4,
    textAlign: 'center',
  },
  rateInput: {
    backgroundColor: '#2d2d44',
    borderRadius: 8,
    padding: 10,
    fontSize: 14,
    color: '#fff',
    textAlign: 'center',
  },
  option2Toggle: {
    marginVertical: 12,
  },
  option2ToggleBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 10,
  },
  option2ToggleText: {
    fontSize: 14,
    color: '#fff',
  },
  modalSaveButton: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: '#4ECDC4',
    borderRadius: 12,
    padding: 16,
    margin: 16,
    gap: 8,
  },
  modalSaveButtonText: {
    fontSize: 16,
    fontWeight: '600',
    color: '#1a1a2e',
  },
  // Document type choice styles
  docTypeCard: {
    backgroundColor: '#2d2d44',
    borderRadius: 16,
    padding: 18,
    marginBottom: 14,
    flexDirection: 'row',
    alignItems: 'center',
    borderWidth: 1,
    borderColor: '#3d3d54',
  },
  docTypeIconWrap: {
    width: 52,
    height: 52,
    borderRadius: 12,
    backgroundColor: 'rgba(78, 205, 196, 0.1)',
    justifyContent: 'center',
    alignItems: 'center',
    marginRight: 14,
  },
  docTypeTextWrap: {
    flex: 1,
  },
  docTypeTitle: {
    fontSize: 15,
    fontWeight: '700',
    color: '#fff',
    marginBottom: 3,
  },
  docTypeDesc: {
    fontSize: 12,
    color: '#aaa',
    marginBottom: 2,
  },
  docTypeHint: {
    fontSize: 10,
    color: '#666',
    fontStyle: 'italic',
  },
  // Residual success styles
  residualSummary: {
    backgroundColor: '#2d2d44',
    borderRadius: 16,
    padding: 18,
    marginBottom: 20,
    width: '100%',
  },
  residualSummaryTitle: {
    fontSize: 18,
    fontWeight: '700',
    color: '#4ECDC4',
    textAlign: 'center',
    marginBottom: 14,
  },
  residualBrandRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    paddingVertical: 8,
    borderBottomWidth: 1,
    borderBottomColor: '#3d3d54',
  },
  residualBrandName: {
    fontSize: 14,
    color: '#fff',
    fontWeight: '500',
  },
  residualBrandCount: {
    fontSize: 14,
    color: '#4ECDC4',
    fontWeight: '600',
  },
  residualEmailStatus: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    marginTop: 14,
    paddingTop: 14,
    borderTopWidth: 1,
    borderTopColor: '#3d3d54',
  },
  residualEmailText: {
    fontSize: 13,
    flex: 1,
  },
});
