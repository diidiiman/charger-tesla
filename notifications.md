# Enabling Notifications for iOS and Android

## iOS
1. Ensure your app is registered on the Apple Developer Portal and has Push Notifications enabled in its App ID.
2. Generate an APNs Authentication Key (.p8 file) and upload it to your Expo account via `eas credentials` or the Expo web dashboard.
3. The app requests permission during the initial setup flow. When users tap "Enable", the OS prompt will appear.
4. Expo handles the delivery through APNs automatically when the backend hits the `https://exp.host/--/api/v2/push/send` endpoint.

## Android
1. Set up a Firebase project and add your Android app with its package name.
2. Download the `google-services.json` file and place it in your app directory, then reference it in `app.json` (`expo.android.googleServicesFile`).
3. If using FCM V1, upload your Firebase Server Key to Expo using `eas credentials` or the Expo web dashboard.
4. On Android 13 (API 33)+, the OS prompt will appear asking for POST_NOTIFICATIONS permission when the app requests it during onboarding. On older versions, permission is granted at installation.