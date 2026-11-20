# STATUS — Budżet domowy (HA_Budget)

Stan na: 2026-11-20. Wersja: **0.1.4** (na dysku; GitHub: **do wgrania**).

Uwaga: w repo istnieje tag `0.0.1` z pełnym kodem 0.1.0 — HACS instaluje z taga,
nie z `main`. Po każdym wgraniu poprawki trzeba tworzyć **nowy tag** (Code → Tags →
New tag; nazwa = wersja z manifestu), inaczej HACS nie pobierze poprawki.

## Co jest zrobione
- Integracja HACS `custom_components/budget` (domena `budget`):
  - **SQLite** (plik `budget_<ID wpisu>.db` w katalogu konfiguracji) — wpływy, wydatki, kategorie, planowane budżety, ustawienia. Dane przetrwają restarty/aktualizacje; usunięcie wpisu **nie kasuje bazy**.
  - **Encje sensor**: Wpływy/Wydatki/Bilans (miesiąc), Pozostało z budżetu, Wpływy/Wydatki (poprzedni miesiąc — seria miesięczna do panelu Historia), per-kategoria: kwota + pozostało vs plan.
  - **Encje number**: Budżet miesięczny (plan) + Budżet: <kategoria> (edytowalne z UI).
  - **Wydatki stałe**: kategoria `recurring` + budżet > 0 → automatycznie księgowana 1. dnia miesiąca o 00:05 (idempotentnie; wyłączane w config flow).
  - **8 usług**: add/update/remove_category, add/delete_transaction, set_total_budget, set_category_budget, **get_history** (12 miesięcy + szczegóły miesiąca z transakcjami).
  - Config flow: 1 wpis na instalację, nazwa + auto-księgowanie stałych.
  - Tłumaczenia PL (strings.json + translations/pl.json), services.yaml z opisami PL.
- Testy zielone (2026-11-20): `py_compile` wszystkich modułów, walidacja JSON/YAML, **test funkcjonalny warstwy danych** (kategorie z duplikatami nazw, budżety, transakcje, podsumowania miesięczne, idempotentność wydatków stałych, walidacja błędów, usuwanie).

## Struktura plików (do wgrania na GitHub)
```
HA_Budget/
├── .gitignore
├── hacs.json
├── README.md
└── custom_components/budget/
    ├── __init__.py
    ├── button.py
    ├── config_flow.py
    ├── const.py
    ├── data.py
    ├── manifest.json
    ├── number.py
    ├── select.py
    ├── sensor.py
    ├── services.yaml
    ├── strings.json
    └── translations/pl.json
```

## Do zrobienia (kolejność)
1. **GitHub**: nowe repo `ravek71/HA_Budget` (publiczne) → wgranie plików wg struktury powyżej (Web UI, jak HA_News).
2. **HACS**: Integracje → ⋮ → Dodaj integrację custom → `https://github.com/ravek71/HA_Budget` → zainstaluj → restart HA.
3. **HA**: Ustawienia → Urządzenia i integracje → Dodaj integrację → Budżet domowy (nazwa + auto-stałe).
4. **Start**: `budget.add_category` (Wypłata/income, Czynsz/expense+recurring, kategorie z planami) → `number.*` budżety → `budget.add_transaction` → dashboard + Historia.

## Uwagi techniczne
- Kwoty zawsze > 0; kierunek (wpływ/wydatek) = typ kategorii.
- Waluta encji: `zł` (stała w `sensor.py`/`number.py`).
- WAŻNE: pliki platform muszą mieć nazwy w liczbie pojedynczej (`sensor.py`,
  `number.py`) — HA importuje je jako `budget.sensor` / `budget.number`.
- `get_history` zwraca `{months[12], month: {…by_category, transactions[]}, total_budget}` — do grafów/automatów.
- Coordinator bez interwału — odświeżany po każdej usłudze/number i przy zmianie miesiąca.
- `manifest.json`: `integration_type: entity`, `config_flow: true`, brak `requirements` (czysta stdlib).
