import axiosInstance from './axiosInstance';

export interface LoginData {
  username: string;
  password: string;
}

export interface CreateUserData {
  username: string;
  email?: string;
  password: string;
  is_admin?: boolean;
}

export interface UpdateUserData {
  email?: string;
  password?: string;
  is_active?: boolean;
  is_admin?: boolean;
}

export interface TokenResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
}

export interface UserResponse {
  user_id: string;
  username: string;
  email: string;
  is_active: boolean;
  is_admin: boolean;
  created_at: string;
}

export const login = async (data: LoginData): Promise<TokenResponse> => {
  const params = new URLSearchParams();
  params.append('username', data.username);
  params.append('password', data.password);
  
  const response = await axiosInstance.post('/auth/login/', params, {
    headers: {
      'Content-Type': 'application/x-www-form-urlencoded',
    },
  });
  return response.data;
};

export const getCurrentUser = async (): Promise<UserResponse> => {
  console.log('getCurrentUser called');
  const response = await axiosInstance.get('/auth/me');
  console.log('getCurrentUser response:', response.status, response.data);
  return response.data;
};

export const listUsers = async (): Promise<UserResponse[]> => {
  const response = await axiosInstance.get('/auth/users');
  return Array.isArray(response.data) ? response.data : [];
};

export const createUser = async (data: CreateUserData): Promise<UserResponse> => {
  const response = await axiosInstance.post('/auth/users/', data);
  return response.data;
};

export const updateUser = async (userId: string, data: UpdateUserData): Promise<UserResponse> => {
  const response = await axiosInstance.put(`/auth/users/${userId}`, data);
  return response.data;
};

export const deleteUser = async (userId: string): Promise<void> => {
  await axiosInstance.delete(`/auth/users/${userId}`);
};

export const getToken = (): string | null => {
  return localStorage.getItem('access_token');
};

export const setToken = (token: string): void => {
  console.log('setToken called with:', token.substring(0, 30), '...');
  localStorage.setItem('access_token', token);
};

export const removeToken = (): void => {
  console.log('removeToken called!');
  localStorage.removeItem('access_token');
};

export const getRefreshToken = (): string | null => {
  return localStorage.getItem('refresh_token');
};

export const setRefreshToken = (token: string): void => {
  localStorage.setItem('refresh_token', token);
};

export const removeRefreshToken = (): void => {
  localStorage.removeItem('refresh_token');
};

export const clearAuth = (): void => {
  removeToken();
  removeRefreshToken();
};

export const refreshToken = async (): Promise<TokenResponse> => {
  const refreshToken = getRefreshToken();
  if (!refreshToken) {
    throw new Error('No refresh token available');
  }
  
  const response = await axiosInstance.post('/auth/refresh/', {
    refresh_token: refreshToken,
  });
  return response.data;
};
