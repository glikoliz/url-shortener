const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000/api/v1';

let isRefreshing = false;
let refreshSubscribers: (() => void)[] = [];

const subscribeTokenRefresh = (cb: () => void) => {
  refreshSubscribers.push(cb);
};

const onTokenRefreshed = () => {
  refreshSubscribers.map((cb) => cb());
  refreshSubscribers = [];
};

interface ApiOptions extends RequestInit {
  body?: any;
}

export const apiClient = async (endpoint: string, { body, ...customConfig }: ApiOptions = {}) => {
  const headers: Record<string, string> = { 'Content-Type': 'application/json' };

  const config: RequestInit = {
    method: body ? 'POST' : 'GET',
    credentials: 'include',
    ...customConfig,
    headers: {
      ...headers,
      ...(customConfig.headers as Record<string, string>),
    },
  };

  if (body) {
    if (body instanceof FormData) {
      if (config.headers) {
        delete (config.headers as Record<string, string>)['Content-Type'];
      }
      config.body = body;
    } else {
      config.body = JSON.stringify(body);
    }
  }

  try {
    const response = await fetch(`${API_URL}${endpoint}`, config);
    const data = await response.json().catch(() => null);

    if (response.ok) {
      return data;
    }

    // Handle 401 Unauthorized - attempt to refresh
    if (response.status === 401 && !endpoint.includes('/auth/login') && !endpoint.includes('/auth/refresh')) {
      if (!isRefreshing) {
        isRefreshing = true;
        try {
          const refreshResponse = await fetch(`${API_URL}/auth/refresh`, {
            method: 'POST',
            credentials: 'include',
          });

          if (refreshResponse.ok) {
            isRefreshing = false;
            onTokenRefreshed();

            const retryResponse = await fetch(`${API_URL}${endpoint}`, config);
            return await retryResponse.json();
          } else {
            isRefreshing = false;
            logout();
            throw new Error('Session expired');
          }
        } catch (e) {
          isRefreshing = false;
          logout();
          throw e;
        }
      } else {
        await new Promise<void>((resolve) => {
          subscribeTokenRefresh(() => resolve());
        });

        const retryResponse = await fetch(`${API_URL}${endpoint}`, config);
        return await retryResponse.json();
      }
    }

    let errorMessage = 'API Error';
    if (data?.error?.message) {
      errorMessage = data.error.message;
    } else if (data?.detail) {
      errorMessage = typeof data.detail === 'string' ? data.detail : JSON.stringify(data.detail);
    }

    throw new Error(errorMessage);

  } catch (error: any) {
    if (error.message === 'Session expired') {
      logout();
    }
    throw error;
  }
};

export const logout = async () => {
  try {
    await fetch(`${API_URL}/auth/logout`, { method: 'POST', credentials: 'include' });
  } catch (e) {
    console.error('Failed to logout on server', e);
  }

  if (window.location.pathname !== '/login') {
    window.location.href = '/login';
  }
};
