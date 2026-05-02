import React, { useState, useEffect } from 'react';
import GlassCard from './GlassCard';
import { apiClient } from '../api/client';
import { Trash2, Copy, ExternalLink, Calendar, Link2, Check } from 'lucide-react';

const LinksTable = ({ refreshTrigger }) => {
  const [links, setLinks] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState('');
  const [copiedCode, setCopiedCode] = useState(null);

  const fetchLinks = async () => {
    setIsLoading(true);
    try {
      const data = await apiClient('/links');
      setLinks(data || []);
    } catch (err) {
      setError('Failed to load your links');
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchLinks();
  }, [refreshTrigger]);

  const handleDelete = async (shortCode) => {
    if (!window.confirm('Are you sure you want to delete this link?')) return;
    
    try {
      await apiClient(`/links/${shortCode}`, { method: 'DELETE' });
      setLinks(links.filter(link => link.short_code !== shortCode));
    } catch (err) {
      alert('Failed to delete link');
    }
  };

  const handleCopy = (url, code) => {
    navigator.clipboard.writeText(url);
    setCopiedCode(code);
    setTimeout(() => setCopiedCode(null), 2000);
  };

  if (isLoading) {
    return (
      <GlassCard>
        <h2 style={{ fontSize: '20px', marginBottom: '16px' }}>Your Links</h2>
        <div style={{ textAlign: 'center', padding: '40px', color: 'var(--text-secondary)' }}>
          Loading your links...
        </div>
      </GlassCard>
    );
  }

  if (error) {
    return (
      <GlassCard>
        <h2 style={{ fontSize: '20px', marginBottom: '16px' }}>Your Links</h2>
        <div style={{ color: 'var(--error-color)', textAlign: 'center', padding: '20px' }}>
          {error}
        </div>
      </GlassCard>
    );
  }

  if (links.length === 0) {
    return (
      <GlassCard>
        <h2 style={{ fontSize: '20px', marginBottom: '16px' }}>Your Links</h2>
        <div style={{ textAlign: 'center', padding: '40px', color: 'var(--text-secondary)' }}>
          You haven't shortened any links yet.
        </div>
      </GlassCard>
    );
  }

  return (
    <GlassCard>
      <h2 style={{ fontSize: '20px', marginBottom: '20px' }}>Your Links</h2>
      
      <div style={{ overflowX: 'auto' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left' }}>
          <thead>
            <tr style={{ borderBottom: '1px solid var(--glass-border)', color: 'var(--text-secondary)', fontSize: '14px' }}>
              <th style={{ padding: '12px 16px', fontWeight: '500' }}>Short URL</th>
              <th style={{ padding: '12px 16px', fontWeight: '500' }}>Original URL</th>
              <th style={{ padding: '12px 16px', fontWeight: '500' }}>Clicks</th>
              <th style={{ padding: '12px 16px', fontWeight: '500' }}>Created</th>
              <th style={{ padding: '12px 16px', fontWeight: '500', textAlign: 'right' }}>Actions</th>
            </tr>
          </thead>
          <tbody>
            {links.map((link) => (
              <tr key={link.short_code} style={{ borderBottom: '1px solid rgba(255,255,255,0.05)', transition: 'background 0.2s' }} className="hover-row">
                <td style={{ padding: '16px' }}>
                  <a href={link.short_url} target="_blank" rel="noreferrer" style={{ display: 'inline-flex', alignItems: 'center', gap: '6px', fontWeight: '500', color: '#00d4ff' }}>
                    {link.short_url.replace(/^https?:\/\//, '')}
                    <ExternalLink size={14} />
                  </a>
                </td>
                <td style={{ padding: '16px', maxWidth: '300px', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', color: 'var(--text-secondary)', fontSize: '14px' }}>
                  {link.original_url}
                </td>
                <td style={{ padding: '16px', fontWeight: '600' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                    {link.clicks}
                  </div>
                </td>
                <td style={{ padding: '16px', color: 'var(--text-secondary)', fontSize: '14px' }}>
                  {new Date(link.created_at).toLocaleDateString()}
                </td>
                <td style={{ padding: '16px', textAlign: 'right' }}>
                  <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '8px' }}>
                    <button
                      onClick={() => handleCopy(link.short_url, link.short_code)}
                      style={{
                        padding: '6px',
                        background: 'rgba(255,255,255,0.05)',
                        borderRadius: '6px',
                        color: copiedCode === link.short_code ? '#00ff88' : 'var(--text-secondary)',
                        transition: 'all 0.2s'
                      }}
                      title="Copy"
                    >
                      {copiedCode === link.short_code ? <Check size={16} /> : <Copy size={16} />}
                    </button>
                    <button
                      onClick={() => handleDelete(link.short_code)}
                      style={{
                        padding: '6px',
                        background: 'rgba(255,51,102,0.1)',
                        borderRadius: '6px',
                        color: 'var(--error-color)',
                        transition: 'all 0.2s'
                      }}
                      title="Delete"
                      onMouseOver={e => e.currentTarget.style.background = 'rgba(255,51,102,0.2)'}
                      onMouseOut={e => e.currentTarget.style.background = 'rgba(255,51,102,0.1)'}
                    >
                      <Trash2 size={16} />
                    </button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <style>{`
        .hover-row:hover { background: rgba(255,255,255,0.02); }
      `}</style>
    </GlassCard>
  );
};

export default LinksTable;
