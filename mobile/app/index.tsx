import { useEffect, useState, useCallback } from 'react';
import { ActivityIndicator, View } from 'react-native';
import { Redirect, router } from 'expo-router';
import { api } from '../src/api';
import { getOrCreateDeviceId, introSeen, session } from '../src/storage';
import { theme } from '../src/theme';
import { Body, Button, Card, ErrorBox, H2 } from '../src/components/ui';

type NextRoute = '/intro' | '/region' | '/connect' | '/dashboard' | null;

export default function Entry() {
  const [next, setNext] = useState<NextRoute>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(true);

  const bootstrap = useCallback(async () => {
    setBusy(true);
    setError(null);
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
      const isAuthError = e.status === 401 && (String(e.message).toLowerCase().includes('user not found') || String(e.message).toLowerCase().includes('invalid session'));
      if (isAuthError) {
        console.warn('auth error on backend, will re-register on next mount');
        return; // api.ts handles clearing session and router.replace('/')
      }
      console.warn('bootstrap failed', e);
      // If we haven't seen the intro, it's safe to fall back to it
      if (!(await introSeen.get())) {
        setNext('/intro');
      } else {
        // Otherwise show a retry screen so we don't loop
        setError(e.message || 'Failed to connect to the server.');
      }
    } finally {
      setBusy(false);
    }
  }, []);

  useEffect(() => {
    bootstrap();
  }, [bootstrap]);

  if (error) {
    return (
      <View style={{ flex: 1, backgroundColor: theme.bg.base, padding: theme.space['2xl'], justifyContent: 'center' }}>
        <Card style={{ gap: theme.space.lg }}>
          <H2>Connection Error</H2>
          <ErrorBox>{error}</ErrorBox>
          <Body muted>Ensure the backend is running and reachable.</Body>
          <Button title="Retry" variant="primary" loading={busy} onPress={bootstrap} />
        </Card>
      </View>
    );
  }

  if (busy || next == null) {
    return (
      <View style={{ flex: 1, backgroundColor: theme.bg.base, alignItems: 'center', justifyContent: 'center' }}>
        <ActivityIndicator color={theme.fg.primary} />
      </View>
    );
  }
  return <Redirect href={next} />;
}
