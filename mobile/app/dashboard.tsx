import { useCallback, useEffect, useState } from 'react';
import { RefreshControl, ScrollView, StyleSheet, View, Pressable } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { router } from 'expo-router';
import * as Linking from 'expo-linking';
import { Feather } from '@expo/vector-icons';
import { api, Dashboard as DashboardData } from '../src/api';
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

  const load = useCallback(async () => {
    try {
      const d = await api.dashboard();
      setData(d);
      setError(null);
    } catch (e: any) { setError(e.message); }
  }, []);

  useEffect(() => { load(); }, [load]);

  async function run(fn: () => Promise<any>) {
    setBusy(true);
    try { await fn(); await load(); }
    catch (e: any) { setError(e.message); }
    finally { setBusy(false); }
  }

  async function onRefresh() {
    setRefreshing(true); await load(); setRefreshing(false);
  }

  const charge = data?.charge || {};
  const chargingState: string | undefined = charge.charging_state;
  const charging = chargingState === 'Charging';
  const plugged = chargingState && chargingState !== 'Disconnected';

  return (
    <SafeAreaView style={styles.root} edges={['top']}>
      <ScrollView
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor={theme.fg.muted} />}
        contentContainerStyle={{ padding: theme.space['2xl'], gap: theme.space.lg }}
      >
        <View style={styles.header}>
          <H1>Tesla Charger</H1>
          <Pill
            tone={data?.subscription_active ? 'ok' : undefined}
            label={data?.subscription_active ? 'Pro' : 'Free'}
          />
        </View>

        {/* Price */}
        <Pressable 
          onPress={() => {
            if (data?.settings.region) {
              Linking.openURL(`https://data.nordpoolgroup.com/auction/day-ahead/prices?deliveryDate=latest&currency=EUR&aggregation=Hourly&deliveryAreas=${data.settings.region}`);
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
                EUR / kWh {data?.settings.vat_included ? '(incl. VAT)' : '(excl. VAT)'}
              </Body>
            </View>
            {data?.settings.threshold_price != null && (
              <Body muted style={{ marginTop: theme.space.sm, fontSize: theme.size.sm }}>
                Threshold {data.settings.threshold_price.toFixed(4)} EUR/kWh {data.settings.vat_included ? '(incl. VAT)' : '(excl. VAT)'}
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
              <Button title="Connect Tesla" variant="primary" onPress={() => router.push('/connect')} />
            </View>
          </Card>
        ) : (
          <Card>
            <View style={styles.row}>
              <View>
                <Label>Vehicle</Label>
                <Body style={{ fontSize: theme.size.lg, fontWeight: '600', marginTop: 2 }}>
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

            <View style={{ flexDirection: 'row', gap: theme.space.sm }}>
              <Button
                style={{ flex: 1 }}
                title="Start charging"
                variant="primary"
                disabled={busy || !plugged || charging}
                onPress={() => run(api.chargeStart)}
              />
              <Button
                style={{ flex: 1 }}
                title="Stop charging"
                disabled={busy || !charging}
                onPress={() => run(api.chargeStop)}
              />
            </View>
            <View style={{ marginTop: theme.space.sm }}>
              <Button style={{ width: '100%' }} title="Refresh" variant="ghost" onPress={() => run(load)} disabled={busy} />
            </View>
          </Card>
        )}

        <View style={{ flexDirection: 'row', gap: theme.space.sm }}>
          <Button style={{ flex: 1 }} title="Settings" variant="ghost" onPress={() => router.push('/settings')} />
          <Button
            style={{ flex: 1 }}
            title={data?.subscription_active ? 'Manage Pro' : 'Upgrade to Pro'}
            variant={data?.subscription_active ? 'ghost' : 'primary'}
            onPress={() => router.push('/upgrade')}
          />
        </View>

        {error && <ErrorBox>{error}</ErrorBox>}
      </ScrollView>
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
