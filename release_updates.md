# Release Updates

## Since `v1.0.0`

These notes summarize the product and platform changes currently present in the working tree after the `Release: v1.0.0` commit.

## Product Highlights

- A new **Log Registry** has been added for supervisory auditing. Examiners and administrators can review change history by exam, inspect diffs, export logs, and, when allowed, delete logs by scope.
- Zertan now records **automatic audit entries** when exams or questions are created, updated, archived, deleted, or imported from a package.
- **Question ordering is now reliable and self-healing**. New questions can be inserted at a specific position, leaving position empty appends to the end, and the system resequences questions after create, update, archive, delete, and startup normalization.
- **Global-scope exam permissions are stricter**. Examiners can still view global exams, but only the domain administrator can manage questions for globally scoped content.
- The **Live Exams** area now supports the case where an administrator is also an assigned participant, so self-assigned live exams can be seen and launched directly.
- The **profile modal** now surfaces the user’s assigned groups and has a more stable layout for longer content.
- **Drag and drop questions** received a stronger interaction model with pointer-based gestures, visual drag ghosts, clearer hover states, and better desktop/touch behavior.
- The interface has been **scaled down globally** so both the browser UI and the installable client feel closer to a reduced browser zoom level.

## New Audit And Supervision Layer

- New overview and detail pages were added for the log registry.
- New API endpoints were added for:
  - log overview
  - exam-level detail
  - scoped export
  - scoped deletion
- Audit entries store:
  - actor identity and role
  - exam metadata
  - affected question metadata
  - before/after snapshots
  - textual diffs
  - scope groups
- Group scope and domain scope exports are now supported for supervisory use.

## Content Management Improvements

- Question creation and editing now handle **position as an optional field** instead of forcing a default position.
- Reordering no longer leaves duplicate positions or gaps behind.
- Archived questions are pushed behind active ones when the sequence is normalized.
- Package import now records imported exams and imported questions in the audit trail.

## UX And Workspace Improvements

- Administrators now have a dedicated **Assigned to you** panel in Live Exams.
- The profile area now shows **group membership chips**.
- Long profile content and modal panels scroll more cleanly.
- Live exam modal sizing was tightened to avoid layout overflow.
- The desktop client selector window was visually reduced to match the new web scale.

## Platform And Data Layer

- Database schema advanced to **version 11**.
- New persistence tables were added for:
  - `log_registry_entries`
  - `log_registry_scope_groups`
- New indexes were added for audit-log retrieval by exam, action, and group scope.
- Database startup now normalizes legacy question positions automatically.

## Validation Coverage Added

- New or expanded tests cover:
  - log registry routing and API registration
  - question position resequencing
  - database startup normalization
  - global exam permission boundaries
  - administrator self-assigned live exams
  - enriched public user payloads with group memberships

## Notes

- These notes intentionally focus on meaningful product and platform changes.
- Binary release artifacts currently present in the diff were not treated as feature updates here.
