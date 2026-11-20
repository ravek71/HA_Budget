# Changelog

## 0.1.1 (2026-11-20)

- Fix: `cv.range` → `vol.Range` w schemacie usługi `get_history` — błąd importu
  `config_flow` po restarcie (`AttributeError: module 'homeassistant.helpers.config_validation'
  has no attribute 'range'`).

## 0.1.0 (2026-11-20)

- Wersja początkowa: kategorie (wpływy/wydatki), transakcje, wydatki stałe
  (auto-księgowanie 1. dnia miesiąca), planowane budżety (miesięczny + per kategoria),
  sensory (miesiąc, poprzedni miesiąc, per kategoria, pozostało), numbery budżetów,
  usługa `get_history` (12 miesięcy + szczegóły miesiąca), config flow po polsku,
  SQLite (`budget_<ID wpisu>.db`).
