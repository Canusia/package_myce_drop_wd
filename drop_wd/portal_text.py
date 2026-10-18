"""Portal page text ("blurbs"), read from whichever app owns it.

The instructor and faculty portal text is moving out of cis into the portal
packages (package-cis#81, #82). Each role's sources, most preferred first: the
package's nested editable layout, its installed layout, then cis's copy, so
this works on tenants on either side of the move.

Availability is checked with ``find_spec`` rather than ``try/except ImportError``
so that a real import error inside a present module still raises.
"""
import importlib
import importlib.util

PORTAL_TEXT_SOURCES = {
    'instructor': (
        ('instructor.instructor.settings.instructor_portal', 'instructor_portal'),
        ('instructor.settings.instructor_portal', 'instructor_portal'),
        ('cis.settings.instructor_portal', 'instructor_portal'),
    ),
    'faculty': (
        ('faculty.faculty.settings.faculty_portal_text', 'faculty_portal_text'),
        ('faculty.settings.faculty_portal_text', 'faculty_portal_text'),
        ('cis.settings.faculty_portal', 'faculty_portal'),
    ),
}


def has_module(name):
    """True when the dotted module ``name`` is importable."""
    try:
        return importlib.util.find_spec(name) is not None
    except ModuleNotFoundError:  # a parent package is missing
        return False


def portal_text(role):
    """The stored page text for the ``role`` portal, or {} when nothing owns it."""
    for module, attr in PORTAL_TEXT_SOURCES[role]:
        if has_module(module):
            value = getattr(importlib.import_module(module), attr).from_db()
            return value if isinstance(value, dict) else {}
    return {}
