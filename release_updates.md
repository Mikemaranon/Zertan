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
- `v2.0.0` - personalized error-focused formal attempts, shared skeleton loading states, and modal-driven exam management entrypoints

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

## v2.0.0

`v2.0.0` adds personalized **error-focused formal attempts** per exam and also refines the workspace with calmer loading behavior and cleaner exam-management entrypoints. Users can now ask Zertan to assemble a formal practice attempt from the questions they continue to miss in their own submitted history, instead of only building from the full question bank.

This release builds on the existing attempt and statistics model rather than introducing a parallel tracking system. Error-focused selection uses only persisted submitted-attempt data, ignores study-mode checking activity, and keeps the same fixed-attempt behavior once the server assembles the final question set. The builder flow now exposes this mode from the catalog and study entry points, lets users adjust the failure-percentage threshold, and previews whether enough unresolved mistakes currently qualify.

- Eligibility now requires unresolved mistakes that were failed in submitted attempts at least twice and still meet the selected failure-percentage threshold.
- Questions that the user has since mastered are excluded automatically by comparing the latest failed and latest correct submitted attempts.
- Candidate ranking now favors stronger repeated failure signals first, then more recent unresolved misses.
- The resulting attempt still respects the existing builder filters, pagination rules, and persisted result flow.
- The Tauri client home page now restores its three footer links and opens them through the operating system browser instead of leaving the desktop shell with non-working anchors.

Automated coverage expanded around personalized builder metadata, threshold handling, unresolved-history filtering, and attempt creation from ranked error-focused candidates.

This same release also refines perceived performance across the main web workspace by introducing shared **skeleton loading states** on the heaviest pages instead of leaving large panels blank while data is still arriving. The goal is not flashy motion, but calmer and more informative loading behavior that preserves layout, reduces abrupt shifts, and makes longer requests feel intentional.

The new loading pattern is shared rather than page-specific. Zertan now uses common skeleton primitives for KPI cards, content cards, question panels, filter areas, and form sections, which keeps the experience visually consistent across the product while staying within the platform's restrained, professional design direction. Local retry states were also added for these initial loads so a failed request can be retried in context instead of only surfacing as a generic top-level error.

- Skeleton loading now covers the personal dashboard and the global statistics workspace.
- The exam catalog, study entry page, and exam builder now render structured placeholders before their heavier data finishes loading.
- Exam management now loads with reusable skeleton cards and keeps edit metadata actions visibly busy while exam details are being fetched.
- Shared loading and retry helpers were introduced in the plain JavaScript frontend instead of scattering one-off placeholders through each page.
- The attempt-type modal now keeps its footer anchored to the bottom of the dialog while the option list expands or scrolls above it, so the action buttons no longer float upward when the modal has spare vertical space.

This release keeps the stack and page model unchanged while making the desktop-first experience feel steadier during real-world network and database waits.

It also cleans up the **Manage exams** workspace so the list remains the primary focus and creation flows no longer compete with it inline. Instead of keeping large always-visible forms on the page, Zertan now exposes dedicated entry actions in the top-right corner of the exam listing and opens the existing create and import workflows inside focused modals.

The goal of this release is administrative clarity rather than feature expansion. Examiners and administrators can still create exams, edit exam metadata, and import structured packages with the same underlying validation and scope rules, but those actions now happen in a more contained interaction model that keeps the listing readable and reduces visual clutter during day-to-day management.

- The **Create exam** action now opens the metadata form in a modal from the exam management toolbar.
- The existing **Edit metadata** action reuses that same modal with the current exam values preloaded.
- The **Import package** action now opens the package-upload flow in its own modal instead of reserving page space for a secondary form.
- Reviewer access to the page remains intact for question-management workflows, while creation and import entrypoints stay limited to the higher management roles that already owned those actions.

`v2.0.0` preserves the current Flask, SQLite, and plain-JavaScript architecture while making the admin-facing and user-facing experience calmer, steadier, and easier to scan.
