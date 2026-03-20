# Architecture: UI Feedback Round 1

**Date:** 2026-03-20
**Author:** Architect Agent
**Status:** Ready for QA scaffolding & Engineering

---

## 1. Feedback Summary

This document architects fixes for the first round of user feedback after live testing. The feedback covers 5 areas: Header/Footer redesign, responsive layout, station list improvements, map improvements, and chat improvements.

---

## 2. Milestone Structure

| Milestone | Issues | Priority |
|-----------|--------|----------|
| M1: Header & Footer Redesign | #73, #74 | P0 - Critical UX |
| M2: Responsive Layout | #75 | P1 - Important |
| M3: Station List Improvements | #76, #77, #78 | P0 - Critical UX |
| M4: Map Improvements | #79, #80, #81, #82, #83, #84 | P1 - Important |
| M5: Chat Improvements | #85, #86, #87, #88 | P1 - Important |

**Actual Issue Mapping:**
| Issue | Title |
|-------|-------|
| #73 | Redesign header: left-aligned callsign + clock, right-aligned ko-fi |
| #74 | New footer with TX/RX, RF state, APRS-IS state |
| #75 | Responsive layout with terminal size breakpoints |
| #76 | Sortable station list column headers with direction toggle |
| #77 | Expand symbol display in station list |
| #78 | Add space between chat icon and callsign in station list |
| #79 | Add toggleable map legend/key for station icons |
| #80 | Station list selection highlights station on map |
| #81 | Map station selection highlights row in station list |
| #82 | Enter on map station opens station info screen |
| #83 | Show chat indicator on map for stations with chat history |
| #84 | Improve station clustering with zoom-dependent grouping radius |
| #85 | Add ability to delete a chat conversation |
| #86 | Don't create chat file until message is actually sent |
| #87 | Verify chat timestamps display correctly |
| #88 | Add mini map with distance to chat screen |

---

## 3. Detailed Architecture

### 3.1 Header Redesign (Issue #73)

**Current state:** `StatusBar(Static)` renders a single `Rich.Text` line with segments separated by `│` dividers: `Callsign │ Connection │ TX/RX │ Ko-fi`. Everything is left-aligned in a single flow.

**Target layout:**
```
┌──────────────────────────────────────────────────────────────────┐
│ W7XXX-9  12:34 CST / 18:34 UTC          ☕ ko-fi.com/philj2    │
│ [LEFT-ALIGNED]                              [RIGHT-ALIGNED]     │
└──────────────────────────────────────────────────────────────────┘
```

**Design:**

Replace `StatusBar(Static)` with `StatusBar(Widget)` using a `Horizontal` layout containing two regions:

```python
class StatusBar(Widget):
    DEFAULT_CSS = """
    StatusBar {
        dock: top;
        height: 1;
        background: #1a2233;
        layout: horizontal;
    }
    #header-left {
        width: 1fr;
        content-align: left middle;
    }
    #header-right {
        width: auto;
        content-align: right middle;
    }
    """
```

**Left region** (`Static#header-left`):
- Callsign (bold white)
- Clock: `HH:MM TZ / HH:MM UTC` updated every second via `set_interval(1, _update_clock)`

**Right region** (`Static#header-right`):
- Ko-fi link (yellow): `☕ ko-fi.com/philj2`

**Clock implementation:**
- Use `datetime.now().astimezone()` for local time with timezone abbreviation
- Use `datetime.now(timezone.utc)` for UTC
- Format: `HH:MM TZ / HH:MM UTC`
- Timer: `self.set_interval(1, self._update_clock)` on mount
- Update only the left Static, not the whole bar

**Files modified:**
- `aprs_tui/ui/status_bar.py` — Full rewrite
- `aprs_tui/ui/styles.tcss` — Update StatusBar rules

