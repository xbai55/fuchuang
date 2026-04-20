import type { User } from '../types';

const TOKEN_KEY = 'access_token';
const USER_KEY = 'user';
const EXPIRY_SKEW_MS = 30_000;

const decodeJwtPayload = (token: string): { exp?: unknown } | null => {
  const payload = token.split('.')[1];
  if (!payload) {
    return null;
  }

  try {
    const normalized = payload.replace(/-/g, '+').replace(/_/g, '/');
    const padded = normalized.padEnd(normalized.length + ((4 - normalized.length % 4) % 4), '=');
    return JSON.parse(window.atob(padded));
  } catch {
    return null;
  }
};

export const isAccessTokenUsable = (token: string | null, nowMs = Date.now()): boolean => {
  if (!token) {
    return false;
  }

  const payload = decodeJwtPayload(token);
  if (typeof payload?.exp !== 'number') {
    return false;
  }

  return payload.exp * 1000 > nowMs + EXPIRY_SKEW_MS;
};

export const storage = {
  // Token 操作
  getToken: (): string | null => {
    return localStorage.getItem(TOKEN_KEY);
  },

  getValidToken: (): string | null => {
    const token = localStorage.getItem(TOKEN_KEY);
    if (!isAccessTokenUsable(token)) {
      localStorage.removeItem(TOKEN_KEY);
      localStorage.removeItem(USER_KEY);
      return null;
    }
    return token;
  },

  setToken: (token: string): void => {
    localStorage.setItem(TOKEN_KEY, token);
  },

  removeToken: (): void => {
    localStorage.removeItem(TOKEN_KEY);
  },

  // 用户信息操作
  getUser: (): User | null => {
    const userStr = localStorage.getItem(USER_KEY);
    if (userStr) {
      try {
        return JSON.parse(userStr);
      } catch {
        return null;
      }
    }
    return null;
  },

  setUser: (user: User): void => {
    localStorage.setItem(USER_KEY, JSON.stringify(user));
  },

  removeUser: (): void => {
    localStorage.removeItem(USER_KEY);
  },

  // 清除所有
  clear: (): void => {
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(USER_KEY);
  },

  // 检查是否已登录
  isAuthenticated: (): boolean => {
    return storage.getValidToken() !== null;
  },
};
