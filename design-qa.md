# Design QA — Experiment list delete confirmation

## Evidence

- Source visual truth: `/Users/yizhou/.codex/generated_images/01a029f0-2b3d-7851-ac21-353272942eb6/exec-71183831-4c3b-4fc4-a793-8b3b57bcc0d5.png`
- Source pixels: 1487 × 1058; normalized to 1440 × 1024 at `/Users/yizhou/Documents/Electrical Tracking App/.codex_tmp/delete-modal-qa/source-1440x1024.png`.
- Browser implementation: `/Users/yizhou/Documents/Electrical Tracking App/.codex_tmp/delete-modal-qa/implementation-final-1440x1024.png`
- Implementation pixels/CSS viewport: 1440 × 1024 at device pixel ratio 1.
- Narrow-view evidence: `/Users/yizhou/Documents/Electrical Tracking App/.codex_tmp/delete-modal-qa/implementation-final-900x900.png`
- Combined comparison: `/Users/yizhou/Documents/Electrical Tracking App/.codex_tmp/delete-modal-qa/side-by-side-final.png`
- Annotation implementation: `/Users/yizhou/Documents/Electrical Tracking App/.codex_tmp/delete-modal-qa/add-experiment-button-smaller.png`
- State: CAT001 experiment list with the delete confirmation for CAT001AA open.

## Findings

- No actionable P0/P1/P2 visual differences remain.
- Fonts and typography: the implementation retains Atlas' existing system font stack and matches the selected target's compact 16px title and 14px supporting copy. Title, identifier, and warning copy remain legible without wrapping at both checked viewports.
- Spacing and layout rhythm: the modal is 440 × 228 CSS px, centered, with a 40px warning icon, 32px close control, compact body spacing, and a separated 42px-button footer. It is intentionally shorter than the selected visual in response to the user's feedback.
- Colors and tokens: existing Atlas/Bootstrap primary, danger, border, muted-text, and overlay treatments are preserved. The destructive action remains the only strong red control.
- Image and icon fidelity: no raster imagery is required. Existing Bootstrap Icons provide the warning, close, plus, cancel, trash, edit, and genealogy icons; no placeholder or handcrafted icon assets were introduced.
- Copy and content: the title includes the target code; experiment deletion reports the live step/cell/sample counts; step deletion explains affected material-usage, sample, and cell records; both state that deletion cannot be undone.
- Accessibility and interaction: focus enters the modal on open, Escape and Cancel close it, focus returns to the triggering delete button after the transition, decorative icons are hidden from assistive technology, and controls have object-specific accessible names.
- Responsive check: at 900 × 900 the 440px modal remains centered with no horizontal overflow (`bodyScrollWidth = 900`).

## Comparison history

1. Initial browser comparison found two P2 fidelity issues: the global compact icon-button rule constrained “新增实验” and “新增步骤” to 28px squares, and the Bootstrap close button rendered at roughly 48px.
2. Fixed the add controls with explicit content-sized dimensions and selected colors; fixed the close button with border-box sizing.
3. Post-fix evidence: “新增实验” was initially 96 × 36px, “新增步骤” is 82 × 32px, the close button is 32 × 32px, the warning icon is 40 × 40px, and the modal is 440 × 228px. Browser console errors: none.
4. A subsequent browser annotation requested a smaller “新增实验” button. The scoped update reduced only that control to approximately 84 × 30px with 12px text, 4px icon gap, and 9px horizontal padding. The surrounding table, action column, row controls, and modal were unchanged. Post-update browser console errors: none.

## Primary interactions tested

- Open experiment delete confirmation and verify the target code and live counts.
- Close with Escape and verify focus restoration.
- Reopen, close with Cancel, and verify focus restoration.
- Confirm the initial focus is inside the modal on the Cancel button.
- Verify the compact modal at 1440 × 1024 and 900 × 900.
- Confirm there are no browser console errors.

## Follow-up polish

- P3: if desired, the overlay opacity could be reduced slightly to keep more table context visible; it is currently consistent with Bootstrap's default modal treatment.

final result: passed

---

# Design QA — 首页概览与教程

## Evidence

- Source visual truth: `/Users/yizhou/.codex/generated_images/01a04de0-2401-7ad2-8245-9f80e68bb4c2/exec-b9561b69-6b1b-4846-8e8d-4f84a401c8f5.png`
- Source pixels: 1487 × 1058.
- Browser implementation: `/Users/yizhou/Documents/Electrical Tracking App/.codex_tmp/overview-implementation-v3.png`
- Implementation pixels / CSS viewport: 1488 × 1058, device pixel ratio 1.
- Combined comparison: `/Users/yizhou/Documents/Electrical Tracking App/.codex_tmp/overview-comparison.png`
- State: signed-in staff user, global overview, 14-day range.

## Findings

- No actionable P0/P1/P2 visual differences remain.
- Fonts and typography: the implementation keeps Atlas' established system font stack and reproduces the selected hierarchy: strong Chinese greeting, compact overview labels, prominent blue/teal metrics, and readable tutorial metadata.
- Spacing and layout rhythm: header, sidebar, overview panel, three-card tutorial grid, and help strip align with the source at the same viewport. The implementation keeps a slightly roomier panel width to fit the existing 240px sidebar without reducing metric readability.
- Colors and tokens: existing Atlas text, border, muted surface, blue, teal, and green tokens are preserved. The selected white panel and restrained blue chart treatment are matched without introducing a competing visual system.
- Image quality and asset fidelity: all three tutorial cards use project-local, high-resolution generated laboratory photography with matching cool, clinical art direction and intentional 16:9 crops. Existing Bootstrap Icons are used for interface icons; no placeholders or custom drawn icons were introduced.
- Copy and content: Chinese greeting, date, 概览, metric labels, tutorial titles, help labels, and 更新日志 copy match the selected direction. Live values are populated from the permitted queryset rather than from mock constants.
- Focused regions were not required: the equal-size combined comparison keeps all metric labels, chart dates, tutorial titles, and help items legible.

