# drop_wd — MyCE Drop/WD Request Package

Django app for managing student Drop/Withdrawal requests in the MyCE platform.

## Package Info

- Package name: `myce_drop_wd`
- Installed as: `drop_wd` (production) / `drop_wd.drop_wd` (dev submodule)
- App configs: `drop_wd.apps.DropWdConfig` (prod), `drop_wd.drop_wd.apps.DevDropWdConfig` (dev)

## Structure

```
drop_wd/          ← Django app
  models.py       ← DropWDRequest model
  views.py        ← All views (shared across CE, instructor, HS admin, student)
  forms.py        ← Request, review, signature, and student forms
  signals.py      ← post_save/pre_save handlers for notifications and note-keeping
  serializers.py  ← DRF serializers
  urls/
    ce.py
    instructor.py
    highschool_admin.py
    student.py
  settings/
    drop_wd_email.py  ← SettingForm + drop_wd_email config class
  services/
    __init__.py         ← get_requests_table_config() resolver
    _base.py            ← bundled copy of the shared build_table_config() helper
    requests_table.py   ← packaged default table config
  templatetags/
    drop_wd_tables.py   ← {% drop_wd_requests_table %} inclusion tag
  staticfiles/
    drop_wd/js/
      requests_table.js ← DataTable wiring for both portal and CE tables
  templates/
    drop_wd/
      _requests_table.html     ← shared table partial (portal + CE)
      _ce_requests_table.html  ← CE wrapper (filter form + partial)
      ce/
      instructor/       ← Base template; student + HS admin inherit via {% include %}
      highschool_admin/
      student/
```

## Key Concepts

### Settings (`drop_wd_email`)
Stored in the `Setting` model under key `drop_wd.drop_wd.settings.drop_wd_email`.
Use `drop_wd_email.from_db()` to read. Key fields:

| Field | Purpose |
|---|---|
| `is_active` | Yes / No / Debug |
| `allowed_terms` | List of term IDs — if empty, drops are NOT permitted |
| `allowed_registration_statuses` | Registration statuses eligible for drop requests |
| `allowed_class_section_statuses` | Class section statuses shown when selecting a term |
| `start_new_request` | Which roles can initiate a request |
| `signatures_required_from` | Which roles must approve |
| `notification_list` | Who receives email notifications |

Helper methods on `drop_wd_email`:
- `get_allowed_terms()` → list of term IDs
- `get_allowed_registration_statuses()` → list of status keys
- `get_allowed_class_section_statuses()` → list of status keys

### Drop Permitted Logic
`allowed_terms` empty → no drops permitted. The `drops_permitted` context variable is passed to templates; the "Submit New Request" tab shows an alert instead of the form when False.

### Email Notifications
- **`send_received_notification()`** — fired on `post_save` when a request is first created; sends to CE office
- **`send_processed_notification()`** — fired on `pre_save` only when status changes to `'processed'`; sends to `created_by` + all checked parties in `notification_list`
- `validate_email` from Django raises `ValidationError` on invalid (does NOT return bool) — always use try/except pattern, never `if validate_email(...)`

### Notes
All notes (CE note, review notes, private notes from processed email) are saved to the student's note model via `student.add_note()`. Meta field uses `type: 'private'` and a role-specific key (`private_note`, `instructor_note`, `counselor_note`, `student_note`).

### Requests Table Config Pattern

The Drop/WD requests DataTable is built once in Python and rendered from one
partial, instead of being duplicated as inline `<thead>` + `<script>` in each
template.

| Piece | Role |
|---|---|
| `services/requests_table.py` | Packaged default: column header HTML, scope maps, the four profiles, `build_config()` |
| `services/_base.py` | `build_table_config()` — assembles the context dict and JSON-encodes `opts` |
| `services/__init__.py` | `get_requests_table_config()` — resolves tenant override vs packaged default |
| `templatetags/drop_wd_tables.py` | `{% drop_wd_requests_table %}` inclusion tag for the CE table |
| `templates/drop_wd/_requests_table.html` | Shared `<table>` markup; consumes `config` |
| `templates/drop_wd/_ce_requests_table.html` | CE wrapper (filter form) around the partial |
| `staticfiles/drop_wd/js/requests_table.js` | Column renderers + DataTable init, driven by `opts_json` |

Python owns the `<th>` markup (`data-data` / `data-name` must be real ORM
paths — see the DataTables gotchas below); JS owns the column renderers. The
two registries share the same column-key namespace (`submitted_on`, `student`,
`approvals`, …), so a key added in one must be added in the other.

**Profiles.** `build_config(variant=…)` picks one of four:

| Variant | Used by | Notes |
|---|---|---|
| `portal` | instructor / student / HS-admin requests page | 5-min auto-reload |
| `portal_approver` | same page for users who may approve | adds the `select` checkbox column + `mark_as_approved` bulk action; default order shifts to index 1 |
| `ce_index` | `/ce/drop_wd/` index page | CE column set, column search, 10-min auto-reload, `record-details` link (opens the iframe modal) |
| `ce_record_tab` | the seven cis detail-page tabs | same as `ce_index` but a plain link (already inside the iframe), and drops the column the tab is scoped by (`SCOPE_COLUMN`) |

The 5-vs-10-minute auto-reload split is inherited from the pre-refactor
templates and is intentional — the CE table is often left open on a detail
page, so do not unify the two values.

**Why `get_requests_table_config()` falls back.** A tenant may override the
whole config module by adding `myce_tenant_configs/services/drop_wd_requests_table.py`.
But `myce_tenant_configs` is per-tenant and lives in-tree in each tenant repo,
while `drop_wd` is pip-installed into *every* tenant. A hard import would 500
any tenant that has not added that app, so the resolver tries
`cis.services.table_configs.get_table_config('drop_wd_requests_table')` and
falls back to the packaged `services/requests_table` on `ImportError` /
`ModuleNotFoundError` (missing tenant module) or `AttributeError` (tenant has
no `TABLE_CONFIGS_APP` setting). An override module must expose the same
surface: `build_config`, `scoped_api_url`, `CE_DEFAULT_API_URL`.

**Why `_base.py` is duplicated.** It is a deliberate copy of
`myce_tenant_configs/services/_base.py`. The package cannot import another
app's private module for the same reason as above, and the helper is small and
stable — so it is bundled. If the shared version changes, sync the two by hand.

**Host requirement.** `drop_wd`'s `staticfiles/` directory must be on the
host's `STATICFILES_DIRS` or `requests_table.js` will 404. `myce/settings.py`
does this with the usual editable-submodule conditional
(`get_package_path("drop_wd.drop_wd")` if the nested package exists, else
`get_package_path("drop_wd")`), joined with `'staticfiles'`. Note the directory
is `staticfiles/`, not `static/` — and it must be listed in `MANIFEST.in` or it
will not ship in the sdist/wheel.

### Dev vs Production
In dev (submodule), the module path is `drop_wd.drop_wd.*`. In production (pip install), it's `drop_wd.*`. The host app (`myce/urls.py`, `myce/settings.py`) handles the difference via `settings.DEBUG`.

## URL Namespaces
- `ce_drop_wd` — CE staff
- `instructor_drop_wd` — Instructors
- `highschool_admin` / `student` — HS admins and students (reuse instructor template)
