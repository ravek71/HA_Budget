# Budżet domowy — integracja Home Assistant (HACS)

Integracja do **planowania i śledzenia domowego budżetu**: wpływy, wydatki,
**wydatki stałe** (automatyczne na początku miesiąca), **kategorie z
planowanymi budżetami**, **wykresy miesiąca** i **pełna historia**
(dane zapisywane lokalnie w SQLite, przetrwają restarty i aktualizacje).

Bez zewnętrznych wymagań — tylko standardowa biblioteka Pythona (`sqlite3`).

## Co daje

| Encja | Opis |
|---|---|
| `sensor.* Wpływy (miesiąc)` | suma wpływów bieżącego miesiąca |
| `sensor.* Wydatki (miesiąc)` | suma wydatków bieżącego miesiąca (atrybuty: rozbicie na kategorie, budżet, pozostało) |
| `sensor.* Bilans (miesiąc)` | wpływy − wydatki |
| `sensor.* Pozostało z budżetu` | planowany budżet miesięczny − wydatki (ujemne = przekroczenie) |
| `sensor.* Wpływy/Wydatki (poprzedni miesiąc)` | zamknięty poprzedni miesiąc — dzięki temu panel **Historia** pokazuje serię miesięczną (wykres) |
| `sensor.* Wydatki/Wpływy: <kategoria>` | kwota kategorii w bieżącym miesiącu |
| `sensor.* Pozostało: <kategoria>` | budżet kategorii − wydane (brak planu = nieznany) |
| `number.* Budżet miesięczny (plan)` | **planowany budżet na miesiąc** (edytowalny) |
| `number.* Budżet: <kategoria>` | **planowany budżet kategorii** (edytowalny) |
| `number.* Kwota do dodania` | **formularz karty**: tymczasowa kwota (nie księgowana, czyści się po dodaniu/restarcie) |
| `select.* Kategoria do dodania` | **formularz karty**: cel transakcji (wpływy i wydatki) |
| `button.* Dodaj transakcję` | **formularz karty**: księguje kwotę + kategorię jednym tapnięciem |

Dodatkowo usługa `budget.get_history` zwraca ostatnie **12 miesięcy**
(wpływy/wydatki/bilans/budżet) + szczegóły miesiąca z listą transakcji —
do wykresów w szablonach (np. grafy) i automatów.

## Instalacja (HACS)

1. HACS → *Integracje* → ⋮ → *Dodaj integrację custom* → URL:
   `https://github.com/ravek71/HA_Budget`
2. Zainstaluj **Budżet domowy**, zrestartuj HA.
3. *Ustawienia → Urządzenia i integracje → Dodaj integrację → Budżet domowy*:
   - nazwa budżetu,
   - „Automatycznie księguj wydatki stałe na początku miesiąca” (domyślnie: tak).

Bez HACS: skopiuj folder `custom_components/budget` do katalogu
konfiguracji HA i zrestartuj.

## Użytkowanie

### 1. Kategorie (usługi, panel *Otwórz usługę*)

Wpływy (np. wypłata):

```yaml
service: budget.add_category
data:
  name: Wypłata
  kind: income
```

Wydatki stałe (np. czynsz 2000 zł, automatycznie co 1. dnia miesiąca):

```yaml
service: budget.add_category
data:
  name: Czynsz
  kind: expense
  recurring: true
  monthly_budget: 2000
```

Kategoria z planem (np. jedzenie, maks. 1500 zł/mies.):

```yaml
service: budget.add_category
data:
  name: Jedzenie
  kind: expense
  monthly_budget: 1500
```

Pozostałe usługi: `update_category`, `remove_category`, `add_transaction`,
`delete_transaction`, `set_total_budget`, `set_category_budget`,
`get_history` — opisy w `custom_components/budget/services.yaml`.

### 2. Planowanie

- **Budżet na miesiąc**: encja `number.* Budżet miesięczny (plan)`
  (lub `budget.set_total_budget`).
- **Budżety kategorii**: `number.* Budżet: <kategoria>`
  (lub `budget.set_category_budget`).
- Wydatek stały = kategoria z `recurring: true` i budżetem > 0 —
  kwota budżetu jest automatycznie księgowana **1. dnia miesiąca**
  (idempotentnie; można wyłączyć w konfiguracji integracji).

### 3. Księgowanie

```yaml
service: budget.add_transaction
data:
  category: jedzenie
  amount: 86.5
  note: Biedronka
# date: 2026-11-20   # opcjonalnie (domyślnie: dzisiaj)
```

### 4. Karta dodawania transakcji (bez helperów, bez YAML)

Integracja dostarcza własny „formularz” jako encje — **nie trzeba
tworzyć żadnych helperów** (`input_number`/`input_text` są w HA
helperami YAML-owymi i nie mają API do tworzenia z integracji):

1. Dashboard → „+ Dodaj kartę” → **Encje** (karta typu `entities` —
   działa też na starych pulpitach).
2. Dodaj do niej 3 encje urządzenia „Budżet domowy”:
   - **Kwota do dodania** (`number`) — wpisz kwotę,
   - **Kategoria do dodania** (`select`) — wybierz kategorię
     (wpływy i wydatki),
   - **Dodaj transakcję** (`button`) — tapnięcie księguje transakcję
     i czyści formularz.

Wpływy miesięczne: ustaw kwotę, wybierz np. „Wypłata”, tapnij
„Dodaj transakcję”. Kwota w formularzu trzymana jest w pamięci
integracji (po restarcie HA wraca do 0). Notatkę transakcji można
podać tylko przez usługę `add_transaction` (karta zapisuje
notatkę „Dodane z karty”).

### 5. Wykresy i historia

- Panel **Historia** w HA: czujniki `Wpływy (poprzedni miesiąc)` /
  `Wydatki (poprzedni miesiąc)` dają gotową miesięczną serię.
- Wykres bieżącego miesiąca z rozbiciem na kategorie — z atrybutów
  `Wydatki (miesiąc)` (`rozbicie`) albo z `budget.get_history`:

```yaml
service: budget.get_history
data: {}
# result.months: ostatnie 12 miesięcy {year, month, income, expenses, balance, budget}
# result.month:  szczegóły miesiąca {income, expenses, balance, by_category, transactions[]}
```

## Gdzie są dane

`/config/budget_<ID wpisu>.db` (SQLite). Usuwanie wpisu konfiguracji
**nie kasuje bazy** — historia zostaje. Ręczny backup = kopia pliku.

## Uwagi

- Kwoty zawsze dodatnie; kierunek (wpływ/wydatek) wynika z typu kategorii.
- Waluta w encjach: `zł` (stała w kodzie, łatwo zmienić).
- Jeden wpis integracji na instalację (jeden budżet gospodarstwa).
