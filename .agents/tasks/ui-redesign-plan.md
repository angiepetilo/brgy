# Barangay Portal UI/UX Redesign Plan
## Full Apple HIG Implementation (macOS Desktop + iOS Mobile)

**Goal:** Transform the current web-style UI into a native-feeling Apple HIG-compliant interface that works beautifully on both desktop (macOS style) and mobile (iOS style).

**Timeline:** 2-3 weeks full implementation  
**Approach:** Module-by-module redesign with testing at each stage

---

## Design Principles

### **macOS HIG (Desktop: ≥768px)**
- **Clarity:** High-density layouts, precise typography, subtle refinements
- **Deference:** Content-first, chrome recedes
- **Depth:** Visual layers, smooth transitions

### **iOS HIG (Mobile: <768px)**
- **Clarity:** Touch-optimized, legible at every size
- **Deference:** Full-screen content, translucency
- **Depth:** Layered navigation, gestural fluidity

---

## Phase 1: Design System Foundation (Week 1, Days 1-2)

### 1.1 Typography System
**File:** `static/css/design-tokens.css` (new)

```css
/* SF Pro Font Stack */
:root {
  --font-family-base: -apple-system, BlinkMacSystemFont, "SF Pro Text", "SF Pro Display", system-ui, sans-serif;
  --font-family-display: "SF Pro Display", -apple-system, system-ui, sans-serif;
  --font-family-mono: "SF Mono", "Menlo", monospace;
  
  /* Desktop Typography Scale (macOS HIG) */
  --text-xxlarge: 24px;      /* KPI numbers */
  --text-xlarge: 22px;       /* Window titles */
  --text-large: 18px;        /* Section headers */
  --text-body: 13px;         /* Table cells, inputs */
  --text-label: 11px;        /* Column headers, labels */
  --text-caption: 10px;      /* Badges, timestamps */
  
  /* Mobile Typography Scale (iOS HIG) */
  --text-mobile-title1: 28px;
  --text-mobile-title2: 22px;
  --text-mobile-headline: 17px;
  --text-mobile-body: 17px;
  --text-mobile-callout: 16px;
  --text-mobile-footnote: 13px;
  
  /* Font Weights */
  --weight-regular: 400;
  --weight-medium: 500;
  --weight-semibold: 600;
  --weight-bold: 700;
  
  /* Letter Spacing */
  --tracking-tight: -0.26px;
  --tracking-normal: 0px;
  --tracking-wide: 0.12px;
}
```

### 1.2 Color System (Apple Neutrals + Semantic)
```css
:root {
  /* Light Mode (macOS/iOS) */
  --color-canvas: #FFFFFF;
  --color-sidebar: #F5F5F7;
  --color-hover: #F2F2F7;
  --color-border: #E5E5E7;
  --color-text-primary: #1D1D1F;
  --color-text-secondary: #86868B;
  --color-accent-blue: #0071E3;
  --color-success-green: #34C759;
  --color-error-red: #FF3B30;
  --color-warning-orange: #FF9500;
  
  /* Dark Mode */
  @media (prefers-color-scheme: dark) {
    --color-canvas: #1E1E1E;
    --color-sidebar: #161617;
    --color-hover: #2C2C2E;
    --color-border: #38383A;
    --color-text-primary: #F5F5F7;
    --color-text-secondary: #A1A1A6;
    --color-accent-blue: #2997FF;
    --color-success-green: #30D158;
    --color-error-red: #FF453A;
    --color-warning-orange: #FF9F0A;
  }
}
```

### 1.3 Spacing & Sizing System
```css
:root {
  /* Desktop Dimensions (macOS HIG) */
  --toolbar-height: 52px;
  --sidebar-width: 240px;
  --content-padding: 24px;
  --table-header-height: 32px;
  --table-row-height: 42px;
  --button-height: 32px;
  --button-height-compact: 28px;
  --corner-radius: 6px;
  --corner-radius-large: 10px;
  
  /* Mobile Dimensions (iOS HIG) */
  --mobile-nav-bar: 44px;
  --mobile-tab-bar: 49px;
  --mobile-touch-target: 44px;
  --mobile-margin: 16px;
  --mobile-corner-radius: 12px;
  
  /* Spacing Scale (8pt grid) */
  --space-xs: 4px;
  --space-sm: 8px;
  --space-md: 16px;
  --space-lg: 24px;
  --space-xl: 32px;
}
```

---

## Phase 2: Core Layout Architecture (Week 1, Days 3-5)

### 2.1 Desktop Split-View Structure (≥768px)
**Files:** `templates/base.html`, `static/css/layout-desktop.css`

