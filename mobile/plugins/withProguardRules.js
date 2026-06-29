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
        const rules = "\n# Nitro modules rules\n-keep class com.margelo.nitro.** { *; }\n-keep class com.margelo.nitro.iap.** { *; }\n";
        if (!contents.includes('-keep class com.margelo.nitro.**')) {
          contents += rules;
          fs.writeFileSync(file, contents);
        }
      }
      return config;
    },
  ]);
};