**Migration notes:**
- `update_state()`, `increment_rx()`, `increment_tx()` methods **removed** from StatusBar
- TX/RX counters move to Footer (Issue #74)
- Connection state moves to Footer (Issue #74)
- `app.py` callers updated to target new Footer widget instead

---

### 3.2 Footer Redesign (Issue #74)

**Current state:** Uses Textual's built-in `Footer()` widget which shows keybindings. Connection state and TX/RX counters are in the header.

**Target layout:**
```
┌──────────────────────────────────────────────────────────────────┐
│ TX: 15  RX: 342 │ RF: [=] Connected │ APRS-IS: [=] Connected   │
└──────────────────────────────────────────────────────────────────┘
```

**Design:**

Create new `AppFooter(Widget)` to replace Textual's `Footer()`:

```python
class AppFooter(Widget):
    DEFAULT_CSS = """
    AppFooter {
        dock: bottom;
        height: 1;
        background: #1a2233;
        layout: horizontal;
    }
    """
```

**Segments (left to right):**

1. **TX/RX counters** — `TX: {n}  RX: {n}` (white)
2. **Separator** — `│`
3. **RF Connection State** — Shows primary transport state:
   - `RF: [=] {transport_name}` (green) — Connected
   - `RF: [~] Connecting...` (yellow) — Connecting
   - `RF: [~] Reconnecting...` (yellow) — Reconnecting
   - `RF: [X] Disconnected` (red) — Disconnected
   - `RF: [X] Failed` (red) — Failed
   - `RF: [—] Not configured` (dim) — No RF transport configured
4. **Separator** — `│`
5. **APRS-IS Connection State** — Same pattern:
   - `IS: [=] Connected` (green)
   - `IS: [~] Connecting...` (yellow)
   - `IS: [X] Disconnected` (red)
   - `IS: [—] Not configured` (dim)

**State tracking:**
- `_rf_state: ConnectionState` — Primary transport state
- `_is_state: ConnectionState` — APRS-IS transport state
- `_rf_transport_name: str` — e.g., "Mobilinkd TNC4"
- `_tx_count: int`, `_rx_count: int`

**Methods (same API as old StatusBar for TX/RX):**
- `update_rf_state(state, transport_name)`
- `update_is_state(state)`
- `increment_tx()`, `increment_rx()`

**Files modified:**
- `aprs_tui/ui/footer.py` — **New file**
- `aprs_tui/ui/styles.tcss` — Add AppFooter rules
- `aprs_tui/app.py` — Replace `Footer()` with `AppFooter()` in `compose()`, update all state/counter call sites

**Dependencies:** Issue #73 (header) should be done first or simultaneously since they share state migration from StatusBar.

---

### 3.3 Clock Widget (Issue #75)

**Merged into Issue #73.** The clock is part of the header redesign. No separate implementation needed — covered by the StatusBar rewrite in #73.

---

### 3.4 Responsive Layout (Issue #76)

**Current state:** Fixed `fr`-based layout: `#stream-panel: 2fr`, `#station-panel: 1fr`, `#message-panel: height 10`. No adaptation to terminal size.

**Target:** Panels reflow based on terminal dimensions, similar to CSS media queries. Textual supports this natively with CSS media queries on terminal dimensions.

**Breakpoints:**

| Terminal Width | Layout |
|---------------|--------|
| >= 120 cols (wide) | Current 3-column: Stream(2fr) + Station(1fr), Message(10 lines) |
| 80-119 cols (medium) | 2-column: Stream/Map stacked with Station, Message(8 lines) |
| < 80 cols (narrow) | Single column: Tabbed panels, Message(6 lines) |

| Terminal Height | Adjustment |
|----------------|------------|
| >= 40 rows | Full layout |
| 24-39 rows | Message panel shrinks to 6 lines |
| < 24 rows | Message panel collapses to compose-only (2 lines) |

**Implementation using Textual CSS media queries:**

```tcss
/* Default: wide layout (>= 120 cols) */
#main-panels { layout: horizontal; }
#stream-panel { width: 2fr; }
#station-panel { width: 1fr; }
#message-panel { height: 10; }

/* Medium: 80-119 cols */
@media (width < 120) {
    #stream-panel { width: 3fr; }
    #station-panel { width: 2fr; }
    #message-panel { height: 8; }
}

/* Narrow: < 80 cols */
@media (width < 80) {
    #main-panels { layout: vertical; }
    #stream-panel { width: 1fr; height: 1fr; }
    #station-panel { width: 1fr; height: 1fr; display: none; }
    #message-panel { height: 6; }
}

/* Short terminal */
@media (height < 30) {
    #message-panel { height: 6; }
}

@media (height < 24) {
    #message-panel { height: 2; }
    #msg-inbox { display: none; }
}
```

**Additional logic in `app.py`:**
- On resize event, check if narrow mode → show tab bar for switching between Stream/Station/Map panels
- Use `on_resize()` to toggle panel visibility and add a simple tab indicator

**Files modified:**
- `aprs_tui/ui/styles.tcss` — Add media queries
- `aprs_tui/app.py` — Add resize handler, panel tab switching for narrow mode

**Risk:** Textual's CSS media query support should be verified for the exact syntax. May need `on_resize` callback approach as fallback.

---

### 3.5 Sortable Station List Headers (Issue #77)

**Current state:** `StationPanel(DataTable)` has 3 sort options (`last_heard`, `callsign`, `distance`) cycled via `cycle_sort()`. No UI indicator. No per-column click sorting. No reverse toggle.

**Target:**
- Clicking a column header sorts by that column
- Clicking the same column again reverses sort direction
- Visual indicator (▲/▼) on active sort column
- Initial sort directions:
  - Callsign → Ascending (A-Z)
  - Last Heard → Ascending (oldest first? **Note:** user said "Ascending" but this likely means most-recent-first which is actually descending by timestamp. Clarification: treat "Ascending" as the natural/intuitive order — for Last Heard, most recent first)
  - Distance → Ascending (nearest first)
  - Bearing → Ascending (0° first)
  - Pkts → Descending (most packets first)

**Design:**

Add sort state tracking per column:

```python
SORT_COLUMNS = {
    "Callsign":   {"key": "callsign",   "default_reverse": False},
    "Last Heard":  {"key": "last_heard",  "default_reverse": False},
    "Dist":        {"key": "distance",    "default_reverse": False},
    "Brg":         {"key": "bearing",     "default_reverse": False},
    "Pkts":        {"key": "packet_count","default_reverse": True},
}
```

State:
```python
self._sort_column: str = "Last Heard"
self._sort_reverse: bool = False  # False = default direction for column
```

**Header click handling:**
- Override `on_data_table_header_selected` event
- If same column clicked: toggle `_sort_reverse`
- If different column: set new column, reset to default direction
- Update column header text to include sort indicator: `"Callsign ▲"` or `"Callsign ▼"`
- Trigger `_refresh_stations()` on app

**Sorting in StationTracker:**
- Extend `get_stations()` to accept `sort_by` and `reverse` parameters
- Add `bearing` and `packet_count` sort keys:

```python
elif sort_by == "bearing":
    stations.sort(key=lambda s: s.bearing if s.bearing is not None else float("inf"))
elif sort_by == "packet_count":
    stations.sort(key=lambda s: s.packet_count, reverse=True)
```

**Files modified:**
- `aprs_tui/ui/station_panel.py` — New sort state, header click handler, indicator rendering
- `aprs_tui/core/station_tracker.py` — Add bearing + packet_count sort, add `reverse` param
- `aprs_tui/app.py` — Pass reverse param in `_refresh_stations()`

---

### 3.6 Fix Symbol Display in Station List (Issue #78)

**Current state:** `SYMBOL_MAP` in `station_panel.py` maps 8 APRS symbols to text like `[car]`, `[jog]`, etc. Symbols not in the map show as empty string `""`.

**Problem:** The "Sym" column shows blank for most stations because only 8 symbols are mapped.

**Fix:**
1. Expand `SYMBOL_MAP` to cover the full APRS primary symbol table (first ~40 most common)
2. Use `DEFAULT_SYMBOL = "[?]"` instead of `""` for unmapped symbols
3. Show the raw symbol codes (`/>`, `/-`, etc.) as fallback if no friendly name exists

**Recommended expanded map (station_panel.py):**

```python
SYMBOL_MAP = {
    "/>": "Car", "/[": "Jog", "/-": "Hse", "/k": "Trk",
    "/_": "WX",  "/#": "Dgi", "/&": "GW",  "/b": "Bik",
    "/O": "Bal", "/R": "RV",  "/Y": "Yht", "/u": "18W",
    "/p": "Rov", "/s": "Boa", "/v": "Van", "/j": "Jep",
    "/f": "FD",  "/a": "Amb", "/U": "Bus", "/X": "Hel",
    "/g": "Air", "/^": "Ant", "\\n": "EM!", "/!": "Pol",
    "/'": "Air", "/=": "Trn",
}
DEFAULT_SYMBOL = "---"
```

**Files modified:**
- `aprs_tui/ui/station_panel.py` — Expand SYMBOL_MAP, set default

---

### 3.7 Chat Icon Spacing in Station List (Issue #79)

**Current state:** Line 101: `call_display = f"💬{stn.callsign}"` — no space between emoji and callsign.

**Fix:** Change to `call_display = f"💬 {stn.callsign}"` — add a single space.

**Files modified:**
- `aprs_tui/ui/station_panel.py` — Line 101

---

### 3.8 Map Key / Legend (Issue #80)

**Current state:** Station symbols on the map are single characters (`>`, `H`, `#`, `&`, `W`, etc.) defined in `station_overlay.py:SYMBOL_MAP`. No legend is displayed.

**Target:** Add a toggleable map legend showing what each symbol means.

**Design:**

Add a legend overlay rendered at the bottom-right of the map panel when toggled on:

```
┌─ Legend ──────┐
│ > Car/Mobile  │
│ H House/QTH   │
│ # Digipeater  │
│ & Gateway     │
│ W Weather     │
│ P Pedestrian  │
│ * Other       │
│ (3) Cluster   │
└───────────────┘
```

**Implementation:**
- New toggle key: `?` (question mark) on MapPanel
- Render legend as Rich Text overlay in the last N lines of the map output
- Legend content sourced from `station_overlay.SYMBOL_MAP`
- Draw over the bottom-right corner of the canvas output
- Add `?:Key` to the key hints line

**Files modified:**
- `aprs_tui/map/panel.py` — Add `_show_legend` toggle, `?` key binding, legend rendering
- `aprs_tui/map/station_overlay.py` — Export `LEGEND_ENTRIES` list for the legend

---

### 3.9 Bidirectional Selection: Station List ↔ Map (Issues #81, #82)

**Current state:**
- `StationPanel` posts `StationSelected` message when cursor moves
- `MapPanel` has `selected_callsign` property used during rendering
- `app.py` handles `StationPanel.StationSelected` and calls `stream_panel.highlight(callsign)`
- Map selection (`n`/`N` keys) cycles stations but does NOT notify the station list

**Target:**
- Selecting a station in the list highlights it on the map
- Selecting a station on the map highlights it in the station list
- Both directions work seamlessly

**Design:**

**List → Map (Issue #81):**
Already partially working. In `app.py`, when handling `StationPanel.StationSelected`:
```python
def on_station_panel_station_selected(self, event):
    self.query_one(StreamPanel).highlight(event.callsign)
    # ADD: Update map selection
    map_panel = self.query_one(MapPanel)
    map_panel.select_station(event.callsign)
```

**Map → List (Issue #82):**
Add a new message to MapPanel:
```python
class MapPanel(Widget):
    class StationSelected(Message):
        def __init__(self, callsign: str) -> None:
            super().__init__()
            self.callsign = callsign
```

When `n`/`N` cycles to a new station, post `self.post_message(self.StationSelected(callsign))`.

In `app.py`:
```python
def on_map_panel_station_selected(self, event):
    station_panel = self.query_one(StationPanel)
    station_panel.select_callsign(event.callsign)  # New method
    self.query_one(StreamPanel).highlight(event.callsign)
```

Add `StationPanel.select_callsign(callsign)` method:
```python
def select_callsign(self, callsign: str) -> None:
    """Programmatically select a station row."""
    if callsign in self._callsigns:
        self._user_selected = True
        self.show_cursor = True
        row_idx = self._callsigns.index(callsign)
        self.move_cursor(row=row_idx)
        self.selected_callsign = callsign
```

**Files modified:**
- `aprs_tui/map/panel.py` — Add `StationSelected` message, post on `n`/`N` cycle, add `select_station()` method
- `aprs_tui/ui/station_panel.py` — Add `select_callsign()` method
- `aprs_tui/app.py` — Add `on_map_panel_station_selected` handler, update `on_station_panel_station_selected`

---

### 3.10 Enter on Map Station → Info Screen (Issue #83)

**Current state:** `MapPanel` has `n`/`N` to cycle stations. No Enter action on the selected station.

**Target:** Pressing Enter on a selected station on the map brings up a station info screen.

**Design:**

Add `Enter` key binding to `MapPanel`:
```python
Binding("enter", "activate_station", "Station Info", show=False)
```

Action handler:
```python
def action_activate_station(self) -> None:
    if self._selected_callsign:
        self.post_message(self.StationActivated(self._selected_callsign))
```

Add `StationActivated` message to `MapPanel` (mirrors `StationPanel.StationActivated`).

In `app.py`, handle both `StationPanel.StationActivated` and `MapPanel.StationActivated` with the same handler → open station info screen (or chat screen, depending on existing behavior).

**Station Info Screen** — Create `ui/station_info_screen.py`:

```
┌─ Station: W7XXX-9 ──────────────────────────────┐
│                                                   │
│  Callsign:    W7XXX-9                            │
│  Symbol:      Car (/>)                           │
│  Position:    45.4234°N 122.6819°W               │
│  Comment:     "Field portable station"           │
│  Last Heard:  30s ago                            │
│  Distance:    5.2 km                             │
│  Bearing:     120°                               │
│  Packets:     42                                 │
│  Sources:     RF (Mobilinkd TNC4), APRS-IS       │
│  Info Type:   position                           │
│                                                   │
│  [dim]Enter[/dim] Chat  [dim]Esc[/dim] Close     │
└──────────────────────────────────────────────────┘
```

- `ModalScreen` with station details from `StationRecord`
- Enter from info screen opens chat with that station
- Escape closes

**Files modified:**
- `aprs_tui/ui/station_info_screen.py` — **New file**
- `aprs_tui/map/panel.py` — Add Enter binding, `StationActivated` message
- `aprs_tui/app.py` — Handle `MapPanel.StationActivated`, push station info screen

---

### 3.11 Chat Icon on Map (Issue #84)

**Current state:** Chat indicator `💬` shown in station list only. Map shows station symbol character only.

**Target:** If a station has chat history, show a chat indicator next to the station symbol on the map.

**Design:**

Pass `chat_callsigns: set[str]` to `StationOverlay.render_stations()`:

```python
def render_stations(self, stations, own_callsign, selected_callsign=None, chat_callsigns=None):
```

After drawing the station symbol, if the callsign is in `chat_callsigns`, append a `*` (or `C`) character adjacent to the symbol:

```python
if chat_callsigns and station.callsign.upper() in chat_callsigns:
    # Draw chat indicator one cell to the right of the symbol
    canvas.draw_text(dot_x + 2, dot_y, "C")  # "C" for chat
```

The `C` uses a distinct style (e.g., cyan) to differentiate from station labels.

**Flow:**
- `MapPanel.render()` passes `chat_callsigns` from app state
- `MapPanel` needs a `set_chat_callsigns(callsigns)` method called by the app

**Files modified:**
- `aprs_tui/map/station_overlay.py` — Accept and render chat indicator
- `aprs_tui/map/panel.py` — Pass chat_callsigns through render pipeline
- `aprs_tui/app.py` — Pass chat callsigns to map panel on refresh

---

### 3.12 Station Clustering Improvements (Issue #85)

**Current state:** `CLUSTER_THRESHOLD = 3` in station_overlay.py. Stations in the same character cell are clustered as `(N)`. No multi-level clustering.

**Target:** Group stations at different zoom levels to make the map easier to read at low zoom.

**Design:**

Implement zoom-dependent clustering with a larger grouping radius at lower zoom levels:

```python
def _cluster_radius(zoom: float) -> int:
    """Return cluster radius in character cells based on zoom level."""
    if zoom >= 14:
        return 1    # Tight: only same-cell
    elif zoom >= 11:
        return 2    # Medium: 2-cell radius
    elif zoom >= 8:
        return 3    # Wide: 3-cell radius
    else:
        return 5    # Very wide: 5-cell radius
```

**Algorithm:**
1. Convert all station positions to character-cell coordinates
2. Based on zoom level, determine cluster radius
3. Use grid-based spatial hashing: divide canvas into grid cells of `radius` size
4. Cells with >= threshold stations become clusters
5. Render cluster with count and most-recently-heard callsign: `(5) W7XXX`

**Priority rendering:** Own station and selected station are NEVER clustered — always rendered individually.

**Files modified:**
- `aprs_tui/map/station_overlay.py` — New clustering algorithm with zoom-dependent radius

---

### 3.13 Delete Chat (Issue #86)

**Current state:** `chat_store.delete_chat()` exists but is not exposed in the UI.

**Target:** User can delete a chat conversation.

**Design:**

Option A (chosen): Add `d` key binding in `ChatScreen` with confirmation:
```python
Binding("ctrl+d", "delete_chat", "Delete Chat", show=True)
```

Action:
```python
def action_delete_chat(self) -> None:
    # Post message to app to handle deletion
    self.post_message(self.DeleteChat(self.peer_callsign))
    self.dismiss(None)
```

In `app.py`:
```python
def on_chat_screen_delete_chat(self, event):
    from aprs_tui.core.chat_store import delete_chat
    delete_chat(event.callsign)
    self.notify(f"Chat with {event.callsign} deleted")
    self._refresh_stations()  # Update chat indicators
```

Also add to the footer hints in ChatScreen: `[dim]Ctrl+D[/dim] Delete`

**Files modified:**
- `aprs_tui/ui/chat_screen.py` — Add delete binding, `DeleteChat` message
- `aprs_tui/app.py` — Handle `DeleteChat` message

---

### 3.14 Lazy Chat Creation (Issue #87)

**Current state:** Need to verify — chat may be saved to disk when screen opens. The `ChatScreen` loads history in `on_mount()` and saves on dismiss. If there are no messages, an empty file might be created.

**Target:** Don't create/save a chat file until an actual message is sent or received.

**Design:**

In `app.py`, when dismissing `ChatScreen`, only call `save_chat()` if the conversation has messages:

```python
# In the chat dismiss callback
if chat_screen.messages:
    save_chat(peer_callsign, [m.to_dict() for m in chat_screen.messages])
```

Also ensure that `ChatScreen` does NOT call `save_chat` on its own — only the app does it in the dismiss handler.

If `load_chat()` returns empty, do NOT add the callsign to `chat_callsigns`.

**Files modified:**
- `aprs_tui/app.py` — Guard `save_chat()` call with message check
- `aprs_tui/core/chat_store.py` — Ensure `list_chat_callsigns()` skips empty arrays (already checks `st_size > 2`)

---

### 3.15 Chat Timestamps (Issue #88)

**Current state:** Already implemented! `ChatScreen._render_message()` at line 144:
```python
ts = time.strftime("%H:%M", time.localtime(msg.timestamp))
line.append(f"{ts} ", style="dim #484f58")
```

**Status:** Already working. Verify in QA that timestamps display correctly.

---

### 3.16 Mini Map in Chat Screen (Issue #89)

**Target:** In the chat screen, show a small map auto-zoomed to show both stations with distance.

**Design:**

Add a mini map panel to `ChatScreen` layout:

```
┌─ Chat: W7XXX ↔ N7YYY ───────── 5.2 km ─────────┐
│ ┌─────────────────────────┐                       │
│ │       Mini Map          │  14:23 W7XXX → msg   │
│ │   Own:  ★               │  14:24 N7YYY → msg   │
│ │   Peer: ●               │  14:25 W7XXX → msg   │
│ │   5.2 km apart          │                       │
│ └─────────────────────────┘                       │
├───────────────────────────────────────────────────┤
│ Message to N7YYY... (Enter)                       │
├───────────────────────────────────────────────────┤
│ Enter Send  Esc Close  Ctrl+D Delete              │
└───────────────────────────────────────────────────┘
```

**Implementation:**

1. Create `MiniMapWidget(Static)` — simplified map renderer
   - Takes two lat/lon pairs (own + peer)
   - Auto-calculates zoom to fit both with padding
   - Renders using `BrailleCanvas` (reuse existing infrastructure)
   - Shows two markers (own = `★`, peer = `●`)
   - Shows distance text centered below
   - Fixed size: 25 chars wide, 8 rows tall

2. In `ChatScreen.compose()`:
   ```python
   with Horizontal(id="chat-body"):
       yield MiniMapWidget(own_lat, own_lon, peer_lat, peer_lon, id="chat-minimap")
       yield RichLog(id="chat-log", wrap=True, markup=False)
   ```

3. If peer has no position, hide the mini map (display: none)

4. Distance displayed in title bar: `Chat: W7XXX ↔ N7YYY — 5.2 km`

**Zoom calculation:**
```python
def _fit_zoom(lat1, lon1, lat2, lon2, canvas_w, canvas_h):
    """Calculate zoom level that fits both points with 20% padding."""
    # Use the haversine distance and map to appropriate zoom
    ...
```

**Files modified:**
- `aprs_tui/ui/mini_map.py` — **New file**: MiniMapWidget
- `aprs_tui/ui/chat_screen.py` — Integrate MiniMapWidget, pass coordinates, show distance in title

---

## 4. Dependency Graph

```
#73 Header Redesign ──┐
                       ├──→ #74 Footer Redesign (shares state migration)
#75 Clock (merged → #73)

#77 Sortable Headers ──→ standalone
#78 Symbol Display   ──→ standalone
#79 Chat Icon Spacing ──→ standalone (trivial)

#81 List→Map Selection ──┐
                          ├──→ #83 Enter→Info Screen
#82 Map→List Selection ──┘

#80 Map Legend ──→ standalone
#84 Chat Icon on Map ──→ standalone (depends on chat_callsigns plumbing)
#85 Station Clustering ──→ standalone

#86 Delete Chat ──→ standalone
#87 Lazy Chat Creation ──→ standalone
#88 Chat Timestamps ──→ already done (verify only)
#89 Mini Map in Chat ──→ depends on #81/#82 (needs station position lookup)
```

## 5. Risk Register

| Risk | Impact | Mitigation |
|------|--------|------------|
| Textual CSS media queries may not support all breakpoints | Responsive layout (#76) may need Python-based resize handling | Verify Textual docs; fallback to `on_resize()` callback |
| Braille canvas mini map rendering at small sizes may be unreadable | Chat mini map (#89) may be too small to be useful | Test at 25x8 chars; fall back to text-only distance display if unreadable |
| DataTable header click events may require Textual version >= 0.47 | Sortable headers (#77) | Verify Textual version; may need `on_header_selected` or custom header row |
| Clock timer (1s interval) could impact performance | Header clock (#73) | Only update the clock Static, not full layout reflow |
| Bidirectional selection could cause infinite loop | List↔Map selection (#81, #82) | Add guard: `if self.selected_callsign == callsign: return` |

---

## 6. Issue List for GitHub

| # | Title | Milestone | Labels | Depends On |
|---|-------|-----------|--------|------------|
| 73 | Redesign header: left-aligned callsign + clock, right-aligned ko-fi | M1 | `type:enhancement`, `area:ui` | — |
| 74 | New footer with TX/RX, RF state, APRS-IS state | M1 | `type:enhancement`, `area:ui` | #73 |
| 76 | Responsive layout with terminal size breakpoints | M2 | `type:enhancement`, `area:ui` | — |
| 77 | Sortable station list column headers with direction toggle | M3 | `type:enhancement`, `area:ui` | — |
| 78 | Expand symbol display in station list | M3 | `type:bug`, `area:ui` | — |
| 79 | Add space between chat icon and callsign in station list | M3 | `type:bug`, `area:ui` | — |
| 80 | Add toggleable map legend/key for station icons | M4 | `type:enhancement`, `area:map` | — |
| 81 | Station list selection highlights station on map | M4 | `type:enhancement`, `area:map` | — |
| 82 | Map station selection highlights row in station list | M4 | `type:enhancement`, `area:map` | — |
| 83 | Enter on map station opens station info screen | M4 | `type:enhancement`, `area:map`, `area:ui` | #81, #82 |
| 84 | Show chat indicator on map for stations with chat history | M4 | `type:enhancement`, `area:map` | — |
| 85 | Improve station clustering with zoom-dependent grouping radius | M4 | `type:enhancement`, `area:map` | — |
| 86 | Add ability to delete a chat | M5 | `type:enhancement`, `area:chat` | — |
| 87 | Don't create chat file until message is sent | M5 | `type:bug`, `area:chat` | — |
| 88 | Verify chat timestamps display correctly | M5 | `type:test`, `area:chat` | — |
| 89 | Add mini map with distance to chat screen | M5 | `type:enhancement`, `area:chat`, `area:map` | — |

---

## Agent Handoff: Architect

**Status:** Complete
**Outputs produced:**
- `docs/ARCHITECTURE-FEEDBACK-R1.md` (this document)

**Next agent:** QA
**Next agent inputs:**
- This architecture document
- Each GitHub Issue once created
- Test requirements to scaffold per issue

**Then:** Engineer
**Engineer inputs:**
- Architecture doc + QA test scaffolding + GitHub Issues

**Blockers or flags:**
- Verify Textual CSS media query support before starting #76
- Verify DataTable header click events before starting #77
- Issue #88 (chat timestamps) may already be complete — QA to verify
