import { Stack } from 'expo-router';
import { StatusBar } from 'expo-status-bar';
import { SafeAreaProvider } from 'react-native-safe-area-context';
import { theme } from '../src/theme';

export default function RootLayout() {
  return (
    <SafeAreaProvider>
      <StatusBar style="light" />
      <Stack
        screenOptions={{
          headerStyle: { backgroundColor: theme.bg.base },
          headerTitleStyle: { color: theme.fg.primary, fontWeight: '600' },
          headerTintColor: theme.fg.primary,
          headerShadowVisible: false,
          headerBackTitleVisible: false,
          headerBackTitle: 'Back',
          contentStyle: { backgroundColor: theme.bg.base },
        }}
      >
        <Stack.Screen name="index" options={{ headerShown: false }} />
        <Stack.Screen name="intro" options={{ headerShown: false }} />
        <Stack.Screen name="region" options={{ title: 'Choose region' }} />
        <Stack.Screen name="connect" options={{ title: 'Connect Tesla' }} />
        <Stack.Screen name="dashboard" options={{ headerShown: false, title: 'Back' }} />
        <Stack.Screen name="settings" options={{ title: 'Settings', headerBackTitle: 'Back' }} />
        <Stack.Screen name="upgrade" options={{ title: 'Tesla Charger Pro', headerBackTitle: 'Back' }} />
        <Stack.Screen name="auth" options={{ headerShown: false }} />
      </Stack>
    </SafeAreaProvider>
  );
}
