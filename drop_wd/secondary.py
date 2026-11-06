"""Secondary teachers on a class section (cis#154), for Drop/WD.

A secondary teacher may see and submit Drop/WD requests for a section, and
gets its emails, only when the Secondary Teacher Access setting allows
DROP_WD. The rule lives in cis.secondary_access; on an older cis without it
(tenants with their own in-repo cis) only the primary teacher counts, as
before.
"""
import importlib.util

from django.db.models import Q


def _has_module(name):
    try:
        return importlib.util.find_spec(name) is not None
    except ModuleNotFoundError:  # a parent package is missing
        return False


def has_secondary_access():
    return _has_module('cis.secondary_access')


def user_sections_q(user, prefix=''):
    """Q for sections (reached through `prefix`) where `user` may do Drop/WD."""
    if not has_secondary_access():
        return Q(**{f'{prefix}teacher__user': user})
    from cis.secondary_access import DROP_WD, user_sections_q as q
    return q(user, DROP_WD, prefix=prefix)


def teacher_filter_q(teacher_id, prefix=''):
    """Q for sections taught by teacher `teacher_id`, primary or secondary
    (a CE filter, so not limited by the setting)."""
    if not _has_module('cis.models.section_secondary'):
        return Q(**{f'{prefix}teacher__id': teacher_id})
    from cis.models.section_secondary import teacher_q
    return teacher_q(teacher=teacher_id, prefix=prefix)


def user_can(section, user):
    """May `user` see/submit Drop/WD requests on `section`?"""
    if not has_secondary_access():
        teacher = getattr(section, 'teacher', None)
        return bool(teacher is not None and user is not None
                    and teacher.user_id == getattr(user, 'pk', None))
    from cis.secondary_access import DROP_WD, user_can as can
    return can(section, user, DROP_WD)


def notified_users(section):
    """Accounts of the teachers to email about `section`'s Drop/WD requests:
    the primary, plus secondaries the setting allows."""
    if has_secondary_access():
        from cis.secondary_access import DROP_WD, notified_teachers
        teachers = notified_teachers(section, DROP_WD)
    else:
        teacher = getattr(section, 'teacher', None)
        teachers = [teacher] if teacher is not None else []
    return [t.user for t in teachers if getattr(t, 'user', None) is not None]
