import { useEffect, useState } from 'react';
import { Platform, StyleSheet, View } from 'react-native';
import { api, SubscriptionStatus } from '../src/api';
import { Body, Button, Card, ErrorBox, H1, H2, Label, Pill } from '../src/components/ui';
import { theme } from '../src/theme';

/**
 * Upgrade screen.
 *
 * This screen presents the Pro tier and triggers an in-app purchase via
 * `expo-in-app-purchases`. To keep the scaffold runnable on Expo Go (which
 * doesn't support native IAP), the purchase call is wrapped in a try/catch
 * that falls back to a "manual receipt" prompt — in a real build (EAS dev
 * client or production), the native IAP path is taken.
 */
export default function Upgrade() {
  const [status, setStatus] = useState<SubscriptionStatus | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    (async () => {
      try { setStatus(await api.subscriptionStatus()); }
      catch (e: any) { setError(e.message); }
    })();
  }, []);

  async function buy() {
    setError(null); setBusy(true);
    try {
      // Lazy-import so Expo Go doesn't crash on missing native module.
      const IAP = await import('expo-in-app-purchases').catch(() => null);
      let receipt: string;
      let product_id = 'charging_pro_monthly';
      if (IAP && typeof IAP.connectAsync === 'function') {
        await IAP.connectAsync();
        await IAP.getProductsAsync([product_id]);
        const result = await IAP.purchaseItemAsync(product_id);
        const purchase = (result as any)?.results?.[0];
        receipt = purchase?.transactionReceipt || purchase?.purchaseToken || '';
        if (!receipt) throw new Error('purchase did not return a receipt');
      } else {
        // Expo Go / web — send a stub receipt; backend STUB_ALLOW_ALL treats it as valid.
        receipt = `stub-${Date.now()}`;
      }

      const verified = await api.verifySubscription({
        platform: Platform.OS === 'ios' ? 'ios' : 'android',
        product_id,
        receipt,
      });
      setStatus(verified);
    } catch (e: any) { setError(e.message); }
    finally { setBusy(false); }
  }

  async function enableAuto() {
    setBusy(true); setError(null);
    try {
      await api.putSettings({ auto_charge_enabled: true });
      setStatus({ ...(status as SubscriptionStatus), active: true });
    } catch (e: any) { setError(e.message); }
    finally { setBusy(false); }
  }

  return (
    <View style={styles.root}>
      <Card>
        <View style={{ flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' }}>
          <Label>Tesla Charger Pro</Label>
          <Pill tone={status?.active ? 'ok' : undefined} label={status?.active ? 'Active' : 'Inactive'} />
        </View>
        <H1 style={{ marginTop: theme.space.md }}>€4 / month</H1>
        <Body muted style={{ marginTop: theme.space.md }}>
          With Pro, the app watches the price for your region and automatically starts and stops your
          Tesla’s charging session whenever the price crosses your threshold. Cancel any time from the
          App Store or Play Store.
        </Body>
      </Card>

      {error && <View style={{ marginTop: theme.space.lg }}><ErrorBox>{error}</ErrorBox></View>}

      <View style={{ flex: 1 }} />

      <View style={{ marginTop: theme.space.lg, gap: theme.space.sm }}>
        {!status?.active ? (
          <Button title="Subscribe via App Store / Play" variant="primary" loading={busy} onPress={buy} />
        ) : (
          <Button title="Enable auto-charging" variant="primary" loading={busy} onPress={enableAuto} />
        )}
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: theme.bg.base, padding: theme.space['2xl'] },
});
