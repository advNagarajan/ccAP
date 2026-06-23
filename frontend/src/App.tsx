import React, { useState } from 'react';
import { AuthProvider, useAuth } from './context/AuthContext';
import { Login } from './pages/Login';
import { AppShell } from './components/AppShell';

// Import Page Components
import { Sources } from './pages/Sources';
import { Targets } from './pages/Targets';
import { Jobs } from './pages/Jobs';
import { DLQ } from './pages/DLQ';
import { Fallback } from './pages/Fallback';
import { Review } from './pages/Review';
import { Admin } from './pages/Admin';
import { Audit } from './pages/Audit';

const AppContent: React.FC = () => {
  const { token, loading } = useAuth();
  const [activeTab, setActiveTab] = useState('sources');

  React.useEffect(() => {
    if (!loading) {
      if (!token) {
        if (window.location.pathname !== '/login') {
          window.history.replaceState({}, '', '/login');
        }
      } else {
        if (window.location.pathname === '/login') {
          window.history.replaceState({}, '', '/');
        }
      }
    }
  }, [token, loading]);

  if (loading) {
    return (
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          minHeight: '100vh',
          backgroundColor: '#09090b',
          color: '#fafafa',
          fontFamily: 'sans-serif',
        }}
      >
        <span>Loading session...</span>
      </div>
    );
  }

  if (!token) {
    return <Login />;
  }

  const renderContent = () => {
    // Check for deep-linked review tab: e.g. "review:uuid"
    if (activeTab.startsWith('review:')) {
      const jobId = activeTab.split(':')[1];
      return <Review jobId={jobId} onClose={() => setActiveTab('jobs')} />;
    }

    switch (activeTab) {
      case 'sources':
        return <Sources />;
      case 'targets':
        return <Targets />;
      case 'jobs':
        return <Jobs setActiveTab={setActiveTab} />;
      case 'dlq':
        return <DLQ />;
      case 'fallback':
        return <Fallback />;
      case 'admin':
        return <Admin />;
      case 'audit':
        return <Audit />;
      default:
        return <div style={{ color: '#fafafa' }}>Tab not found</div>;
    }
  };

  return (
    <AppShell activeTab={activeTab} setActiveTab={setActiveTab}>
      {renderContent()}
    </AppShell>
  );
};

function App() {
  return (
    <AuthProvider>
      <AppContent />
    </AuthProvider>
  );
}

export default App;
