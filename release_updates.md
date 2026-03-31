# Release Updates

This document keeps the long-term release history for Zertan. It is written as a cumulative product narrative rather than a raw dump of commits, so each version explains what changed, why it mattered, and how it moved the platform forward.

# Index

- `v1.0.0` - base product release, exam flows, import/export, statistics, packaging foundation
    - `v1` patches and hotfixes
        - `v1.0.1` - first desktop packaging hotfix line, icon generation, platform artifact normalization
        - `v1.0.2` - release pipeline verification, launcher fixes, richer native packaging outputs
    - `v1.1.0` - audit registry, stronger content ordering rules, permission tightening, UX refinements
        - `v1.1.1` - shared confirmation modal, protected administrator deletion rules, Linux packaging hardening
    - `v1.2.0` - embedded server administration console, live runtime visibility, packaged server UI integration, expanded color themes

# v1.0.0

`v1.0.0` establishes the first full Zertan product baseline. From the start, Zertan shipped on the intended stack: Flask for the web layer, SQLite for persistence, JWT-backed authentication, and a plain HTML/CSS/JavaScript frontend with no SPA runtime and no frontend build pipeline.

The core learning and exam model was already in place. Zertan shipped with role-based authentication, protected pages, study mode for flexible review, formal exam mode with fixed server-built attempts, pagination in groups of five questions, and persisted results and statistics for formal attempts. The content model also already supported editable exam and question-bank structures, question assets, tags, topics, exam scope/group assignment, and import/export packages built around `exam.json`, one JSON file per question, and related assets.

The runtime and deployment story was also present from day one. Debug startup could seed demo content automatically, production-style first run required an explicit bootstrap administrator password, and runtime data, database files, and uploaded assets were kept separate from source files. Docker deployment and native packaging entrypoints for Windows, Linux, and macOS were already documented and wired.

- Automated coverage already existed for auth and role handling, protected routes, question normalization, exam pagination, live exam assignment rules, import/export validation, and bootstrap/runtime database behavior.

## `v1` patches and hotfixes

There are not any changes that justify a `1.x.0` version, so bellow will be documented the hotfixes before jumping to `v1.1.0`

### v1.0.1

`v1.0.1` is a packaging-focused hotfix release on the first desktop release line. It shifts the project toward real platform-native outputs instead of zip-only packaging and introduces shared application icon generation from the Zertan source asset.

- Native release outputs were normalized around Windows `.exe`, macOS `.dmg`, and Debian `.deb`.
- Platform-specific icon outputs were wired for Windows `.ico`, macOS `.icns`, and Linux packaged installation.
- The desktop build script gained stronger output-directory preparation, release naming, and per-platform packaging helpers.
- The PyInstaller spec and GitHub release workflow were updated to collect the correct platform artifacts.

New automated tests were added for icon generation, Windows packaging, macOS packaging, and Debian package layout generation.

### v1.0.2

`v1.0.2` continues the early packaging line with release-pipeline and launcher fixes. The release process gained stronger execution control, explicit build output checks, Debian metadata verification, and macOS DMG layout verification. Release publishing also became more informative through generated manifests, SHA-256 checksums, and Docker image digest tracking.

On the packaging side, macOS builds improved with version propagation into the packaged bundle, code-signing hooks, a staged DMG layout with an `Applications` shortcut, and cleaner app-bundle metadata. Windows and macOS outputs moved further away from console-style bundles and closer to polished native artifacts, while the desktop launcher became more reliable inside frozen bundles through better Linux `_internal` resolution, better macOS `Resources` handling, and cleaner frozen-path behavior.

- Linux packaged launches no longer require a terminal window.
- Automated coverage expanded around icon generation, version propagation, signed DMG staging, and frozen resource resolution.

## v1.1.0

`v1.1.0` is the first major product-and-operations upgrade after the initial `v1.0.x` baseline. It adds a dedicated **Log Registry** for supervisory auditing and makes question ordering more resilient across content-management workflows.

The new Log Registry gives examiners and administrators visibility into exam-scoped activity, including overview pages, exam detail pages, scoped export, and controlled deletion where allowed. Zertan now records automatic audit entries when exams or questions are created, updated, archived, deleted, or imported, and those entries store richer context such as actor identity, role, exam metadata, question metadata, before/after snapshots, textual diffs, and scope-group information.

