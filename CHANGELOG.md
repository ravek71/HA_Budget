# Changelog

## 0.1.3 (2026-11-20)

- Fix: `sensors.py` → `sensor.py` — HA ładuje platformy jako moduły
  `budget.sensor` / `budget.number`, więc plik musi mieć nazwę w liczbie
  pojedynczej (`ModuleNotFoundError: Platform budget.sensor not found`).

## 0.1.2 (2026-11-20)

- Fix: `BudgetData.__init__` — `hass.config.path()` zwraca `str`, a kod oczekiwał
  `Path` (`AttributeError: 'str' object has no attribute 'parent'`). Ścieżka
  normalizowana do `Path` w konstruktorze.

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
