# Changelog

All notable changes to `myce_drop_wd` (the MyCE Drop/Withdrawal request app).

Releases are git-tag-driven on `Canusia/package_myce_drop_wd`; each tenant pins a tag
through the `git+https://…@<tag>` line in its `webapp/requirements.txt`. The package's
`version` in `setup.cfg` and `pyproject.toml` always declares the tag it was cut at — pip
keys upgrades off the version string, not the tag, so a frozen version makes an
incremental install silently keep the old code.

## Unreleased

### Fixed
- **`myce_cis` is optional again, so tenants that keep `cis` in their own repo can
  upgrade** (#17). v2026.2.5 made `myce_cis>=0.1.7a` a hard dependency and imported
  `cis.highschool_scope` when the report module loaded; neither exists for an in-repo
  `cis`. `myce_cis` is now the optional `campus` extra (`myce_drop_wd[campus]`) in both
  `pyproject.toml` and `setup.cfg`, and the Drop/WD requests report falls back to the
  pre-v2026.2.5 picker (active schools by name) when `cis.highschool_scope` is absent —
  checked with `importlib.util.find_spec`, so a real import error inside a multi-campus
  `cis` still surfaces. The campus picker tests skip without it.

### Security
- **Every drop/withdraw view and feed stays inside the caller's scope** (#8, #9, #10).
  New `drop_wd/scoping.py` defines it — `registrations_for(user, role=…)` /
  `requests_for(user, role=…)`: CE staff everything, instructors the sections they
  teach, HS admins students at their schools, students their own. Before this the
  request id alone was the key:
  - `submit_request` built the registration choice from the posted id, so an
    instructor or HS admin could file against any registration. It now returns 403
    outside the scope of a role that may submit.
  - The HS admin request page compared a HighSchool id against a HighSchool queryset,
    which never matched, so any HS admin could open and sign any school's request. It
    now 404s outside the admin's schools.
  - `bulk_actions` (`mark_as_approved`) updated any ids posted. It is now POST-only
    with CSRF, touches only in-scope rows, and reports `updated` / `skipped` counts.
  - `delete_record` and `send_processed_email` had no role check (a student could
    delete a request); both are CE-only and POST-only. The request page's
    `update_drop_wd_request` action (edits the registration) is CE-only.
- **The signature written is decided by the acting role's own scope, not the union of
  the user's roles** (#12, #13, #14). The acting role comes from the portal URL the
  request came through (`ce_drop_wd`, `instructor_drop_wd`, `highschool_admin_drop_wd`,
  `student_drop_wd`); a portal whose role the user doesn't hold 404s / 403s. So a
  teacher who is also an HS admin:
  - may review or bulk-approve as *instructor* only on sections they teach, and as
    *counselor* only for students at their schools;
  - is no longer auto-approved as instructor when submitting a request for a
    colleague's section (the submit-time pre-approval in `signals.py` is now scoped
    the same way).
  Student and parent signatures (`DropWDSignatureForm`) are accepted only from the
  student on their own request; instructors and HS admins can no longer overwrite
  them. `review_request` is accepted only when that role's approval is pending.
- Access tests cover each role against each view, plus the two-role (instructor + HS
  admin) and colleague's-section cases.

### Changed
- The requests page is chosen by portal, not by the first role the user holds: a
  teacher who is also an HS admin gets the HS admin page under `/highschool_admin/`.
  The page's feed URL carries `&portal=<role>` so its rows match what that portal's
  detail page and bulk action accept; each portal's bulk button posts to its own
  `<portal>_drop_wd:bulk_actions` (new on the student portal).
- The HS admin request page offers the review when the *counselor* approval is
  pending (it checked the student approval).
- `RequestReviewForm.save()` takes `role=`; without it, it keeps the old
  first-matching-role guess for outside callers.

**Templates:** tenant overrides of `drop_wd/instructor/requests.html` must POST
`bulk_actions` with the CSRF token (GET now returns 405), and overrides of
`drop_wd/ce/request.html` must POST `delete_record`.

## v2026.2.7 — 2026-10-18

