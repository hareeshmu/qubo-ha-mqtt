# 7. Lovelace Dashboard

An animated Qubo-app-style dashboard card: green halo with floating particles,
mode buttons that light up in per-mode colors, PM2.5 history graph.

## HACS cards required

Install from HACS → Frontend (add custom repo if missing):

| Card | Repo |
|------|------|
| Mushroom | [piitaya/lovelace-mushroom](https://github.com/piitaya/lovelace-mushroom) |
| mini-graph-card | [kalkih/mini-graph-card](https://github.com/kalkih/mini-graph-card) |
| button-card | [custom-cards/button-card](https://github.com/custom-cards/button-card) |
| stack-in-card | [custom-cards/stack-in-card](https://github.com/custom-cards/stack-in-card) |
| card-mod | [thomasloven/lovelace-card-mod](https://github.com/thomasloven/lovelace-card-mod) |

Restart HA after installing.

## Dashboard layout

This repo has two styles:

- **`lovelace/cards/main-unified-dashboard.yaml`** — single unified card with
  animated halo + mode row + conditional speed pills. Best for the main
  device view.
- **`lovelace/cards/halo-pm25-only.yaml`** — just the halo
- **`lovelace/cards/mode-buttons-row.yaml`** — 5-button mode row
- **`lovelace/cards/pm25-graph-24h.yaml`** — 24h history graph
- **`lovelace/cards/controls-row-pills.yaml`** — timer / lock / silent / dimmer
- **`lovelace/cards/filter-and-diagnostics.yaml`** — filter life + buttons
- **`lovelace/cards/today-pm25-stats.yaml`** — min/avg/max + total minutes
- **`lovelace/lovelace-purifier-card.yaml`** — minimal, uses denysdovhan's
  purifier-card (different aesthetic).

## Setup

1. HA dashboard → ✏️ Edit → top-right `⋮` → **Raw configuration editor**, or:
2. **+ Add Card → Manual** → paste the YAML
3. Save

### Recommended: one-view, panel layout

Create a new view:
- Layout: **Panel (single card)**
- Paste the entire `00-main-qubo-style.yaml` content as a single Manual card

The halo renders full-width, mode buttons fill the bottom, and the speed
pills appear when Manual is selected.

## Customization

### Change PM2.5 thresholds (Good/Moderate/Poor)

In `00-main-qubo-style.yaml`, find the `ringRgb` ladder:

```js
var ringRgb = v < 50   ? '134,239,172'   // Good
            : v <= 100 ? '251,191,36'    // Moderate
            : v < 200  ? '251,146,60'    // Poor
            :           '248,113,113';   // Very Poor
```

And the adjacent `label` / `labelColor`. Adjust to WHO, Indian CPCB, or your
local standard.

### Change mode button colors

Each mode button has a `card_mod` block with a gradient. Find e.g. Manual:

```yaml
background: linear-gradient(135deg,#14b8a6 0%,#0f766e 100%) !important
```

Replace the hex pair with any CSS gradient.

### Replace the default image of `purifier-card`

```yaml
type: custom:purifier-card
entity: fan.qubo_r700_fan
image: /local/my_purifier.png   # place file in /config/www/
```

## Troubleshooting

- **"Custom element doesn't exist"** — a card isn't loaded. Hard refresh
  browser, or restart HA.
- **Halo is off-center** — your view layout is "Sections"; switch to
  **Panel** or drag the card to span full width.
- **Pills don't change when clicked** — see doc 8 troubleshooting;
  HA's fan `percentage` attribute must be populated.
- **Halo doesn't animate** — some browsers throttle `@keyframes`. Try a
  different browser or check console for CSS errors.

## Next step

[→ 08 Troubleshooting](08-troubleshooting.md)
