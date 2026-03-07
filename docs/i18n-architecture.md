# Bilingual i18n Architecture for OperatorOne

## Overview
This document outlines the internationalization (i18n) strategy for the OperatorOne platform, ensuring seamless bilingual support for English (`en`) and Simplified Chinese (`zh`).

## Locale Structure
- **Supported Locales**: `en` (English) and `zh` (Simplified Chinese).
- **Default Locale**: `en` (for external facing product), with `zh` being primary for internal portal users.
- **File Structure**:
  ```
  packages/i18n/
  ├── locales/
  │   ├── en/
  │   │   ├── common.json
  │   │   ├── nav.json
  │   │   ├── portal.json
  │   │   └── product.json
  │   └── zh/
  │       ├── common.json
  │       ├── nav.json
  │       ├── portal.json
  │       └── product.json
  └── index.ts (T10)
  ```

## Namespace Conventions
Keys are organized into namespaces to keep translation files manageable and context-specific.
- `common`: Shared strings used across all apps (e.g., "Save", "Cancel", "Loading...").
- `nav`: Navigation labels and menu items.
- `portal`: Strings specific to the internal platform-portal app.
- `product`: Strings specific to the external product-ui app.

**Key Naming Rules**:
- Use `camelCase` or `kebab-case` for keys (consistent within files).
- Structure: `category.action` or `component.label`.
- Example: `nav.home`, `action.submit`, `status.success`.

## Language Switching Behavior
- **Route-Based Switching**: The locale is determined by the URL path prefix.
  - `/en/...` loads the application in English.
  - `/zh/...` loads the application in Chinese.
- **Redirects**: Visiting the root `/` should redirect to the user's preferred language or the default `/en/`.
- **Persistence**: Language preference can be persisted in local storage but the URL is the source of truth.

## Fallback Strategy
- **Chain**: `zh` → `en`.
- If a translation key is missing in `zh`, the system will fall back to the `en` value.
- This ensures the UI never breaks or shows empty strings, even if a translation is pending.

## Implementation Rules
1. **NO Inline Copy**: absolute prohibition on hardcoded strings in React components. All text must use the `t()` function or `<Trans>` component.
2. **Shared Package**: All locale files reside in `packages/i18n/`. Apps import from this shared package, ensuring consistency.
3. **Strict Parity**: Every key in `en` must exist in `zh` (even if the value is identical initially). CI/CD checks should enforce this.

## Sample Key Structure (Common)
```json
{
  "nav": {
    "home": "Home",
    "status": "Status",
    "settings": "Settings"
  },
  "action": {
    "save": "Save",
    "cancel": "Cancel",
    "retry": "Retry"
  },
  "status": {
    "ready": "Ready",
    "error": "Error",
    "loading": "Loading..."
  },
  "app": {
    "title": "OperatorOne"
  }
}
```
