# Drop/WD Request — Product Guide

## Overview

The Drop/WD Request module allows students, instructors, and high school administrators to submit, track, and approve requests to drop or withdraw from a dual enrollment class section. CE staff manage the end-to-end lifecycle from a central dashboard.

---

## Architecture

### Package

| Mode | App label | AppConfig |
|---|---|---|
| Production (pip) | `drop_wd` | `drop_wd.apps.DropWdConfig` |
| Development (submodule) | `drop_wd.drop_wd` | `drop_wd.drop_wd.apps.DevDropWdConfig` |

The host application detects which mode is active via `settings.DEBUG` and adjusts `INSTALLED_APPS` and URL routing accordingly.

### Dependencies

- `cis` — CustomUser, Student, StudentRegistration, ClassSection, Term, HSAdministrator models
- `setting` — `Setting` model used to persist configuration
- `report` — Report registration via `AppConfig.REPORTS`
- `mailer` — Email delivery
- `model_utils.FieldTracker` — Detects status changes on `DropWDRequest`

---

## Data Model

### `DropWDRequest`

| Field | Type | Notes |
|---|---|---|
| `id` | UUID | Primary key |
| `registration` | FK → StudentRegistration | One request per registration (unique) |
| `created_by` | FK → CustomUser | Person who submitted the request |
| `processed_by` | FK → CustomUser | CE staff who processed it |
| `status` | CharField | `requested` \| `processed` |
| `note` | TextField | Submitter's message to CE office |
| `ce_note` | TextField | CE staff public note |
| `notes` | JSONField | Role-specific review notes (`instructor_note`, `counselor_note`, `student_note`) |
| `student_signature` | CharField | `Not Needed` \| `Pending` \| `Approved` \| `Not Approved` |
| `parent_signature` | CharField | Same options as above |
| `instructor_signature` | CharField | Same options as above |
| `counselor_signature` | CharField | Same options as above |
| `status_changed_on` | JSONField | Timestamps keyed by status, e.g. `processed_on` |

---

## Request Lifecycle

### Statuses

| Status | Meaning |
|---|---|
| `requested` | Request submitted, awaiting processing |
| `processed` | CE staff has processed the request |

### Signature Statuses

`Not Needed` → `Pending` → `Approved` / `Not Approved`

Signatures are only required from roles configured in the **Signatures Required From** setting. When a request is submitted by a role that is also required to approve it, their signature is automatically set to `Approved`.

---

## Settings

All settings are stored in the `Setting` model under the key `drop_wd.drop_wd.settings.drop_wd_email` and managed via the **Settings → Drop/WD Requests** page.

### Reading settings in code

```python
from drop_wd.settings.drop_wd_email import drop_wd_email

settings = drop_wd_email.from_db()          # full dict
terms    = drop_wd_email.get_allowed_terms() # list of term IDs (empty = not permitted)
statuses = drop_wd_email.get_allowed_registration_statuses()
sections = drop_wd_email.get_allowed_class_section_statuses()
```

### Setting fields

| Field | Type | Behaviour when empty |
|---|---|---|
| `is_active` | Select | — |
| `allowed_terms` | Multi-select | **No drops permitted** |
| `allowed_registration_statuses` | Multi-select | All statuses allowed |
| `allowed_class_section_statuses` | Multi-select | All section statuses shown |
| `start_new_request` | Multi-checkbox | Nobody can start |
| `signatures_required_from` | Multi-checkbox | No approvals required |
| `notification_list` | Multi-checkbox | Nobody notified (except `created_by`) |
| `processed_email_subject` | Text | — |
| `processed_email` | Textarea | — |
| `email_address_to_cep` | Text | CE office not notified |
| `email_subject_to_cep` | Text | — |
| `email_to_cep` | Textarea | — |

---

## Views

All views live in `drop_wd/views.py` and are shared across portals. URL namespaces determine which portal context is active.

| URL namespace | Portal |
|---|---|
| `ce_drop_wd` | CE Staff |
| `instructor_drop_wd` | Instructor |
| `highschool_admin_drop_wd` | High School Administrator |
| `student_drop_wd` | Student |

### Key views

| View | Description |
|---|---|
| `requests` | Main list page; renders per-role template |
| `submit_request` | POST endpoint to create a new `DropWDRequest` |
| `drop_request` | Detail/review page for a single request |
| `do_bulk_action` | Bulk approve signatures |
| `send_processed_email` | CE-only — manually trigger processed notification |
| `delete_record` | CE-only — hard delete a request |

