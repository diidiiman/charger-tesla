import Constants from 'expo-constants';
import { router } from 'expo-router';
import { session } from './storage';

const BASE: string =
  (process.env.EXPO_PUBLIC_API_BASE as string | undefined) ||
  (Constants.expoConfig?.extra?.apiBase as string | undefined) ||
  'https://charging.clankersystems.com';

console.log('API BASE URL:', BASE);

async function req<T>(method: string, path: string, body?: unknown, auth = true): Promise<T> {
  const headers: Record<string, string> = { 'content-type': 'application/json' };
  if (auth) {
    const token = await session.get();
    if (token) headers.authorization = `Bearer ${token}`;
  }
  const res = await fetch(`${BASE}${path}`, {
    method,
    headers,
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });
  const text = await res.text();
  let json: any;
  try { json = text ? JSON.parse(text) : null; } catch { json = { raw: text }; }
  if (!res.ok) {
    const detailText = json?.detail || json?.error || `request failed: ${res.status}`;
    if (res.status === 401 && String(detailText).toLowerCase().includes('user not found')) {
      await session.clear();
      router.replace('/');
    }
    const err = new Error(detailText);
    (err as any).status = res.status;
    throw err;
  }
  return json as T;
}

export type Region = { code: string; label: string };

export type UserSettings = {
  region: string | null;
  threshold_price: number | null;
  currency: string;
  vat_included: boolean;
  units: string;
  auto_charge_enabled: boolean;
};

export type CurrentPrice = {
  region: string;
  currency: string;
  unit: string;
  price: number;
  valid_from: string;
  valid_to: string;
  provider: string;
};

export type Dashboard = {
  settings: UserSettings;
  tesla_linked: boolean;
  vehicle: { id: string; vin: string | null; display_name: string | null } | null;
  price: CurrentPrice | null;
  charge: Record<string, any> | null;
  subscription_active: boolean;
};

export type SubscriptionStatus = {
  active: boolean;
  product_id: string | null;
  expires_at: string | null;
  platform: string | null;
};

export const api = {
  base: BASE,
  registerDevice: (device_id: string) =>
    req<{ token: string; user_id: number }>('POST', '/v1/auth/device', { device_id }, false),
  regions: () => req<Region[]>('GET', '/v1/regions'),
  getSettings: () => req<UserSettings>('GET', '/v1/settings'),
  putSettings: (patch: Partial<UserSettings>) => req<UserSettings>('PUT', '/v1/settings', patch),
  getPrice: () => req<CurrentPrice>('GET', '/v1/price'),
  dashboard: () => req<Dashboard>('GET', '/v1/dashboard'),
  startTeslaAuth: (return_url?: string) => req<{ authorize_url: string }>('POST', '/auth/tesla/start', { return_url }),
  unlinkTesla: () => req<{ ok: boolean }>('POST', '/auth/tesla/unlink'),
  chargeStart: () => req<any>('POST', '/v1/charge/start'),
  chargeStop: () => req<any>('POST', '/v1/charge/stop'),
  chargeWake: () => req<any>('POST', '/v1/charge/wake'),
  subscriptionStatus: () => req<SubscriptionStatus>('GET', '/v1/subscription'),
  verifySubscription: (payload: { platform: 'ios' | 'android'; product_id: string; receipt: string }) =>
    req<SubscriptionStatus>('POST', '/v1/subscription/verify', payload),
  cancelSubscription: () => req<{ ok: boolean }>('DELETE', '/v1/subscription'),
};
