# Release Updates

This document keeps a cumulative release history for Zertan. Each section records what a version introduced and how it improved the product, UX, platform, packaging, or validation work compared with the previous release line, so the file can serve as a long-term roadmap and change log reference.

# Index

- `v1.0.0` - base product release, operational stack, exam flows, native packaging foundation
  - `v1.0.0`: hotfixes
    - `v1.0.1` - legacy desktop packaging hotfixes for icons and release artifacts
    - `v1.0.2` - legacy release pipeline and desktop launcher fixes
  - `v1.1.0` - audit registry, stronger content ordering rules, permission tightening, UX refinements
    - `v1.1.1` - shared confirmation modal, protected admin deletion rules, Linux packaging hardening

# v1.0.0

`v1.0.0` established the first full Zertan product baseline.

- Zertan shipped as a serious certification study platform built on the intended stack:
  - Flask for the web layer
  - SQLite for persistence
  - JWT-backed sessions for authentication
  - HTML, CSS, and vanilla JavaScript for the frontend
- The application shipped as a server-rendered experience with no SPA runtime, no frontend build pipeline, and no external database dependency.
- The core learning model was already in place:
  - role-based authentication and protected pages
  - study mode for flexible question practice
  - formal exam mode with fixed server-built attempts
  - exam pagination in groups of 5 questions
  - persisted results and statistics for formal attempts
- The content layer already supported:
  - editable exam and question-bank structures
  - import/export packages with `exam.json`, one JSON file per question, and related assets
  - question assets, tags, topics, and exam scope/group assignment structures
  - live exam assignment flows
- The runtime model was already production-aware:
  - debug startup could seed demo content automatically
  - production-style first run required an explicit bootstrap administrator password
  - runtime data, database files, and uploaded assets were separated from source files
- Docker deployment and local native packaging foundations were already documented and wired:
  - container image and compose deployment
  - OS-specific native packaging entrypoints for Windows, Linux, and macOS
  - dedicated packaged server behavior and packaged client behavior
- Automated coverage already existed for:
  - auth and role handling
  - protected routes and API bootstrap
  - question normalization and parsing
  - exam pagination and live exam assignment rules
  - import/export validation
  - bootstrap/runtime database behavior

### v1.0.1

`v1.0.1` was a packaging-focused hotfix release on the early desktop release line.

- Native desktop release outputs moved toward real platform artifacts instead of zip-only packaging:
  - Windows `.exe`
  - macOS `.dmg`
  - Debian `.deb`
- Shared application icon generation was added from the Zertan source asset for release builds.
- Platform-specific icon outputs were wired for:
  - Windows `.ico`
  - macOS `.icns`
  - Linux packaged icon installation
- The desktop build script gained stronger output-directory preparation, release naming, and per-platform packaging helpers.
- The PyInstaller spec was updated to support platform-aware packaging and icon injection.
- GitHub release workflow publishing was updated to collect the correct per-platform release artifact types.
- New automated tests were added for:
  - icon generation
  - Windows packaging
  - macOS packaging
  - Debian package layout generation

### v1.0.2

`v1.0.2` continued the legacy packaging line with release-pipeline and launcher fixes.

- The release workflow gained stronger execution control and verification:
  - workflow concurrency protection
  - explicit build output checks
  - Debian package metadata verification
  - macOS DMG layout verification
- Release publishing was enriched with:
  - generated release manifests
  - SHA-256 checksum output
  - Docker image digest tracking
- macOS packaging improved with:
  - version propagation into the packaged bundle
  - code-signing support hooks
  - staged DMG layout with an `Applications` shortcut
  - cleaner app-bundle metadata
- Windows and macOS desktop packaging were refined to behave more like polished native app outputs instead of console-style bundles.
- The desktop launcher became more reliable when running from frozen bundles:
  - better Linux `_internal` resource resolution
  - better macOS `Resources` bundle resolution
  - cleaner frozen-path handling
- Linux desktop launch behavior was refined so packaged launches no longer require a terminal window.
- Automated coverage expanded with new tests around:
  - macOS icon generation
  - version propagation into PyInstaller builds
  - signed DMG staging expectations
  - frozen bundle resource resolution

## v1.1.0

