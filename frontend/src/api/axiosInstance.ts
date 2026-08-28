import axios, { type AxiosRequestConfig } from 'axios';
import { getToken, setToken, clearAuth, refreshToken as apiRefreshToken } from './auth';

interface RetryConfig extends AxiosRequestConfig {
  retry?: number;
  retryDelay?: number;
  _retry?: boolean;
}

// 始终同源 /v1 → Vercel api/index.cjs（https）→ HF Space。
// 禁止使用 VITE_BACKEND_URL 等绝对地址，否则 HTTPS 前端会 Mixed Content。
const axiosInstance = axios.create({
  baseURL: '/v1',
  timeout: 60000,
  headers: {
    'Content-Type': 'application/json',
  },
});

axiosInstance.interceptors.request.use(
  (config) => {
    const token = getToken();
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    const cfg = config as RetryConfig;
    cfg.retry = cfg.retry || 0;
    cfg.retryDelay = cfg.retryDelay || 3000;
    cfg._retry = cfg._retry || false;
    return config;
  },
  (error) => {
    return Promise.reject(error);
  }
);

axiosInstance.interceptors.response.use(
  (response) => {
    console.log(`API Success: ${response.config.url} - Status: ${response.status}`);
    return response;
  },
  async (error) => {
    const config = error.config as RetryConfig;
    
    console.error(`API Error: ${config?.url}`);
    console.error('Error response:', error.response?.status, error.response?.data);
    console.error('Error message:', error.message);
    
    const isTimeout =
      error.code === 'ECONNABORTED' ||
      (typeof error.message === 'string' && error.message.toLowerCase().includes('timeout'));
    const isRetryableStatus =
      error.response?.status === 502 ||
      error.response?.status === 503 ||
      error.response?.status === 504;
    const maxRetries = config.url?.includes('/generate/status/') ? 5 : 2;

    if ((isRetryableStatus || isTimeout) && (config.retry ?? 0) < maxRetries) {
      console.log(`Retry attempt ${(config.retry ?? 0) + 1} for ${config.url}`);
      config.retry = (config.retry ?? 0) + 1;
      await new Promise(resolve => setTimeout(resolve, config.retryDelay ?? 3000));
      return axiosInstance(config);
    }
    
    if (error.response?.status === 401) {
      const requestUrl = config?.url || '';
      const authPaths = ['/auth/login', '/auth/register', '/auth/refresh'];
      const isAuthPath = authPaths.some(path => requestUrl.includes(path));
      
      if (!isAuthPath && !config._retry) {
        try {
          console.log('Attempting to refresh token...');
          const newToken = await apiRefreshToken();
          if (newToken && newToken.access_token) {
            setToken(newToken.access_token);
            config._retry = true;
            if (!config.headers) {
              config.headers = {};
            }
            config.headers.Authorization = `Bearer ${newToken.access_token}`;
            return axiosInstance(config);
          }
        } catch (refreshError) {
          console.error('Token refresh failed:', refreshError);
        }
        
        console.log('Token expired or refresh failed, redirecting to login');
        clearAuth();
        if (window.location.pathname !== '/login' && window.location.pathname !== '/signup') {
          window.location.href = '/login';
        }
      }
    }
    
    return Promise.reject(error);
  }
);

export default axiosInstance;
