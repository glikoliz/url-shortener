import React, { createContext, useContext, useEffect, useState, useRef } from 'react';
import { useAuth } from './AuthContext';
import { apiClient } from '../api/client';
import type { SSEEvent } from '../types';

interface SSEContextType {
  isConnected: boolean;
  error: boolean;
}

const SSEContext = createContext<SSEContextType | undefined>(undefined);

export const SSEProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const { user } = useAuth();
  const [isConnected, setIsConnected] = useState(false);
  const [error, setError] = useState(false);
  const listeners = useRef<Set<(data: SSEEvent) => void>>(new Set());

  // Method for components to subscribe to events
  const subscribe = (callback: (data: SSEEvent) => void) => {
    listeners.current.add(callback);
    return () => {
      listeners.current.delete(callback);
    };
  };

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
      };

      eventSource.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          listeners.current.forEach(listener => listener(data));
        } catch (err) {
        }
      };

      eventSource.onerror = async () => {
        setIsConnected(false);
        try {
          // Check if session is still valid
          await apiClient('/auth/me');
          if (eventSource && eventSource.readyState === EventSource.CLOSED) {
            setError(true);
            reconnectTimeout = setTimeout(connect, 3000);
          }
        } catch (err) {
          setError(true);
        }
      };
    };

    connect();

    return () => {
      if (eventSource) eventSource.close();
      if (reconnectTimeout) clearTimeout(reconnectTimeout);
    };
  }, [user]);

  return (
    <SSEContext.Provider value={{ isConnected, error }}>
      {(children as any).__sse_subscribe = subscribe}
      {children}
    </SSEContext.Provider>
  );
};


const SSEInternalContext = createContext<((cb: (data: SSEEvent) => void) => () => void) | null>(null);

export const OptimizedSSEProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const { user } = useAuth();
  const [isConnected, setIsConnected] = useState(false);
  const [error, setError] = useState(false);
  const listeners = useRef<Set<(data: SSEEvent) => void>>(new Set());

  const subscribe = (callback: (data: SSEEvent) => void) => {
    listeners.current.add(callback);
    return () => {
      listeners.current.delete(callback);
    };
  };

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
      };

      eventSource.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          listeners.current.forEach(l => l(data));
        } catch (err) {
          // Parse error: skipping message
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
          setError(true);
        }
      };
    };

    connect();
    return () => {
      if (eventSource) eventSource.close();
      if (reconnectTimeout) clearTimeout(reconnectTimeout);
    };
  }, [user]);

  return (
    <SSEContext.Provider value={{ isConnected, error }}>
      <SSEInternalContext.Provider value={subscribe}>
        {children}
      </SSEInternalContext.Provider>
    </SSEContext.Provider>
  );
};

export const useSSEStatus = () => {
  const context = useContext(SSEContext);
  if (context === undefined) {
    throw new Error('useSSEStatus must be used within a SSEProvider');
  }
  return context;
};

export const useSSESubscription = (onEvent: (data: SSEEvent) => void) => {
  const subscribe = useContext(SSEInternalContext);
  const onEventRef = useRef(onEvent);

  useEffect(() => {
    onEventRef.current = onEvent;
  }, [onEvent]);

  useEffect(() => {
    if (!subscribe) return;
    const unsubscribe = subscribe((data) => onEventRef.current(data));
    return () => unsubscribe();
  }, [subscribe]);
};