## Comparison history

1. The first browser capture loaded a cached `app.css?v=16`, so the new page appeared unstyled (P1).
2. Bumped the existing stylesheet cache key to `v=17`, restarted the local preview, and captured the same 1488 × 1058 state again.
3. The post-fix combined comparison shows the selected two-column overview panel, three tutorial cards, and help strip at the intended proportions. Browser console errors: none.

## Primary interactions tested

- Switch overview from 全局 to 我的.
- Change the trend range from 14 to 30 days and verify the URL/state update.
- Open 更新日志 and verify the repository's `[Unreleased]` content renders.
- Confirm no browser console errors after the interaction sequence.

## Follow-up polish

- P3: tutorial card imagery is slightly taller than the reference at some intermediate desktop widths; this preserves the generated photographs' focal subjects and remains responsive.

final result: passed

---

# Design QA — Cell / Sample association

## Evidence

- Source visual truth: `/Users/yizhou/.codex/generated_images/01a037d0-6037-7452-9de3-56cf253c2cea/exec-52f0f163-c426-4865-a75a-eee77c680907.png`
- Source pixels: 1487 × 1058; normalized to 1440 × 1024 at `/Users/yizhou/Documents/Electrical Tracking App/.codex_tmp/sample-link-qa/source-normalized-1440x1024.png`.
- Browser implementation: `/Users/yizhou/Documents/Electrical Tracking App/.codex_tmp/sample-link-qa/implementation-final-v6-1440x1024.png`
- Implementation pixels/CSS viewport: 1440 × 1024 at device pixel ratio 1.
- Focused source drawer: `/Users/yizhou/Documents/Electrical Tracking App/.codex_tmp/sample-link-qa/source-drawer-v4-520x960.png`
- Focused implementation drawer: `/Users/yizhou/Documents/Electrical Tracking App/.codex_tmp/sample-link-qa/implementation-drawer-v6-520x960.png`
- Responsive evidence: `/Users/yizhou/Documents/Electrical Tracking App/.codex_tmp/sample-link-qa/implementation-final-v6-900x900.png`
- State: edit PCA001AA-FN00, Cell tab active, first cell selected, drawer open, three existing links, and `PCA001AA-MX` search showing the first cursor page.

## Findings

- No actionable P0/P1/P2 visual differences remain.
- Fonts and typography: the implementation retains Atlas' existing system stack and compact editor scale. Drawer hierarchy, sample identifiers, metadata, dates, and statuses remain readable without unintended wrapping.
- Spacing and layout rhythm: the 520px drawer matches the selected target's right-side proportion. It starts below the 64px global header, keeps the permission notice and actions fixed, and leaves search results as the only scrolling region. The left side remains the existing modal editor rather than introducing a parallel full-page route.
- Colors and tokens: the implementation uses the existing Atlas blue/teal, border, muted-text, and warning colors. Selected samples, completion status, permission note, and primary action retain the selected target's semantic balance.
- Image and icon fidelity: no raster imagery is required. Existing Bootstrap Icons provide search, link, close, shield, and action icons; no placeholder or handcrafted assets were introduced.
- Copy and content: the drawer exposes Cell identity, selected count, Project/Experiment/Step filters, grouped Step label, sample lineage path, date, Step status, permission scope, clear selection, and an exact-count apply action.
- Accessibility and interaction: the drawer is labelled as a modal dialog, Escape closes it, focus returns to the trigger, controls use semantic inputs/buttons, and search status updates through a live region.
- Intentional product constraint: the source visual is a standalone full-page editor, while Atlas edits Steps in an existing Bootstrap modal. The association table and drawer follow the source without replacing that established route or navigation contract.

## Comparison history

1. Initial comparison found three P2 differences: the drawer was 470px and re-dimmed the editor, selected samples occupied a separate chip block, and result rows omitted the source Step label/date/status. The permission scope note also scrolled out of view.
2. Fixed the drawer to 520px with a transparent click-away layer, moved the selected count into the header, added `清除选择`, and made the apply action report the selected count.
3. Added Step template labels, lineage path, sample creation date, Step status, and a fixed warning-style permission note. Post-fix evidence is the v6 full-view and focused drawer capture above.
4. The final browser pass loaded 25 results, loaded the next cursor page to 30, changed selection from 3 to 4, cleared it to 0, canceled without mutating the row, reopened with the original 3 selections, and reported zero console errors.

## Primary interactions tested

- Open the Step editor, switch to Cell, and open association for an existing Cell.
- Debounced prefix search and stale-request cancellation behavior.
- First 25 results plus cursor-based “加载更多” to 30 results.
- Select, clear, cancel, reopen, and verify draft selection isolation.
- Escape close and trigger focus restoration.
- Team-scoped Project/Experiment/Step filter loading.
- 1440 × 1024 and 900 × 900 overflow checks (`bodyScrollWidth = viewport width`).

## Follow-up polish

- P3: a later batch-association flow can reuse the same drawer, but it was not introduced in this first implementation because the current editor saves Cell rows individually.

final result: passed
