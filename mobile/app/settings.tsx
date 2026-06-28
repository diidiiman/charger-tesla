import { useEffect, useState } from 'react';
import { Pressable, StyleSheet, TextInput, View, ScrollView, KeyboardAvoidingView, Platform, Modal } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Picker } from '@react-native-picker/picker';
import { Feather } from '@expo/vector-icons';
import { router } from 'expo-router';
import { api, Region, UserSettings, getCurrency } from '../src/api';
import { Body, Button, ErrorBox, Label, BottomBar } from '../src/components/ui';
import { theme } from '../src/theme';

export default function Settings() {
  const [regions, setRegions] = useState<Region[]>([]);
  const [settings, setSettings] = useState<UserSettings | null>(null);
  const [threshold, setThreshold] = useState('');
  const [vatIncluded, setVatIncluded] = useState(true);
  const [priceChangeReminder, setPriceChangeReminder] = useState(true);
  const [autoCharge, setAutoCharge] = useState(false);
  const [hasPro, setHasPro] = useState(false);
  const [units, setUnits] = useState<'metric' | 'imperial'>('metric');
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
          {Platform.OS === 'ios' ? (
            <>
              <Pressable
                style={{ marginTop: theme.space.lg, height: 44, paddingHorizontal: theme.space.md, borderRadius: theme.radius.md, backgroundColor: theme.bg.input, borderWidth: 1, borderColor: theme.border.subtle, flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' }}
                onPress={() => setPickerVisible(true)}
              >
                <Body style={{ color: settings?.region ? theme.fg.primary : theme.fg.faint }}>
                  {settings?.region ? `${regions?.find(r => r.code === settings.region)?.label} (${settings.region})` : 'Select a region...'}
                </Body>
                <Feather name="chevron-down" size={20} color={theme.fg.primary} />
              </Pressable>
      
              <Modal visible={pickerVisible} animationType="slide" transparent={true}>
                <View style={{ flex: 1, justifyContent: 'flex-end', backgroundColor: 'rgba(0,0,0,0.5)' }}>
                  <View style={{ backgroundColor: theme.bg.surface, paddingBottom: 40, borderTopLeftRadius: theme.radius.lg, borderTopRightRadius: theme.radius.lg }}>
                    <View style={{ flexDirection: 'row', justifyContent: 'flex-end', padding: theme.space.md, borderBottomWidth: 1, borderBottomColor: theme.border.subtle }}>
                      <Button title="Done" variant="ghost" onPress={() => setPickerVisible(false)} />
                    </View>
                    <Picker
                      selectedValue={settings?.region || ''}
                      onValueChange={(itemValue) => settings && setSettings({ ...settings, region: itemValue })}
                    >
                      {regions?.map((item) => (
                        <Picker.Item key={item.code} label={`${item.label} (${item.code})`} value={item.code} color={theme.fg.primary} />
                      ))}
                    </Picker>
                  </View>
                </View>
              </Modal>
            </>
          ) : (
            <View style={{ marginTop: theme.space.lg, overflow: 'hidden', borderRadius: theme.radius.md, backgroundColor: theme.bg.input, borderWidth: 1, borderColor: theme.border.subtle }}>
              <Picker
                selectedValue={settings?.region || ''}
                onValueChange={(itemValue) => settings && setSettings({ ...settings, region: itemValue })}
                style={{ color: theme.fg.primary }}
                dropdownIconColor={theme.fg.primary}
              >
                <Picker.Item label="Select a region..." value="" />
                {regions?.map((item) => (
                  <Picker.Item key={item.code} label={`${item.label} (${item.code})`} value={item.code} />
                ))}
              </Picker>
            </View>
          )}
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

const styles = StyleSheet.create({
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