### Changed
- **Instructor Drop/WD page text comes from the instructor portal package when it is
  installed** (package-cis#82). `portal_text('instructor')` reads
  package-instructor_portal's setting and falls back to `cis.settings.instructor_portal`,
  so the page works on tenants on either side of the move.

## v2026.2.6 — 2026-10-18

### Added
- **Drop/WD tab on the instructor class section page, registered from here.** The instructor
  portal (`package-instructor_portal` v0.0.1) no longer hardwires this tab; `drop_wd/tabs.py`
  registers it on the portal's `instructor_class_section_tabs` registry from both app configs'
  `ready()`. It looks up `instructor.instructor.registry` (editable submodule) and then
  `instructor.registry`, and does nothing when neither exists, so tenants still on the in-tree
  instructor app are unaffected.

## v2026.2.3 — 2026-08-29

### Added
- **This changelog**, and `CHANGELOG.md` added to `MANIFEST.in` so it ships in the sdist.

## v2026.2.2 — 2026-08-29

### Fixed
- **The "New Request" page no longer stops at 50 students, or 50 class sections.**
  `ClassRegistrationViewSet` and `ClassSectionViewSet` set no `pagination_class`, so both
  inherited the project-wide `DatatablesPageNumberPagination`. That class only speaks the
  DataTables `start`/`length` protocol when the renderer format is `datatables`; for the
  plain-JSON `$.getJSON` calls these two endpoints actually serve, it falls through to
  stock `PageNumberPagination` at `PAGE_SIZE = 50` and exposes no `page_size` query param,
  so the client could not ask for more. The three `start_request.html` templates then read
  `data.results` and never followed `data.next`. A section's 51st student was silently
  unreachable — no error, no truncation notice — and so was a term's 51st class section,
  which hits any instructor or HS admin with a large load. Both viewsets now set
  `pagination_class = None`, and the templates read `data.results || data` so a future
  pagination change cannot blank the dropdown.

### Changed
- **Both dropdown feeders serve lean, purpose-built serializers.** Returning every row is
  only affordable if a row is cheap. cis's `StudentRegistrationSerializer` embeds the
  whole `ClassSectionSerializer`, which in turn embeds course → campus/location, teacher,
  term → academic_year, highschool and the syllabi set: 60 registrations cost 1,571
  queries and 390 KB, roughly 26 queries per row and most of them past any depth
  `select_related` can reach. Lifting the cap on top of that would have made a
  300-student section ≈ 7,800 queries. `DropdownRegistrationSerializer` and
  `DropdownClassSectionSerializer` emit exactly the fields the templates read, in the same
  nested shape.

  | Endpoint | Before | After |
  |---|---|---|
  | 60 registrations | 1,571 queries / 390 KB | 11 queries / 9.4 KB |
  | 60 sections | 1,209 queries / 232 KB | 9 queries / 5.8 KB |

  Both `status` and `status_pretty` are emitted, so the instructor and HS-admin templates
  (which read `status_pretty`) and the student template (which reads `status`) keep working
  unchanged. Query-count and response-shape tests guard against a revert to the nested
  serializer.

  The allowed-registration-status filter, the per-role scoping (CE / student / instructor
  / HS-admin) and the surname ordering are unchanged; each is covered by a test that
  exercises it past the old 50-row boundary.

### Fixed (packaging)
- **Version metadata now matches the tag.** `setup.cfg` declared `0.1` and
  `pyproject.toml` `0.0.1` across every release up to and including v2026.2.1, so pip
  treated an existing install as already satisfied and no tag of this package could be
  picked up by an incremental `pip install -r requirements.txt` — no error, no warning.
  Confirmed in a live container, which reported `myce_drop_wd-0.0.1` installed while the
  pin read `@v2026.2.1`.

## v2026.2.1 — 2026-08-07

### Fixed
- The Drop/WD requests export is scoped to the student's high school.

## v2026.2.0 — 2026-07-31

### Added
- A Summary tab on the CE requests page, aggregating requests by term, high school,
  course, instructor and status, with a per-month series and a term filter.

## v2026.1.1 — 2026-07-31

### Fixed
- The CE table shim stopped printing its own comment onto the page. A Django `{# … #}`
  comment cannot span lines; the multi-line one shipped in v2026.1.0 was left unparsed and
  rendered as visible text on the CE index page and all seven detail tabs.

## v2026.1.0 — 2026-07-31

### Changed
- **Breaking:** the requests DataTables moved onto the shared table-config pattern. The
  column header HTML, scope maps and the four profiles (`portal`, `portal_approver`,
  `ce_index`, `ce_record_tab`) are built once in Python and rendered from one partial,
  replacing the inline `<thead>` + `<script>` duplicated across templates. A tenant may
  override the whole config module via `myce_tenant_configs/services/drop_wd_requests_table.py`.

### Added
- A School Type column on the Drop/WD requests export.

## v2026.0.4 — 2026-07-02

### Added
- A Section # column on the instructor, HS-admin and student requests tables; CRN, section
  and instructor are now separate columns.

## v2026.0.3 — 2026-06-30

### Fixed
- Notifications tolerate a class section with no assigned teacher.

## v2026.0.2 — 2026-04-14

### Added
- `open` added to the selectable class section statuses.

## Earlier

Tags `v1.0.0` (2026-01-25), `2026.0.1` (2026-03-19) and `v0.0.1` (2026-04-29) predate the
CalVer `YYYY.MAJOR.MINOR` scheme and are not in date order with the `v2026.*` line. They
cover the initial extraction: router base names, passing `request` through to
`EditStudentRegistration.save()`, and tolerating a missing processed-email template.
