# Tesla Nord Pool Mobile — Interface Design System

> Per the `interface-design` skill convention
> (https://github.com/Dammyjay93/interface-design). Source of truth for every
> UI decision in the Expo app.

## Direction: **Precision & Density**

A vehicle command panel. Dark, monochrome, single accent. Numbers come first;
chrome stays out of the way. Borders define structure rather than shadows.

## Tokens (consumed from `src/theme.ts`)

### Color

| Token            | Hex       | Role                                |
| ---------------- | --------- | ----------------------------------- |
| `bg.base`        | `#0a0a0c` | App background                      |
| `bg.surface`     | `#111114` | Card surface                        |
| `bg.input`       | `#17171c` | Input / inset                       |
| `border.subtle`  | `#26262e` | Hairline dividers, card edges       |
| `border.strong`  | `#3a3a44` | Hover / focus / pressed             |
| `fg.primary`     | `#f5f5f7` | Body text                           |
| `fg.muted`       | `#a1a1aa` | Secondary                           |
| `fg.faint`       | `#6b6b75` | Captions, units, labels             |
| `accent`         | `#e31937` | Tesla red — actionable / critical   |
| `accent.soft`    | `#3a151b` | Accent backdrop                     |
| `ok`             | `#3ddc97` | Charging / success                  |
| `warn`           | `#f4b942` | Warning                             |

### Spacing scale (4px base)

`xs=4, sm=8, md=12, lg=16, xl=20, 2xl=24, 3xl=32, 4xl=48`.

### Typography

- System font stack.
- Sizes: `xs=12, sm=13, base=15, lg=20, xl=32`.
- Stat numerics: tabular figures, letter-spacing −0.02em.
- Labels: uppercased, +0.08em letter-spacing, `fg.faint`, xs.

### Depth strategy

**Borders only.** No drop shadows. Pressed states bump the border to
`border.strong`. Buttons fill with `accent` for primary actions; everything
else uses transparent / `bg.input` with a hairline border.

### Component patterns

- Button: 44pt tall, padding 16, radius 8.
- Card: padding 24, radius 12, border 1px `border.subtle`.
- Stat: small uppercased label, large tabular value, small `fg.faint` unit.
- Progress bar: 6pt tall, `bg.input` track, `accent` fill (or `ok` when charging).
- Pill: 26pt tall, mono caps, 6pt dot prefix.

## Rules

1. Tokens only. If you reach for a hex literal, add a token first.
2. One accent — `accent` flags actionable primary or critical state. No decoration.
3. Numeric data uses tabular figures.
4. Consistency over novelty.
