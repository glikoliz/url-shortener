const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000/api/v1';

let isRefreshing = false;
let refreshSubscribers: ((token: string) => void)[] = [];

const subscribeTokenRefresh = (cb: (token: string) => void) => {
  refreshSubscribers.push(cb);
};

const onTokenRefreshed = (token: string) => {
  refreshSubscribers.map((cb) => cb(token));
  refreshSubscribers = [];
};

interface ApiOptions extends RequestInit {
  body?: any;
}

export const apiClient = async (endpoint: string, { body, ...customConfig }: ApiOptions = {}) => {
  const token = localStorage.getItem('token');
  const headers: Record<string, string> = { 'Content-Type': 'application/json' };

  if (token) {
    headers.Authorization = `Bearer ${token}`;
  }

  const config: RequestInit = {
    method: body ? 'POST' : 'GET',
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

    // Handle 401 Unauthorized
    if (response.status === 401 && !endpoint.includes('/auth/login') && !endpoint.includes('/auth/refresh')) {
      const refreshToken = localStorage.getItem('refreshToken');

      if (!refreshToken) {
        logout();
        throw new Error('Session expired');
      }

      if (!isRefreshing) {
        isRefreshing = true;
        try {
          const refreshResponse = await fetch(`${API_URL}/auth/refresh`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ refresh_token: refreshToken }),
          });

          if (refreshResponse.ok) {
            const { access_token, refresh_token } = await refreshResponse.json();
            localStorage.setItem('token', access_token);
            localStorage.setItem('refreshToken', refresh_token);
            isRefreshing = false;
            onTokenRefreshed(access_token);

            if (config.headers) {
              (config.headers as Record<string, string>).Authorization = `Bearer ${access_token}`;
            }
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
        // Wait for refresh to complete and retry
        const newToken = await new Promise<string>((resolve) => {
          subscribeTokenRefresh((token) => resolve(token));
        });

        if (config.headers) {
          (config.headers as Record<string, string>).Authorization = `Bearer ${newToken}`;
        }
        const retryResponse = await fetch(`${API_URL}${endpoint}`, config);
        return await retryResponse.json();
      }
    }

    // Handle errors using the NEW structure: { success: false, error: { message, details } }
    let errorMessage = 'API Error';

    if (data?.error?.message) {
      errorMessage = data.error.message;
      if (data.error.details && Array.isArray(data.error.details)) {
         const details = data.error.details.map((e: any) => `${e.loc?.join('.') || 'input'}: ${e.msg}`).join('; ');
         errorMessage = `${errorMessage} (${details})`;
      }
    } else if (data?.detail) {
        // Fallback for old style errors
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

const logout = () => {
  localStorage.removeItem('token');
  localStorage.removeItem('refreshToken');
  if (window.location.pathname !== '/login') {
    window.location.href = '/login';
  }
};
