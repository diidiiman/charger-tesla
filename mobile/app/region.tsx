import { useEffect, useState } from 'react';
import { Pressable, StyleSheet, View, TextInput, ScrollView, KeyboardAvoidingView, Platform, Modal } from 'react-native';
import { Picker } from '@react-native-picker/picker';
import { Feather } from '@expo/vector-icons';
import { router } from 'expo-router';
import { api, Region, getCurrency } from '../src/api';
import { getOrCreateDeviceId, session } from '../src/storage';
import { Body, Button, ErrorBox, Label } from '../src/components/ui';
import { theme } from '../src/theme';

export default function RegionPicker() {
  const [regions, setRegions] = useState<Region[] | null>(null);
  const [selected, setSelected] = useState<string | null>(null);
  const [threshold, setThreshold] = useState<string>('0.10');
  const [vatIncluded, setVatIncluded] = useState(true);
  const [units, setUnits] = useState<'metric' | 'imperial'>('metric');
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [pickerVisible, setPickerVisible] = useState(false);

  useEffect(() => {
    (async () => {
      try {
        if (!(await session.get())) {
          const id = await getOrCreateDeviceId();
          const r = await api.registerDevice(id);
          await session.set(r.token);
        }
        const [list, settings] = await Promise.all([api.regions(), api.getSettings()]);
        list.sort((a, b) => a.code.localeCompare(b.code));
        setRegions(list);
        if (settings.region) setSelected(settings.region);
        if (settings.threshold_price != null) setThreshold(settings.threshold_price.toString());
        if (settings.vat_included != null) setVatIncluded(settings.vat_included);
        if (settings.units != null) setUnits(settings.units as 'metric' | 'imperial');
      } catch (e: any) {
        setError(e.message);
      }
    })();
  }, []);

  async function save() {
    if (!selected) return;
    setError(null); setBusy(true);
    try {
      const t = parseFloat(threshold);
      await api.putSettings({ region: selected, threshold_price: Number.isFinite(t) ? t : undefined, vat_included: vatIncluded, units, currency: getCurrency(selected) });
      router.replace('/notifications');
    } catch (e: any) { setError(e.message); }
    finally { setBusy(false); }
  }

  return (
    <KeyboardAvoidingView behavior={Platform.OS === 'ios' ? 'padding' : 'height'} style={styles.root}>
      <ScrollView contentContainerStyle={styles.scrollContent}>
        <View style={styles.card}>
          <Label>Region</Label>
          <Body muted style={{ marginTop: theme.space.sm }}>
            Nord Pool delivery area where your car is plugged in.
          </Body>

          {Platform.OS === 'ios' ? (
            <>
              <Pressable
                style={{ marginTop: theme.space.lg, height: 44, paddingHorizontal: theme.space.md, borderRadius: theme.radius.md, backgroundColor: theme.bg.input, borderWidth: 1, borderColor: theme.border.subtle, flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' }}
                onPress={() => setPickerVisible(true)}
              >
                <Body style={{ color: selected ? theme.fg.primary : theme.fg.faint }}>
                  {selected ? `${regions?.find(r => r.code === selected)?.label} (${selected})` : 'Select a region...'}
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
                      selectedValue={selected || ''}
                      onValueChange={(itemValue) => setSelected(itemValue)}
                    >
                      <Picker.Item label="Select a region..." value="" color={theme.fg.primary} />
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
                selectedValue={selected || ''}
                onValueChange={(itemValue) => setSelected(itemValue)}
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
          <Label>{`Threshold price (${getCurrency(selected)} / kWh)`}</Label>
          <Body muted style={{ marginTop: theme.space.sm }}>
            Charge while the price is at or below this.
          </Body>
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

        <View style={{ marginTop: theme.space.xl }}>
          <Button title="Continue" variant="primary" disabled={!selected} loading={busy} onPress={save} />
        </View>
      </ScrollView>
    </KeyboardAvoidingView>
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
