import { useEffect, useState } from 'react';
import { ActivityIndicator, StyleSheet, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { router } from 'expo-router';
import * as Linking from 'expo-linking';
import { api } from '../src/api';
import { Body, Button, Card, H2, Label } from '../src/components/ui';
import { useTheme, Theme } from '../src/theme';

const createStyles = (theme: Theme) => StyleSheet.create({
  root: { flex: 1, backgroundColor: theme.bg.base },
});


function getVehicleYear(vin: string): number {
  if (!vin || vin.length < 10) return 2024; // Default to new
  const char = vin.charAt(9).toUpperCase();
  const yearMap: Record<string, number> = {
    'A': 2010, 'B': 2011, 'C': 2012, 'D': 2013, 'E': 2014,
    'F': 2015, 'G': 2016, 'H': 2017, 'J': 2018, 'K': 2019,
    'L': 2020, 'M': 2021, 'N': 2022, 'P': 2023, 'R': 2024,
    'S': 2025, 'T': 2026, 'V': 2027, 'W': 2028, 'X': 2029,
    'Y': 2030,
  };
  return yearMap[char] || 2024;
}

export default function Pairing() {
  const { theme } = useTheme();
  const styles = createStyles(theme);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    (async () => {
      try {
        const dash = await api.dashboard();
        const vYear = getVehicleYear(dash.vehicle?.vin || '');
        
        // If year is prior to 2021, we don't need Virtual Key pairing, just redirect
        if (vYear < 2021) {
          router.replace('/dashboard');
        } else {
          setLoading(false);
        }
      } catch (e) {
        // On error, default to showing the prompt just in case
        setLoading(false);
      }
    })();
  }, []);

  function pair() {
    Linking.openURL('https://tesla.com/_ak/api.charging.clankersystems.com');
  }

  function continueToDashboard() {
    router.replace('/dashboard');
  }

  if (loading) {
    return (
      <View style={{ flex: 1, backgroundColor: theme.bg.base, alignItems: 'center', justifyContent: 'center' }}>
        <ActivityIndicator color={theme.fg.primary} />
      </View>
    );
  }

  // 2021+ Virtual Key Pairing
  return (
    <SafeAreaView style={styles.root} edges={['top', 'bottom']}>
      <View style={{ flex: 1, padding: theme.space['2xl'], justifyContent: 'center' }}>
        <Card>
          <Label>Security Step</Label>
          <H2 style={{ marginTop: theme.space.md }}>Pair Virtual Key</H2>
          <Body muted style={{ marginTop: theme.space.md }}>
            To automatically start and stop charging and stream telemetry data, modern Tesla vehicles (2021+) require you to approve this app as a "Virtual Key".
          </Body>
          <Body muted style={{ marginTop: theme.space.md }}>
            Tapping the button below will open your official Tesla app to approve the connection.
          </Body>
        </Card>

        <View style={{ marginTop: theme.space.xl, gap: theme.space.sm }}>
          <Button title="Open Tesla App to Pair" variant="primary" onPress={pair} />
          <Button title="Continue to Dashboard" variant="ghost" onPress={continueToDashboard} />
        </View>
      </View>
    </SafeAreaView>
  );
}


