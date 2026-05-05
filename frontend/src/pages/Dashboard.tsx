import { useMemo, useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import GlassCard from '../components/GlassCard';
import { BarChart3, Link as LinkIcon, History } from 'lucide-react';
import ShortenForm from '../components/ShortenForm';
import LinksTable from '../components/LinksTable';
import { apiClient } from '../api/client';
import { useSSESubscription, useSSEStatus } from '../context/SSEContext';
import { useAuth } from '../context/AuthContext';
import type { Link, SSEEvent } from '../types';

const Dashboard = () => {
  const { user } = useAuth();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [anonLinks, setAnonLinks] = useState<Link[]>([]);

  // Load anonymous links from localStorage
  useEffect(() => {
    if (!user) {
      const saved = localStorage.getItem('anonymous_links');
      if (saved) {
        try {
          setAnonLinks(JSON.parse(saved));
        } catch (e) {
          console.error('Failed to parse anonymous links', e);
        }
      }
    }
  }, [user]);

  const { data: links = [], isLoading } = useQuery<Link[]>({
    queryKey: ['links'],
    queryFn: () => apiClient('/links'),
    enabled: !!user,
  });

  const stats = useMemo(() => ({
    totalLinks: links.length,
    totalClicks: links.reduce((acc, link) => acc + (link.clicks || 0), 0)
  }), [links]);

  const { isConnected, error: sseError } = useSSEStatus();

  useSSESubscription((data: SSEEvent) => {
    if (!user) return;
    if (data.type === 'link_created' && data.link) {
      queryClient.setQueryData<Link[]>(['links'], (prev) => [data.link!, ...(prev || [])]);
    } else if (data.type === 'link_deleted' && data.short_code) {
      queryClient.setQueryData<Link[]>(['links'], (prev) =>
        (prev || []).filter(link => link.short_code !== data.short_code)
      );
    } else if (data.type === 'link_updated' && data.short_code) {
      queryClient.setQueryData<Link[]>(['links'], (prev) =>
        (prev || []).map(link =>
          link.short_code === data.short_code
            ? { ...link, clicks: data.clicks! }
            : link
        )
      );
    }
  });

  const handleRefresh = () => {
    if (user) {
      queryClient.invalidateQueries({ queryKey: ['links'] });
    } else {
      // For anonymous users, just reload from localStorage
      const saved = localStorage.getItem('anonymous_links');
      if (saved) setAnonLinks(JSON.parse(saved));
    }
  };

  return (
    <div className="animate-fade-in" style={{ display: 'flex', flexDirection: 'column', gap: '32px' }}>

      {!user ? (
        <div style={{ textAlign: 'center', padding: '20px 0 40px' }}>
          <h1 style={{ fontSize: '32px', fontWeight: '700', marginBottom: '12px' }}>
            URL Shortener
          </h1>
          <p style={{ color: 'var(--text-secondary)', fontSize: '16px', maxWidth: '600px', margin: '0 auto 32px' }}>
            Shorten your links instantly. Authorized users can also track detailed click statistics.
          </p>

          <div style={{ display: 'flex', justifyContent: 'center', gap: '16px', marginBottom: '40px' }}>
             <button
                onClick={() => navigate('/links/DEMO/analytics')}
                style={{
                  background: 'rgba(56,189,248,0.1)',
                  border: '1px solid rgba(56,189,248,0.2)',
                  color: 'var(--accent-color)',
                  padding: '12px 24px',
                  borderRadius: '12px',
                  fontWeight: '600',
                  cursor: 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '8px',
                  transition: 'all 0.2s'
                }}
                onMouseOver={e => {
                  e.currentTarget.style.background = 'rgba(56,189,248,0.2)';
                  e.currentTarget.style.transform = 'translateY(-2px)';
                }}
                onMouseOut={e => {
                  e.currentTarget.style.background = 'rgba(56,189,248,0.1)';
                  e.currentTarget.style.transform = 'translateY(0)';
                }}
              >
                <BarChart3 size={18} />
                View Demo Analytics
              </button>
          </div>

          <div style={{ marginBottom: '40px' }}>
            <ShortenForm onShortened={handleRefresh} />
          </div>

          {anonLinks.length > 0 && (
            <div style={{ textAlign: 'left' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '16px' }}>
                <History size={20} color="var(--accent-color)" />
                <h2 style={{ fontSize: '20px', fontWeight: '600', margin: 0 }}>Recent Links (this session)</h2>
              </div>
              <LinksTable links={anonLinks} isLoading={false} />
              <p style={{ marginTop: '16px', fontSize: '13px', color: 'var(--text-secondary)' }}>
                Tip: Register to save these links permanently and see detailed click statistics.
              </p>
            </div>
          )}
        </div>
      ) : (
        <>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <h1 style={{ fontSize: '24px', fontWeight: '700', margin: 0 }}>Dashboard</h1>
          </div>

          {/* Top Section: Stats */}
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))', gap: '24px' }}>
            <GlassCard style={{ padding: '24px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
                <div style={{ background: 'rgba(106, 0, 255, 0.2)', padding: '12px', borderRadius: '12px' }}>
                  <LinkIcon size={24} color="var(--accent-color)" />
                </div>
                <div>
                  <p style={{ color: 'var(--text-secondary)', fontSize: '14px', marginBottom: '4px' }}>Total Links</p>
                  <h3 style={{ fontSize: '28px', fontWeight: '700', margin: 0 }}>{stats.totalLinks}</h3>
                </div>
              </div>
            </GlassCard>

            <GlassCard style={{ padding: '24px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
                <div style={{ background: 'rgba(0, 212, 255, 0.2)', padding: '12px', borderRadius: '12px' }}>
                  <BarChart3 size={24} color="#00d4ff" />
                </div>
                <div>
                  <p style={{ color: 'var(--text-secondary)', fontSize: '14px', marginBottom: '4px' }}>Total Clicks</p>
                  <h3 style={{ fontSize: '28px', fontWeight: '700', margin: 0 }}>{stats.totalClicks}</h3>
                </div>
              </div>
            </GlassCard>
          </div>

          {/* Middle Section: Shorten Form */}
          <ShortenForm onShortened={handleRefresh} />

          {/* Bottom Section: Links Table */}
          <LinksTable links={links} isLoading={isLoading} onDelete={handleRefresh} />
        </>
      )}
    </div>
  );
};

export default Dashboard;
