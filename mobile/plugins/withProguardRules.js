const { withDangerousMod } = require('expo/config-plugins');
const fs = require('fs');
const path = require('path');

module.exports = function withProguardRules(config) {
  return withDangerousMod(config, [
    'android',
    async (config) => {
      const file = path.join(config.modRequest.platformProjectRoot, 'app', 'proguard-rules.pro');
      if (fs.existsSync(file)) {
        let contents = fs.readFileSync(file, 'utf8');
        const rules = `
# Nitro modules rules
-keep class com.margelo.nitro.** { *; }
-keep class com.margelo.nitro.iap.** { *; }
-keep class dev.hyo.openiap.** { *; }
-keep class com.android.billingclient.** { *; }
-keep class kotlin.** { *; }
-keep class kotlinx.coroutines.** { *; }
-keep class kotlin.coroutines.** { *; }
`;
        if (!contents.includes('-keep class dev.hyo.openiap.**')) {
          contents += rules;
          fs.writeFileSync(file, contents);
        } else if (!contents.includes('-keep class kotlin.coroutines.**')) {
          contents += `\n-keep class kotlin.** { *; }\n-keep class kotlinx.coroutines.** { *; }\n-keep class kotlin.coroutines.** { *; }\n`;
          fs.writeFileSync(file, contents);
        }
      }
      return config;
    },
  ]);
};
