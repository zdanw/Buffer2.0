import axios, { type AxiosRequestConfig } from 'axios';
import { getToken, removeToken } from './auth';

interface RetryConfig extends AxiosRequestConfig {
  retry?: number;
  retryDelay?: number;
}

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
    return config;
  },
  (error) => {
    return Promise.reject(error);
  }
);

axiosInstance.interceptors.response.use(
  (response) => {
    return response;
  },
  async (error) => {
    const config = error.config as RetryConfig;
    
    if (error.response?.status === 504 && (config.retry ?? 0) < 2) {
      config.retry = (config.retry ?? 0) + 1;
      await new Promise(resolve => setTimeout(resolve, config.retryDelay ?? 3000));
      return axiosInstance(config);
    }
    
    if (error.response?.status === 401) {
      const requestUrl = config?.url || '';
      const authPaths = ['/auth/login', '/auth/register', '/auth/me'];
      const isAuthPath = authPaths.some(path => requestUrl.includes(path));
      
      if (!isAuthPath) {
        removeToken();
        window.location.href = '/login';
      }
    }
    
    return Promise.reject(error);
  }
);

export default axiosInstance;
