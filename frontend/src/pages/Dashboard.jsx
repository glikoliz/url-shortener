import { useState, useEffect, useCallback } from 'react';
import GlassCard from '../components/GlassCard';
import { BarChart3, Link as LinkIcon } from 'lucide-react';
import ShortenForm from '../components/ShortenForm';
import LinksTable from '../components/LinksTable';
import LiveIndicator from '../components/LiveIndicator';
import { apiClient } from '../api/client';
import { useSSE } from '../hooks/useSSE';

const Dashboard = () => {
  const [links, setLinks] = useState([]);
  const [stats, setStats] = useState({ totalLinks: '--', totalClicks: '--' });
  const [isLoading, setIsLoading] = useState(true);

  const updateStats = useCallback((linksData) => {
    setStats({
      totalLinks: linksData.length,
      totalClicks: linksData.reduce((acc, link) => acc + (link.clicks || 0), 0)
    });
  }, []);

  const fetchLinks = useCallback(async (showLoading = false) => {
    if (showLoading) {
      Promise.resolve().then(() => setIsLoading(true));
    }
    try {
      const data = await apiClient('/links');
      if (data) {
        setLinks(data);
        updateStats(data);
      }
    } catch (err) {
      console.error("Failed to fetch links", err);
    } finally {
      if (showLoading) setIsLoading(false);
    }
  }, [updateStats]);

  // Real-time updates via SSE hook
  const { isConnected, error: sseError } = useSSE((data) => {
    if (data.type === 'link_created' && data.link) {
      setLinks(prev => {
        const newLinks = [data.link, ...prev];
        updateStats(newLinks);
        return newLinks;
      });
    } else if (data.type === 'link_deleted' && data.short_code) {
      setLinks(prev => {
        const newLinks = prev.filter(link => link.short_code !== data.short_code);
        updateStats(newLinks);
        return newLinks;
      });
    } else if (data.type === 'link_updated' && data.short_code) {
      setLinks(prev => {
        const newLinks = prev.map(link =>
          link.short_code === data.short_code
            ? { ...link, clicks: data.clicks }
            : link
        );
        updateStats(newLinks);
        return newLinks;
      });
    }
  });

  useEffect(() => {
    const loadData = async () => {
      await fetchLinks();
    };
    loadData();
  }, [fetchLinks]);

  const handleShortened = () => fetchLinks(false);
  const handleDeleted = () => fetchLinks(false);

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
      <ShortenForm onShortened={handleShortened} />

      {/* Bottom Section: Links Table */}
      <LinksTable links={links} isLoading={isLoading} onDelete={handleDeleted} />
    </div>
  );
};

export default Dashboard;
