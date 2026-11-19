<!-- claude-company:begin -->
## claude-company

This project runs **claude-company**, a hierarchical SDLC system for Claude Code.

- Main sessions act as CEO: drive the project through `/company` and `COMPANY.md`.
- Subagents obey their brief plus `company/METHOD.md` - the brief is the contract.
- Gates are the definition of done and are hook-enforced. Red stays red until proven green.
- Run gates with `company/run-gates.sh`; configure them in `company/gates.config`.
- Frozen surfaces (`company/frozen-surfaces.json`) change only via a change request in `company/change-requests/`.
- Project state lives in `company/state/` (STATUS, RESUME, WORRIES, DECISIONS).

New to this project, or adopting an existing codebase? Run `/company-init`. Then `/company`.
<!-- claude-company:end -->
