import { storage } from './storage';

export const USER_SETTINGS_CHANGED_EVENT = 'user-settings-changed';

export const getPrivacyMode = (): boolean => {
  return storage.getUser()?.privacy_mode ?? false;
};

export const notifyUserSettingsChanged = (): void => {
  window.dispatchEvent(new Event(USER_SETTINGS_CHANGED_EVENT));
};

export const maskUsername = (value: string): string => {
  const text = value.trim();
  if (!text) {
    return '';
  }
  if (text.length === 1) {
    return '*';
  }
  if (text.length === 2) {
    return `${text[0]}*`;
  }
  return `${text[0]}${'*'.repeat(text.length - 2)}${text[text.length - 1]}`;
};

export const maskEmail = (value: string): string => {
  const text = value.trim();
  if (!text || !text.includes('@')) {
    return '***';
  }
  const [local, domain] = text.split('@');
  if (!domain) {
    return '***';
  }
  if (local.length <= 1) {
    return `*@${domain}`;
  }
  if (local.length === 2) {
    return `${local[0]}*@${domain}`;
  }
  return `${local[0]}***${local[local.length - 1]}@${domain}`;
};

export const maskPhone = (value: string): string => {
  const digits = value.replace(/\D/g, '');
  if (digits.length < 7) {
    return '***';
  }
  return `${digits.slice(0, 3)}****${digits.slice(-4)}`;
};

export const maskText = (value: string): string => {
  const text = value.trim();
  if (!text) {
    return '';
  }
  if (text.length <= 6) {
    return `${text[0]}***`;
  }
  return `${text.slice(0, 3)}***${text.slice(-3)}`;
};