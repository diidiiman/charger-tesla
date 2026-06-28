import React from 'react';
import {
  ActivityIndicator,
  Pressable,
  PressableProps,
  StyleSheet,
  Text,
  TextProps,
  View,
  ViewProps,
  Dimensions,
} from 'react-native';
import { LinearGradient } from 'expo-linear-gradient';
import { theme } from '../theme';

const screenWidth = Dimensions.get('window').width;

export function Card({ style, children, ...rest }: ViewProps) {
  return (
    <View style={[styles.card, style]} {...rest}>
      {children}
    </View>
  );
}

export function Label({ children, style, ...rest }: TextProps) {
  return (
    <Text style={[styles.label, style]} {...rest}>
      {String(children).toUpperCase()}
    </Text>
  );
}

export function H1({ children, style, ...rest }: TextProps) {
  return (
    <Text style={[styles.h1, style]} {...rest}>
      {children}
    </Text>
  );
}

export function H2({ children, style, ...rest }: TextProps) {
  return (
    <Text style={[styles.h2, style]} {...rest}>
      {children}
    </Text>
  );
}

export function Body({ children, style, muted, ...rest }: TextProps & { muted?: boolean }) {
  return (
    <Text style={[styles.body, muted && { color: theme.fg.muted }, style]} {...rest}>
      {children}
    </Text>
  );
}

type ButtonProps = PressableProps & { title: string; variant?: 'primary' | 'default' | 'ghost'; loading?: boolean };
export function Button({ title, variant = 'default', loading, disabled, style, ...rest }: ButtonProps) {
  return (
    <Pressable
      disabled={disabled || loading}
      style={({ pressed }) => [
        styles.btn,
        variant === 'primary' && styles.btnPrimary,
        variant === 'ghost' && styles.btnGhost,
        pressed && { borderColor: theme.border.strong },
        (disabled || loading) && { opacity: 0.5 },
        typeof style === 'function' ? undefined : style,
      ]}
      {...rest}
    >
      {loading ? (
        <ActivityIndicator color={variant === 'primary' ? '#fff' : theme.fg.primary} />
      ) : (
        <Text style={[styles.btnText, variant === 'primary' && { color: '#fff' }]}>{title}</Text>
      )}
    </Pressable>
  );
}

export function Pill({ tone, label }: { tone?: 'ok' | 'warn' | 'bad'; label: string }) {
  const color =
    tone === 'ok' ? theme.ok : tone === 'warn' ? theme.warn : tone === 'bad' ? theme.accent : theme.fg.muted;
  return (
    <View style={styles.pill}>
      <View style={[styles.dot, { backgroundColor: color }]} />
      <Text style={[styles.pillText, { color }]}>{label.toUpperCase()}</Text>
    </View>
  );
}

export function Stat({ label, value, unit }: { label: string; value: string | number | null | undefined; unit?: string }) {
  return (
    <View style={{ gap: theme.space.sm, minWidth: 120 }}>
      <Label>{label}</Label>
      <View style={{ flexDirection: 'row', alignItems: 'baseline', gap: theme.space.xs }}>
        <Text style={styles.statValue}>{value ?? '—'}</Text>
        {unit && value != null ? <Text style={styles.statUnit}>{unit}</Text> : null}
      </View>
    </View>
  );
}

export function ProgressBar({ value, charging }: { value: number; charging?: boolean }) {
  const pct = Math.max(0, Math.min(100, value));
  return (
    <View style={styles.bar}>
      <View
        style={{
          width: `${pct}%`,
          height: '100%',
          backgroundColor: charging ? theme.ok : theme.fg.faint,
        }}
      />
    </View>
  );
}

export function Divider() {
  return <View style={{ height: 1, backgroundColor: theme.border.subtle, marginVertical: theme.space.xl }} />;
}

export function ErrorBox({ children }: { children: React.ReactNode }) {
  return (
    <View style={styles.error}>
      <Text style={{ color: theme.fg.primary, fontSize: theme.size.sm }}>{children}</Text>
    </View>
  );
}

export function BottomBar({ children, style, ...rest }: ViewProps) {
  return (
    <View style={[styles.bottomBarContainer, style]} {...rest}>
      <LinearGradient 
        colors={['rgba(10, 10, 12, 0)', '#0a0a0c']} 
        style={styles.bottomBarFade} 
        pointerEvents="none" 
      />
      <View style={styles.bottomBarContent}>
        {children}
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  card: {
    backgroundColor: theme.bg.surface,
    borderColor: theme.border.subtle,
    borderWidth: 1,
    borderRadius: theme.radius.lg,
    padding: theme.space['2xl'],
  },
  label: {
    color: theme.fg.faint,
    fontSize: theme.size.xs,
    letterSpacing: 1.1,
    fontWeight: '500',
  },
  h1: { color: theme.fg.primary, fontSize: theme.size.xl, fontWeight: '600', letterSpacing: -0.5 },
  h2: { color: theme.fg.primary, fontSize: theme.size.lg, fontWeight: '600' },
  body: { color: theme.fg.primary, fontSize: theme.size.base, lineHeight: 22 },
  btn: {
    height: 44,
    paddingHorizontal: theme.space.lg,
    borderRadius: theme.radius.md,
    borderWidth: 1,
    borderColor: theme.border.subtle,
    backgroundColor: theme.bg.input,
    alignItems: 'center',
    justifyContent: 'center',
    flexDirection: 'row',
    gap: theme.space.sm,
    minWidth: 120,
  },
  btnPrimary: { backgroundColor: theme.accent, borderColor: theme.accent },
  btnGhost: { backgroundColor: 'transparent' },
  btnText: { color: theme.fg.primary, fontSize: theme.size.sm, fontWeight: '500' },
  pill: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    height: 26,
    paddingHorizontal: theme.space.md,
    borderRadius: 999,
    borderWidth: 1,
    borderColor: theme.border.subtle,
  },
  dot: { width: 6, height: 6, borderRadius: 3 },
  pillText: { fontSize: theme.size.xs, letterSpacing: 0.8, fontWeight: '500' },
  statValue: {
    color: theme.fg.primary,
    fontSize: theme.size.xl,
    fontWeight: '500',
    fontVariant: ['tabular-nums'],
    letterSpacing: -0.5,
  },
  statUnit: { color: theme.fg.faint, fontSize: theme.size.base, fontVariant: ['tabular-nums'] },
  bar: {
    width: '100%',
    height: 6,
    backgroundColor: theme.bg.input,
    borderRadius: 999,
    borderWidth: 1,
    borderColor: theme.border.subtle,
    overflow: 'hidden',
  },
  error: {
    borderWidth: 1,
    borderColor: theme.accent,
    backgroundColor: theme.accentSoft,
    padding: theme.space.md,
    borderRadius: theme.radius.sm,
  },
  bottomBarContainer: {
    position: 'relative',
    backgroundColor: theme.bg.base,
    width: screenWidth,
  },
  bottomBarFade: {
    position: 'absolute',
    top: -20,
    left: 0,
    width: screenWidth,
    height: 20,
  },
  bottomBarContent: {
    paddingHorizontal: theme.space['2xl'],
    paddingBottom: theme.space['2xl'],
    paddingTop: theme.space.md,
    backgroundColor: theme.bg.base,
    flexDirection: 'row',
    gap: theme.space.sm,
  },
});
