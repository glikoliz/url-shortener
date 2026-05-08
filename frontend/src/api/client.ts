const API_URL = import.meta.env.VITE_API_URL || '';

let isRefreshing = false;
let refreshSubscribers: ((success: boolean) => void)[] = [];

const subscribeTokenRefresh = (cb: (success: boolean) => void) => {
  refreshSubscribers.push(cb);
};

const onTokenRefreshed = (success: boolean) => {
  refreshSubscribers.forEach((cb) => cb(success));
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

  const fullUrl = `${API_URL}${endpoint}`;

  try {
    const response = await fetch(fullUrl, config);

    // Handle 401 - attempt to refresh (all endpoints except /auth/refresh itself)
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
            onTokenRefreshed(true);

            const retryResponse = await fetch(fullUrl, config);
            if (!retryResponse.ok) {
              // /auth/me returning 401 even after refresh means session is truly gone
              if (endpoint === '/auth/me') throw new Error('Unauthorized');
              throw new Error('Retry failed after refresh');
            }
            return await retryResponse.json();
          } else {
            isRefreshing = false;
            onTokenRefreshed(false);
            if (endpoint !== '/auth/me') logout();
            throw new Error('Unauthorized');
          }
        } catch (e) {
          isRefreshing = false;
          onTokenRefreshed(false);
          throw e;
        }
      } else {
        // Wait for refresh to complete
        const success = await new Promise<boolean>((resolve) => {
          subscribeTokenRefresh((res) => resolve(res));
        });

        if (success) {
          const retryResponse = await fetch(fullUrl, config);
          if (!retryResponse.ok) throw new Error('Retry failed after refresh');
          return await retryResponse.json();
        } else {
          throw new Error('Unauthorized');
        }
      }
    }

    const data = await response.json().catch(() => null);

    if (response.ok) {
      return data;
    }

    let errorMessage = 'API Error';
    if (data?.error?.message) {
      errorMessage = data.error.message;
    } else if (data?.detail) {
      errorMessage = typeof data.detail === 'string' ? data.detail : JSON.stringify(data.detail);
    }

    throw new Error(errorMessage);

  } catch (error: any) {
    throw error;
  }
};

export const logout = async () => {
  try {
    await fetch(`${API_URL}/auth/logout`, { method: 'POST', credentials: 'include' });
  } catch (e) {
    // Silently fail or log in dev
  }

  if (window.location.pathname !== '/login') {
    window.location.href = '/login';
  }
};
