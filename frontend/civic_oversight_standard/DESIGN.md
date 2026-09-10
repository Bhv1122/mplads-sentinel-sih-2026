---
name: Civic Oversight Standard
colors:
  surface: '#faf8ff'
  surface-dim: '#d2d9f4'
  surface-bright: '#faf8ff'
  surface-container-lowest: '#ffffff'
  surface-container-low: '#f2f3ff'
  surface-container: '#eaedff'
  surface-container-high: '#e2e7ff'
  surface-container-highest: '#dae2fd'
  on-surface: '#131b2e'
  on-surface-variant: '#44474c'
  inverse-surface: '#283044'
  inverse-on-surface: '#eef0ff'
  outline: '#75777d'
  outline-variant: '#c5c6cd'
  surface-tint: '#525f75'
  primary: '#000000'
  on-primary: '#ffffff'
  primary-container: '#0e1c2f'
  on-primary-container: '#77849c'
  inverse-primary: '#bac7e1'
  secondary: '#4059aa'
  on-secondary: '#ffffff'
  secondary-container: '#8fa7fe'
  on-secondary-container: '#1d3989'
  tertiary: '#000000'
  on-tertiary: '#ffffff'
  tertiary-container: '#2a1702'
  on-tertiary-container: '#9d7e5e'
  error: '#ba1a1a'
  on-error: '#ffffff'
  error-container: '#ffdad6'
  on-error-container: '#93000a'
  primary-fixed: '#d6e3fe'
  primary-fixed-dim: '#bac7e1'
  on-primary-fixed: '#0e1c2f'
  on-primary-fixed-variant: '#3a475c'
  secondary-fixed: '#dce1ff'
  secondary-fixed-dim: '#b6c4ff'
  on-secondary-fixed: '#00164e'
  on-secondary-fixed-variant: '#264191'
  tertiary-fixed: '#ffddba'
  tertiary-fixed-dim: '#e4c09c'
  on-tertiary-fixed: '#2a1702'
  on-tertiary-fixed-variant: '#5a4226'
  background: '#faf8ff'
  on-background: '#131b2e'
  surface-variant: '#dae2fd'
typography:
  title-page:
    fontFamily: Public Sans
    fontSize: 20px
    fontWeight: '600'
    lineHeight: 28px
    letterSpacing: -0.015em
  title-section:
    fontFamily: Public Sans
    fontSize: 16px
    fontWeight: '600'
    lineHeight: 24px
    letterSpacing: -0.01em
  title-subsection:
    fontFamily: Public Sans
    fontSize: 14px
    fontWeight: '600'
    lineHeight: 20px
    letterSpacing: -0.005em
  body-default:
    fontFamily: Public Sans
    fontSize: 14px
    fontWeight: '400'
    lineHeight: 20px
    letterSpacing: 0em
  body-strong:
    fontFamily: Public Sans
    fontSize: 14px
    fontWeight: '600'
    lineHeight: 20px
    letterSpacing: 0em
  data-tabular:
    fontFamily: Public Sans
    fontSize: 13px
    fontWeight: '500'
    lineHeight: 18px
    letterSpacing: 0em
  caption-meta:
    fontFamily: Public Sans
    fontSize: 12px
    fontWeight: '400'
    lineHeight: 16px
    letterSpacing: 0.01em
  caption-strong:
    fontFamily: Public Sans
    fontSize: 12px
    fontWeight: '600'
    lineHeight: 16px
    letterSpacing: 0.01em
  micro-badge:
    fontFamily: Public Sans
    fontSize: 11px
    fontWeight: '600'
    lineHeight: 14px
    letterSpacing: 0.025em
rounded:
  sm: 0.125rem
  DEFAULT: 0.25rem
  md: 0.375rem
  lg: 0.5rem
  xl: 0.75rem
  full: 9999px
