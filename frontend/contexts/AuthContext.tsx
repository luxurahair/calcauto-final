import React, { createContext, useContext, useState, useEffect, ReactNode } from 'react';
import AsyncStorage from '@react-native-async-storage/async-storage';
import axios from 'axios';
import { Platform } from 'react-native';
import { API_URL } from '../utils/api';

interface User {
  id: string;
  email: string;
  name: string;
  is_admin?: boolean;
}

interface AuthContextType {
  user: User | null;
  isLoading: boolean;
  isAuthenticated: boolean;
  isAdmin: boolean;
  isDemoUser: boolean;
  login: (email: string, password: string) => Promise<{ success: boolean; error?: string }>;
  register: (name: string, email: string, password: string) => Promise<{ success: boolean; error?: string }>;
  logout: () => Promise<void>;
  getToken: () => Promise<string | null>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

// Storage helper for web compatibility
const storage = {
  async getItem(key: string): Promise<string | null> {
    if (Platform.OS === 'web') {
      return localStorage.getItem(key);
    }
    return AsyncStorage.getItem(key);
  },
  async setItem(key: string, value: string): Promise<void> {
    if (Platform.OS === 'web') {
      localStorage.setItem(key, value);
      return;
    }
    return AsyncStorage.setItem(key, value);
  },
  async removeItem(key: string): Promise<void> {
    if (Platform.OS === 'web') {
      localStorage.removeItem(key);
      return;
    }
    return AsyncStorage.removeItem(key);
  }
};

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    checkAuth();
  }, []);

  const checkAuth = async () => {
    try {
      const token = await storage.getItem('auth_token');
      const userData = await storage.getItem('user_data');
      
      if (token && userData) {
        // Verify token is still valid by making a test request
        try {
          await axios.get(`${API_URL}/api/contacts`, {
            headers: { Authorization: `Bearer ${token}` }
          });
          // Token is valid
          setUser(JSON.parse(userData));
        } catch (err: any) {
          // Token is invalid - auto-login as demo
          console.log('Token invalid, auto-login demo');
          await storage.removeItem('auth_token');
          await storage.removeItem('user_data');
          await autoDemoLogin();
        }
      } else {
        // No stored session — auto-login as demo user
        await autoDemoLogin();
      }
    } catch (error) {
      console.error('Error checking auth:', error);
      await autoDemoLogin();
    } finally {
      setIsLoading(false);
    }
  };

  const autoDemoLogin = async () => {
    try {
      const response = await axios.post(`${API_URL}/api/auth/demo-login`);
      if (response.data.success) {
        await storage.setItem('auth_token', response.data.token);
        await storage.setItem('user_data', JSON.stringify(response.data.user));
        setUser(response.data.user);
      }
    } catch (err) {
      console.error('Demo auto-login failed:', err);
    }
  };

  const login = async (email: string, password: string): Promise<{ success: boolean; error?: string }> => {
    try {
      const response = await axios.post(`${API_URL}/api/auth/login`, {
        email: email.toLowerCase().trim(),
        password,
      });

      if (response.data.success) {
        await storage.setItem('auth_token', response.data.token);
        await storage.setItem('user_data', JSON.stringify(response.data.user));
        setUser(response.data.user);
        return { success: true };
      } else {
        return { success: false, error: response.data.error || 'Erreur de connexion' };
      }
    } catch (error: any) {
      console.error('Login error:', error);
      if (error.code === 'ERR_NETWORK' || !error.response) {
        return { success: false, error: 'Impossible de joindre le serveur. Vérifiez votre connexion.' };
      }
      const message = error.response?.data?.detail || error.response?.data?.error || 'Email ou mot de passe incorrect';
      return { success: false, error: message };
    }
  };

  const register = async (name: string, email: string, password: string): Promise<{ success: boolean; error?: string }> => {
    try {
      const response = await axios.post(`${API_URL}/api/auth/register`, {
        name: name.trim(),
        email: email.toLowerCase().trim(),
        password,
      });

      if (response.data.success) {
        await storage.setItem('auth_token', response.data.token);
        await storage.setItem('user_data', JSON.stringify(response.data.user));
        setUser(response.data.user);
        return { success: true };
      } else {
        return { success: false, error: response.data.error || 'Erreur d\'inscription' };
      }
    } catch (error: any) {
      console.error('Register error:', error);
      const message = error.response?.data?.detail || error.response?.data?.error || 'Erreur d\'inscription';
      return { success: false, error: message };
    }
  };

  const logout = async () => {
    try {
      await storage.removeItem('auth_token');
      await storage.removeItem('user_data');
      setUser(null);
    } catch (error) {
      console.error('Logout error:', error);
    }
  };

  const getToken = async (): Promise<string | null> => {
    return await storage.getItem('auth_token');
  };

  return (
    <AuthContext.Provider value={{
      user,
      isLoading,
      isAuthenticated: !!user,
      isAdmin: user?.is_admin || false,
      isDemoUser: user?.email === 'demo@calcauto.ca',
      login,
      register,
      logout,
      getToken,
    }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
}
