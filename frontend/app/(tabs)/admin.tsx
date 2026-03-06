import React, { useState, useEffect, useCallback, useRef } from 'react';
import {
  View,
  Text,
  StyleSheet,
  FlatList,
  TouchableOpacity,
  ActivityIndicator,
  RefreshControl,
  Alert,
  Platform,
  ScrollView,
  TextInput,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import axios from 'axios';
import { useAuth } from '../../contexts/AuthContext';
import { API_URL } from '../../utils/api';

interface AdminUser {
  id: string;
  name: string;
  email: string;
  created_at: string | null;
  last_login: string | null;
  is_blocked: boolean;
  is_admin: boolean;
  contacts_count: number;
  submissions_count: number;
}

interface AdminStats {
  total_users: number;
  active_users: number;
  blocked_users: number;
  total_contacts: number;
  total_submissions: number;
}

interface ProgramItem {
  id: string;
  brand: string;
  model: string;
  trim: string | null;
  year: number;
  sort_order: number;
  consumer_cash: number;
}

// ============ Excel Manager Component ============
interface ComparisonChange {
  avant: any;
  apres: any;
}
interface ComparisonDetail {
  vehicule: string;
  changes: Record<string, ComparisonChange>;
}

function ComparisonReport({ comparison }: { comparison: ComparisonDetail[] }) {
  if (!comparison || comparison.length === 0) return null;

  const formatValue = (val: any) => {
    if (val === null || val === undefined) return '—';
    if (typeof val === 'object') {
      return Object.entries(val).map(([k, v]) => `${k}: ${v}`).join(', ');
    }
    return String(val);
  };

  return (
    <View style={{ marginTop: 12 }}>
      <Text style={{ color: '#FFD700', fontWeight: '700', fontSize: 15, marginBottom: 8 }}>
        Rapport de comparaison ({comparison.length} modifications)
      </Text>
      {comparison.map((item, idx) => (
        <View key={idx} style={{ backgroundColor: '#1a1a2e', borderRadius: 8, padding: 12, marginBottom: 8, borderLeftWidth: 3, borderLeftColor: '#FFD700' }}>
          <Text style={{ color: '#fff', fontWeight: '700', fontSize: 13, marginBottom: 6 }} data-testid={`comparison-vehicle-${idx}`}>
            {item.vehicule}
          </Text>
          {Object.entries(item.changes).map(([field, change]) => (
            <View key={field} style={{ flexDirection: 'row', marginBottom: 3, flexWrap: 'wrap' }}>
              <Text style={{ color: '#aaa', fontSize: 12, width: 160 }}>{field}:</Text>
              <Text style={{ color: '#FF6B6B', fontSize: 12 }}>{formatValue(change.avant)}</Text>
              <Text style={{ color: '#666', fontSize: 12, marginHorizontal: 6 }}>→</Text>
              <Text style={{ color: '#4ECDC4', fontSize: 12 }}>{formatValue(change.apres)}</Text>
            </View>
          ))}
        </View>
      ))}
    </View>
  );
}

function ExcelManager({ getToken }: { getToken: () => Promise<string> }) {
  const { isDemoUser } = useAuth();
  const [importing, setImporting] = useState(false);
  const [adminPassword, setAdminPassword] = useState(isDemoUser ? 'Liana2018' : '');
  const [result, setResult] = useState<string | null>(null);
  const [resultType, setResultType] = useState<'success' | 'error'>('success');
  const [comparison, setComparison] = useState<ComparisonDetail[] | null>(null);
  const [sciComparison, setSciComparison] = useState<ComparisonDetail[] | null>(null);
  const fileInputRef = useRef<HTMLInputElement | null>(null);

  const handleExport = async () => {
    try {
      const url = `${API_URL}/api/programs/export-excel`;
      if (Platform.OS === 'web') {
        const link = document.createElement('a');
        link.href = url;
        link.download = 'programmes_calcauto.xlsx';
        link.click();
        setResult('Telechargement lance!');
        setResultType('success');
        setComparison(null);
      }
    } catch (e: any) {
      setResult('Erreur: ' + (e.message || 'inconnu'));
      setResultType('error');
    }
  };

  const handleImport = async () => {
    if (!adminPassword) {
      setResult('Entrez le mot de passe admin');
      setResultType('error');
      return;
    }
    if (Platform.OS === 'web' && fileInputRef.current) {
      fileInputRef.current.click();
    }
  };

  const onFileSelected = async (event: any) => {
    const file = event.target?.files?.[0];
    if (!file) return;

    setImporting(true);
    setResult(null);
    setComparison(null);
    try {
      const formData = new FormData();
      formData.append('file', file);
      formData.append('password', adminPassword);

      const response = await axios.post(`${API_URL}/api/programs/import-excel`, formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      });

      const data = response.data;
      setResult(`${data.message}${data.errors?.length ? '\nErreurs: ' + data.errors.join(', ') : ''}`);
      setResultType('success');
      if (data.comparison && data.comparison.length > 0) {
        setComparison(data.comparison);
      }
    } catch (e: any) {
      setResult('Erreur: ' + (e.response?.data?.detail || e.message || 'inconnu'));
      setResultType('error');
    } finally {
      setImporting(false);
      if (fileInputRef.current) fileInputRef.current.value = '';
    }
  };

  return (
    <ScrollView style={{ flex: 1, padding: 16 }}>
      <View style={{ backgroundColor: '#2d2d44', borderRadius: 12, padding: 20, marginBottom: 16 }}>
        <View style={{ flexDirection: 'row', alignItems: 'center', marginBottom: 12 }}>
          <Ionicons name="download-outline" size={24} color="#4ECDC4" />
          <Text style={{ color: '#fff', fontSize: 18, fontWeight: '700', marginLeft: 10 }}>Exporter les programmes</Text>
        </View>
        <Text style={{ color: '#aaa', fontSize: 13, marginBottom: 16 }}>
          Telechargez un fichier Excel avec tous les programmes actuels. Corrigez les valeurs (Consumer Cash, taux, etc.) puis reimportez.
        </Text>
        <TouchableOpacity
          style={{ backgroundColor: '#4ECDC4', borderRadius: 8, paddingVertical: 14, alignItems: 'center' }}
          onPress={handleExport}
        >
          <Text style={{ color: '#1a1a2e', fontWeight: '700', fontSize: 16 }}>Telecharger Excel</Text>
        </TouchableOpacity>
      </View>

      <View style={{ backgroundColor: '#2d2d44', borderRadius: 12, padding: 20, marginBottom: 16 }}>
        <View style={{ flexDirection: 'row', alignItems: 'center', marginBottom: 12 }}>
          <Ionicons name="cloud-upload-outline" size={24} color="#FFD700" />
          <Text style={{ color: '#fff', fontSize: 18, fontWeight: '700', marginLeft: 10 }}>Importer Excel corrige</Text>
        </View>
        <Text style={{ color: '#aaa', fontSize: 13, marginBottom: 16 }}>
          Uploadez le fichier Excel corrige. Les programmes seront mis a jour avec les nouvelles valeurs. Ce fichier devient la source de verite.
        </Text>

        <TextInput
          style={{
            backgroundColor: '#1a1a2e', color: '#fff', borderRadius: 8,
            paddingHorizontal: 16, paddingVertical: 12, marginBottom: 12,
            borderWidth: 1, borderColor: '#444', fontSize: 14,
          }}
          placeholder="Mot de passe admin"
          placeholderTextColor="#666"
          secureTextEntry
          value={adminPassword}
          onChangeText={setAdminPassword}
        />

        {Platform.OS === 'web' && (
          <input
            ref={(el) => { fileInputRef.current = el; }}
            type="file"
            accept=".xlsx,.xls"
            style={{ display: 'none' }}
            onChange={onFileSelected}
          />
        )}

        <TouchableOpacity
          style={{
            backgroundColor: importing ? '#555' : '#FFD700', borderRadius: 8,
            paddingVertical: 14, alignItems: 'center', opacity: importing ? 0.7 : 1,
          }}
          onPress={handleImport}
          disabled={importing}
        >
          {importing ? (
            <ActivityIndicator size="small" color="#1a1a2e" />
          ) : (
            <Text style={{ color: '#1a1a2e', fontWeight: '700', fontSize: 16 }}>Importer le fichier corrige</Text>
          )}
        </TouchableOpacity>
      </View>

      {result && (
        <View style={{
          backgroundColor: resultType === 'success' ? 'rgba(78,205,196,0.15)' : 'rgba(255,107,107,0.15)',
          borderRadius: 8, padding: 16, marginBottom: 16,
          borderWidth: 1, borderColor: resultType === 'success' ? '#4ECDC4' : '#FF6B6B',
        }}>
          <Text style={{ color: resultType === 'success' ? '#4ECDC4' : '#FF6B6B', fontSize: 14 }}>{result}</Text>
        </View>
      )}

      {comparison && <ComparisonReport comparison={comparison} />}
      {sciComparison && <ComparisonReport comparison={sciComparison} />}

      {/* ============ LEASE SCI ============ */}
      <View style={{ backgroundColor: '#2d2d44', borderRadius: 12, padding: 20, marginBottom: 16 }}>
        <View style={{ flexDirection: 'row', alignItems: 'center', marginBottom: 12 }}>
          <Ionicons name="car-sport-outline" size={24} color="#FF6B6B" />
          <Text style={{ color: '#fff', fontSize: 18, fontWeight: '700', marginLeft: 10 }}>Taux Location SCI</Text>
        </View>
        <Text style={{ color: '#aaa', fontSize: 13, marginBottom: 16 }}>
          Exportez les taux de location SCI (standard + alternatif), corrigez, puis reimportez.
        </Text>
        <TouchableOpacity
          style={{ backgroundColor: '#FF6B6B', borderRadius: 8, paddingVertical: 14, alignItems: 'center', marginBottom: 10 }}
          onPress={() => {
            if (Platform.OS === 'web') {
              const link = document.createElement('a');
              link.href = `${API_URL}/api/sci/export-excel`;
              link.download = 'sci_lease_rates.xlsx';
              link.click();
            }
          }}
        >
          <Text style={{ color: '#fff', fontWeight: '700', fontSize: 16 }}>Telecharger Excel Lease SCI</Text>
        </TouchableOpacity>

        {Platform.OS === 'web' && (
          <input
            ref={(el: any) => { (window as any).__sciFileRef = el; }}
            type="file"
            accept=".xlsx,.xls"
            style={{ display: 'none' }}
            onChange={async (event: any) => {
              const file = event?.target?.files?.[0];
              if (!file || !adminPassword) return;
              setImporting(true);
              setResult(null);
              setSciComparison(null);
              try {
                const formData = new FormData();
                formData.append('file', file);
                formData.append('password', adminPassword);
                const response = await axios.post(`${API_URL}/api/sci/import-excel`, formData, {
                  headers: { 'Content-Type': 'multipart/form-data' },
                });
                setResult(`SCI: ${response.data.message}`);
                setResultType('success');
                if (response.data.comparison && response.data.comparison.length > 0) {
                  setSciComparison(response.data.comparison);
                }
              } catch (e: any) {
                setResult('Erreur SCI: ' + (e.response?.data?.detail || e.message));
                setResultType('error');
              } finally {
                setImporting(false);
                if ((window as any).__sciFileRef) (window as any).__sciFileRef.value = '';
              }
            }}
          />
        )}

        <TouchableOpacity
          style={{
            backgroundColor: importing ? '#555' : '#FFD700', borderRadius: 8,
            paddingVertical: 14, alignItems: 'center', opacity: importing ? 0.7 : 1,
          }}
          onPress={() => {
            if (!adminPassword) { setResult('Entrez le mot de passe admin'); setResultType('error'); return; }
            if (Platform.OS === 'web' && (window as any).__sciFileRef) (window as any).__sciFileRef.click();
          }}
          disabled={importing}
        >
          {importing ? (
            <ActivityIndicator size="small" color="#1a1a2e" />
          ) : (
            <Text style={{ color: '#1a1a2e', fontWeight: '700', fontSize: 16 }}>Importer Excel Lease corrige</Text>
          )}
        </TouchableOpacity>
      </View>

      <View style={{ backgroundColor: '#2d2d44', borderRadius: 12, padding: 20, marginBottom: 40 }}>
        <Text style={{ color: '#FFD700', fontSize: 14, fontWeight: '700', marginBottom: 8 }}>Instructions</Text>
        <Text style={{ color: '#aaa', fontSize: 12, lineHeight: 20 }}>
          1. Telechargez l'Excel actuel{'\n'}
          2. Ouvrez dans Excel/Google Sheets{'\n'}
          3. Corrigez: Consumer Cash, taux Option 1/2{'\n'}
          4. NE PAS modifier la colonne ID (programmes){'\n'}
          5. Bonus Cash = 0 (ignorer Delivery Credit){'\n'}
          6. Opt2 / Alt vide = pas d'option{'\n'}
          7. Sauvegardez et reimportez ici{'\n'}
          8. Apres import, tous les utilisateurs seront deconnectes
        </Text>
      </View>
    </ScrollView>
  );
}

