import { useMemo } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import GlassCard from '../components/GlassCard';
import { BarChart3, Link as LinkIcon } from 'lucide-react';
import ShortenForm from '../components/ShortenForm';
import LinksTable from '../components/LinksTable';
import LiveIndicator from '../components/LiveIndicator';
import { apiClient } from '../api/client';
import { useSSE } from '../hooks/useSSE';
import type { Link, SSEEvent } from '../types';

const Dashboard = () => {
  const queryClient = useQueryClient();

  const { data: links = [], isLoading } = useQuery<Link[]>({
    queryKey: ['links'],
    queryFn: () => apiClient('/links'),
  });

  const stats = useMemo(() => ({
    totalLinks: links.length,
    totalClicks: links.reduce((acc, link) => acc + (link.clicks || 0), 0)
  }), [links]);

  const { isConnected, error: sseError } = useSSE((data: SSEEvent) => {
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
    queryClient.invalidateQueries({ queryKey: ['links'] });
  };

  return (
    <div className="animate-fade-in" style={{ display: 'flex', flexDirection: 'column', gap: '32px' }}>

      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <h1 style={{ fontSize: '24px', fontWeight: '700', margin: 0 }}>Dashboard</h1>
        <LiveIndicator isConnected={isConnected} error={sseError} />
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
    </div>
  );
};

export default Dashboard;
