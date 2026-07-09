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
  const response = await axiosInstance.post('/auth/login', data);
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
  return response.data;
};

export const createUser = async (data: CreateUserData): Promise<UserResponse> => {
  const response = await axiosInstance.post('/auth/users', data);
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

export const isAuthenticated = (): boolean => {
  return !!getToken();
};

export const getUserRole = (): boolean | null => {
  const token = getToken();
  if (!token) return null;
  try {
    const payload = JSON.parse(atob(token.split('.')[1]));
    return payload.is_admin || false;
  } catch {
    return null;
  }
};