// ============ Vehicle Order Manager Component ============
function VehicleOrderManager({ getToken }: { getToken: () => Promise<string> }) {
  const { isDemoUser } = useAuth();
  const [programs, setPrograms] = useState<ProgramItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [selectedYear, setSelectedYear] = useState(2026);
  const [selectedBrand, setSelectedBrand] = useState('Tous');
  const [hasChanges, setHasChanges] = useState(false);
  const [dragIndex, setDragIndex] = useState<number | null>(null);
  const [adminPassword, setAdminPassword] = useState(isDemoUser ? 'Liana2018' : '');
  const [showPasswordInput, setShowPasswordInput] = useState(false);
  const dragOverIndex = useRef<number | null>(null);

  const brands = ['Tous', 'Chrysler', 'Jeep', 'Dodge', 'Ram', 'Fiat'];
  const years = [2026, 2025];

  const fetchPrograms = useCallback(async () => {
    try {
      setLoading(true);
      const res = await axios.get(`${API_URL}/api/programs`);
      setPrograms(res.data);
      setHasChanges(false);
    } catch (error) {
      console.error('Error fetching programs:', error);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { fetchPrograms(); }, [fetchPrograms]);

  const filtered = programs
    .filter(p => p.year === selectedYear)
    .filter(p => selectedBrand === 'Tous' || p.brand === selectedBrand)
    .sort((a, b) => a.sort_order - b.sort_order);

  const moveItem = (fromIdx: number, toIdx: number) => {
    if (fromIdx === toIdx) return;
    const updated = [...filtered];
    const [moved] = updated.splice(fromIdx, 1);
    updated.splice(toIdx, 0, moved);

    // Reassign sort_order sequentially
    const newPrograms = [...programs];
    updated.forEach((item, idx) => {
      const pIdx = newPrograms.findIndex(p => p.id === item.id);
      if (pIdx !== -1) {
        newPrograms[pIdx] = { ...newPrograms[pIdx], sort_order: idx };
      }
    });
    setPrograms(newPrograms);
    setHasChanges(true);
  };

  const handleSave = async () => {
    if (!adminPassword) {
      setShowPasswordInput(true);
      return;
    }
    setSaving(true);
    try {
      const ordersToSave = filtered.map((p, idx) => ({
        id: p.id,
        sort_order: idx,
      }));

      const token = await getToken();
      await axios.put(`${API_URL}/api/programs/reorder`, {
        password: adminPassword,
        orders: ordersToSave,
      }, {
        headers: { Authorization: `Bearer ${token}` }
      });

      setHasChanges(false);
      setShowPasswordInput(false);
      if (Platform.OS === 'web') {
        alert('Ordre sauvegardé avec succès !');
      } else {
        Alert.alert('Succès', 'Ordre sauvegardé avec succès !');
      }
    } catch (error: any) {
      const msg = error.response?.data?.detail || 'Erreur lors de la sauvegarde';
      if (Platform.OS === 'web') alert(msg);
      else Alert.alert('Erreur', msg);
    } finally {
      setSaving(false);
    }
  };

  // HTML5 Drag & Drop handlers (web only)
  const handleDragStart = (e: any, idx: number) => {
    setDragIndex(idx);
    e.dataTransfer.effectAllowed = 'move';
    e.dataTransfer.setData('text/plain', String(idx));
  };

  const handleDragOver = (e: any, idx: number) => {
    e.preventDefault();
    e.dataTransfer.dropEffect = 'move';
    dragOverIndex.current = idx;
  };

  const handleDrop = (e: any, toIdx: number) => {
    e.preventDefault();
    const fromIdx = dragIndex;
    if (fromIdx !== null && fromIdx !== toIdx) {
      moveItem(fromIdx, toIdx);
    }
    setDragIndex(null);
    dragOverIndex.current = null;
  };

  const handleDragEnd = () => {
    setDragIndex(null);
    dragOverIndex.current = null;
  };

  if (loading) {
    return (
      <View style={os.loadingWrap}>
        <ActivityIndicator size="large" color="#4ECDC4" />
      </View>
    );
  }

  return (
    <View style={os.container}>
      {/* Year Filter */}
      <View style={os.filterRow}>
        <Text style={os.filterLabel}>Année:</Text>
        {years.map(y => (
          <TouchableOpacity
            key={y}
            style={[os.filterBtn, selectedYear === y && os.filterBtnActive]}
            onPress={() => { setSelectedYear(y); setHasChanges(false); }}
          >
            <Text style={[os.filterBtnText, selectedYear === y && os.filterBtnTextActive]}>{y}</Text>
          </TouchableOpacity>
        ))}
      </View>

      {/* Brand Filter */}
      <ScrollView horizontal showsHorizontalScrollIndicator={false} style={os.brandScroll}>
        {brands.map(b => (
          <TouchableOpacity
            key={b}
            style={[os.filterBtn, selectedBrand === b && os.filterBtnActive]}
            onPress={() => setSelectedBrand(b)}
          >
            <Text style={[os.filterBtnText, selectedBrand === b && os.filterBtnTextActive]}>{b}</Text>
          </TouchableOpacity>
        ))}
      </ScrollView>

      <Text style={os.countLabel}>{filtered.length} programmes - Glissez pour réordonner</Text>

      {/* Save Button + Password */}
      {hasChanges && (
        <View style={os.saveSection}>
          {showPasswordInput && (
            <TextInput
              style={os.passwordInput}
              placeholder="Mot de passe admin"
              placeholderTextColor="#666"
              secureTextEntry
              value={adminPassword}
              onChangeText={setAdminPassword}
              onSubmitEditing={handleSave}
            />
          )}
          <TouchableOpacity style={os.saveBtn} onPress={handleSave} disabled={saving}>
            {saving ? (
              <ActivityIndicator size="small" color="#fff" />
            ) : (
              <>
                <Ionicons name="save" size={18} color="#fff" />
                <Text style={os.saveBtnText}>{showPasswordInput ? 'Confirmer' : 'Sauvegarder l\'ordre'}</Text>
              </>
            )}
          </TouchableOpacity>
        </View>
      )}

      {/* Draggable List */}
      <ScrollView style={os.listScroll} contentContainerStyle={{ paddingBottom: 120 }}>
        {filtered.map((item, idx) => {
          const isBeingDragged = dragIndex === idx;
          return (
            <View
              key={item.id}
              // @ts-ignore - web-only props
              draggable={Platform.OS === 'web'}
              onDragStart={(e: any) => handleDragStart(e, idx)}
              onDragOver={(e: any) => handleDragOver(e, idx)}
              onDrop={(e: any) => handleDrop(e, idx)}
              onDragEnd={handleDragEnd}
              style={[
                os.programCard,
                isBeingDragged && os.programCardDragging,
              ]}
            >
              {/* Drag Handle */}
              <View style={os.dragHandle}>
                <Ionicons name="menu" size={22} color="#666" />
              </View>

              {/* Sort Order Badge */}
              <View style={os.orderBadge}>
                <Text style={os.orderBadgeText}>{idx + 1}</Text>
              </View>

              {/* Program Info */}
              <View style={os.programInfo}>
                <Text style={os.programBrand}>{item.brand}</Text>
                <Text style={os.programModel}>{item.model}</Text>
                <Text style={os.programTrim} numberOfLines={1}>{item.trim || '(tous)'}</Text>
              </View>

              {/* Consumer Cash */}
              {item.consumer_cash > 0 && (
                <View style={os.cashBadge}>
                  <Text style={os.cashText}>{Math.round(item.consumer_cash).toLocaleString()} $</Text>
                </View>
              )}

              {/* Up/Down Arrows */}
              <View style={os.arrowCol}>
                <TouchableOpacity
                  style={[os.arrowBtn, idx === 0 && os.arrowBtnDisabled]}
                  onPress={() => idx > 0 && moveItem(idx, idx - 1)}
                  disabled={idx === 0}
                >
                  <Ionicons name="chevron-up" size={18} color={idx === 0 ? '#444' : '#4ECDC4'} />
                </TouchableOpacity>
                <TouchableOpacity
                  style={[os.arrowBtn, idx === filtered.length - 1 && os.arrowBtnDisabled]}
                  onPress={() => idx < filtered.length - 1 && moveItem(idx, idx + 1)}
                  disabled={idx === filtered.length - 1}
                >
                  <Ionicons name="chevron-down" size={18} color={idx === filtered.length - 1 ? '#444' : '#4ECDC4'} />
                </TouchableOpacity>
              </View>
            </View>
          );
        })}
      </ScrollView>
    </View>
  );
}

const os = StyleSheet.create({
  container: { flex: 1 },
  loadingWrap: { flex: 1, justifyContent: 'center', alignItems: 'center', paddingTop: 40 },
  filterRow: { flexDirection: 'row', alignItems: 'center', paddingHorizontal: 16, paddingTop: 12, gap: 8 },
  filterLabel: { color: '#888', fontSize: 13, marginRight: 4 },
  brandScroll: { paddingHorizontal: 16, paddingTop: 8, maxHeight: 44 },
  filterBtn: { paddingHorizontal: 14, paddingVertical: 6, borderRadius: 16, backgroundColor: '#2d2d44', marginRight: 6 },
  filterBtnActive: { backgroundColor: '#4ECDC4' },
  filterBtnText: { color: '#ccc', fontSize: 13, fontWeight: '600' },
  filterBtnTextActive: { color: '#1a1a2e' },
  countLabel: { color: '#888', fontSize: 12, paddingHorizontal: 16, paddingTop: 10, paddingBottom: 4 },
  saveSection: { paddingHorizontal: 16, paddingVertical: 8, gap: 8 },
  passwordInput: {
    backgroundColor: '#1a1a2e', borderWidth: 1, borderColor: '#4ECDC4', borderRadius: 8,
    paddingHorizontal: 14, paddingVertical: 10, color: '#fff', fontSize: 14,
  },
  saveBtn: {
    flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 8,
    backgroundColor: '#4ECDC4', marginHorizontal: 16, marginVertical: 8, paddingVertical: 10,
    borderRadius: 8,
  },
  saveBtnText: { color: '#1a1a2e', fontSize: 14, fontWeight: '700' },
  listScroll: { flex: 1, paddingHorizontal: 12 },
  programCard: {
    flexDirection: 'row', alignItems: 'center', backgroundColor: '#2d2d44',
    borderRadius: 8, padding: 10, marginBottom: 4, gap: 8,
    ...(Platform.OS === 'web' ? { cursor: 'grab' } : {}),
  },
  programCardDragging: { opacity: 0.4, borderWidth: 2, borderColor: '#4ECDC4', borderStyle: 'dashed' },
  dragHandle: { width: 28, alignItems: 'center', justifyContent: 'center' },
  orderBadge: {
    width: 26, height: 26, borderRadius: 13, backgroundColor: '#4ECDC4',
    alignItems: 'center', justifyContent: 'center',
  },
  orderBadgeText: { color: '#1a1a2e', fontSize: 12, fontWeight: '700' },
  programInfo: { flex: 1, marginLeft: 4 },
  programBrand: { color: '#4ECDC4', fontSize: 10, fontWeight: '600', textTransform: 'uppercase', letterSpacing: 0.5 },
  programModel: { color: '#fff', fontSize: 14, fontWeight: '600' },
  programTrim: { color: '#aaa', fontSize: 11, marginTop: 1 },
  cashBadge: { backgroundColor: 'rgba(78, 205, 196, 0.15)', paddingHorizontal: 8, paddingVertical: 3, borderRadius: 6 },
  cashText: { color: '#4ECDC4', fontSize: 11, fontWeight: '600' },
  arrowCol: { alignItems: 'center', gap: 2, marginLeft: 4 },
  arrowBtn: {
    width: 30, height: 24, alignItems: 'center', justifyContent: 'center',
    backgroundColor: '#1a1a2e', borderRadius: 4,
  },
  arrowBtnDisabled: { opacity: 0.3 },
});

// ============ Main Admin Screen ============
export default function AdminScreen() {
  const { user, getToken } = useAuth();
  const [users, setUsers] = useState<AdminUser[]>([]);
  const [stats, setStats] = useState<AdminStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [actionLoading, setActionLoading] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<'users' | 'order' | 'excel'>('users');

  const fetchData = useCallback(async () => {
    try {
      const token = await getToken();
      const headers = { Authorization: `Bearer ${token}` };
      const [usersRes, statsRes] = await Promise.all([
        axios.get(`${API_URL}/api/admin/users`, { headers }),
        axios.get(`${API_URL}/api/admin/stats`, { headers }),
      ]);
      setUsers(usersRes.data);
      setStats(statsRes.data);
    } catch (error: any) {
      console.error('Error fetching admin data:', error);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [getToken]);

  useEffect(() => { fetchData(); }, [fetchData]);

  const onRefresh = () => { setRefreshing(true); fetchData(); };

  const handleBlockUser = async (userId: string, userName: string) => {
    const confirmed = await new Promise<boolean>((resolve) => {
      if (Platform.OS === 'web') resolve(window.confirm(`Bloquer ${userName} ?`));
      else Alert.alert('Confirmer', `Bloquer ${userName} ?`, [
        { text: 'Annuler', onPress: () => resolve(false), style: 'cancel' },
        { text: 'Bloquer', onPress: () => resolve(true), style: 'destructive' },
      ]);
    });
    if (!confirmed) return;

    setActionLoading(userId);
    try {
      const token = await getToken();
      await axios.put(`${API_URL}/api/admin/users/${userId}/block`, {}, { headers: { Authorization: `Bearer ${token}` } });
      setUsers(users.map(u => u.id === userId ? { ...u, is_blocked: true } : u));
      setStats(stats ? { ...stats, active_users: stats.active_users - 1, blocked_users: stats.blocked_users + 1 } : null);
    } catch (error: any) {
      const msg = error.response?.data?.detail || 'Erreur';
      Platform.OS === 'web' ? alert(msg) : Alert.alert('Erreur', msg);
    } finally { setActionLoading(null); }
  };

  const handleUnblockUser = async (userId: string, userName: string) => {
    setActionLoading(userId);
    try {
      const token = await getToken();
      await axios.put(`${API_URL}/api/admin/users/${userId}/unblock`, {}, { headers: { Authorization: `Bearer ${token}` } });
      setUsers(users.map(u => u.id === userId ? { ...u, is_blocked: false } : u));
      setStats(stats ? { ...stats, active_users: stats.active_users + 1, blocked_users: stats.blocked_users - 1 } : null);
    } catch (error: any) {
      const msg = error.response?.data?.detail || 'Erreur';
      Platform.OS === 'web' ? alert(msg) : Alert.alert('Erreur', msg);
    } finally { setActionLoading(null); }
  };

  const formatDate = (dateStr: string | null) => {
    if (!dateStr) return 'Jamais';
    return new Date(dateStr).toLocaleDateString('fr-CA', {
      year: 'numeric', month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit',
    });
  };

  const renderUserCard = ({ item }: { item: AdminUser }) => {
    const isCurrentUser = item.id === user?.id;
    return (
      <View style={[styles.userCard, item.is_blocked && styles.userCardBlocked]}>
        <View style={styles.userHeader}>
          <View style={styles.userAvatar}>
            <Text style={styles.avatarText}>{item.name.charAt(0).toUpperCase()}</Text>
            {item.is_admin && (
              <View style={styles.adminBadge}>
                <Ionicons name="shield-checkmark" size={12} color="#FFD700" />
              </View>
            )}
          </View>
          <View style={styles.userInfo}>
            <View style={styles.nameRow}>
              <Text style={styles.userName}>{item.name}</Text>
              {item.is_blocked && (
                <View style={styles.blockedBadge}><Text style={styles.blockedText}>BLOQUE</Text></View>
              )}
            </View>
            <Text style={styles.userEmail}>{item.email}</Text>
          </View>
        </View>
        <View style={styles.statsRow}>
          <View style={styles.statItem}>
            <Ionicons name="people-outline" size={16} color="#4ECDC4" />
            <Text style={styles.statText}>{item.contacts_count} contacts</Text>
          </View>
          <View style={styles.statItem}>
            <Ionicons name="document-text-outline" size={16} color="#4ECDC4" />
            <Text style={styles.statText}>{item.submissions_count} soumissions</Text>
          </View>
        </View>
        <View style={styles.datesRow}>
          <Text style={styles.dateLabel}>Inscrit: {formatDate(item.created_at)}</Text>
          <Text style={styles.dateLabel}>Derniere connexion: {formatDate(item.last_login)}</Text>
        </View>
        {!item.is_admin && !isCurrentUser && (
          <View style={styles.actionsRow}>
            {actionLoading === item.id ? (
              <ActivityIndicator size="small" color="#4ECDC4" />
            ) : item.is_blocked ? (
              <TouchableOpacity style={styles.unblockButton} onPress={() => handleUnblockUser(item.id, item.name)}>
                <Ionicons name="checkmark-circle" size={18} color="#4ECDC4" />
                <Text style={styles.unblockButtonText}>Debloquer</Text>
              </TouchableOpacity>
            ) : (
              <TouchableOpacity style={styles.blockButton} onPress={() => handleBlockUser(item.id, item.name)}>
                <Ionicons name="ban" size={18} color="#FF6B6B" />
                <Text style={styles.blockButtonText}>Bloquer</Text>
              </TouchableOpacity>
            )}
          </View>
        )}
      </View>
    );
  };

  if (loading) {
    return (
      <SafeAreaView style={styles.container}>
        <View style={styles.loadingContainer}>
          <ActivityIndicator size="large" color="#4ECDC4" />
          <Text style={styles.loadingText}>Chargement...</Text>
        </View>
      </SafeAreaView>
    );
  }

  return (
    <SafeAreaView style={styles.container}>
      <View style={styles.header}>
        <Text style={styles.title}>Administration</Text>
        <Ionicons name="shield-checkmark" size={20} color="#FFD700" style={{ marginLeft: 10 }} />
      </View>

      {/* Tab Switcher */}
      <View style={styles.tabRow}>
        <TouchableOpacity
          style={[styles.tab, activeTab === 'users' && styles.tabActive]}
          onPress={() => setActiveTab('users')}
        >
          <Ionicons name="people" size={16} color={activeTab === 'users' ? '#1a1a2e' : '#888'} />
          <Text style={[styles.tabText, activeTab === 'users' && styles.tabTextActive]}>Utilisateurs</Text>
        </TouchableOpacity>
        <TouchableOpacity
          style={[styles.tab, activeTab === 'order' && styles.tabActive]}
          onPress={() => setActiveTab('order')}
        >
          <Ionicons name="swap-vertical" size={16} color={activeTab === 'order' ? '#1a1a2e' : '#888'} />
          <Text style={[styles.tabText, activeTab === 'order' && styles.tabTextActive]}>Ordre</Text>
        </TouchableOpacity>
        <TouchableOpacity
          style={[styles.tab, activeTab === 'excel' && styles.tabActive]}
          onPress={() => setActiveTab('excel')}
        >
          <Ionicons name="document-text" size={16} color={activeTab === 'excel' ? '#1a1a2e' : '#888'} />
          <Text style={[styles.tabText, activeTab === 'excel' && styles.tabTextActive]}>Excel</Text>
        </TouchableOpacity>
      </View>

      {activeTab === 'users' ? (
        <>
          {stats && (
            <View style={styles.statsContainer}>
              <View style={styles.statsCard}>
                <Text style={styles.statsNumber}>{stats.total_users}</Text>
                <Text style={styles.statsLabel}>Utilisateurs</Text>
              </View>
              <View style={styles.statsCard}>
                <Text style={[styles.statsNumber, { color: '#4ECDC4' }]}>{stats.active_users}</Text>
                <Text style={styles.statsLabel}>Actifs</Text>
              </View>
              <View style={styles.statsCard}>
                <Text style={[styles.statsNumber, { color: '#FF6B6B' }]}>{stats.blocked_users}</Text>
                <Text style={styles.statsLabel}>Bloques</Text>
              </View>
              <View style={styles.statsCard}>
                <Text style={styles.statsNumber}>{stats.total_contacts}</Text>
                <Text style={styles.statsLabel}>Contacts</Text>
              </View>
            </View>
          )}
          <FlatList
            data={users}
            renderItem={renderUserCard}
            keyExtractor={(item) => item.id}
            contentContainerStyle={styles.listContent}
            refreshControl={
              <RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor="#4ECDC4" colors={['#4ECDC4']} />
            }
            ListEmptyComponent={
              <View style={styles.emptyContainer}>
                <Ionicons name="people-outline" size={48} color="#888" />
                <Text style={styles.emptyText}>Aucun utilisateur</Text>
              </View>
            }
          />
        </>
      ) : activeTab === 'order' ? (
        <VehicleOrderManager getToken={getToken} />
      ) : (
        <ExcelManager getToken={getToken} />
      )}
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#1a1a2e' },
  loadingContainer: { flex: 1, justifyContent: 'center', alignItems: 'center' },
  loadingText: { color: '#888', marginTop: 10 },
  header: {
    flexDirection: 'row', alignItems: 'center', justifyContent: 'center',
    paddingVertical: 14, paddingHorizontal: 20, borderBottomWidth: 1, borderBottomColor: '#2d2d44',
  },
  title: { fontSize: 22, fontWeight: 'bold', color: '#fff' },
  tabRow: {
    flexDirection: 'row', paddingHorizontal: 16, paddingVertical: 8, gap: 8,
    borderBottomWidth: 1, borderBottomColor: '#2d2d44',
  },
  tab: {
    flex: 1, flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 6,
    paddingVertical: 10, borderRadius: 8, backgroundColor: '#2d2d44',
  },
  tabActive: { backgroundColor: '#4ECDC4' },
  tabText: { color: '#888', fontSize: 13, fontWeight: '600' },
  tabTextActive: { color: '#1a1a2e' },
  statsContainer: {
    flexDirection: 'row', justifyContent: 'space-around', paddingVertical: 14, paddingHorizontal: 10,
    borderBottomWidth: 1, borderBottomColor: '#2d2d44',
  },
  statsCard: { alignItems: 'center', paddingHorizontal: 10 },
  statsNumber: { fontSize: 22, fontWeight: 'bold', color: '#fff' },
  statsLabel: { fontSize: 11, color: '#888', marginTop: 3 },
  listContent: { padding: 16, paddingBottom: 100 },
  userCard: { backgroundColor: '#2d2d44', borderRadius: 12, padding: 16, marginBottom: 12 },
  userCardBlocked: { borderWidth: 1, borderColor: '#FF6B6B', opacity: 0.8 },
  userHeader: { flexDirection: 'row', alignItems: 'center', marginBottom: 12 },
  userAvatar: {
    width: 48, height: 48, borderRadius: 24, backgroundColor: '#4ECDC4',
    justifyContent: 'center', alignItems: 'center', position: 'relative',
  },
  avatarText: { fontSize: 20, fontWeight: 'bold', color: '#1a1a2e' },
  adminBadge: { position: 'absolute', bottom: -2, right: -2, backgroundColor: '#1a1a2e', borderRadius: 10, padding: 2 },
  userInfo: { flex: 1, marginLeft: 12 },
  nameRow: { flexDirection: 'row', alignItems: 'center', gap: 8 },
  userName: { fontSize: 16, fontWeight: '600', color: '#fff' },
  userEmail: { fontSize: 14, color: '#888', marginTop: 2 },
  blockedBadge: { backgroundColor: '#FF6B6B', paddingHorizontal: 8, paddingVertical: 2, borderRadius: 4 },
  blockedText: { fontSize: 10, fontWeight: 'bold', color: '#fff' },
  statsRow: { flexDirection: 'row', gap: 20, marginBottom: 8 },
  statItem: { flexDirection: 'row', alignItems: 'center', gap: 6 },
  statText: { fontSize: 13, color: '#ccc' },
  datesRow: { marginBottom: 12 },
  dateLabel: { fontSize: 12, color: '#666', marginBottom: 2 },
  actionsRow: { flexDirection: 'row', justifyContent: 'flex-end', borderTopWidth: 1, borderTopColor: '#3d3d54', paddingTop: 12 },
  blockButton: {
    flexDirection: 'row', alignItems: 'center', gap: 6,
    backgroundColor: 'rgba(255, 107, 107, 0.1)', paddingVertical: 8, paddingHorizontal: 16,
    borderRadius: 8, borderWidth: 1, borderColor: '#FF6B6B',
  },
  blockButtonText: { color: '#FF6B6B', fontWeight: '600' },
  unblockButton: {
    flexDirection: 'row', alignItems: 'center', gap: 6,
    backgroundColor: 'rgba(78, 205, 196, 0.1)', paddingVertical: 8, paddingHorizontal: 16,
    borderRadius: 8, borderWidth: 1, borderColor: '#4ECDC4',
  },
  unblockButtonText: { color: '#4ECDC4', fontWeight: '600' },
  emptyContainer: { alignItems: 'center', paddingVertical: 40 },
  emptyText: { color: '#888', marginTop: 12, fontSize: 16 },
});