```html
<!-- Desktop Layout -->
<div class="app-container desktop">
  <!-- Fixed Sidebar: 240px -->
  <aside class="sidebar">
    <div class="sidebar-header">
      <img src="logo" class="sidebar-logo">
      <span class="sidebar-title">Barangay Portal</span>
    </div>
    <nav class="sidebar-nav">
      <!-- Navigation items: 32px height each -->
      <a href="#" class="nav-item active">
        <svg class="nav-icon">...</svg>
        <span class="nav-label">Dashboard</span>
        <span class="nav-badge">3</span>
      </a>
    </nav>
  </aside>
  
  <!-- Main Content Area -->
  <main class="content-area">
    <!-- Toolbar: 52px height -->
    <header class="toolbar">
      <h1 class="toolbar-title">Page Title</h1>
      <div class="toolbar-actions">
        <button class="btn-toolbar">Filter</button>
        <button class="btn-toolbar-primary">New</button>
      </div>
    </header>
    
    <!-- Scrollable Content: 24px padding -->
    <div class="content-body">
      {% block content %}{% endblock %}
    </div>
  </main>
</div>
```

**CSS:**
```css
@media (min-width: 768px) {
  .app-container.desktop {
    display: grid;
    grid-template-columns: 240px 1fr;
    height: 100vh;
  }
  
  .sidebar {
    background: var(--color-sidebar);
    border-right: 1px solid var(--color-border);
    display: flex;
    flex-direction: column;
    overflow-y: auto;
  }
  
  .nav-item {
    height: 32px;
    padding: 6px 10px;
    display: flex;
    align-items: center;
    gap: 8px;
    border-radius: var(--corner-radius);
    transition: background 0.15s ease;
  }
  
  .nav-item.active {
    background: var(--color-accent-blue);
    color: white;
  }
  
  .nav-item:hover:not(.active) {
    background: var(--color-hover);
  }
  
  .toolbar {
    height: var(--toolbar-height);
    border-bottom: 1px solid var(--color-border);
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 0 var(--content-padding);
  }
  
  .content-body {
    padding: var(--content-padding);
    overflow-y: auto;
  }
}
```

### 2.2 Mobile Stack Layout (<768px)
**File:** `static/css/layout-mobile.css`

```html
<!-- Mobile Layout -->
<div class="app-container mobile">
  <!-- Top Navigation Bar: 44px -->
  <header class="mobile-nav-bar">
    <button class="nav-back">
      <svg>chevron-left</svg>
    </button>
    <h1 class="nav-title">Page Title</h1>
    <button class="nav-action">Edit</button>
  </header>
  
  <!-- Scrollable Content -->
  <main class="mobile-content">
    {% block content %}{% endblock %}
  </main>
  
  <!-- Bottom Tab Bar: 49px -->
  <nav class="mobile-tab-bar">
    <a href="#" class="tab-item active">
      <svg class="tab-icon">home</svg>
      <span class="tab-label">Home</span>
    </a>
    <!-- 3-5 tabs -->
  </nav>
</div>
```

**CSS:**
```css
@media (max-width: 767px) {
  .app-container.mobile {
    display: flex;
    flex-direction: column;
    height: 100vh;
  }
  
  .mobile-nav-bar {
    height: var(--mobile-nav-bar);
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 0 var(--mobile-margin);
    border-bottom: 1px solid var(--color-border);
    background: var(--color-canvas);
  }
  
  .mobile-content {
    flex: 1;
    overflow-y: auto;
    padding: var(--mobile-margin);
  }
  
  .mobile-tab-bar {
    height: var(--mobile-tab-bar);
    display: flex;
    background: var(--color-sidebar);
    border-top: 1px solid var(--color-border);
  }
  
  .tab-item {
    flex: 1;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: 2px;
    min-height: var(--mobile-touch-target);
  }
  
  .tab-icon {
    width: 25px;
    height: 25px;
  }
  
  .tab-label {
    font-size: 10px;
    font-weight: var(--weight-medium);
  }
}
```

---

## Phase 3: High-Density Data Tables (Week 1, Day 6-7)

### 3.1 Desktop Table (40-44px rows)
**File:** `static/css/components/table-desktop.css`

```html
<div class="hig-table-container">
  <table class="hig-table">
    <thead>
      <tr>
        <th class="align-left">Name</th>
        <th class="align-left">Purok</th>
        <th class="align-right">Fee</th>
        <th class="align-center">Status</th>
        <th class="align-right">Actions</th>
      </tr>
    </thead>
    <tbody>
      <tr>
        <td class="align-left">Juan Dela Cruz</td>
        <td class="align-left">Purok 1</td>
        <td class="align-right">₱75.00</td>
        <td class="align-center">
          <span class="badge badge-success">Active</span>
        </td>
        <td class="align-right">
          <button class="btn-icon">Edit</button>
        </td>
      </tr>
    </tbody>
  </table>
</div>
```

