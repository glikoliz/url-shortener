import { useEffect, useState, useRef } from 'react';
import { useAuth } from '../context/AuthContext';
import { apiClient } from '../api/client';
import type { SSEEvent } from '../types';

export const useSSE = (onEvent: (data: SSEEvent) => void) => {
  const { user, logout } = useAuth();
  const [isConnected, setIsConnected] = useState(false);
  const [error, setError] = useState(false);
  const onEventRef = useRef<(data: SSEEvent) => void>(onEvent);

  useEffect(() => {
    onEventRef.current = onEvent;
  }, [onEvent]);

  useEffect(() => {
    if (!user) return;

    let eventSource: EventSource | null = null;
    let reconnectTimeout: ReturnType<typeof setTimeout> | null = null;

    const connect = () => {
      const API_URL = (import.meta as any).env.VITE_API_URL || 'http://localhost:8000/api/v1';
      const url = `${API_URL}/links/events/stream`;

      eventSource = new EventSource(url, { withCredentials: true });

      eventSource.onopen = () => {
        setIsConnected(true);
        setError(false);
        console.log('SSE Connected');
      };

      eventSource.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          if (onEventRef.current) {
            onEventRef.current(data);
          }
        } catch (err) {
          console.error('SSE Parse Error:', err);
        }
      };

      eventSource.onerror = async () => {
        setIsConnected(false);
        try {
          await apiClient('/auth/me');
          if (eventSource && eventSource.readyState === EventSource.CLOSED) {
            setError(true);
            reconnectTimeout = setTimeout(connect, 3000);
          }
        } catch (err) {
          console.log('SSE stop retry: session invalid');
          setError(true);
        }
      };
    };

    connect();

    return () => {
      if (eventSource) eventSource.close();
      if (reconnectTimeout) clearTimeout(reconnectTimeout);
    };
  }, [user, logout]);

  return { isConnected, error };
};
