import { useRef, useState } from 'react';
import {
  Dimensions,
  FlatList,
  StyleSheet,
  View,
  NativeSyntheticEvent,
  NativeScrollEvent,
  Platform,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { router } from 'expo-router';
import { Body, Button, H1, Label, Pill } from '../src/components/ui';
import { introSeen } from '../src/storage';
import { useTheme, Theme } from '../src/theme';

const createStyles = (theme: Theme) => StyleSheet.create({
  root: { flex: 1, backgroundColor: theme.bg.base },
  header: {
    paddingHorizontal: theme.space['2xl'],
    paddingTop: theme.space.lg,
    paddingBottom: theme.space['2xl'],
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  slide: {
    backgroundColor: theme.bg.surface,
    borderColor: theme.border.subtle,
    borderWidth: 1,
    borderRadius: theme.radius.lg,
    padding: theme.space['2xl'],
    minHeight: 280,
  },
  dots: {
    flexDirection: 'row',
    alignSelf: 'center',
    gap: 6,
    marginVertical: theme.space.xl,
  },
  dot: { width: 6, height: 6, borderRadius: 3, backgroundColor: theme.border.strong },
});


type Slide = { label: string; title: string; body: string };

const SLIDES: Slide[] = [
  {
    label: 'Step 1',
    title: 'Charge only when power is cheap.',
    body:
      'We pull Nord Pool day-ahead prices and use them to decide whether it is the right time to charge your Tesla.',
  },
  {
    label: 'Step 2',
    title: 'Set your threshold.',
    body:
      'Tell us the price you’re comfortable paying. Below it, the app considers charging cheap. Above it, expensive.',
  },
  {
    label: 'Step 3',
    title: 'Connect your Tesla.',
    body:
      'Sign in to your Tesla account through the official Fleet API. We store an encrypted refresh token so we can check the state of charge and trigger commands.',
  },
  {
    label: 'Pro',
    title: 'Optional: hands-free.',
    body:
      `Upgrade to Pro (via the ${Platform.OS === 'ios' ? 'App Store' : 'Play Store'}) and the app starts and stops charging for you whenever the price crosses your threshold.`,
  },
];

const { width } = Dimensions.get('window');

export default function Intro() {
  const { theme } = useTheme();
  const styles = createStyles(theme);
  const ref = useRef<FlatList>(null);
  const [index, setIndex] = useState(0);

  function onScroll(e: NativeSyntheticEvent<NativeScrollEvent>) {
    const i = Math.round(e.nativeEvent.contentOffset.x / width);
    if (i !== index) setIndex(i);
  }

  async function next() {
    if (index < SLIDES.length - 1) {
      ref.current?.scrollToIndex({ index: index + 1, animated: true });
    } else {
      await introSeen.mark();
      router.replace('/');
    }
  }

  return (
    <SafeAreaView style={styles.root} edges={['top', 'bottom']}>
      <View style={styles.header}>
        <H1>Tesla Nord Pool</H1>
        <Pill label={`${index + 1} / ${SLIDES.length}`} />
      </View>

      <View style={{ flex: 1, justifyContent: 'center' }}>
        <FlatList
          ref={ref}
          data={SLIDES}
          horizontal
          pagingEnabled
          showsHorizontalScrollIndicator={false}
          keyExtractor={(_, i) => String(i)}
          onScroll={onScroll}
          scrollEventThrottle={16}
          style={{ flexGrow: 0 }}
          renderItem={({ item }) => (
            <View style={{ width, paddingHorizontal: theme.space['2xl'] }}>
              <View style={styles.slide}>
                <Label>{item.label}</Label>
                <H1 style={{ marginTop: theme.space.md }}>{item.title}</H1>
                <Body muted style={{ marginTop: theme.space.lg }}>
                  {item.body}
                </Body>
              </View>
            </View>
          )}
        />
      </View>

      <View>
        <View style={styles.dots}>
          {SLIDES.map((_, i) => (
            <View
              key={i}
              style={[styles.dot, i === index && { backgroundColor: theme.fg.primary, width: 18 }]}
            />
          ))}
        </View>

        <View style={{ paddingHorizontal: theme.space['2xl'], paddingBottom: theme.space.xl }}>
          <Button
            title={index === SLIDES.length - 1 ? 'Get started' : 'Next'}
            variant="primary"
            onPress={next}
          />
        </View>
      </View>
    </SafeAreaView>
  );
}


