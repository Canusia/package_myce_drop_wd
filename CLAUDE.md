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
  templates/
    drop_wd/
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

### Dev vs Production
In dev (submodule), the module path is `drop_wd.drop_wd.*`. In production (pip install), it's `drop_wd.*`. The host app (`myce/urls.py`, `myce/settings.py`) handles the difference via `settings.DEBUG`.

## URL Namespaces
- `ce_drop_wd` — CE staff
- `instructor_drop_wd` — Instructors
- `highschool_admin` / `student` — HS admins and students (reuse instructor template)