spacing:
  unit-2: 0.125rem
  unit-4: 0.25rem
  unit-6: 0.375rem
  unit-8: 0.5rem
  unit-12: 0.75rem
  unit-16: 1rem
  unit-20: 1.25rem
  unit-24: 1.5rem
  unit-32: 2rem
  table-cell-x: 0.75rem
  table-cell-y: 0.5rem
  toolbar-height: 3.25rem
  sidebar-width: 16rem
  inspector-width: 22rem
---

## Brand & Style

This design system is engineered for civic accountability, auditability, and high-density regulatory oversight. It caters to civil servants, compliance investigators, data auditors, and administrative leads who review thousands of records, financial transactions, and statutory disclosures daily.

The visual language follows **disciplined enterprise minimalism** with an architectural, structural demeanor:
- **Tone:** Authoritative, dispassionate, neutral, and meticulously precise.
- **Form Follows Data:** Zero ornamental flourishes, zero gradients, zero frosted glassmorphism, and zero ambient floating cards. Interfaces prioritize information density, rapid scanning, and unequivocal legal clarity over marketing-driven white space.
- **Structural Integrity:** Visual hierarchy is enforced predominantly through precise hairline structural borders, crisp typographic hierarchy, and tonal surface shifts rather than dramatic shadows or high-saturation accents.

## Colors

The palette operates with severe institutional restraint. Color is treated as a functional tool for delineation, legibility, and critical status signaling rather than decorative styling.

### Canvas & Surface Architecture
- **Base Background:** `#ffffff` for core workspaces, active tables, sheets, and modal viewports.
- **Sub-canvas / Recessed Background:** `#f8fafc` (Slate-50) for application frame backdrops, toolbars, and global sidebars.
- **Muted Surface / Hover Layer:** `#f1f5f9` (Slate-100) for table row hovering, selected state containers, and inactive segmented controls.

### Hairline Grids & Borders
- **Standard Structural Border:** `#e2e8f0` (Slate-200) for grid dividers, field outlines, and standard container boundaries.
- **Emphasized Border:** `#cbd5e1` (Slate-300) for structural splitters, sticky table headers, active tab underlines, and focused region separators.

### Typography & Content Tone
- **Primary Ink:** `#0f172a` (Slate-900) ensures maximum contrast against pure white backgrounds for sustained legibility during multi-hour review sessions.
- **Secondary Ink:** `#475569` (Slate-600) for table headers, metadata tags, audit stamps, and secondary prompts.
- **Muted Ink:** `#94a3b8` (Slate-400) for disabled fields, empty states, and micro breadcrumb dividers.

### Primary Accents
- **Institutional Primary (`#0b192c`):** Deep Navy for key administrative action buttons, active navigation item indicators, and root entity headings.
- **Interactive Secondary (`#1e3a8a`):** Classic institutional blue for hyperlinks, focused input rings, and active selection filters.

### Semantic Status Signaling
Status accents are applied exclusively as restrained visual cues (such as 6px or 8px status indicator dots, text badges with neutral backing, or subtle hairline status tags). They are never applied as saturated flood fills:
- **Normal / Verified / Complete:** `#10b981` (Emerald).
- **Warning / Pending Audit / Advisory:** `#f59e0b` (Amber).
- **Critical / Non-Compliant / Flagged:** `#f43f5e` (Rose).

## Typography

The typographic scale uses **Public Sans**—an open, neutral grotesque typeface conceived for administrative and governmental rigor. It preserves clarity under high data density and low screen scaling.

### Numeric & Metric Standardization
- All figures, timestamps, currency amounts, and reference IDs must be rendered with OpenType tabular figures (`font-variant-numeric: tabular-nums;` or `font-feature-settings: "tnum"`). This prevents optical wobble across dense ledger columns.

