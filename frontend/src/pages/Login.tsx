import React, { useState } from 'react';
import { useAuth } from '../context/AuthContext';
import { api } from '../utils/api';
import { KeyRound, Mail, AlertCircle, ShieldAlert } from 'lucide-react';

export const Login: React.FC = () => {
  const { login } = useAuth();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!email || !password) return;

    setLoading(true);
    setError(null);

    try {
      const data = await api.post('/auth/login', { email, password });
      login(data.access_token, data.user);
    } catch (err: any) {
      setError(err.message || 'Failed to login');
    } finally {
      setLoading(false);
    }
  };

  const handleDevAutoLogin = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await api.post('/auth/login', {
        email: 'dev-engineer@sutherland.com',
        password: 'DevPassword123!',
      });
      login(data.access_token, data.user);
    } catch (err: any) {
      setError(
        'Dev login failed. Ensure FastAPI is running and dev user is created.'
      );
    } finally {
      setLoading(false);
    }
  };

  return (
    <div
      style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        minHeight: '100vh',
        backgroundColor: '#09090b',
        padding: '20px',
      }}
    >
      <div
        style={{
          width: '100%',
          maxWidth: '400px',
          backgroundColor: '#18181b',
          border: '1px solid #27272a',
          borderRadius: '6px',
          padding: '32px',
        }}
      >
        <div style={{ textAlign: 'center', marginBottom: '24px' }}>
          <div
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              justifyContent: 'center',
              width: '48px',
              height: '48px',
              backgroundColor: 'rgba(14, 165, 233, 0.1)',
              borderRadius: '50%',
              marginBottom: '16px',
            }}
          >
            <KeyRound size={24} color="#0ea5e9" />
          </div>
          <h2 style={{ fontSize: '20px', fontWeight: 600 }}>Smart Data Portal</h2>
          <p
            style={{
              fontSize: '13px',
              color: '#a1a1aa',
              marginTop: '4px',
            }}
          >
            Sign in to manage data ingestion & schemas
          </p>
        </div>

        {error && (
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '8px',
              backgroundColor: 'rgba(239, 68, 68, 0.1)',
              border: '1px solid rgba(239, 68, 68, 0.2)',
              color: '#ef4444',
              borderRadius: '6px',
              padding: '12px',
              fontSize: '13px',
              marginBottom: '20px',
            }}
          >
            <AlertCircle size={16} style={{ flexShrink: 0 }} />
            <span>{error}</span>
          </div>
        )}

        <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
          <div>
            <label htmlFor="email">Email Address</label>
            <div style={{ position: 'relative' }}>
              <Mail
                size={16}
                color="#71717a"
                style={{
                  position: 'absolute',
                  left: '12px',
                  top: '50%',
                  transform: 'translateY(-50%)',
                }}
              />
              <input
                id="email"
                type="email"
                placeholder="you@company.com"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
                style={{ paddingLeft: '36px' }}
              />
            </div>
          </div>

          <div>
            <label htmlFor="password">Password</label>
            <div style={{ position: 'relative' }}>
              <KeyRound
                size={16}
                color="#71717a"
                style={{
                  position: 'absolute',
                  left: '12px',
                  top: '50%',
                  transform: 'translateY(-50%)',
                }}
              />
              <input
                id="password"
                type="password"
                placeholder="••••••••"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                style={{ paddingLeft: '36px' }}
              />
            </div>
          </div>

          <button
            type="submit"
            className="btn"
            disabled={loading}
            style={{ width: '100%', marginTop: '8px', height: '40px' }}
          >
            {loading ? 'Signing in...' : 'Sign In'}
          </button>
        </form>

        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            margin: '20px 0',
            color: '#71717a',
            fontSize: '12px',
          }}
        >
          <div style={{ flex: 1, height: '1px', backgroundColor: '#27272a' }}></div>
          <span style={{ padding: '0 10px' }}>DEV OPTIONS</span>
          <div style={{ flex: 1, height: '1px', backgroundColor: '#27272a' }}></div>
        </div>

        <button
          onClick={handleDevAutoLogin}
          className="btn btn-secondary"
          disabled={loading}
          style={{
            width: '100%',
            height: '40px',
            fontSize: '13px',
            borderColor: '#3f3f46',
            color: '#fafafa',
          }}
        >
          <ShieldAlert size={16} />
          Auto-Login as OWNER
        </button>
      </div>
    </div>
  );
};
