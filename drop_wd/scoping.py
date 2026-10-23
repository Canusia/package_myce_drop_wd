"""Who may see, file and sign which drop/withdraw requests.

Two questions, kept apart on purpose:

* **Which records may a user reach?** ``registrations_for(user)`` /
  ``requests_for(user)`` with no role answer it for list feeds: the union of
  every role the user holds.
* **Which signature may a user write on a record?** That is decided by one
  role's own scope, never the union. A teacher who is also an HS admin can
  reach every request at their school, but may sign as *instructor* only on
  sections they teach, and as *counselor* only for students at their schools
  (#12, #13). Pass ``role=`` for that.

The acting role is taken from the portal URL the request came through
(``acting_role``), not guessed from the user's groups.
"""
from django.db.models import Q

from cis.utils import (
    user_has_instructor_role,
    user_has_highschool_admin_role,
    user_has_student_role,
    user_has_cis_role,
)
from cis.models.section import StudentRegistration
from cis.models.highschool_administrator import HSAdministrator

from .models import DropWDRequest


CE = 'ce'
INSTRUCTOR = 'instructor'
HIGHSCHOOL_ADMIN = 'highschool_admin'
STUDENT = 'student'

# Legacy priority, used only when a view is reached outside this package's
# URLconfs and so has no portal namespace to go by.
ROLES = (CE, INSTRUCTOR, HIGHSCHOOL_ADMIN, STUDENT)

ROLE_CHECKS = {
    CE: user_has_cis_role,
    INSTRUCTOR: user_has_instructor_role,
    HIGHSCHOOL_ADMIN: user_has_highschool_admin_role,
    STUDENT: user_has_student_role,
}

# app_name of each urls/<portal>.py -> the role that portal serves.
PORTAL_ROLES = {
    'ce_drop_wd': CE,
    'instructor_drop_wd': INSTRUCTOR,
    'highschool_admin_drop_wd': HIGHSCHOOL_ADMIN,
    'student_drop_wd': STUDENT,
}

# The signature each role writes when it approves.
SIGNATURE_FIELDS = {
    INSTRUCTOR: 'instructor_signature',
    HIGHSCHOOL_ADMIN: 'counselor_signature',
    STUDENT: 'student_signature',
}


def user_has_role(user, role):
    """Cached on the user object (for request.user, its lazy wrapper, shared
    by the whole request): a page asks the same question many times, and
    each cis check is a groups query. Never cleared -- a test that changes a
    user's groups after asking must use a fresh user instance."""
    check = ROLE_CHECKS.get(role)
    if check is None:
        return False
    cache = user.__dict__.setdefault('_drop_wd_roles', {})
    if role not in cache:
        cache[role] = bool(check(user))
    return cache[role]


def submitting_roles(user):
    """Roles the user holds that the settings let start a request."""
    from .settings.drop_wd_email import drop_wd_email
    # The same 'start_new_request' list DropWDRequest.can_*_submit_request()
    # read, read once. CE may always start one.
    allowed = {CE} | set(drop_wd_email.from_db().get('start_new_request') or [])
    return [role for role in ROLES if role in allowed and user_has_role(user, role)]


def acting_role(request):
    """The role this request acts as, or None if the caller doesn't hold it.

    Taken from the portal namespace the URL resolved through
    (instructor_drop_wd, highschool_admin_drop_wd, ...), so a user holding
    several roles acts as the portal they are on. A view reached through some
    other URLconf falls back to the first role the user holds -- for reads
    only: a write with no portal to go by gets None, so it can't sign in a
    role the caller never chose.
    """
    match = getattr(request, 'resolver_match', None)
    app_names = getattr(match, 'app_names', None) or []
    portal_role = PORTAL_ROLES.get(app_names[-1]) if app_names else None

    if portal_role is not None:
        return portal_role if user_has_role(request.user, portal_role) else None

    if request.method not in ('GET', 'HEAD'):
        return None

    for role in ROLES:
        if user_has_role(request.user, role):
            return role
    return None


def _role_scope(user, role):
    """Q over StudentRegistration for one role; matches nothing if the user
    doesn't hold it. CE is unrestricted."""
    if not user_has_role(user, role):
        return Q(pk__in=[])
    if role == CE:
        return Q()
    if role == INSTRUCTOR:
        return Q(class_section__teacher__user=user)
    if role == HIGHSCHOOL_ADMIN:
        hsadmin = HSAdministrator.objects.filter(user__id=user.id).first()
        if hsadmin is None:
            return Q(pk__in=[])
        return Q(student__highschool__in=hsadmin.get_highschools())
    if role == STUDENT:
        return Q(student__user=user)
    return Q(pk__in=[])


def _held_roles(user, role=None, roles=None):
    if role is not None:
        roles = (role,)
    elif roles is None:
        roles = ROLES
    return [r for r in roles if user_has_role(user, r)]


def registrations_for(user, role=None, roles=None):
    """StudentRegistrations a user may see, file or sign for.

    ``role``: that one role's scope only (what a signature must be checked
    against). ``roles``: the union over those roles. Neither: the union over
    every role the user holds -- CE staff all, instructors the sections they
    teach, HS admins students at their schools, students their own. A role the
    user doesn't hold contributes nothing, so anyone else gets none.
    """
    held = _held_roles(user, role, roles)
    records = StudentRegistration.objects.all()
    if CE in held:
        return records

    scope = Q(pk__in=[])
    for r in held:
        scope |= _role_scope(user, r)
    return records.filter(scope)


def requests_for(user, role=None, roles=None):
    """DropWDRequests on registrations_for(user, role, roles)."""
    held = _held_roles(user, role, roles)
    if CE in held:
        return DropWDRequest.objects.all()
    return DropWDRequest.objects.filter(
        registration__in=registrations_for(user, roles=held))


def registration_in_role_scope(user, role, registration):
    """True if ``registration`` is inside ``role``'s own scope for ``user``."""
    return registrations_for(user, role=role).filter(pk=registration.pk).exists()
