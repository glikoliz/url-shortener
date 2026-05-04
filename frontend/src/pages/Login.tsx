import { useState } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import GlassCard from '../components/GlassCard';
import { LogIn } from 'lucide-react';

import { useMutation } from '@tanstack/react-query';
import type { FormEvent } from 'react';

const Login = () => {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const { login } = useAuth();
  const navigate = useNavigate();

  const mutation = useMutation({
    mutationFn: () => login(email, password),
    onSuccess: () => {
      navigate('/');
    }
  });

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    mutation.mutate();
  };

  const isLoading = mutation.isPending;
  const error = mutation.error?.message;

  return (
    <div className="auth-container">
      <GlassCard className="animate-fade-in" style={{ width: '100%', maxWidth: '420px' }}>
        <div style={{ textAlign: 'center', marginBottom: '32px' }}>
          <div style={{
            display: 'inline-flex',
            padding: '12px',
            borderRadius: '50%',
            background: 'var(--glass-bg)',
            border: '1px solid var(--glass-border)',
            marginBottom: '16px'
          }}>
            <LogIn size={28} color="var(--accent-color)" />
          </div>
          <h1 style={{ fontSize: '24px', fontWeight: '600', marginBottom: '8px' }}>Welcome Back</h1>
          <p style={{ color: 'var(--text-secondary)', fontSize: '14px' }}>Sign in to manage your links</p>
        </div>

        {error && (
          <div style={{
            background: 'rgba(255, 51, 102, 0.1)',
            border: '1px solid var(--error-color)',
            color: 'var(--error-color)',
            padding: '12px',
            borderRadius: '8px',
            marginBottom: '20px',
            fontSize: '14px',
            textAlign: 'center'
          }}>
            {error}
          </div>
        )}

        <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
          <div>
            <label style={{ display: 'block', fontSize: '14px', color: 'var(--text-secondary)', marginBottom: '6px' }}>Email</label>
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
              style={{
                width: '100%',
                padding: '12px 16px',
                background: 'rgba(0,0,0,0.2)',
                border: '1px solid var(--glass-border)',
                borderRadius: '8px',
                color: 'white',
                fontSize: '15px',
                transition: 'border-color 0.2s'
              }}
              placeholder="you@example.com"
            />
          </div>

          <div>
            <label style={{ display: 'block', fontSize: '14px', color: 'var(--text-secondary)', marginBottom: '6px' }}>Password</label>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              style={{
                width: '100%',
                padding: '12px 16px',
                background: 'rgba(0,0,0,0.2)',
                border: '1px solid var(--glass-border)',
                borderRadius: '8px',
                color: 'white',
                fontSize: '15px',
                transition: 'border-color 0.2s'
              }}
              placeholder="••••••••"
            />
          </div>

          <button
            type="submit"
            disabled={isLoading}
            style={{
              marginTop: '8px',
              padding: '14px',
              background: 'var(--accent-color)',
              color: 'white',
              borderRadius: '8px',
              fontWeight: '600',
              fontSize: '15px',
              transition: 'background-color 0.2s, transform 0.1s',
              opacity: isLoading ? 0.7 : 1,
              transform: isLoading ? 'none' : 'translateY(0)',
              cursor: isLoading ? 'not-allowed' : 'pointer',
            }}
            onMouseDown={e => { if (!isLoading) e.currentTarget.style.transform = 'scale(0.98)' }}
            onMouseUp={e => { if (!isLoading) e.currentTarget.style.transform = 'scale(1)' }}
            onMouseLeave={e => { if (!isLoading) e.currentTarget.style.transform = 'scale(1)' }}
          >
            {isLoading ? 'Signing in...' : 'Sign In'}
          </button>
        </form>

        <p style={{ textAlign: 'center', marginTop: '24px', fontSize: '14px', color: 'var(--text-secondary)' }}>
          Don't have an account? <Link to="/register" style={{ fontWeight: '500' }}>Sign up</Link>
        </p>
      </GlassCard>
    </div>
  );
};

export default Login;
