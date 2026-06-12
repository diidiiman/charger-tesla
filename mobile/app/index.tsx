import { useEffect } from 'react';
import { ActivityIndicator, View } from 'react-native';
import { Redirect, router } from 'expo-router';
import { useState } from 'react';
import { api } from '../src/api';
import { getOrCreateDeviceId, introSeen, session } from '../src/storage';
import { theme } from '../src/theme';

type NextRoute = '/intro' | '/region' | '/connect' | '/dashboard' | null;

export default function Entry() {
  const [next, setNext] = useState<NextRoute>(null);

  useEffect(() => {
    (async () => {
      try {
        if (!(await introSeen.get())) { setNext('/intro'); return; }

        let token = await session.get();
        if (!token) {
          const id = await getOrCreateDeviceId();
          const r = await api.registerDevice(id);
          await session.set(r.token);
          token = r.token;
        }

        const settings = await api.getSettings();
        if (!settings.region) { setNext('/region'); return; }

        const dash = await api.dashboard();
        if (!dash.tesla_linked) { setNext('/connect'); return; }

        setNext('/dashboard');
      } catch (e: any) {
        if (e.status === 401 && String(e.message).toLowerCase().includes('user not found')) {
          console.warn('user not found on backend, will re-register on next mount');
          return; // api.ts handles clearing session and router.replace('/')
        }
        // Fall back to intro on any bootstrap failure.
        console.warn('bootstrap failed', e);
        setNext('/intro');
      }
    })();
  }, []);

  if (next == null) {
    return (
      <View style={{ flex: 1, backgroundColor: theme.bg.base, alignItems: 'center', justifyContent: 'center' }}>
        <ActivityIndicator color={theme.fg.primary} />
      </View>
    );
  }
  return <Redirect href={next} />;
}