Question ordering also became self-healing. Position is now treated as optional during create and edit flows, while resequencing runs automatically after create, update, archive, delete, and startup normalization. Archived questions are pushed behind active ones during normalization, reducing broken or duplicate ordering states.

- Global-scope exam permissions became stricter, limiting global question-content management to the domain administrator.
- Self-assigned live exams for administrators now appear correctly in the user-facing workflow.
- The profile modal, live exam modal sizing, and drag-and-drop interaction model all received targeted UX refinements.
- The schema version moved to `11`, adding new log-registry tables, scope-group support, and retrieval indexes.

Validation coverage expanded accordingly, including tests for log registry routing, question resequencing, startup normalization, global permission boundaries, self-assigned live exams, and richer public user payloads.

### v1.1.1

`v1.1.1` builds on `v1.1.0` with a tighter UX and stronger account-protection rules. The most visible improvement is the new shared confirmation flow, which replaces browser-native confirm dialogs with a reusable modal that behaves consistently across the product.

- The confirmation modal now covers exam submission, exam deletion, question deletion, live exam closing, live exam deletion, log registry deletion, user deletion, and group deletion.
- The modal adds consistent copy, focus restoration, escape and backdrop dismissal, and queued handling for consecutive confirmations.

This release also hardens administrator deletion rules. The backend now treats protected accounts explicitly instead of trusting raw deletion requests, which means administrators cannot delete themselves and cannot remove the protected bootstrap administrator account. The admin UI surfaces that safety state clearly so the restriction is visible before a destructive action is attempted.

- Allowed user deletions now clear active sessions before removing the record.
- The user payload exposes `can_delete`, `delete_block_reason`, and `is_protected`.
- The schema version moved to `12`, adding persistent protected-account enforcement through `users.is_protected`.

On the packaging side, `v1.1.1` improves Linux server runtime reliability for `pywebview`, GTK, and `gi`. Debian packaging declares the required GTK/WebKit dependencies, launcher behavior prepares the runtime environment more carefully, and Linux build documentation explains the needed packages more clearly. Release artifacts were refreshed on Linux and macOS, and automated coverage expanded around protected-user handling and deletion cleanup.

## v1.2.0

`v1.2.0` introduces the new embedded **Server Administration Console** for the packaged server runtime. Instead of only showing that the server is alive, the desktop window now exposes a full interface with live runtime data, endpoint visibility, directory browsing, feature toggles, and recent API activity. The same release line also expands the product theme system with additional color palettes, giving users more visual options while keeping the UI within Zertan's restrained, professional design direction.

The new console is structured as a desktop-first operational UI with an overview section, a searchable directory for users and groups, a feature management view, and an activity feed for meaningful API requests. It refreshes continuously, can open the live site in the browser, can copy the active URL, and can request a clean shutdown directly from the embedded server window.

- The overview now exposes runtime metadata such as primary URL, loopback URL, data directory, database path, media root, instance ID, and uptime.
- The directory view lets operators inspect users and groups in place, with floating search results and detail modals.
- The features view lets operators toggle registered site capabilities directly against the current domain database.
- The activity feed records important API traffic while filtering out noisy bulk `GET` requests, so mutating operations and failures remain visible.

This release also adds the bridge and snapshot infrastructure needed to keep the desktop console synchronized with the running Flask backend. The packaged server now builds a live runtime snapshot from database state, connection information, feature flags, session counts, question counts, and captured API requests, then exposes that snapshot to the embedded UI through the `pywebview` bridge layer.

- The server launcher now loads console UI assets both from source and from frozen bundles.
- The server status window became a larger, resizable application window backed by the new console bridge.
- PyInstaller packaging now bundles the console UI assets with the packaged server build.
- Automated coverage expanded with tests for request logging, refresh behavior, formatting, and console HTML generation.

The release also includes a small client-window adjustment so the desktop client is less constrained by hard minimum dimensions, expanded selectable color themes across the client experience, and refreshed packaged artifacts for the `v1.2.0` line.
