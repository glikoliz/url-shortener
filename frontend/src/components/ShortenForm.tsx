import { useState, type FormEvent } from 'react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import GlassCard from './GlassCard';
import { apiClient } from '../api/client';
import { Link2, Sparkles, Settings2, Copy, Check, AlertTriangle } from 'lucide-react';
import { useSSESubscription } from '../context/SSEContext';
import { useAuth } from '../context/AuthContext';
import type { Link, SSEEvent } from '../types';

interface ShortenFormProps {
  onShortened?: () => void;
}

const ShortenForm = ({ onShortened }: ShortenFormProps) => {
  const queryClient = useQueryClient();
  const [originalUrl, setOriginalUrl] = useState('');
  const [customCode, setCustomCode] = useState('');
  const [ttlDays, setTtlDays] = useState<string | number>(30);
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [copied, setCopied] = useState(false);
  const [bgError, setBgError] = useState<string | null>(null);

  const { user } = useAuth();
  const mutation = useMutation<Link, Error, any>({
    mutationFn: (payload) => apiClient('/links', {
      method: 'POST',
      body: payload
    }),
    onSuccess: (newLink) => {
      setOriginalUrl('');
      setCustomCode('');
      setBgError(null);

      // Save to local storage for anonymous users
      if (!user) {
        const savedLinks = JSON.parse(localStorage.getItem('anonymous_links') || '[]');
        localStorage.setItem('anonymous_links', JSON.stringify([newLink, ...savedLinks].slice(0, 10)));
      }

      if (onShortened) onShortened();
    }
  });

  const isLoading = mutation.isPending;
  const error = mutation.error?.message;
  const result = mutation.data;

  // Subscribe to global SSE events
  useSSESubscription((data: SSEEvent) => {
    if (data.type === 'link_deleted' && result && data.short_code === result.short_code) {
      if (data.reason === 'recursive_loop') {
        setBgError('Recursive loop detected. This link is not allowed and has been removed.');
      }
    }
  });

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setBgError(null);

    const payload: {
      original_url: string;
      ttl_minutes: number | null;
      custom_code?: string;
    } = {
      original_url: originalUrl,
      ttl_minutes: ttlDays ? parseInt(ttlDays.toString()) * 24 * 60 : null
    };

    if (customCode.trim()) {
      payload.custom_code = customCode.trim();
    }

    mutation.mutate(payload);
  };

  const handleCopy = () => {
    if (result?.short_url) {
      navigator.clipboard.writeText(result.short_url);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  return (
    <GlassCard>
      <h2 style={{ fontSize: '20px', marginBottom: '20px', display: 'flex', alignItems: 'center', gap: '8px' }}>
        <Sparkles size={20} color="var(--accent-color)" />
        Create New Short Link
      </h2>

      <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
        {error && (
          <div style={{
            background: 'rgba(255, 51, 102, 0.1)',
            border: '1px solid var(--error-color)',
            color: 'var(--error-color)',
            padding: '12px',
            borderRadius: '8px',
            fontSize: '14px'
          }}>
            {error}
          </div>
        )}

        <div style={{ display: 'flex', gap: '12px' }}>
          <div style={{ flex: 1, position: 'relative' }}>
            <div style={{ position: 'absolute', left: '16px', top: '50%', transform: 'translateY(-50%)' }}>
              <Link2 size={20} color="var(--text-secondary)" />
            </div>
            <input
              type="url"
              placeholder="Paste your long URL here..."
              value={originalUrl}
              onChange={e => setOriginalUrl(e.target.value)}
              required
              style={{
                width: '100%',
                padding: '16px 16px 16px 48px',
                background: 'rgba(0,0,0,0.3)',
                border: '1px solid var(--glass-border)',
                borderRadius: '12px',
                color: 'white',
                fontSize: '16px',
                transition: 'all 0.2s'
              }}
            />
          </div>
          <button
            type="submit"
            disabled={isLoading}
            style={{
              padding: '0 24px',
              background: 'var(--accent-color)',
              color: 'white',
              borderRadius: '12px',
              fontWeight: '600',
              fontSize: '16px',
              transition: 'background-color 0.2s, transform 0.1s',
              opacity: isLoading ? 0.7 : 1,
              cursor: isLoading ? 'not-allowed' : 'pointer',
              whiteSpace: 'nowrap'
            }}
          >
            {isLoading ? 'Shortening...' : 'Shorten'}
          </button>
        </div>

        <div>
          <button
            type="button"
            onClick={() => setShowAdvanced(!showAdvanced)}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
              background: 'transparent',
              color: 'var(--text-secondary)',
              fontSize: '14px',
              padding: '4px 0'
            }}
          >
            <Settings2 size={16} />
            {showAdvanced ? 'Hide Advanced Options' : 'Advanced Options'}
          </button>
        </div>

        {showAdvanced && (
          <div className="animate-fade-in" style={{
            display: 'grid',
            gridTemplateColumns: '1fr 1fr',
            gap: '16px',
            padding: '16px',
            background: 'rgba(255, 255, 255, 0.02)',
            borderRadius: '8px',
            border: '1px dashed var(--glass-border)'
          }}>
            {!user && (
              <div style={{ gridColumn: '1 / -1', marginBottom: '8px', padding: '8px', background: 'rgba(255, 215, 0, 0.1)', border: '1px solid rgba(255, 215, 0, 0.3)', borderRadius: '6px', fontSize: '12px', color: '#ffd700', display: 'flex', alignItems: 'center', gap: '8px' }}>
                <AlertTriangle size={14} />
                Sign in to use custom aliases and longer expiration. Anonymous links expire in 7 days.
              </div>
            )}
            <div>
              <label style={{ display: 'block', fontSize: '13px', color: 'var(--text-secondary)', marginBottom: '6px' }}>Custom Alias (optional)</label>
              <input
                type="text"
                placeholder={user ? "e.g. my-campaign" : "Pro feature"}
                value={customCode}
                onChange={e => setCustomCode(e.target.value)}
                maxLength={20}
                disabled={!user}
                style={{
                  width: '100%',
                  padding: '10px 12px',
                  background: user ? 'rgba(0,0,0,0.2)' : 'rgba(0,0,0,0.4)',
                  border: '1px solid var(--glass-border)',
                  borderRadius: '6px',
                  color: user ? 'white' : 'rgba(255,255,255,0.3)',
                  fontSize: '14px',
                  cursor: user ? 'text' : 'not-allowed'
                }}
              />
            </div>
            <div>
              <label style={{ display: 'block', fontSize: '13px', color: 'var(--text-secondary)', marginBottom: '6px' }}>Expiration (Days)</label>
              <input
                type="number"
                min="1"
                max="365"
                value={user ? ttlDays : 7}
                onChange={e => setTtlDays(e.target.value)}
                disabled={!user}
                style={{
                  width: '100%',
                  padding: '10px 12px',
                  background: user ? 'rgba(0,0,0,0.2)' : 'rgba(0,0,0,0.4)',
                  border: '1px solid var(--glass-border)',
                  borderRadius: '6px',
                  color: user ? 'white' : 'rgba(255,255,255,0.3)',
                  fontSize: '14px',
                  cursor: user ? 'text' : 'not-allowed'
                }}
              />
            </div>
          </div>
        )}
      </form>

      {/* Background Error State (Recursive Loop Detected) */}
      {bgError && (
        <div className="animate-fade-in" style={{
          marginTop: '24px',
          padding: '20px',
          background: 'rgba(255, 51, 102, 0.1)',
          border: '1px solid var(--error-color)',
          borderRadius: '12px',
          display: 'flex',
          alignItems: 'center',
          gap: '12px',
          color: 'var(--error-color)'
        }}>
          <AlertTriangle size={24} />
          <p style={{ fontSize: '14px', fontWeight: '500' }}>{bgError}</p>
        </div>
      )}

      {/* Result Section (Only if no background error) */}
      {result && !bgError && (
        <div className="animate-fade-in" style={{
          marginTop: '24px',
          padding: '16px 20px',
          background: 'rgba(0, 212, 255, 0.08)',
          border: '1px solid rgba(0, 212, 255, 0.2)',
          borderRadius: '16px'
        }}>
          <p style={{ fontSize: '13px', color: 'var(--text-secondary)', marginBottom: '8px', display: 'flex', alignItems: 'center', gap: '6px' }}>
            <Sparkles size={14} color="#00d4ff" />
            Your short URL is ready:
          </p>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '12px' }}>
            <a href={result.short_url} target="_blank" rel="noreferrer" style={{ fontSize: '18px', fontWeight: '600', color: '#00d4ff', wordBreak: 'break-all' }}>
              {result.short_url}
            </a>
            <button
              onClick={handleCopy}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '8px',
                padding: '8px 16px',
                background: copied ? '#00ff88' : 'rgba(0, 212, 255, 0.15)',
                color: copied ? '#000' : 'white',
                borderRadius: '8px',
                fontWeight: '600',
                fontSize: '14px',
                transition: 'all 0.2s',
                border: '1px solid rgba(0, 212, 255, 0.2)',
                flexShrink: 0
              }}
            >
              {copied ? <Check size={16} /> : <Copy size={16} />}
              {copied ? 'Copied!' : 'Copy'}
            </button>
          </div>
        </div>
      )}
    </GlassCard>
  );
};

export default ShortenForm;
