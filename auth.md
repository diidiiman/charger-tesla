# Authentication Setup Guide

This guide walks you through setting up Google and Apple authentication for the Tesla Charger app on both iOS and Android.

## 1. Apple Sign-In (iOS Only)

Apple Sign-In requires configuration in the Apple Developer Portal and is natively supported by Expo Go on iOS. For standalone builds, you must configure the capabilities.

### Apple Developer Portal
1. Go to your [Apple Developer Account](https://developer.apple.com/account).
2. Navigate to **Certificates, Identifiers & Profiles** -> **Identifiers**.
3. Create or select your App ID (e.g., `com.clankersystems.teslacharger`).
4. Scroll down to **Capabilities** and enable **Sign In with Apple**. 
5. Save the configuration. If you had to enable it just now, you will need to regenerate your Provisioning Profiles.

### Expo Configuration
Your `app.json` is already configured with the `expo-apple-authentication` plugin.
When you build your iOS app using EAS (`eas build -p ios`), EAS will automatically sync your App ID capabilities if you use auto-managed credentials.

## 2. Google Sign-In (iOS & Android)

Google Sign-In requires configuring a project in the Google Cloud Console and setting up OAuth client IDs for Web, iOS, and Android. Note: `@react-native-google-signin/google-signin` requires a custom dev client (EAS Build) and **will not work in standard Expo Go**.

### Google Cloud Console Setup
1. Go to the [Google Cloud Console](https://console.cloud.google.com/).
2. Create a new project or select an existing one.
3. Navigate to **APIs & Services** -> **OAuth consent screen** and configure it (set it to External, fill in app name, support email, etc.). Add `.../auth/userinfo.email` and `.../auth/userinfo.profile` to your scopes.
4. Go to **Credentials** -> **Create Credentials** -> **OAuth client ID**.

### Create Client IDs
You must create *three* separate Client IDs, even if you only use mobile apps:

**A. Web Client ID (Required for React Native)**
1. Choose **Web application**.
2. Name it (e.g., "Web Client").
3. Click **Create**.
4. **Copy the Client ID**. You will need to insert this into your mobile app code!
   - In `mobile/app/login.tsx`, locate `GoogleSignin.configure({ ... })` and set the `webClientId` to this exact value.

**B. iOS Client ID**
1. Create another OAuth client ID, choose **iOS**.
2. Set the Bundle ID exactly as it is in your `app.json` (e.g., `com.clankersystems.teslacharger`).
3. Click **Create**.
4. Copy the `IOS_URL_SCHEME` from the created client (it looks like `com.googleusercontent.apps.XXX...`).
5. Open your `mobile/app.json` and add the scheme to the Google Signin plugin:
   ```json
   "plugins": [
     [
       "@react-native-google-signin/google-signin",
       {
         "iosUrlScheme": "com.googleusercontent.apps.YOUR_IOS_URL_SCHEME"
       }
     ]
   ]
   ```

**C. Android Client ID**
1. Create another OAuth client ID, choose **Android**.
2. Set the Package Name exactly as it is in your `app.json` (e.g., `com.clankersystems.teslacharger`).
3. You will need to provide the SHA-1 certificate fingerprint of your signing key.
   - If using EAS Build, you can retrieve this by running `eas credentials`, selecting Android, and viewing the Keystore details for your profile.
4. Click **Create**.

### Build and Test
Because Google Sign-In relies on native Firebase/Play Services SDKs, you must create a development build to test it:
```bash
eas build --profile development --platform android
eas build --profile development --platform ios
```
Install the resulting app on your device, and the Google Sign-In flow will work seamlessly.