# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

Manages course drop/withdrawal requests with multi-stakeholder approval workflows. Supports signatures from students, parents, instructors, and counselors with configurable requirements.

## Key Components

### Model (`models.py`)
**DropWDRequest** - Main request entity with:
- `registration` (FK to StudentRegistration) - One request per registration (unique constraint)
- `status` - 'requested', 'processed', 'approved', 'not_approved'
- `status_changed_on` (JSONField) - Tracks status change timestamps
- Signature fields: `student_signature`, `parent_signature`, `instructor_signature`, `counselor_signature`
- Each signature has status: Not Needed, Pending, Approved, Not Approved

### URL Structure (Role-Based)
- `/ce/drop_wd/` - Full management for CE office
- `/instructor/drop_wd/` - Instructor view with class filtering
- `/student/drop_wd/` - Student's own requests
- `/highschool_admin/drop_wd/` - HS admin view with school filtering

### Key Endpoints
- `submit_request` - Create new drop/wd request
- `drop_request/<id>` - View/edit with role-based templates
- `parent_signature/<id>` - Public parent approval page
- `send_parent_email` - Trigger parent notification

## Signature Workflow

1. Request created, signatures auto-set based on config and submitter role
2. If parent approval needed, email sent with secure approval URL
3. Each approver signs via their portal or email link
4. When all required signatures collected, status updates
5. Notifications sent on status changes

## Configuration

Via `drop_wd_email` settings form:
- Who can start requests (student, instructor, hs_admin)
- Which approvals required (student, parent, instructor, counselor)
- Email templates with variables: `{{student_name}}`, `{{course_name}}`, `{{highschool_name}}`
- Notification recipients per status change

## Signals (`signals.py`)
- **pre_save:** Updates `status_changed_on`, triggers notifications
- **post_save:** On new request, sends CE notification, auto-sets signatures

## Integration

- Links to `cis.models.StudentRegistration` for course/student data
- Updates student profile notes on status changes
- Uses `django-model-utils.FieldTracker` for change detection
- Custom `SignatureField` from `form_fields` package
