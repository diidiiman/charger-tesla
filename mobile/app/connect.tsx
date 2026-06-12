import { useEffect, useState } from 'react';
import { StyleSheet, View } from 'react-native';
import * as WebBrowser from 'expo-web-browser';
import * as Linking from 'expo-linking';
import { router } from 'expo-router';
import { api } from '../src/api';
import { Body, Button, ErrorBox, H2, Label, Pill } from '../src/components/ui';
import { theme } from '../src/theme';

export default function Connect() {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const sub = Linking.addEventListener('url', ({ url }) => {
      if (url.includes('://auth')) {
        const parsed = Linking.parse(url);
        const ok = (parsed.queryParams?.ok as string) === '1';
        if (ok) router.replace('/dashboard');
        else setError(`Tesla sign-in failed: ${parsed.queryParams?.error || 'unknown'}`);
      }
    });
    return () => sub.remove();
  }, []);

  async function start() {
    setError(null); setBusy(true);
    try {
      const { authorize_url } = await api.startTeslaAuth();
      const result = await WebBrowser.openAuthSessionAsync(authorize_url, Linking.createURL('auth'));
      if (result.type === 'success' && result.url) {
        const parsed = Linking.parse(result.url);
        if ((parsed.queryParams?.ok as string) === '1') router.replace('/dashboard');
        else setError(`Tesla sign-in failed: ${parsed.queryParams?.error || 'unknown'}`);
      }
    } catch (e: any) { setError(e.message); }
    finally { setBusy(false); }
  }

  return (
    <View style={styles.root}>
      <View style={styles.card}>
        <View style={{ flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' }}>
          <Label>Tesla account</Label>
          <Pill label="Not connected" />
        </View>

        <H2 style={{ marginTop: theme.space.md }}>Sign in to Tesla</H2>
        <Body muted style={{ marginTop: theme.space.md }}>
          The Tesla login page opens in a secure browser sheet. After you sign in,
          Tesla redirects back to this app automatically — we store an encrypted
          refresh token to read your state of charge and trigger charging commands.
        </Body>
      </View>

      {error && <View style={{ marginTop: theme.space.lg }}><ErrorBox>{error}</ErrorBox></View>}

      <View style={{ flex: 1 }} />

      <View style={{ marginTop: theme.space.xl }}>
        <Button title="Sign in with Tesla" variant="primary" loading={busy} onPress={start} />
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: theme.bg.base, padding: theme.space['2xl'] },
  card: {
    backgroundColor: theme.bg.surface,
    borderColor: theme.border.subtle,
    borderWidth: 1,
    borderRadius: theme.radius.lg,
    padding: theme.space['2xl'],
  },
});
