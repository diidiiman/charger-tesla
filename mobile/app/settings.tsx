import { useEffect, useState } from 'react';
import { Pressable, StyleSheet, TextInput, View, ScrollView, KeyboardAvoidingView, Platform, Modal } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Feather } from '@expo/vector-icons';
import { router } from 'expo-router';
import { api, Region, UserSettings, getCurrency } from '../src/api';
import { Body, Button, ErrorBox, Label, BottomBar, Select } from '../src/components/ui';
import { useTheme, Theme } from '../src/theme';

const createStyles = (theme: Theme) => StyleSheet.create({
  root: { flex: 1, backgroundColor: theme.bg.base },
  scrollContent: { flexGrow: 1, padding: theme.space['2xl'] },
  card: {
    backgroundColor: theme.bg.surface,
    borderColor: theme.border.subtle,
    borderWidth: 1,
    borderRadius: theme.radius.lg,
    padding: theme.space['2xl'],
  },
  row: {
    paddingVertical: theme.space.md,
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  radio: {
    width: 18, height: 18, borderRadius: 9,
    borderWidth: 1, borderColor: theme.border.strong,
  },
  checkbox: {
    width: 18, height: 18, borderRadius: 4,
    borderWidth: 1, borderColor: theme.border.strong,
  },
  checkboxActive: {
    borderColor: theme.accent, backgroundColor: theme.accent,
  },
  input: {
    marginTop: theme.space.md,
    height: 44,
    paddingHorizontal: theme.space.md,
    backgroundColor: theme.bg.input,
    borderWidth: 1,
    borderColor: theme.border.subtle,
    borderRadius: theme.radius.md,
    color: theme.fg.primary,
    fontVariant: ['tabular-nums'],
    fontSize: theme.size.base,
  },
});


export default function Settings() {
  const { theme, themeMode, setThemeMode } = useTheme();
  const styles = createStyles(theme);
  const [regions, setRegions] = useState<Region[]>([]);
  const [settings, setSettings] = useState<UserSettings | null>(null);
  const [threshold, setThreshold] = useState('');
  const [vatIncluded, setVatIncluded] = useState(true);
  const [priceChangeReminder, setPriceChangeReminder] = useState(true);
  const [autoCharge, setAutoCharge] = useState(false);
  const [hasPro, setHasPro] = useState(false);
  const [units, setUnits] = useState<'metric' | 'imperial'>('metric');
  const [selectedThemeMode, setSelectedThemeMode] = useState<'system' | 'light' | 'dark'>(themeMode);
  const [teslaLinked, setTeslaLinked] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [pickerVisible, setPickerVisible] = useState(false);

  useEffect(() => {
    (async () => {
      try {
        const [r, s, sub, dash] = await Promise.all([api.regions(), api.getSettings(), api.subscriptionStatus(), api.dashboard()]);
        setRegions(r);
        setSettings(s);
        setHasPro(sub.active);
        setTeslaLinked(dash.tesla_linked);
        if (s.threshold_price != null) setThreshold(s.threshold_price.toString());
        if (s.vat_included != null) setVatIncluded(s.vat_included);
        if (s.price_change_reminder != null) setPriceChangeReminder(s.price_change_reminder);
        if (s.auto_charge_enabled != null) setAutoCharge(s.auto_charge_enabled);
        if (s.units != null) setUnits(s.units as 'metric' | 'imperial');
      } catch (e: any) { setError(e.message); }
    })();
  }, []);

  async function save() {
    if (!settings) return;
    setError(null); setBusy(true);
    try {
      const t = parseFloat(threshold);
      await setThemeMode(selectedThemeMode);
      const updated = await api.putSettings({
        region: settings.region ?? undefined,
        threshold_price: Number.isFinite(t) ? t : undefined,
        vat_included: vatIncluded,
        price_change_reminder: priceChangeReminder,
        auto_charge_enabled: autoCharge,
        units,
        currency: getCurrency(settings.region ?? undefined),
      });
      setSettings(updated);
      router.back();
    } catch (e: any) { setError(e.message); }
    finally { setBusy(false); }
  }

  async function unlink() {
    setBusy(true);
    try {
      await api.unlinkTesla();
      router.replace('/dashboard');
    } catch (e: any) { setError(e.message); }
    finally { setBusy(false); }
  }

  return (
    <SafeAreaView style={styles.root} edges={['bottom']}>
      <KeyboardAvoidingView behavior={Platform.OS === 'ios' ? 'padding' : 'height'} style={{ flex: 1 }}>
        <ScrollView style={{ flex: 1 }} contentContainerStyle={styles.scrollContent}>
        <View style={styles.card}>
          <Label>Region</Label>
          <Select
            options={(regions || []).map(r => ({ label: `${r.label} (${r.code})`, value: r.code }))}
            value={settings?.region || null}
            onChange={(val) => settings && setSettings({ ...settings, region: val })}
            placeholder="Select a region..."
          />
        </View>

        <View style={[styles.card, { marginTop: theme.space.lg }]}>
          <Label>{`Threshold price (${getCurrency(settings?.region)} / kWh)`}</Label>
          <TextInput
            value={threshold}
            onChangeText={setThreshold}
            keyboardType="decimal-pad"
            placeholder="0.10"
            placeholderTextColor={theme.fg.faint}
            style={styles.input}
          />
          <Pressable onPress={() => setVatIncluded(!vatIncluded)} style={[styles.row, { marginTop: theme.space.sm, paddingVertical: theme.space.xs }]}>
            <Body>Price includes VAT</Body>
            <View style={[styles.checkbox, vatIncluded && styles.checkboxActive]} />
          </Pressable>
        </View>

        <View style={[styles.card, { marginTop: theme.space.lg }]}>
          <Label>Notifications & Automation</Label>
          <View style={{ marginTop: theme.space.md }}>
            <Pressable onPress={() => {
              if (!hasPro) {
                router.push('/upgrade');
              } else {
                setAutoCharge(!autoCharge);
              }
            }} style={[styles.row, { paddingVertical: theme.space.xs }]}>
              <Body>Enable Auto-Charging</Body>
              <View style={[styles.checkbox, autoCharge && styles.checkboxActive]} />
            </Pressable>
            <View style={{ height: 1, backgroundColor: theme.border.subtle, marginVertical: theme.space.xs }} />
            <Pressable onPress={() => setPriceChangeReminder(!priceChangeReminder)} style={[styles.row, { paddingVertical: theme.space.xs }]}>
              <Body>Price change charging reminder</Body>
              <View style={[styles.checkbox, priceChangeReminder && styles.checkboxActive]} />
            </Pressable>
          </View>
        </View>

        <View style={[styles.card, { marginTop: theme.space.lg }]}>
          <Label>Units</Label>
          <View style={{ marginTop: theme.space.md }}>
            <Pressable onPress={() => setUnits('metric')} style={styles.row}>
              <Body style={{ fontWeight: units === 'metric' ? '600' : '400' }}>Metric (km)</Body>
              <View style={[styles.radio, units === 'metric' && { borderColor: theme.accent, backgroundColor: theme.accent }]} />
            </Pressable>
            <View style={{ height: 1, backgroundColor: theme.border.subtle }} />
            <Pressable onPress={() => setUnits('imperial')} style={styles.row}>
              <Body style={{ fontWeight: units === 'imperial' ? '600' : '400' }}>Imperial (mi)</Body>
              <View style={[styles.radio, units === 'imperial' && { borderColor: theme.accent, backgroundColor: theme.accent }]} />
            </Pressable>
          </View>
        </View>

        <View style={[styles.card, { marginTop: theme.space.lg }]}>
          <Label>Appearance</Label>
          <View style={{ marginTop: theme.space.md }}>
            <Pressable onPress={() => setSelectedThemeMode('system')} style={styles.row}>
              <Body style={{ fontWeight: selectedThemeMode === 'system' ? '600' : '400' }}>System Default</Body>
              <View style={[styles.radio, selectedThemeMode === 'system' && { borderColor: theme.accent, backgroundColor: theme.accent }]} />
            </Pressable>
            <View style={{ height: 1, backgroundColor: theme.border.subtle }} />
            <Pressable onPress={() => setSelectedThemeMode('light')} style={styles.row}>
              <Body style={{ fontWeight: selectedThemeMode === 'light' ? '600' : '400' }}>Light Mode</Body>
              <View style={[styles.radio, selectedThemeMode === 'light' && { borderColor: theme.accent, backgroundColor: theme.accent }]} />
            </Pressable>
            <View style={{ height: 1, backgroundColor: theme.border.subtle }} />
            <Pressable onPress={() => setSelectedThemeMode('dark')} style={styles.row}>
              <Body style={{ fontWeight: selectedThemeMode === 'dark' ? '600' : '400' }}>Dark Mode</Body>
              <View style={[styles.radio, selectedThemeMode === 'dark' && { borderColor: theme.accent, backgroundColor: theme.accent }]} />
            </Pressable>
          </View>
        </View>

        {error && <View style={{ marginTop: theme.space.lg }}><ErrorBox>{error}</ErrorBox></View>}

        <View style={{ flex: 1, minHeight: theme.space['2xl'] }} />

        {(teslaLinked || hasPro) && (
          <View style={{ marginTop: theme.space.xl, gap: theme.space.sm }}>
            {teslaLinked && <Button title="Disconnect Tesla account" onPress={unlink} disabled={busy} />}
            {hasPro && <Button title="Manage subscription" variant="ghost" onPress={() => router.push('/upgrade')} disabled={busy} />}
          </View>
        )}
        </ScrollView>
        <BottomBar>
          <Button title="Save" variant="primary" loading={busy} onPress={save} style={{ flex: 1 }} />
        </BottomBar>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}


