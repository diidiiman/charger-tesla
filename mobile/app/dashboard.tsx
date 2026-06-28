import { useCallback, useState, useEffect } from 'react';
import { RefreshControl, ScrollView, StyleSheet, View, Pressable } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useFocusEffect, router } from 'expo-router';
import * as WebBrowser from 'expo-web-browser';
import * as Linking from 'expo-linking';
import { Feather } from '@expo/vector-icons';
import { api, Dashboard as DashboardData, getCurrency } from '../src/api';
import {
  Body,
  Button,
  Card,
  Divider,
  ErrorBox,
  H1,
  Label,
  Pill,
  ProgressBar,
  Stat,
} from '../src/components/ui';
import { theme } from '../src/theme';

function chargingTone(state?: string) {
  if (!state) return undefined;
  const s = state.toLowerCase();
  if (s === 'charging' || s === 'complete') return 'ok' as const;
  if (s === 'stopped') return 'warn' as const;
  return undefined;
}

export default function Dashboard() {
  const [data, setData] = useState<DashboardData | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [refreshing, setRefreshing] = useState(false);
  const [busy, setBusy] = useState(false);
  const [startBusy, setStartBusy] = useState(false);
  const [stopBusy, setStopBusy] = useState(false);
  const [refreshBusy, setRefreshBusy] = useState(false);
  const [authBusy, setAuthBusy] = useState(false);

  useEffect(() => {
    const sub = Linking.addEventListener('url', ({ url }) => {
      if (url.includes('://auth')) {
        const parsed = Linking.parse(url);
        const ok = (parsed.queryParams?.ok as string) === '1';
        if (ok) router.replace('/pairing');
        else setError(`Tesla sign-in failed: ${parsed.queryParams?.error || 'unknown'}`);
      }
    });
    return () => sub.remove();
  }, []);

  async function startTeslaAuth() {
    setError(null); setAuthBusy(true);
    try {
      const returnUrl = Linking.createURL('auth');
      const { authorize_url } = await api.startTeslaAuth(returnUrl);
      const result = await WebBrowser.openAuthSessionAsync(authorize_url, returnUrl);
      if (result.type === 'success' && result.url) {
        const parsed = Linking.parse(result.url);
        if ((parsed.queryParams?.ok as string) === '1') router.replace('/pairing');
        else setError(`Tesla sign-in failed: ${parsed.queryParams?.error || 'unknown'}`);
      }
    } catch (e: any) { setError(e.message); }
    finally { setAuthBusy(false); }
  }

  const load = useCallback(async () => {
    try {
      const d = await api.dashboard();
      setData(d);
      setError(null);
    } catch (e: any) { setError(e.message); }
  }, []);

  useFocusEffect(
    useCallback(() => {
      load();
    }, [load])
  );

  async function run(fn: () => Promise<any>, setSpinner?: (v: boolean) => void) {
    if (setSpinner) setSpinner(true);
    setBusy(true);
    try { await fn(); await load(); }
    catch (e: any) { setError(e.message); }
    finally { 
      if (setSpinner) setSpinner(false);
      setBusy(false); 
    }
  }

  async function onRefresh() {
    setRefreshing(true); await load(); setRefreshing(false);
  }

  const charge = data?.charge || {};
  const chargingState: string | undefined = charge.charging_state;
  const charging = chargingState === 'Charging';
  const plugged = chargingState && chargingState !== 'Disconnected';

  return (
    <SafeAreaView style={styles.root} edges={['top', 'bottom']}>
      <ScrollView
        style={{ flex: 1 }}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor={theme.fg.muted} />}
        contentContainerStyle={{ padding: theme.space['2xl'], gap: theme.space.lg }}
      >
        <View style={styles.header}>
          <H1>Tesla Nord Pool</H1>
          <Pill
            tone={data?.subscription_active ? 'ok' : undefined}
            label={data?.subscription_active ? 'Pro' : 'Free'}
          />
        </View>

        {/* Price */}
        <Pressable 
          onPress={() => {
            if (data?.settings.region) {
              const currency = getCurrency(data.settings.region);
              Linking.openURL(`https://data.nordpoolgroup.com/auction/day-ahead/prices?deliveryDate=latest&currency=${currency}&aggregation=Hourly&deliveryAreas=${data.settings.region}`);
            }
          }}
        >
          <Card>
            <View style={styles.row}>
              <View>
                <View style={{ flexDirection: 'row', alignItems: 'center', gap: theme.space.xs }}>
                  <Label>Current price</Label>
                  <Feather name="external-link" size={12} color={theme.fg.faint} />
                </View>
                <Body muted style={{ fontSize: theme.size.xs, marginTop: 4 }}>
                  {data?.price ? `${data.price.region} • Nord Pool` : '—'}
                </Body>
              </View>
              {data?.settings.threshold_price != null && (
                <Pill
                  tone={data.price && data.price.price <= data.settings.threshold_price ? 'ok' : 'warn'}
                  label={
                    data.price
                      ? data.price.price <= data.settings.threshold_price ? 'Cheap' : 'Expensive'
                      : 'No price'
                  }
                />
              )}
            </View>
            <View style={{ flexDirection: 'row', alignItems: 'baseline', marginTop: theme.space.lg, gap: theme.space.sm }}>
              <Body style={{ fontSize: theme.size.xl, lineHeight: 38, fontWeight: '500', fontVariant: ['tabular-nums'], letterSpacing: -0.5 }}>
                {data?.price ? data.price.price.toFixed(4) : '—'}
              </Body>
              <Body muted style={{ fontVariant: ['tabular-nums'] }}>
                {getCurrency(data?.settings.region)} / kWh {data?.settings.vat_included ? '(incl. VAT)' : '(excl. VAT)'}
              </Body>
            </View>
            {data?.settings.threshold_price != null && (
              <Body muted style={{ marginTop: theme.space.sm, fontSize: theme.size.sm }}>
                Threshold {data.settings.threshold_price.toFixed(4)} {getCurrency(data.settings.region)}/kWh {data.settings.vat_included ? '(incl. VAT)' : '(excl. VAT)'}
              </Body>
            )}
          </Card>
        </Pressable>

        {/* Car */}
        {!data?.tesla_linked ? (
          <Card>
            <View style={styles.row}>
              <Label>Vehicle</Label>
              <Pill tone="bad" label="Not connected" />
            </View>
            <Body muted style={{ marginTop: theme.space.md }}>
              Connect your Tesla account to view live charging state and enable auto-charging.
            </Body>
            <View style={{ marginTop: theme.space.lg }}>
              <Button title="Connect Tesla" variant="primary" loading={authBusy} onPress={startTeslaAuth} />
            </View>
          </Card>
        ) : (
          <Card style={{ padding: 0 }}>
            <View style={{ padding: theme.space['2xl'] }}>
              <View style={styles.row}>
                <View style={{ flex: 1, paddingRight: theme.space.md }}>
                  <Label>Vehicle</Label>
                  <Body numberOfLines={1} style={{ fontSize: theme.size.lg, fontWeight: '600', marginTop: 2 }}>
                    {data?.vehicle?.display_name ?? 'Tesla'}
                  </Body>
                </View>
                <Pill tone={chargingTone(chargingState)} label={chargingState ?? 'Unknown'} />
              </View>

            {typeof charge.battery_level === 'number' && (
              <View style={{ marginTop: theme.space.lg, gap: theme.space.sm }}>
                <View style={styles.row}>
                  <Label>State of charge</Label>
                  {charge.charge_limit_soc != null && (
                    <Body muted style={{ fontSize: theme.size.xs, fontVariant: ['tabular-nums'] }}>
                      limit {charge.charge_limit_soc}%
                    </Body>
                  )}
                </View>
                <ProgressBar value={charge.battery_level} charging={charging} />
              </View>
            )}

            <View style={styles.grid}>
              <Stat label="Battery" value={charge.battery_level ?? null} unit="%" />
              <Stat 
                label="Range" 
                value={charge.battery_range != null ? Math.round(data?.settings.units === 'metric' ? charge.battery_range * 1.60934 : charge.battery_range) : null} 
                unit={data?.settings.units === 'metric' ? 'km' : 'mi'} 
              />
              <Stat label="Power" value={charge.charger_power ?? null} unit="kW" />
              {charging && charge.minutes_to_full_charge != null && (
                <Stat label="To full" value={Math.round(charge.minutes_to_full_charge)} unit="min" />
              )}
            </View>

          <Divider />

          {data?.vehicle?.is_at_home ? (
            <>
              <View style={{ flexDirection: 'row', gap: theme.space.sm }}>
                <Button
                  style={{ flex: 1 }}
                  title="Start charging"
                  variant="primary"
                  loading={startBusy}
                  disabled={busy || !plugged || charging}
                  onPress={() => run(api.chargeStart, setStartBusy)}
                />
                <Button
                  style={{ flex: 1 }}
                  title="Stop charging"
                  loading={stopBusy}
                  disabled={busy || !charging}
                  onPress={() => run(api.chargeStop, setStopBusy)}
                />
              </View>
              <View style={{ marginTop: theme.space.sm }}>
                <Button style={{ width: '100%' }} title="Refresh" variant="ghost" loading={refreshBusy} onPress={() => run(load, setRefreshBusy)} disabled={busy} />
              </View>
            </>
          ) : (
            <>
              {data?.vehicle?.location ? (
                <View style={{ flexDirection: 'row', gap: theme.space.sm }}>
                  <Button 
                    style={{ flex: 1 }} 
                    title="Mark as home location" 
                    variant="primary" 
                    disabled={busy}
                    onPress={async () => {
                      setBusy(true);
                      try {
                        await api.putSettings({ 
                          home_latitude: data.vehicle!.location!.latitude,
                          home_longitude: data.vehicle!.location!.longitude
                        });
                        await load();
                      } catch (e: any) { setError(e.message); }
                      finally { setBusy(false); }
                    }} 
                  />
                </View>
              ) : (
                <View style={{ padding: theme.space.md, backgroundColor: theme.bg.input, borderRadius: theme.radius.sm }}>
                  <Body muted style={{ textAlign: 'center', fontSize: theme.size.sm }}>
                    Location unavailable. Pull to refresh to mark as home.
                  </Body>
                </View>
              )}
              <View style={{ marginTop: theme.space.sm }}>
                <Button style={{ width: '100%' }} title="Refresh" variant="ghost" loading={refreshBusy} onPress={() => run(load, setRefreshBusy)} disabled={busy} />
              </View>
            </>
          )}
          </View>
        </Card>
        )}

        {error && <ErrorBox>{error}</ErrorBox>}
      </ScrollView>

      <View style={{ flexDirection: 'row', gap: theme.space.sm, paddingHorizontal: theme.space['2xl'], paddingBottom: theme.space['2xl'], paddingTop: theme.space.md, backgroundColor: theme.bg.base }}>
        <Button style={{ flex: 1 }} title="Settings" variant="ghost" onPress={() => router.push('/settings')} />
        <Button
          style={{ flex: 1 }}
          title={data?.subscription_active ? 'Manage Pro' : 'Upgrade to Pro'}
          variant={data?.subscription_active ? 'ghost' : 'primary'}
          onPress={() => router.push('/upgrade')}
        />
      </View>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: theme.bg.base },
  header: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' },
  row: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' },
  grid: {
    marginTop: theme.space.lg,
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: theme.space.xl,
  },
});