**CSS:**
```css
.hig-table {
  width: 100%;
  border-collapse: collapse;
  font-size: var(--text-body);
  font-family: var(--font-family-base);
}

.hig-table thead tr {
  height: var(--table-header-height);
  background: var(--color-sidebar);
  border-bottom: 1px solid var(--color-border);
}

.hig-table thead th {
  font-size: var(--text-label);
  font-weight: var(--weight-medium);
  color: var(--color-text-secondary);
  text-transform: uppercase;
  letter-spacing: var(--tracking-wide);
  padding: 0 12px;
}

.hig-table tbody tr {
  height: var(--table-row-height);
  border-bottom: 1px solid var(--color-hover);
  transition: background 0.1s ease;
}

.hig-table tbody tr:hover {
  background: var(--color-hover);
}

.hig-table tbody td {
  padding: 0 12px;
  font-size: var(--text-body);
  color: var(--color-text-primary);
}

/* Semantic Alignment */
.align-left { text-align: left; }
.align-right { text-align: right; }
.align-center { text-align: center; }

/* Status Badges */
.badge {
  display: inline-block;
  padding: 0 8px;
  height: 20px;
  line-height: 20px;
  border-radius: 4px;
  font-size: var(--text-caption);
  font-weight: var(--weight-semibold);
}

.badge-success {
  background: rgba(52, 199, 89, 0.15);
  color: var(--color-success-green);
}
```

### 3.2 Mobile List (Stacked Cards)
```css
@media (max-width: 767px) {
  .hig-table-container {
    display: none; /* Hide desktop table */
  }
  
  .mobile-list {
    display: flex;
    flex-direction: column;
    gap: 8px;
  }
  
  .mobile-list-item {
    background: var(--color-canvas);
    border: 1px solid var(--color-border);
    border-radius: var(--mobile-corner-radius);
    padding: 16px;
    min-height: var(--mobile-touch-target);
  }
}
```

---

## Phase 4: Native Controls & Buttons (Week 2, Days 1-2)

### 4.1 Desktop Buttons (32px height, 6px radius)
```css
.btn {
  height: var(--button-height);
  padding: 0 14px;
  border-radius: var(--corner-radius);
  font-size: var(--text-body);
  font-weight: var(--weight-medium);
  font-family: var(--font-family-base);
  border: none;
  cursor: pointer;
  transition: all 0.15s ease;
}

.btn-primary {
  background: var(--color-accent-blue);
  color: white;
}

.btn-primary:hover {
  background: #005BB5;
}

.btn-secondary {
  background: transparent;
  color: var(--color-text-primary);
  border: 1px solid var(--color-border);
}

.btn-destructive {
  background: var(--color-error-red);
  color: white;
}

.btn-compact {
  height: var(--button-height-compact);
  padding: 0 12px;
  font-size: 12px;
}
```

### 4.2 Mobile Buttons (44px touch targets)
```css
@media (max-width: 767px) {
  .btn {
    height: var(--mobile-touch-target);
    padding: 0 20px;
    font-size: var(--text-mobile-body);
    border-radius: var(--mobile-corner-radius);
  }
}
```

---

## Phase 5: Module-by-Module Redesign (Week 2-3)

### Priority Order:
1. **Dashboard** (Week 2, Day 3)
   - KPI cards (24px display, 10px rounded)
   - Desktop: 4-column grid
   - Mobile: Stacked cards

2. **Appointments List** (Week 2, Days 4-5)
   - Desktop: High-density table
   - Mobile: Swipeable cards
   - Filters in toolbar

3. **Blotter Module** (Week 2, Days 6-7)
   - Case list table
   - Detail view split-pane (desktop)
   - Mobile: Stack navigation

4. **Residents/Records** (Week 3, Days 1-2)
   - RBI table with filters
   - Inline editing
   - Mobile: Search + cards

5. **System Settings** (Week 3, Days 3-4)
   - Tabbed interface
   - Forms with proper spacing
   - Mobile: Grouped lists

6. **Statistics** (Week 3, Day 5)
   - Chart containers
   - Export buttons
   - Responsive grids

---

## Phase 6: Modal & Form Refinement (Week 3, Day 6)

