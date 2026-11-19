# VPNConnect design language

_Status: proposed 2026-11-19 with spec-easy-gui (new language; the old UI had none).
Owner of changes: CEO. Builders: read this once, then the spec's `### UX notes`._

VPNConnect is a small Tkinter + ttk window used by non-technical employees. One
window, one job per screen, one primary button per screen. Tk 8.6 only, no new
dependencies, no image files.

## 1. Theme

- `ttk.Style().theme_use("clam")`. Every colour below is set explicitly, so the app
  looks the same under light and dark GNOME themes. Do not read system colours.
- Also set `root.configure(bg=BG)` and `root.option_add("*Menu.background", ...)`
  so classic Tk widgets (Menu, Text, Canvas, tk.Frame) match.

## 2. Colour tokens (fixed palette)

| Token | Hex | Use | Contrast (checked) |
|---|---|---|---|
| `BG` | `#FFFFFF` | window, cards, entries | - |
| `BG_SUBTLE` | `#F6F8FA` | Details log, disabled entry field | - |
| `TEXT` | `#1F2328` | all body text, labels, entry text | 15.8:1 on BG |
| `TEXT_MUTED` | `#57606A` | hints, secondary lines, version | 6.4:1 on BG, 6.0:1 on BG_SUBTLE |
| `BORDER` | `#8C959F` | entry and secondary button borders | 3.0:1 on BG (non-text) |
| `PRIMARY` | `#0B5CAD` | primary button fill, link text, focus ring | white on it 6.7:1; it on BG 6.7:1 |
| `PRIMARY_ACTIVE` | `#094A8C` | primary button hover | white on it 8.9:1 |
| `PRIMARY_PRESSED` | `#073B70` | primary button pressed | > 10:1 |
| `DISABLED_BG` | `#EAEEF2` | disabled button fill | TEXT_MUTED on it 5.5:1 |
| `STATUS_GREY` | `#57606A` | banner: Checking..., Not connected | white on it 6.4:1 |
| `STATUS_AMBER` | `#9A6700` | banner: Connecting..., Setting up..., Disconnecting... | white on it 4.9:1 |
| `STATUS_GREEN` | `#1A7F37` | banner: Connected | white on it 5.1:1 |
| `STATUS_RED` | `#CF222E` | banner: Problem | white on it 5.4:1 |
| `ON_STATUS` | `#FFFFFF` | text and dot on any banner | see rows above |
| `ERROR_BG` | `#FFEBE9` | error message box fill | TEXT 13.8:1, ERROR_TEXT 6.9:1 |
| `ERROR_TEXT` | `#A40E26` | error headline, inline field errors | 7.9:1 on BG |
| `WARN_TEXT` | `#6B4A00` | Caps Lock warning | 7.6:1 on #FFF8E1, higher on BG |
| `NOTE_BG` | `#DDF4FF` | info note box (e.g. "VPN file added.") | TEXT > 13:1 |

Rule: colour never carries meaning alone. Every banner has a word ("Connected"),
every error has a headline.

## 3. Type

All fonts derive from `TkDefaultFont` (GNOME usually gives Cantarell/Noto Sans 10-11pt).
Create named fonts once with `tkinter.font.nametofont("TkDefaultFont").copy()`
and set the size relative to `base = actual size`.

| Token | Size | Weight | Use |
|---|---|---|---|
| `FONT_BODY` | base | normal | labels, entries, buttons, hints |
| `FONT_BODY_BOLD` | base | bold | error headline, "Ask IT to run install.sh." |
| `FONT_TITLE` | base + 5 | bold | screen title ("Set up the VPN", "Sign in") |
| `FONT_HEADER` | base + 1 | bold | connection name in the header row |
| `FONT_BANNER` | base + 2 | bold | banner state word |
| `FONT_BANNER_BIG` | base + 8 | bold | banner state word on the Connected screen |
| `FONT_MONO` | `TkFixedFont`, base - 1 | normal | Details log only |

Never go below `base` for anything a user must read (Details log is for IT).

## 4. Spacing, size, radius

- Spacing scale (px): 4, 8, 12, 16, 24. Window content padding: 24. Gap between
  label and its field: 4. Gap between field groups: 12. Gap before the primary
  button: 16. Gap after banner: 16.
- HiDPI: multiply every px value by `k = max(1.0, root.winfo_fpixels("1i") / 96)`.
- Window: width 440, height fits content. `minsize(380, <requested height>)`.
  Resizable. Content stays top-anchored; extra height is empty space below.