### ViewSets (DRF)

| ViewSet | Endpoint | Filtered by |
|---|---|---|
| `ClassSectionViewSet` | `api/class_sections/` | Term, role, allowed section statuses |
| `ClassRegistrationViewSet` | `api/class_section/registrations/` | Section, term, role, allowed registration statuses |
| `DropWDRequestViewSet` | `api/requests/` | Role, term, student, highschool, teacher, course |

---

## Forms

| Form | Used by | Purpose |
|---|---|---|
| `DropWDRequestForm` | Instructor, HS Admin | New request; filters term/section dropdowns by allowed settings |
| `StudentDropWDRequestForm` | Student | New request; filters registrations by allowed terms/statuses |
| `CEDropRequestForm` | CE Staff | Batch-create requests for multiple registrations |
| `EditDropWDRequestForm` | CE Staff | Update request status and CE note; saves CE note to student notes |
| `RequestReviewForm` | Instructor, HS Admin, Student | Approve/reject; saves note to student notes |
| `DropWDSignatureForm` | Student, Parent | Capture signature |

---

## Signals

### `pre_save` — `status_changed`

Fires before every save of `DropWDRequest`. When status changes:
1. Logs a note on the student record
2. Records the timestamp in `status_changed_on`
3. If new status is `processed` → calls `send_processed_notification()`

### `post_save` — `create_new_request`

Fires after a new `DropWDRequest` is created:
1. Calls `send_received_notification()` to email the CE office
2. Auto-sets signatures to `Approved` for the submitting role (if that role is configured to approve)
3. Logs a note on the student record

---

## Email Notifications

### CE Office email (`send_received_notification`)

Sent when a new request is created.

**Available short codes:**

| Short code | Value |
|---|---|
| `{{submitted_by_first_name}}` | Submitter first name |
| `{{submitted_by_last_name}}` | Submitter last name |
| `{{course_name}}` | Course name |
| `{{class_section_number}}` | Class section number |
| `{{note}}` | Submitter's note |
| `{{instructor_first_name}}` | Instructor first name |
| `{{instructor_last_name}}` | Instructor last name |
| `{{student_first_name}}` | Student first name |
| `{{student_last_name}}` | Student last name |
| `{{term}}` | Term |

### Processed notification (`send_processed_notification`)

Sent when request status changes to `processed` (or triggered manually from CE request page).

**Recipients:** `created_by` (always) + anyone checked in **Notification List** setting.

**Available short codes:**

| Short code | Value |
|---|---|
| `{{student_first_name}}` | Student first name |
| `{{student_last_name}}` | Student last name |
| `{{instructor_first_name}}` | Instructor first name |
| `{{instructor_last_name}}` | Instructor last name |
| `{{course_name}}` | Course name |
| `{{request_status}}` | Drop request status |
| `{{registration_status}}` | Student registration status |
| `{{ce_note}}` | CE staff public note |
| `{{term}}` | Term |

> **Important:** `validate_email` from Django raises `ValidationError` on invalid addresses — it does **not** return a boolean. Always wrap in `try/except`, never use `if validate_email(...)`.

---

## Notes Integration

Every note or annotation added through the module is also persisted to the `StudentNote` model via `student.add_note()`:

| Source | `meta.type` | `meta` key |
|---|---|---|
| Request submitted | `public` | `registration_id` |
| Status changed | `public` | `registration_id` |
| CE note (edit form) | `private` | `private_note` |
| Review note (instructor/counselor/student) | `private` | `instructor_note` / `counselor_note` / `student_note` |
| Private note (manual processed email) | `private` | `private_note` |

---

## Templates

The instructor portal templates serve as the base for all portals:

```
drop_wd/instructor/requests.html   ← base list page
drop_wd/student/requests.html      ← {% include 'drop_wd/instructor/requests.html' %}
drop_wd/highschool_admin/requests.html  ← same
```

Each portal has its own `start_request.html` (the submit new form) and `request.html` (detail view).

---

## Reports

Registered via `AppConfig.REPORTS`. The `drop_wd_requests` report is available to CE staff under **Reports → Classes → Drop/WD Requests Export**.

Report file: `drop_wd/reports/drop_wd_requests.py`
