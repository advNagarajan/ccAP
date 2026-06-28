import React, { createContext, useContext, useState, useEffect } from 'react';
import { getSessionCookie, setSessionCookie, removeSessionCookie } from '../utils/cookies';

export interface User {
  user_id: string;
  email: string;
  role: string;
}

interface AuthContextType {
  token: string | null;
  user: User | null;
  loading: boolean;
  login: (token: string, user: User) => void;
  logout: () => void;
  isAdmin: boolean;
  isOwner: boolean;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [token, setToken] = useState<string | null>(null);
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const savedToken = getSessionCookie('auth_token');
    const savedUser = getSessionCookie('auth_user');

    if (savedToken && savedUser) {
      setToken(savedToken);
      try {
        setUser(JSON.parse(savedUser));
      } catch (e) {
        removeSessionCookie('auth_token');
        removeSessionCookie('auth_user');
      }
    }
    setLoading(false);

    const handleLogout = () => {
      setToken(null);
      setUser(null);
    };

    window.addEventListener('auth-logout', handleLogout);
    return () => window.removeEventListener('auth-logout', handleLogout);
  }, []);

  const login = (newToken: string, newUser: User) => {
    setSessionCookie('auth_token', newToken);
    setSessionCookie('auth_user', JSON.stringify(newUser));
    setToken(newToken);
    setUser(newUser);
  };

  const logout = () => {
    removeSessionCookie('auth_token');
    removeSessionCookie('auth_user');
    setToken(null);
    setUser(null);
  };

  const isAdmin = user ? (user.role === 'ADMIN' || user.role === 'OWNER') : false;
  const isOwner = user ? user.role === 'OWNER' : false;

  return (
    <AuthContext.Provider value={{ token, user, loading, login, logout, isAdmin, isOwner }}>
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};
