import axios from 'axios';
import { getToken, removeToken } from './auth';

const backendUrl = import.meta.env.VITE_BACKEND_URL || '';

const axiosInstance = axios.create({
  baseURL: backendUrl ? `${backendUrl}/api` : '/api',
  timeout: 30000,
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
  (error) => {
    if (error.response?.status === 401) {
      const requestUrl = error.config?.url || '';
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