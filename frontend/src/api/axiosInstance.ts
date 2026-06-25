import axios from 'axios';
import { getToken, removeToken } from './auth';

const axiosInstance = axios.create({
  baseURL: '/api',
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json',
  },
});

axiosInstance.interceptors.request.use(
  (config) => {
    const token = getToken();
    console.log('[' + new Date().toISOString() + '] Request:', config.url, 'Token exists:', !!token, 'Token value:', token ? token.substring(0, 20) + '...' : 'null');
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
      console.log('Authorization header set');
    }
    return config;
  },
  (error) => {
    return Promise.reject(error);
  }
);

axiosInstance.interceptors.response.use(
  (response) => {
    console.log('Response:', response.config.url, response.status);
    return response;
  },
  (error) => {
    console.log('Error:', error.config?.url, error.response?.status, error.message);
    if (error.response?.status === 401) {
      const requestUrl = error.config?.url || '';
      console.log('401 on:', requestUrl);
      const authPaths = ['/auth/login', '/auth/register', '/auth/me', '/api/auth/login', '/api/auth/register', '/api/auth/me'];
      const isAuthPath = authPaths.some(path => requestUrl.includes(path));
      console.log('Is auth path:', isAuthPath);
      
      if (!isAuthPath) {
        console.log('Removing token and redirecting');
        removeToken();
        window.location.href = '/login';
      }
    }
    return Promise.reject(error);
  }
);

export default axiosInstance;