### Scale Hierarchy
- **Page Titles (`20px`):** The maximum scale used across core views. Provides distinct context without displacing vertical data real estate.
- **Section Headers (`16px`):** Delineates data sections, pane groupings, and audit panel boundaries.
- **Subsection & Card Headers (`14px`, Semi-bold):** Sets contextual bounds for sub-tables and property lists.
- **General Body (`14px`, Regular):** Standard copy for descriptions, audit notes, dialog content, and legal text.
- **Data & Grid Cells (`13px`, Medium Tabular):** The primary density layer for data tables, metric grids, and input values.
- **Captions & Metadata (`12px`):** Timestamps, form helper instructions, breadcrumbs, and secondary table column sub-headers.
- **Micro Badges (`11px`, Uppercase/Semi-bold):** Status capsules, record type labels, and statutory category indicators.

## Layout & Spacing

The platform uses a fixed-workspace, continuous-grid layout rather than consumer fluid-marketing columns. The screen real estate is treated as an operational console with defined panes:

### Pane Structure & Rhythms
- **Global Navigation:** Fixed left sidebar (`256px` wide) spanning full height with collapsed icon-only mode (`56px`).
- **Main Operational Canvas:** Fluid container with strict horizontal boundary constraints (`min-width: 960px`).
- **Audit/Inspector Panel:** Fixed right contextual panel (`352px` wide) sliding over or docking alongside the canvas for drill-down investigation without losing position in the root table.

### Spacing Grid
The design system enforces a strict 4px base rhythm:
- `4px` (`0.25rem`): Micro gaps between icons and labels, input inner horizontal spacing.
- `8px` (`0.5rem`): Standard vertical padding for data-dense table rows and compact input elements.
- `12px` (`0.75rem`): Horizontal padding inside form inputs, buttons, and dense cells.
- `16px` (`1rem`): Padding within standard panels, inspection drawers, and between adjacent controls.
- `24px` (`1.5rem`): Outer margins for main canvas pages and modal window interiors.

### Multi-Device Adaptation
- **Desktop (>= 1280px):** Full operational capability: global tree navigation, primary data grid, and persistent inspector pane simultaneously visible.
- **Tablet / Small Workstation (1024px - 1279px):** Inspector pane shifts to a floating overlay sheet; sidebar auto-collapses to a compact state (`56px`).
- **Mobile / Field Device (< 1024px):** Operational layout shifts to stacked panes with persistent sub-headers. Data tables convert to prioritized key-value lists with pagination.

## Elevation & Depth

Visual depth is achieved through **structural surface tiers and hairline borders** rather than shadows. Elevation is binary: content is either on the planar grid or temporarily focused in an overlay layer.

### Tiers
1. **Base Tier (Ground):** Background frame at `#f8fafc`.
2. **Work Surface Tier:** Tables, forms, and audit logs at `#ffffff` bounded by an explicit `1px solid #e2e8f0` border.
3. **Elevated Context Tier (Dropdowns, Tooltips, Popovers):** Pure white `#ffffff`, separated by a `1px solid #cbd5e1` outline and reinforced with an ultra-compact shadow: `0 1px 3px 0 rgba(15, 23, 42, 0.08), 0 1px 2px -1px rgba(15, 23, 42, 0.06)`.
4. **Modal & System Drawers:** Bounded by `1px solid #cbd5e1` with a calibrated shadow: `0 4px 6px -1px rgba(15, 23, 42, 0.08), 0 2px 4px -2px rgba(15, 23, 42, 0.06)`, framed against a semi-opaque neutral backdrop (`#0f172a` at 40% opacity).

### Principles
- No multi-layered, colored, or diffused drop shadows.
- No floating cards with outer margins on white surfaces. Cards must sit flush in a table-like grid, or be separated by `1px` hairlines.

## Shapes

The geometric silhouette is sharp, restrained, and utilitarian:

