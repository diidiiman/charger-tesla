import * as SecureStore from 'expo-secure-store';
import * as Crypto from 'expo-crypto';

const KEY_DEVICE_ID = 'device_id';
const KEY_SESSION = 'session_token';
const KEY_INTRO_SEEN = 'intro_seen';
const KEY_THEME_PREFERENCE = 'theme_preference';

async function safeGet(key: string): Promise<string | null> {
  try {
    return await SecureStore.getItemAsync(key);
  } catch (e) {
    console.warn(`SecureStore failed to get ${key}:`, e);
    try {
      await SecureStore.deleteItemAsync(key);
    } catch (e2) {}
    return null;
  }
}

async function safeSet(key: string, value: string): Promise<void> {
  try {
    await SecureStore.setItemAsync(key, value);
  } catch (e) {
    console.warn(`SecureStore failed to set ${key}:`, e);
  }
}

async function safeDelete(key: string): Promise<void> {
  try {
    await SecureStore.deleteItemAsync(key);
  } catch (e) {
    console.warn(`SecureStore failed to delete ${key}:`, e);
  }
}

export async function getOrCreateDeviceId(): Promise<string> {
  const existing = await safeGet(KEY_DEVICE_ID);
  if (existing) return existing;
  const id = Crypto.randomUUID();
  await safeSet(KEY_DEVICE_ID, id);
  return id;
}

export const session = {
  get: () => safeGet(KEY_SESSION),
  set: (t: string) => safeSet(KEY_SESSION, t),
  clear: () => safeDelete(KEY_SESSION),
};

export const introSeen = {
  get: async () => (await safeGet(KEY_INTRO_SEEN)) === '1',
  mark: () => safeSet(KEY_INTRO_SEEN, '1'),
};

export const themePreference = {
  get: async () => await safeGet(KEY_THEME_PREFERENCE) as 'system' | 'light' | 'dark' | null,
  set: (val: 'system' | 'light' | 'dark') => safeSet(KEY_THEME_PREFERENCE, val),
};
