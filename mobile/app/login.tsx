import { useState, useEffect } from 'react';
import { View, StyleSheet, Platform } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { router } from 'expo-router';
import * as AppleAuthentication from 'expo-apple-authentication';
import { GoogleSignin, statusCodes } from '@react-native-google-signin/google-signin';
import { Body, Button, ErrorBox, H1, Label } from '../src/components/ui';
import { api } from '../src/api';
import { getOrCreateDeviceId, session } from '../src/storage';
import { theme } from '../src/theme';

GoogleSignin.configure({
  // Note: For a production app, provide a real web client ID from Google Cloud Console
  // webClientId: 'YOUR_WEB_CLIENT_ID.apps.googleusercontent.com',
});

export default function Login() {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [appleAvailable, setAppleAvailable] = useState(false);

  useEffect(() => {
    if (Platform.OS === 'ios') {
      AppleAuthentication.isAvailableAsync().then(setAppleAvailable);
    }
  }, []);

  async function loginAnonymous() {
    setBusy(true); setError(null);
    try {
      const id = await getOrCreateDeviceId();
      const r = await api.registerDevice(id);
      await session.set(r.token);
      router.replace('/');
    } catch (e: any) { setError(e.message); }
    finally { setBusy(false); }
  }

  async function loginApple() {
    setBusy(true); setError(null);
    try {
      const credential = await AppleAuthentication.signInAsync({
        requestedScopes: [
          AppleAuthentication.AppleAuthenticationScope.FULL_NAME,
          AppleAuthentication.AppleAuthenticationScope.EMAIL,
        ],
      });
      if (credential.identityToken) {
        const id = await getOrCreateDeviceId();
        const r = await api.authApple(credential.identityToken, id);
        await session.set(r.token);
        router.replace('/');
      } else {
        throw new Error('No identity token returned');
      }
    } catch (e: any) {
      if (e.code !== 'ERR_REQUEST_CANCELED') {
        setError(e.message);
      }
    } finally {
      setBusy(false);
    }
  }

  async function loginGoogle() {
    setBusy(true); setError(null);
    try {
      await GoogleSignin.hasPlayServices();
      const userInfo = await GoogleSignin.signIn();
      // userInfo may have idToken differently based on the new API, 
      // but usually it's userInfo.idToken or userInfo.data.idToken
      const idToken = userInfo.idToken || (userInfo as any).data?.idToken;
      if (idToken) {
        const id = await getOrCreateDeviceId();
        const r = await api.authGoogle(idToken, id);
        await session.set(r.token);
        router.replace('/');
      } else {
        throw new Error('No identity token returned');
      }
    } catch (e: any) {
      if (e.code === statusCodes.SIGN_IN_CANCELLED) {
        // user cancelled
      } else {
        setError(e.message || String(e));
      }
    } finally {
      setBusy(false);
    }
  }

  return (
    <SafeAreaView style={styles.root} edges={['top', 'bottom']}>
      <View style={{ flex: 1, justifyContent: 'center', paddingHorizontal: theme.space['2xl'] }}>
        <H1 style={{ textAlign: 'center', marginBottom: theme.space['4xl'] }}>Tesla Charger</H1>
        
        <View style={{ gap: theme.space.lg }}>
          {appleAvailable && (
            <AppleAuthentication.AppleAuthenticationButton
              buttonType={AppleAuthentication.AppleAuthenticationButtonType.SIGN_IN}
              buttonStyle={AppleAuthentication.AppleAuthenticationButtonStyle.WHITE}
              cornerRadius={theme.radius.md}
              style={{ width: '100%', height: 44 }}
              onPress={loginApple}
            />
          )}

          <Button title="Sign in with Google" variant="default" loading={busy} onPress={loginGoogle} />
          
          <View style={{ flexDirection: 'row', alignItems: 'center', marginVertical: theme.space.md }}>
            <View style={{ flex: 1, height: 1, backgroundColor: theme.border.subtle }} />
            <Body muted style={{ paddingHorizontal: theme.space.md, fontSize: theme.size.sm }}>OR</Body>
            <View style={{ flex: 1, height: 1, backgroundColor: theme.border.subtle }} />
          </View>
          
          <Button title="Continue anonymously" variant="ghost" loading={busy} onPress={loginAnonymous} />
        </View>
        
        {error && <View style={{ marginTop: theme.space.lg }}><ErrorBox>{error}</ErrorBox></View>}
      </View>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: theme.bg.base },
});
