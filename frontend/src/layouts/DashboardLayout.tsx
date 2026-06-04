
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
          <a
            href="https://github.com/glikoliz/url-shortener"
            target="_blank"
            rel="noopener noreferrer"
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '8px',
              color: 'var(--text-secondary)',
              textDecoration: 'none',
              padding: '8px 12px',
              borderRadius: '8px',
              transition: 'background-color 0.2s, color 0.2s'
            }}
            onMouseOver={e => {
              e.currentTarget.style.background = 'rgba(255, 255, 255, 0.05)';
              e.currentTarget.style.color = 'white';
            }}
            onMouseOut={e => {
              e.currentTarget.style.background = 'transparent';
              e.currentTarget.style.color = 'var(--text-secondary)';
            }}
          >
            <svg role="img" viewBox="0 0 24 24" fill="currentColor" style={{ width: '18px', height: '18px' }} xmlns="http://www.w3.org/2000/svg">
              <path d="M12 .297c-6.63 0-12 5.373-12 12 0 5.303 3.438 9.8 8.205 11.385.6.113.82-.258.82-.577 0-.285-.01-1.04-.015-2.04-3.338.724-4.042-1.61-4.042-1.61C4.422 18.07 3.633 17.7 3.633 17.7c-1.087-.744.084-.729.084-.729 1.205.084 1.838 1.236 1.838 1.236 1.07 1.835 2.809 1.305 3.495.998.108-.776.417-1.305.76-1.605-2.665-.3-5.466-1.332-5.466-5.93 0-1.31.465-2.38 1.235-3.22-.135-.303-.54-1.523.105-3.176 0 0 1.005-.322 3.3 1.23.96-.267 1.98-.399 3-.405 1.02.006 2.04.138 3 .405 2.28-1.552 3.285-1.23 3.285-1.23.645 1.653.24 2.873.12 3.176.765.84 1.23 1.91 1.23 3.22 0 4.61-2.805 5.625-5.475 5.92.42.36.81 1.096.81 2.22 0 1.606-.015 2.896-.015 3.286 0 .315.21.69.825.57C20.565 22.092 24 17.592 24 12.297c0-6.627-5.373-12-12-12"/>
            </svg>
            <span style={{ fontSize: '14px', fontWeight: '500' }}>GitHub</span>
          </a>
          {user ? (
            <>
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
