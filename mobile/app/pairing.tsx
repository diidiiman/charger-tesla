import { StyleSheet, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { router } from 'expo-router';
import * as Linking from 'expo-linking';
import { Body, Button, Card, H2, Label } from '../src/components/ui';
import { theme } from '../src/theme';

export default function Pairing() {
  function pair() {
    Linking.openURL('https://tesla.com/_ak/api.charging.clankersystems.com');
  }

  function continueToDashboard() {
    router.replace('/dashboard');
  }

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
            Tapping the button below will open your official Tesla app to approve the connection. If you drive a pre-2021 Model S or X, you can safely skip this step.
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

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: theme.bg.base },
});
