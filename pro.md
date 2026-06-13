# In-App Purchases (Pro Subscription) Setup Guide

This guide walks you through setting up native In-App Purchases (IAP) for subscriptions via the App Store and Google Play, using the `react-native-iap` library.

## 1. App Store Connect (iOS)

To offer subscriptions on iOS, you must configure them in App Store Connect.

### Creating the Subscription
1. Log in to [App Store Connect](https://appstoreconnect.apple.com/) and navigate to your app.
2. In the sidebar under **Features**, select **Subscriptions**.
3. Create a new **Subscription Group** (e.g., "Pro Features").
4. Add a new **Auto-Renewable Subscription** to the group.
5. Set the **Product ID** exactly as it is hardcoded in the app: `charging_pro_monthly`.
6. Set up the subscription duration (e.g., 1 Month) and pricing (€4).
7. Complete all metadata (Display Name, Description, App Store Review Screenshot). Your subscription cannot be tested until the metadata is "Ready to Submit".

### Backend Receipt Verification Configuration
To allow your Python backend to automatically verify receipts with Apple:
1. Go to **Users and Access** -> **Keys** -> **In-App Purchase**.
2. Generate a new key and download the `.p8` file.
3. Note the **Key ID** and your **Issuer ID**.
4. Set the following environment variables in your backend `.env`:
   - `APPSTORE_BUNDLE_ID` (e.g., `com.clankersystems.teslacharger`)
   - `APPSTORE_ISSUER_ID`
   - `APPSTORE_KEY_ID`
   - `APPSTORE_PRIVATE_KEY_PATH` (absolute path to the `.p8` file on the server)
   - `APPSTORE_USE_SANDBOX=True` (Set to `False` in production)

## 2. Google Play Console (Android)

To offer subscriptions on Android, you must configure them in the Google Play Console.

### Creating the Subscription
1. Log in to the [Google Play Console](https://play.google.com/console/) and select your app.
   *(Note: You must have uploaded at least one APK/AAB to a testing track before you can create IAPs).*
2. Under **Monetize** -> **Products**, select **Subscriptions**.
3. Create a new subscription. Set the **Product ID** to: `charging_pro_monthly`.
4. Add a base plan (e.g., auto-renewing, monthly) and set the price.
5. Activate the base plan.

### Backend Receipt Verification Configuration
To allow your Python backend to automatically verify purchase tokens with Google:
1. Go to the [Google Cloud Console](https://console.cloud.google.com/) for your project.
2. Enable the **Google Play Android Developer API**.
3. Go to **Credentials** -> **Create Credentials** -> **Service Account**.
4. Grant the Service Account the "Owner" or "Pub/Sub Admin" roles (or link it in the Play Console under **API access** with financial permissions).
5. Generate a JSON Key for the Service Account and download it.
6. Set the following environment variables in your backend `.env`:
   - `PLAY_PACKAGE_NAME` (e.g., `com.clankersystems.teslacharger`)
   - `PLAY_SERVICE_ACCOUNT_JSON_PATH` (absolute path to the JSON key file)

## 3. Testing IAP

Native In-App Purchases **cannot** be tested in the standard Expo Go app. 

To test the purchase and restore flows:
1. Build a custom development client:
   ```bash
   eas build --profile development --platform ios
   eas build --profile development --platform android
   ```
2. For iOS: You must test on a real physical device. Create a Sandbox Tester account in App Store Connect to process fake transactions.
3. For Android: You can test on an emulator or physical device. Add your Google account to the "License Testing" section in the Google Play Console to process test payments without being charged.
4. When testing locally, ensure `STUB_ALLOW_ALL = False` in your `backend/app/subscriptions.py` file to force the backend to actually reach out to Apple/Google to validate the receipts!