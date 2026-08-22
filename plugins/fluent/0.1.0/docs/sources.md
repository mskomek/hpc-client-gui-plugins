# Rule sources

Rules in this plugin are based on the following official documentation.
We store only concise rule metadata and links — no copied command manuals.

- Fluent journaling / TUI legacy journal information (PyFluent docs):
  https://fluent.docs.pyansys.com/version/dev/user_guide/legacy/tui.html
- Journal conversion workflows, including TUI-to-Python (`-topy`) for
  Fluent 2024 R2+:
  https://fluent.docs.pyansys.com/version/dev/user_guide/convert_journal.html
- ANSYS Fluent migration/material guidance (versioned official help portal;
  access may require an account):
  https://ansyshelp.ansys.com/public/Views/Secured/corp/v252/en/flu_mig/flu_mig_chp_intro.html
  https://ansyshelp.ansys.com/public/Views/Secured/corp/v261/en/flu_ug/flu_ug_JournalFile.html

Verified facts encoded by current rules:

- Recorded journals include `/file/set-tui-version "XX.X"`; for
  Fluent 2025 R2 the version string is `25.2`.
- Unanswered confirmation prompts can prevent journal continuation
  (documented; curated rules deferred until verified per-command).
