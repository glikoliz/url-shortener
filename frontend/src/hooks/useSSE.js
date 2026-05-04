import { useEffect, useState, useRef } from 'react';
import { useAuth } from '../context/AuthContext';

export const useSSE = (onEvent) => {
  const { token, logout } = useAuth();
  const [isConnected, setIsConnected] = useState(false);
  const [error, setError] = useState(false);
  const onEventRef = useRef(onEvent);

  // Update ref when onEvent changes to avoid effect re-runs
  useEffect(() => {
    onEventRef.current = onEvent;
  }, [onEvent]);

  useEffect(() => {
    if (!token) return;

    let eventSource = null;
    let reconnectTimeout = null;

    const connect = () => {
      const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000/api/v1';
      const url = `${API_URL}/links/stream?token=${encodeURIComponent(token)}`;

      eventSource = new EventSource(url);

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

      eventSource.onerror = (err) => {
        setIsConnected(false);
        // If closed, it might be a 401 or network issue
        if (eventSource.readyState === EventSource.CLOSED) {
          setError(true);

          // Basic token expiry check
          try {
            const payload = JSON.parse(atob(token.split('.')[1]));
            if (Date.now() >= payload.exp * 1000) {
              logout();
              return;
            }
          } catch (e) { }

          // Retry logic for network issues
          reconnectTimeout = setTimeout(connect, 5000);
        }
      };
    };

    connect();

    return () => {
      if (eventSource) eventSource.close();
      if (reconnectTimeout) clearTimeout(reconnectTimeout);
    };
  }, [token, logout]);

  return { isConnected, error };
};
