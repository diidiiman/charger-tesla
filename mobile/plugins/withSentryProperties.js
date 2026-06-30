const { withDangerousMod } = require('expo/config-plugins');
const fs = require('fs');
const path = require('path');

module.exports = function withSentryProperties(config) {
  return withDangerousMod(config, [
    'android',
    async (config) => {
      // 1. ProGuard Rules for missing OpenIAP package
      const file = path.join(config.modRequest.platformProjectRoot, 'app', 'proguard-rules.pro');
      if (fs.existsSync(file)) {
        let contents = fs.readFileSync(file, 'utf8');
        const rules = `\n-keep class dev.hyo.openiap.** { *; }\n-keep class com.android.billingclient.** { *; }\n`;
        if (!contents.includes('-keep class dev.hyo.openiap.**')) {
          contents += rules;
          fs.writeFileSync(file, contents);
        }
      }

      // 2. Sentry Properties
      const sentryPropFile = path.join(config.modRequest.platformProjectRoot, 'sentry.properties');
      const sentryProps = `defaults.url=https://de.sentry.io/
defaults.org=clanker-systems
defaults.project=tesla-nord-pool
auth.token=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
`;
      fs.writeFileSync(sentryPropFile, sentryProps);

      return config;
    },
  ]);
};
