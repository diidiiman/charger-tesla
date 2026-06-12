import { useEffect, useState } from 'react';
import { Pressable, StyleSheet, TextInput, View, ScrollView, KeyboardAvoidingView, Platform } from 'react-native';
import { router } from 'expo-router';
import { api, Region, UserSettings } from '../src/api';
import { Body, Button, ErrorBox, Label } from '../src/components/ui';
import { theme } from '../src/theme';

export default function Settings() {
  const [regions, setRegions] = useState<Region[]>([]);
  const [settings, setSettings] = useState<UserSettings | null>(null);
  const [threshold, setThreshold] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    (async () => {
      try {
        const [r, s] = await Promise.all([api.regions(), api.getSettings()]);
        setRegions(r);
        setSettings(s);
        if (s.threshold_price != null) setThreshold(s.threshold_price.toString());
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
      router.replace('/connect');
    } catch (e: any) { setError(e.message); }
    finally { setBusy(false); }
  }

  return (
    <KeyboardAvoidingView behavior={Platform.OS === 'ios' ? 'padding' : 'height'} style={styles.root}>
      <ScrollView contentContainerStyle={styles.scrollContent}>
        <View style={styles.card}>
          <Label>Region</Label>
          <View style={{ marginTop: theme.space.md }}>
            {regions.map((item, index) => {
              const active = settings?.region === item.code;
              return (
                <View key={item.code}>
                  {index > 0 && <View style={{ height: 1, backgroundColor: theme.border.subtle }} />}
                  <Pressable
                    onPress={() => settings && setSettings({ ...settings, region: item.code })}
                    style={styles.row}
                  >
                    <Body style={{ fontWeight: active ? '600' : '400' }}>{item.label}</Body>
                    <View
                      style={[
                        styles.radio,
                        active && { borderColor: theme.accent, backgroundColor: theme.accent },
                      ]}
                    />
                  </Pressable>
                </View>
              );
            })}
          </View>
        </View>

        <View style={[styles.card, { marginTop: theme.space.lg }]}>
          <Label>Threshold price (EUR / kWh)</Label>
          <TextInput
            value={threshold}
            onChangeText={setThreshold}
            keyboardType="decimal-pad"
            placeholder="0.10"
            placeholderTextColor={theme.fg.faint}
            style={styles.input}
          />
        </View>

        {error && <View style={{ marginTop: theme.space.lg }}><ErrorBox>{error}</ErrorBox></View>}

        <View style={{ flex: 1, minHeight: theme.space['2xl'] }} />

        <View style={{ marginTop: theme.space.xl, gap: theme.space.sm }}>
          <Button title="Save" variant="primary" loading={busy} onPress={save} />
          <Button title="Disconnect Tesla account" onPress={unlink} disabled={busy} />
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
