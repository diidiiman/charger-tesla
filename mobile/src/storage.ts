import * as SecureStore from 'expo-secure-store';
import * as Crypto from 'expo-crypto';

const KEY_DEVICE_ID = 'device_id';
const KEY_SESSION = 'session_token';
const KEY_INTRO_SEEN = 'intro_seen';
const KEY_THEME_PREFERENCE = 'theme_preference';

export async function getOrCreateDeviceId(): Promise<string> {
  const existing = await SecureStore.getItemAsync(KEY_DEVICE_ID);
  if (existing) return existing;
  const id = Crypto.randomUUID();
  await SecureStore.setItemAsync(KEY_DEVICE_ID, id);
  return id;
}

export const session = {
  get: () => SecureStore.getItemAsync(KEY_SESSION),
  set: (t: string) => SecureStore.setItemAsync(KEY_SESSION, t),
  clear: () => SecureStore.deleteItemAsync(KEY_SESSION),
};

export const introSeen = {
  get: async () => (await SecureStore.getItemAsync(KEY_INTRO_SEEN)) === '1',
  mark: () => SecureStore.setItemAsync(KEY_INTRO_SEEN, '1'),
};

export const themePreference = {
  get: async () => await SecureStore.getItemAsync(KEY_THEME_PREFERENCE) as 'system' | 'light' | 'dark' | null,
  set: (val: 'system' | 'light' | 'dark') => SecureStore.setItemAsync(KEY_THEME_PREFERENCE, val),
};