### Desktop Modal (macOS Sheet Style)
```css
.modal-overlay {
  background: rgba(0, 0, 0, 0.4);
  backdrop-filter: blur(10px);
}

.modal-content {
  width: 640px;
  max-height: 80vh;
  background: var(--color-canvas);
  border-radius: var(--corner-radius-large);
  box-shadow: 0 24px 48px rgba(0, 0, 0, 0.25);
}

.modal-header {
  height: 52px;
  border-bottom: 1px solid var(--color-border);
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 24px;
}

.modal-body {
  padding: 24px;
  max-height: calc(80vh - 52px - 64px);
  overflow-y: auto;
}

.modal-footer {
  height: 64px;
  border-top: 1px solid var(--color-border);
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 12px;
  padding: 0 24px;
}
```

### Mobile Modal (iOS Sheet Style)
```css
@media (max-width: 767px) {
  .modal-content {
    width: 100%;
    max-height: 90vh;
    border-radius: 12px 12px 0 0;
    position: fixed;
    bottom: 0;
    left: 0;
  }
  
  .modal-grabber {
    width: 36px;
    height: 5px;
    background: var(--color-text-secondary);
    border-radius: 999px;
    margin: 8px auto;
  }
}
```

---

## Phase 7: Testing & Polish (Week 3, Day 7)

### 7.1 Responsive Breakpoints
- **Mobile:** 375px - 767px (iOS)
- **Tablet:** 768px - 1023px (iPad)
- **Desktop:** 1024px+ (macOS)

### 7.2 Dark Mode Testing
```css
@media (prefers-color-scheme: dark) {
  /* All color variables auto-swap */
  /* Test every page in both modes */
}
```

### 7.3 Accessibility
- [ ] All touch targets ≥44px (mobile)
- [ ] All interactive elements ≥32px (desktop)
- [ ] Contrast ratio ≥4.5:1
- [ ] VoiceOver labels
- [ ] Keyboard navigation
- [ ] Focus indicators

### 7.4 Visual Regression Testing
- Screenshot each module before/after
- Compare information density
- Verify alignment
- Check spacing consistency

---

## Implementation Checklist

### Week 1: Foundation
- [x] Read macOS HIG spec
- [x] Read iOS HIG spec
- [x] Create design-tokens.css
- [x] Create layout-desktop.css
- [x] Create layout-mobile.css
- [x] Disable dark mode (force light mode)
- [ ] Update base.html structure (partially done - imports added)
- [x] Build responsive grid system
- [x] Create high-density table CSS
- [ ] Test on real devices

### Week 2: Components & Modules
- [x] Build button component library
- [x] Create form control styles
- [ ] Redesign Dashboard
- [ ] Redesign Appointments
- [ ] Redesign Blotter
- [ ] Update navigation patterns
- [ ] Add gesture support (swipe back)

### Week 3: Polish & Ship
- [ ] Redesign Residents/Records
- [ ] Redesign System Settings
- [ ] Redesign Statistics
- [ ] Refine all modals
- [ ] Dark mode testing
- [ ] Mobile device testing
- [ ] Accessibility audit
- [ ] Performance check
- [ ] Update all 724 tests
- [ ] Deploy to staging

---

## Success Metrics

### Desktop (macOS HIG Compliance)
- [ ] Sidebar: 240px fixed, always visible
- [ ] Toolbar: 52px height
- [ ] Table rows: 40-44px (≥12 visible above fold)
- [ ] Buttons: 32px height, 6px radius
- [ ] Typography: SF Pro scale (22/18/13/11/10)
- [ ] Right-aligned: All currency/numbers
- [ ] Contrast: ≥4.5:1 everywhere

### Mobile (iOS HIG Compliance)
- [ ] Navigation bar: 44px
- [ ] Tab bar: 49px, 3-5 items
- [ ] Touch targets: ≥44px
- [ ] Typography: 17px body (Dynamic Type)
- [ ] Swipe gestures: Back, dismiss
- [ ] Pull to refresh: Native behavior
- [ ] Safe areas: Respected on all devices

### Both Platforms
- [ ] Dark mode: Fully functional
- [ ] Semantic colors: Auto-adapt
- [ ] VoiceOver: Complete navigation
- [ ] Performance: <100ms transitions
- [ ] Zero horizontal scroll
- [ ] Content-first: Chrome recedes

---

## Next Steps

**Ready to start?** I'll begin with Phase 1 (Design System Foundation) unless you want to:
1. Review/modify this plan first
2. Choose a different starting module
3. See mockups before coding

**Which module should I redesign first?**
- Dashboard (for quick visual impact)
- Appointments (most-used feature)
- Blotter (newest, cleanest slate)
- System Settings (admin tools)

Let me know and I'll start building! 🎨
