
import { Outlet } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { LogOut, Link2 } from 'lucide-react';

const DashboardLayout = () => {
  const { user, logout } = useAuth();

  return (
    <div style={{ minHeight: '100vh', display: 'flex', flexDirection: 'column' }}>
      <header style={{
        background: 'var(--glass-bg)',
        backdropFilter: 'blur(12px)',
        WebkitBackdropFilter: 'blur(12px)',
        borderBottom: '1px solid var(--glass-border)',
        padding: '16px 32px',
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
        position: 'sticky',
        top: 0,
        zIndex: 10
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          <div style={{
            background: 'var(--accent-color)',
            padding: '8px',
            borderRadius: '8px',
            display: 'flex'
          }}>
            <Link2 size={24} color="white" />
          </div>
          <h1 style={{ fontSize: '20px', fontWeight: '600', margin: 0 }}>URL Shortener</h1>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '20px' }}>
          {user ? (
            <>
              <div style={{
                display: 'flex',
                alignItems: 'center',
                gap: '8px',
                padding: '6px 12px',
                background: 'rgba(0,0,0,0.2)',
                borderRadius: '20px',
                border: '1px solid var(--glass-border)'
              }}>
                <div style={{ width: '8px', height: '8px', borderRadius: '50%', background: '#00ff88' }}></div>
                <span style={{ fontSize: '14px', color: 'var(--text-secondary)' }}>Online</span>
              </div>

              <button
                onClick={logout}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '8px',
                  background: 'transparent',
                  color: 'var(--text-secondary)',
                  padding: '8px 12px',
                  borderRadius: '8px',
                  transition: 'background-color 0.2s, color 0.2s'
                }}
                onMouseOver={e => {
                  e.currentTarget.style.background = 'rgba(255, 51, 102, 0.1)';
                  e.currentTarget.style.color = 'var(--error-color)';
                }}
                onMouseOut={e => {
                  e.currentTarget.style.background = 'transparent';
                  e.currentTarget.style.color = 'var(--text-secondary)';
                }}
              >
                <LogOut size={18} />
                <span style={{ fontSize: '14px', fontWeight: '500' }}>Logout</span>
              </button>
            </>
          ) : (
            <div style={{ display: 'flex', gap: '12px' }}>
              <a
                href="/login"
                style={{
                  color: 'var(--text-secondary)',
                  textDecoration: 'none',
                  fontSize: '14px',
                  fontWeight: '500',
                  padding: '8px 16px',
                  borderRadius: '8px',
                  transition: 'all 0.2s'
                }}
                onMouseOver={e => e.currentTarget.style.color = 'white'}
                onMouseOut={e => e.currentTarget.style.color = 'var(--text-secondary)'}
              >
                Login
              </a>
              <a
                href="/register"
                style={{
                  background: 'rgba(255, 255, 255, 0.1)',
                  color: 'white',
                  textDecoration: 'none',
                  fontSize: '14px',
                  fontWeight: '500',
                  padding: '8px 16px',
                  borderRadius: '8px',
                  border: '1px solid var(--glass-border)',
                  transition: 'all 0.2s'
                }}
                onMouseOver={e => e.currentTarget.style.background = 'rgba(255, 255, 255, 0.15)'}
                onMouseOut={e => e.currentTarget.style.background = 'rgba(255, 255, 255, 0.1)'}
              >
                Register
              </a>
            </div>
          )}
        </div>
      </header>

      <main style={{
        flex: 1,
        padding: '40px 20px',
        maxWidth: '1200px',
        width: '100%',
        margin: '0 auto'
      }}>
        <Outlet />
      </main>
    </div>
  );
};

export default DashboardLayout;