`v1.1.0` was the first major product-and-operations upgrade over the `v1.0.x` baseline.

- A new **Log Registry** was added for supervisory auditing.
- Examiners and administrators gained log visibility by exam, including:
  - overview pages
  - exam detail pages
  - scoped export
  - scoped deletion where allowed
- Zertan started recording **automatic audit entries** when exams or questions are:
  - created
  - updated
  - archived
  - deleted
  - imported from packages
- Audit entries began storing richer context:
  - actor identity and role
  - exam metadata
  - question metadata
  - before and after snapshots
  - textual diffs
  - scope-group information
- Group-scope and domain-scope exports became available for supervisory workflows.

- Question ordering became significantly more reliable and self-healing.
- Question create and edit flows now treat **position as optional** instead of forcing a default.
- Reordering logic now resequences questions automatically after:
  - create
  - update
  - archive
  - delete
  - startup normalization
- Archived questions are pushed behind active ones during normalization, reducing duplicate or broken ordering states.

- Global-scope exam permissions became stricter.
- Examiners can still view global exams, but only the domain administrator can manage global-scope question content.

- Live Exams improved for administrators who are also assigned participants.
- Self-assigned live exams can now be seen and launched correctly without disappearing from the user-facing workflow.

- The profile modal was improved with:
  - assigned-group chips
  - more stable layout for long content
  - cleaner scrolling behavior
- Live exam modal sizing was tightened to reduce overflow issues.
- The desktop client selector UI was visually scaled down to better match the web UI and reduce oversized presentation.

- Drag and drop questions received a stronger interaction model:
  - pointer-based gestures
  - clearer hover states
  - drag ghost feedback
  - better desktop and touch behavior

- The platform and persistence layer advanced:
  - database schema version moved to `11`
  - new tables were added for `log_registry_entries` and `log_registry_scope_groups`
  - new indexes were added for audit retrieval by exam, action, and group scope
  - database startup now normalizes legacy question positions automatically

- Validation coverage expanded for:
  - log registry routing and API registration
  - question resequencing
  - startup normalization behavior
  - global exam permission boundaries
  - administrator self-assigned live exams
  - enriched public user payloads with group memberships

### v1.1.1

`v1.1.1` built on `v1.1.0` with focused UX, account-safety, and packaging hardening improvements.

- A new reusable **confirmation modal** replaced browser-native confirm dialogs across destructive and high-impact actions.
- The shared confirmation flow now covers:
  - exam submission
  - exam deletion
  - question deletion
  - live exam closing
  - live exam deletion
  - log registry deletion
  - user deletion
  - group deletion
- The new modal adds:
  - consistent copy and button styling
  - focus restoration
  - escape and backdrop dismissal
  - queued handling for consecutive confirmations

- Administrator user deletion now follows explicit backend rules instead of raw API deletion.
- Administrators can no longer delete:
  - their own account
  - the protected bootstrap administrator account
- Allowed deletions now clear active sessions before removing the user record.
- The admin UI now exposes deletion safety state directly in the user card with:
  - `can_delete`
  - `delete_block_reason`
  - `is_protected`

- The data model advanced again:
  - database schema version moved to `12`
  - `users.is_protected` was added for persistent protected-account enforcement
  - seeding and bootstrap normalization now ensure the default administrator remains protected

- The profile modal layout was refined further for smaller screens and long content:
  - better overflow handling
  - more stable stacked behavior
  - cleaner responsive panel transitions

- Linux server packaging became more robust for `pywebview`, GTK, and `gi` runtime requirements.
- Debian packaging now declares the runtime dependencies needed for GTK/WebKit-backed desktop behavior.
- The Linux launcher now prepares `PYTHONPATH` for system `dist-packages` and disables the WebKit GBM renderer by default to reduce startup/runtime failures.
- PyInstaller packaging gained a Linux runtime hook for `gi`, typelib-path setup, and related hidden imports/data collection.
- Linux build documentation was updated to explain the required runtime packages more clearly.
- Release artifacts were refreshed for `v1.1.1` on Linux and macOS.

- Validation coverage expanded again with tests for:
  - protected-user and self-deletion rules in the admin API
  - deletion cleanup behavior
  - user-manager handling of protected accounts and login/profile flows
