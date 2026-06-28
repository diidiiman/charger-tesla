import os
import re

def refactor_file(filepath):
    with open(filepath, 'r') as f:
        content = f.read()

    if 'import { theme } from' not in content and 'import { theme, Theme } from' not in content:
        if 'theme.' in content and 'useTheme' not in content:
             print(f"Skipping {filepath} but it has theme usage!")
        return

    # Replace import
    content = re.sub(r"import \{ theme \} from '([^']+)';", r"import { useTheme, Theme } from '\1';", content)

    # Check if there is StyleSheet.create
    has_stylesheet = 'StyleSheet.create({' in content
    
    if has_stylesheet:
        content = content.replace('StyleSheet.create({', 'const createStyles = (theme: Theme) => StyleSheet.create({', 1)
        # We need to find the end of the StyleSheet.create call to add the closing brace if needed? Wait.
        # Actually it's easier to just replace `const styles = StyleSheet.create` 
        # with `const createStyles = (theme: Theme) => StyleSheet.create`
        content = content.replace('const styles = const createStyles', 'const createStyles') # fix potential double
        content = re.sub(r'const styles = StyleSheet\.create\(\{', r'const createStyles = (theme: Theme) => StyleSheet.create({', content)
        content = re.sub(r'const styles = const createStyles', r'const createStyles', content) # cleanup

    # Inject `const { theme } = useTheme();` inside exported components.
    # Find exported functions
    # For each exported function that doesn't have useTheme:
    def inject_use_theme(match):
        func_sig = match.group(1)
        # Check if it already has useTheme
        if 'const { theme } = useTheme();' in match.group(2):
            return match.group(0)
        
        injection = '\n  const { theme } = useTheme();'
        if has_stylesheet:
            injection += '\n  const styles = createStyles(theme);'
        
        return func_sig + ' {' + injection + match.group(2)

    content = re.sub(r'(export default function \w+\([^)]*\)) {([^}]*)', inject_use_theme, content)
    content = re.sub(r'(export function \w+\([^)]*\)) {([^}]*)', inject_use_theme, content)

    with open(filepath, 'w') as f:
        f.write(content)
    print(f"Refactored {filepath}")

for root, dirs, files in os.walk('mobile'):
    for file in files:
        if file.endswith('.tsx') or file.endswith('.ts'):
            refactor_file(os.path.join(root, file))
