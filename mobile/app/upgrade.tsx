import { useEffect, useState } from 'react';
import { Platform, StyleSheet, View, Linking } from 'react-native';
import { api, SubscriptionStatus } from '../src/api';
import { Body, Button, Card, ErrorBox, H1, H2, Label, Pill } from '../src/components/ui';
import { theme } from '../src/theme';

/**
 * Upgrade screen.
 *
 * This screen presents the Pro tier and triggers an in-app purchase via
 * `react-native-iap`. To keep the scaffold runnable on Expo Go (which
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
      const IAP = await import('react-native-iap').catch(() => null);
      let receipt: string = '';
      let product_id = 'charging_pro_monthly';
      if (IAP && typeof IAP.initConnection === 'function') {
        await IAP.initConnection();
        if (typeof IAP.fetchProducts === 'function') {
          await IAP.fetchProducts({ skus: [product_id], type: 'subs' });
        }
        
        const purchase: any = await new Promise((resolve, reject) => {
          const sub1 = IAP.purchaseUpdatedListener((p: any) => {
            sub1.remove();
            sub2.remove();
            resolve(p);
          });
          const sub2 = IAP.purchaseErrorListener((e: any) => {
            sub1.remove();
            sub2.remove();
            reject(e);
          });
          IAP.requestPurchase({
            request: {
              apple: { sku: product_id },
              google: { skus: [product_id] },
            },
            type: 'subs'
          }).catch((err: any) => {
            sub1.remove();
            sub2.remove();
            reject(err);
          });
        });

        // Finish the transaction so Google/Apple know it was delivered!
        if (typeof IAP.finishTransaction === 'function') {
          await IAP.finishTransaction({ purchase, isConsumable: false });
        }

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

  async function restore() {
    setError(null); setBusy(true);
    try {
      const IAP = await import('react-native-iap').catch(() => null);
      let receipt: string = '';
      let product_id = 'charging_pro_monthly';
      
      if (IAP && typeof IAP.initConnection === 'function') {
        await IAP.initConnection();
        const purchases = await IAP.getAvailablePurchases();
        const validPurchase = purchases.find((p: any) => p.productId === product_id);
        receipt = validPurchase?.transactionReceipt || validPurchase?.purchaseToken || '';
        if (!receipt) throw new Error('No active subscription found to restore.');
      } else {
        receipt = `stub-restore-${Date.now()}`;
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

  async function cancelPlan() {
    if (Platform.OS === 'ios') {
      Linking.openURL('https://apps.apple.com/account/subscriptions');
    } else {
      Linking.openURL('https://play.google.com/store/account/subscriptions?package=com.clankersystems.charging&sku=charging_pro_monthly');
    }
  }

  return (
    <View style={styles.root}>
      <Card>
        <View style={{ flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' }}>
          <Label>Tesla Nord Pool Pro</Label>
          <Pill tone={status?.active ? 'ok' : undefined} label={status?.active ? 'Active' : 'Inactive'} />
        </View>
        <Body muted style={{ marginTop: theme.space.md }}>
          With Pro, the app watches the price for your region and automatically starts and stops your
          Tesla’s charging session whenever the price crosses your threshold. Cancel any time from the
          {Platform.OS === 'ios' ? ' App Store' : ' Play Store'}.
        </Body>
      </Card>

      {error && <View style={{ marginTop: theme.space.lg }}><ErrorBox>{error}</ErrorBox></View>}

      <View style={{ flex: 1 }} />

      <View style={{ marginTop: theme.space.lg, gap: theme.space.sm }}>
        {!status?.active ? (
          <>
            <Button title={`Subscribe via ${Platform.OS === 'ios' ? 'App Store' : 'Play Store'}`} variant="primary" loading={busy} onPress={buy} />
            <Button title="Restore purchases" variant="ghost" loading={busy} onPress={restore} />
          </>
        ) : (
          <Button title="Cancel Pro plan" variant="ghost" loading={busy} onPress={cancelPlan} />
        )}
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: theme.bg.base, padding: theme.space['2xl'] },
});