- Wrapping labels: `wraplength = content width`, updated on `<Configure>`.
- Radius: none. clam draws square corners; do not fake rounded corners.
- Minimum button height: 32 px (padding 12 x 8). Meets WCAG 2.2 target size (24 px).

## 5. Components (use these, invent no others)

| Component | Build | When |
|---|---|---|
| **Header row** | ttk.Frame: connection name (`FONT_HEADER`) left, More menubutton right | top of every main-window screen |
| **Status banner** | tk.Frame bg = status token, padding 12 x 10; Canvas 12x12 dot (filled `ON_STATUS`, no outline) then state word (`FONT_BANNER`, `ON_STATUS`); optional second line (`FONT_BODY`, `ON_STATUS`) | every screen, directly under the header, full width |
| **Primary button** | `Primary.TButton`: bg PRIMARY, fg white, borderwidth 0, padding (12, 8), map active/pressed/disabled. Full content width. | exactly one per screen |
| **Secondary button** | `TButton`: bg BG, fg TEXT, bordercolor BORDER, padding (12, 8), active bg BG_SUBTLE. Full content width. | alternatives on the same screen (quick-pick file, portal) |
| **Link button** | `Link.TButton`: bg BG, fg PRIMARY, borderwidth 0, padding (0, 4), anchor w | "Show details" / "Hide details" |
| **Text field** | label above (`FONT_BODY`, TEXT), ttk.Entry below, full width. Border BORDER, focus border PRIMARY. Disabled: fieldbackground BG_SUBTLE, fg TEXT_MUTED | Sign in |
| **Checkbox** | ttk.Checkbutton | "Show password" only |
| **Field message** | ttk.Label `FONT_BODY` under a field: ERROR_TEXT for errors, WARN_TEXT for Caps Lock | inline validation, Caps Lock |
| **Message box** | tk.Frame bg ERROR_BG (error) or NOTE_BG (info), 1px border in STATUS_RED / PRIMARY, padding 12; headline `FONT_BODY_BOLD`, next-step line `FONT_BODY` TEXT | one per screen at most, right under the banner |
| **More menu** | ttk.Menubutton text "More", direction below, with tk.Menu (tearoff=0) | header row, every main-window screen |
| **Details panel** | Link button + collapsible frame: read-only tk.Text (`FONT_MONO`, BG_SUBTLE, 8 lines, wrap word, ttk.Scrollbar) + secondary "Copy for IT" button | bottom of every main-window screen |
| **Confirm dialog** | `tkinter.messagebox.askokcancel(..., default="cancel", icon="warning")` | destructive actions only (Remove VPN file) |

No messagebox for errors or validation: errors go in the Message box, validation
in Field messages.

## 6. Focus and keyboard

- Focus is always visible. Entries: bordercolor, lightcolor and darkcolor map
  `focus -> PRIMARY`. Buttons: `focusthickness 2`; `focuscolor` white on
  Primary.TButton, PRIMARY on TButton, Link.TButton and TCheckbutton.
- Tab order is top-to-bottom, left-to-right (the natural pack/grid order).
- Return activates the screen's primary action only where the UX notes say so
  (bind on the window, not just on one entry). Space activates the focused button
  (ttk default).
- Escape never closes the main window. It closes an open menu (Tk default) and
  collapses the Details panel if it is open.
- Any state change that moves to a new screen sets focus as the UX notes specify.

## 7. Voice

- Second person, plain words, reading age about 10. Short sentences.
- Say "VPN file", not "profile" or "config". Mention ".ovpn" once, as a hint.
- Say "Sign in", "Connect", "Disconnect". Never "log in", "authenticate", "tunnel".
- Never show nmcli, OpenVPN, D-Bus or exit-code text outside the Details panel.
- Every error = one headline + one sentence that says what to do next.
- Button labels are verbs. A label ends in "..." when it opens a picker or dialog.
- Use three dots "...", never the single ellipsis character. No em-dashes.

## 8. Accessibility floor

WCAG 2.2 AA where Tk allows it: text contrast >= 4.5:1, non-text >= 3:1, visible
focus, full keyboard operation, meaning never by colour alone, target >= 24 px.
Known limit: Tk on Linux does not expose widgets to screen readers (no AT-SPI).
This is a platform limit, not a defect of a screen; the CLI remains the
screen-reader path.
