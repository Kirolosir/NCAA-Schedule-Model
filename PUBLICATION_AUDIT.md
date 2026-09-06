# Publication review

Reviewed September 5, 2026.

## Repository status

The source commit `b875bbf` was rewritten as `caf6e0a` to remove retired setup
files and their dependency entries. Its author, dates, parents, and message were
preserved. The two earlier commits are unchanged. A subsequent local commit
records the finished app and shortened code comments.

The remote has not been updated. Its cached `origin/main` still points to the
old history. Publishing this branch requires a separately approved force-push
with an explicit lease; a normal pull would bring the old history back.

A verified history bundle and working-file archive are stored outside the
repository at `/private/tmp/npi-history-backup.cVtRUo/`. Original objects,
reflogs, and editor recovery metadata remain locally for recovery and are not
included in a normal push of `main`. No repository-wide pruning was performed.

## Data and credentials

The ignore rules exclude Excel exports, virtual environments, Python caches,
environment files, private keys, credential/secret JSON filenames, `local_data/`,
`planning_inputs/`, `reports/`, installed frontend dependencies, build output,
and TypeScript caches. No tracked file matches the current ignore rules.

The two tracked JSON fixtures contain public team names, ratings, records, game
dates/results, source URLs, and provenance hashes. They contain no coach
correspondence, private plans, player-level personal data, or credentials.
Redistribution rights and a public code license still need review.

A token-pattern scan of the prospective source files and the three reachable
commit snapshots found no recognizable access tokens, private-key blocks, or
credential-bearing URLs. No prospective source file is a symlink. These checks
cannot detect every possible secret.

The local server binds to loopback and serves only `web/dist/client`. Plans and
jobs stay in memory. Logs and reports are ignored. Exported comparison JSON can
contain private plans; keep it outside the repository or in `planning_inputs/`.
Removed setup files have backups under ignored `local_data/editor-backup/`.

The frontend package audit reports zero known vulnerabilities as of this review.
Third-party package names, license information, and funding metadata are unchanged
except for removal of the unused build integration.

## Proposed source snapshot

These 111 files form the cleaned source snapshot under the existing ignore
rules. Deleted setup files, private inputs, backups, and generated output are
excluded. Recheck the list if files change before publication.

```text
.gitignore
PUBLICATION_AUDIT.md
README.md
Start Schedule Lab.command
examples/named-opponents.json
examples/rank-band-75-100.json
npi_model/__init__.py
npi_model/__main__.py
npi_model/app_server.py
npi_model/division_npi.py
npi_model/fast_division.py
npi_model/game_value.py
npi_model/outcome_model.py
npi_model/planning.py
npi_model/planning_report.py
npi_model/schedule_optimizer.py
npi_model/schedule_simulator.py
npi_model/season_npi.py
pyproject.toml
scripts/launch_app.py
tests/data/ncaa_2024_10_27_division.json
tests/data/ncaa_2024_10_27_verification.json
tests/test_app_server.py
tests/test_division_npi.py
tests/test_game_value.py
tests/test_schedule_optimizer.py
tests/test_schedule_simulator.py
tests/test_season_npi.py
web/.gitignore
web/.oxfmtrc.json
web/.oxlintrc.json
web/app/globals 2.css
web/app/globals.css
web/app/main.tsx
web/app/page 2.tsx
web/app/page 3.tsx
web/app/page.tsx
web/components.json
web/components/explorer.tsx
web/components/planning-controls.tsx
web/components/results.tsx
web/components/ui/accordion.tsx
web/components/ui/alert-dialog.tsx
web/components/ui/alert.tsx
web/components/ui/aspect-ratio.tsx
web/components/ui/attachment.tsx
web/components/ui/avatar.tsx
web/components/ui/badge.tsx
web/components/ui/breadcrumb.tsx
web/components/ui/bubble.tsx
web/components/ui/button-group.tsx
web/components/ui/button.tsx
web/components/ui/calendar.tsx
web/components/ui/card.tsx
web/components/ui/carousel.tsx
web/components/ui/chart.tsx
web/components/ui/checkbox.tsx
web/components/ui/collapsible.tsx
web/components/ui/combobox.tsx
web/components/ui/command.tsx
web/components/ui/context-menu.tsx
web/components/ui/dialog.tsx
web/components/ui/direction.tsx
web/components/ui/drawer.tsx
web/components/ui/dropdown-menu.tsx
web/components/ui/empty.tsx
web/components/ui/field.tsx
web/components/ui/hover-card.tsx
web/components/ui/input-group.tsx
web/components/ui/input-otp.tsx
web/components/ui/input.tsx
web/components/ui/item.tsx
web/components/ui/kbd.tsx
web/components/ui/label.tsx
web/components/ui/marker.tsx
web/components/ui/menubar.tsx
web/components/ui/message-scroller.tsx
web/components/ui/message.tsx
web/components/ui/native-select.tsx
web/components/ui/navigation-menu.tsx
web/components/ui/pagination.tsx
web/components/ui/popover.tsx
web/components/ui/progress.tsx
web/components/ui/radio-group.tsx
web/components/ui/resizable.tsx
web/components/ui/scroll-area.tsx
web/components/ui/select.tsx
web/components/ui/separator.tsx
web/components/ui/sheet.tsx
web/components/ui/sidebar.tsx
web/components/ui/skeleton.tsx
web/components/ui/slider.tsx
web/components/ui/spinner.tsx
web/components/ui/switch.tsx
web/components/ui/table.tsx
web/components/ui/tabs.tsx
web/components/ui/textarea.tsx
web/components/ui/toast.tsx
web/components/ui/toggle-group.tsx
web/components/ui/toggle.tsx
web/components/ui/tooltip.tsx
web/hooks/use-mobile.ts
web/index.html
web/lib/model.ts
web/lib/utils.ts
web/package-lock.json
web/package.json
web/public/favicon.svg
web/styles-plugin.ts
web/tsconfig.json
web/vite.config.ts
```

Keep coach inputs in `planning_inputs/` and other private data in `local_data/`.
Review any new JSON or CSV file outside those directories before committing.
Recheck this list before a push if the files change.
