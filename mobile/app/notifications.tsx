import { useState } from 'react';
import { StyleSheet, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { router } from 'expo-router';
import Constants from 'expo-constants';
import * as Notifications from 'expo-notifications';
import * as Device from 'expo-device';
import { Body, Button, ErrorBox, H1, Label, Pill } from '../src/components/ui';
import { api } from '../src/api';
import { useTheme, Theme } from '../src/theme';

export default function NotificationsOnboarding() {
  const { theme } = useTheme();
  const styles = createStyles(theme);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function requestPermissionsAndContinue() {
    setBusy(true);
    setError(null);
    try {
      if (Device.isDevice) {
        const { status: existingStatus } = await Notifications.getPermissionsAsync();
        let finalStatus = existingStatus;
        
        if (existingStatus !== 'granted') {
          const { status } = await Notifications.requestPermissionsAsync();
          finalStatus = status;
        }
        
        if (finalStatus === 'granted') {
          const projectId = Constants.expoConfig?.extra?.eas?.projectId ?? Constants.easConfig?.projectId ?? 'dummy-project-id';
          const token = (await Notifications.getExpoPushTokenAsync({ projectId })).data;
          await api.putSettings({ push_token: token, price_change_reminder: true });
        }
      }
      router.replace('/dashboard');
    } catch (e: any) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }

  async function skip() {
    router.replace('/dashboard');
  }

  return (
    <SafeAreaView style={styles.root} edges={['top', 'bottom']}>
      <View style={styles.header}>
        <H1>Tesla Nord Pool</H1>
        <Pill label="Step 3 / 3" />
      </View>

      <View style={{ flex: 1, justifyContent: 'center', paddingHorizontal: theme.space['2xl'] }}>
        <View style={styles.card}>
          <Label>Notifications</Label>
          <H1 style={{ marginTop: theme.space.md }}>Stay informed</H1>
          <Body muted style={{ marginTop: theme.space.lg }}>
            Enable notifications to get alerts when the electricity price crosses your threshold. 
            We'll let you know exactly when your car starts or stops charging to help you save money.
          </Body>
        </View>
        {error && <View style={{ marginTop: theme.space.lg }}><ErrorBox>{error}</ErrorBox></View>}
      </View>

      <View style={{ paddingHorizontal: theme.space['2xl'], paddingBottom: theme.space.xl, gap: theme.space.sm }}>
        <Button
          title="Enable Notifications"
          variant="primary"
          loading={busy}
          onPress={requestPermissionsAndContinue}
        />
        <Button
          title="Maybe Later"
          variant="ghost"
          disabled={busy}
          onPress={skip}
        />
      </View>
    </SafeAreaView>
  );
}

const createStyles = (theme: Theme) => StyleSheet.create({
  root: { flex: 1, backgroundColor: theme.bg.base },
  header: {
    paddingHorizontal: theme.space['2xl'],
    paddingTop: theme.space.lg,
    paddingBottom: theme.space['2xl'],
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  card: {
    backgroundColor: theme.bg.surface,
    borderColor: theme.border.subtle,
    borderWidth: 1,
    borderRadius: theme.radius.lg,
    padding: theme.space['2xl'],
  },
});
