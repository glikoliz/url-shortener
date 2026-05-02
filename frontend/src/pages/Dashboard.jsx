import React, { useState, useEffect } from 'react';
import GlassCard from '../components/GlassCard';
import { BarChart3, Link as LinkIcon } from 'lucide-react';
import ShortenForm from '../components/ShortenForm';
import LinksTable from '../components/LinksTable';
import { apiClient } from '../api/client';

const Dashboard = () => {
  const [refreshTrigger, setRefreshTrigger] = useState(0);
  const [stats, setStats] = useState({ totalLinks: '--', totalClicks: '--' });

  const fetchStats = async () => {
    try {
      const data = await apiClient('/links');
      if (data) {
        setStats({
          totalLinks: data.length,
          totalClicks: data.reduce((acc, link) => acc + link.clicks, 0)
        });
      }
    } catch (err) {
      console.error("Failed to fetch stats", err);
    }
  };

  useEffect(() => {
    fetchStats();
  }, [refreshTrigger]);

  const handleShortened = () => {
    setRefreshTrigger(prev => prev + 1);
  };

  return (
    <div className="animate-fade-in" style={{ display: 'flex', flexDirection: 'column', gap: '32px' }}>
      
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
      <LinksTable refreshTrigger={refreshTrigger} />
      
    </div>
  );
};

export default Dashboard;
