import { useEffect } from 'react';
import { useLocalSearchParams, router } from 'expo-router';
import { View, ActivityIndicator } from 'react-native';
import { theme } from '../src/theme';

/** Fallback landing for the `teslacharger://auth` deep link when not opened
 *  via WebBrowser.openAuthSessionAsync. */
export default function AuthLanding() {
  const { ok } = useLocalSearchParams<{ ok?: string }>();
  useEffect(() => {
    router.replace(ok === '1' ? '/pairing' : '/connect');
  }, [ok]);
  return (
    <View style={{ flex: 1, backgroundColor: theme.bg.base, alignItems: 'center', justifyContent: 'center' }}>
      <ActivityIndicator color={theme.fg.primary} />
    </View>
  );
}