- **Base Radius (`roundedness: 1`):** Core interactive targets—including text inputs, buttons, select menus, and modal frames—use a uniform `4px` (`0.25rem`) radius.
- **Data Panels & Structural Containers:** Containers, panel borders, and table frames use `4px` or `0px` depending on whether they sit inline or flush against viewport boundaries.
- **Status Indicator Dots:** True circles (`rounded-full`, 50% radius) constrained strictly to `6px` or `8px` diameters to avoid resembling buttons or chips.
- **Pill Shapes:** Strictly forbidden for functional buttons or general cards. Used solely for compact tabular count indicators where height does not exceed `20px`.

## Components

### 1. Data Tables
- **Structure:** Clean hairline rows (`1px solid #e2e8f0`). Row height locked to a dense `36px` or comfortable `44px`.
- **Header:** Sticky `#f8fafc` background with a lower border of `1px solid #cbd5e1`. Labels set in `12px` semi-bold `#475569`, tracking slightly open.
- **Interactions:** Subtle hover fill (`#f1f5f9`), no row elevation. Checkbox column aligned left with fixed `40px` cell width.
- **Cell Content:** Tabular numbers right-aligned; entity names and text left-aligned.

### 2. Buttons
- **Primary:** Background `#0b192c`, foreground `#ffffff`, border `1px solid #0b192c`, border-radius `4px`. Hover: `#1e293b`.
- **Secondary / Standard:** Background `#ffffff`, foreground `#0f172a`, border `1px solid #cbd5e1`. Hover: `#f8fafc`.
- **Destructive:** Background `#ffffff`, foreground `#f43f5e`, border `1px solid #f43f5e`. Hover: `#fff1f2`.
- **Height & Spacing:** Compact height `32px` (`px-3`, text `13px`) for toolbars; default height `36px` (`px-4`, text `14px`) for primary dialog triggers. Zero rounded-full buttons.

### 3. Inputs & Form Fields
- **Container:** Background `#ffffff`, border `1px solid #cbd5e1`, radius `4px`, height `32px` (dense) or `36px` (standard).
- **Typography:** `13px` or `14px` with text color `#0f172a`. Placeholder text set in `#94a3b8`.
- **Focus State:** Hairline border switches to `#1e3a8a` with a clean `2px` focus offset or a sharp 1px outer ring `rgba(30, 58, 138, 0.2)`. Never use thick fuzzy halos.
- **Validation:** Error states replace border with `#f43f5e`. Helper text renders in `12px` below input with appropriate semantic color.

### 4. Status Badges & Chips
- **Geometry:** Height `20px`, padding `0 6px`, radius `4px`.
- **Coloration:** Neutral background tint (`#f1f5f9`) with a contextual colored dot:
  - *Normal:* `6px` circle in `#10b981` + `11px` medium text `#0f172a`.
  - *Warning:* `6px` circle in `#f59e0b` + `11px` medium text `#0f172a`.
  - *Critical:* `6px` circle in `#f43f5e` + `11px` medium text `#0f172a`.

### 5. Checkboxes & Radio Controls
- **Geometry:** Checkboxes use a `14px` square with a `2px` corner radius. Radio elements use a `14px` circle.
- **Colors:** Default border `1px solid #94a3b8`, background `#ffffff`. Checked state: Background `#0b192c`, white check icon. Focus: sharp outline ring.

### 6. Panels & Sheets (Inspector)
- **Container:** Flush-docked or modal drawer on the right edge of viewport. Separated by `1px solid #cbd5e1`.
- **Header:** Height `48px`, background `#f8fafc`, bottom border `1px solid #e2e8f0`, equipped with an explicit close icon button and primary metadata summary.
- **Section Dividers:** `1px solid #e2e8f0` with `14px` bold section headers.

### 7. Audit Stamp / Metadata Row
- **Context:** Used to display chain-of-custody, signature hashes, and modification dates.
- **Styling:** Monospaced tabular presentation, `12px` font size, muted slate `#475569`, punctuated with subtle vertical separator lines (`#cbd5e1`).