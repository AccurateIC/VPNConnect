# DECISIONS - maintained by the company. Durable choices and their rationale.

## 2026-11-19 - easy-gui (CEO, owner can veto)
- Stayed on Tkinter (no new dependencies). Spec `company/specs/spec-easy-gui.md`, design `company/design/DESIGN-LANGUAGE.md` (proposed).
- Built from the CEO's spec while the designer was still working (the owner said not to wait). Copy follows the designer's main rules: "VPN file", never "profile"; errors in the window, not pop-ups; no Enter on Connected. Palette/fonts are close to the designer's but not identical (primary `#0969da` vs proposed `#0B5CAD`, both pass 4.5:1).
- Spec ACs were reconciled with the build where the build is clearer (quick-pick becomes primary; banner wording). The auditor's literal-AC list (finding 6) is accepted as reconciled, not as defects.
- Closing the window while connected **or still connecting** disconnects (OQ-GUI-01 kept; extended so a half-started connection is not left running).
- Taken from the designer's proposals: rescan Downloads on focus, inline validation, a "connection dropped" note, and the no-OTP auth copy. Deferred: a Cancel button while connecting, and a contrast unit test.
- The tests gate now runs `python3 -m unittest discover -s tests`. `tests/test_gui.py` needs a display and skips without one.
