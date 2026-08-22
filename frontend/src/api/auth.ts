import axiosInstance from './axiosInstance';

export interface LoginData {
  username: string;
  password: string;
}

export interface RegisterData {
  username: string;
  email: string;
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
  refresh_token?: string;
  token_type: string;
}

export interface UserResponse {
  user_id: string;
  username: string;
  email: string;
  is_active: boolean;
  is_admin: boolean;
  created_at: string;
  onboarding_completed_at?: string | null;
  image_credits_remaining?: number;
  has_system_image_provider?: boolean;
  billing_contact?: string | null;
  billing_enabled?: boolean;
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

export const register = async (data: RegisterData): Promise<TokenResponse> => {
  const response = await axiosInstance.post('/auth/register/', {
    username: data.username,
    email: data.email,
    password: data.password,
  });
  return response.data;
};

const AUTH_USER_ID_KEY = 'pulseforge_auth_user_id';
const ACTIVE_BRAND_KEY = 'pulseforge_active_brand_id';
const ONBOARDING_SKIP_KEY = 'pulseforge_onboarding_skipped';
const STUDIO_STATE_KEY = 'pulseforge_studio_state';
const LEGACY_STUDIO_STATE_KEYS = [
  STUDIO_STATE_KEY,
  'bebcare_content_preview_state',
] as const;

export const getAuthUserId = (): string | null => {
  return localStorage.getItem(AUTH_USER_ID_KEY);
};

export const studioStateStorageKey = (userId: string): string =>
  `${STUDIO_STATE_KEY}:${userId}`;

/** Clear browser-local session data that must not leak across accounts. */
export const clearSessionLocalState = (): void => {
  for (const key of LEGACY_STUDIO_STATE_KEYS) {
    localStorage.removeItem(key);
  }
  for (let i = localStorage.length - 1; i >= 0; i -= 1) {
    const key = localStorage.key(i);
    if (key?.startsWith(`${STUDIO_STATE_KEY}:`)) {
      localStorage.removeItem(key);
    }
  }
  localStorage.removeItem(ACTIVE_BRAND_KEY);
  localStorage.removeItem(ONBOARDING_SKIP_KEY);
  localStorage.removeItem(AUTH_USER_ID_KEY);
};

export const getCurrentUser = async (): Promise<UserResponse> => {
  const response = await axiosInstance.get('/auth/me');
  const user = response.data as UserResponse;
  const previousUserId = getAuthUserId();
  if (previousUserId && previousUserId !== user.user_id) {
    // Token swapped to another account without logout — drop shared session keys.
    localStorage.removeItem(ACTIVE_BRAND_KEY);
    localStorage.removeItem(ONBOARDING_SKIP_KEY);
  }
  // Unscoped studio drafts are obsolete (state is now per-user).
  for (const key of LEGACY_STUDIO_STATE_KEYS) {
    localStorage.removeItem(key);
  }
  localStorage.setItem(AUTH_USER_ID_KEY, user.user_id);
  return user;
};

export const updateCurrentUser = async (data: {
  email?: string;
  password?: string;
  current_password?: string;
}): Promise<UserResponse> => {
  const response = await axiosInstance.patch('/auth/me', data);
  return response.data;
};

export const completeOnboarding = async (): Promise<void> => {
  await axiosInstance.post('/auth/me/onboarding-complete');
};

export const listUsers = async (): Promise<UserResponse[]> => {
  const response = await axiosInstance.get('/auth/users');
  return Array.isArray(response.data) ? response.data : [];
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
  clearSessionLocalState();
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
