"""drop_wd's tabs on the instructor and HS admin class section pages.

The instructor portal owns the registry (instructor/registry.py); drop_wd
registers onto it from its own AppConfig.ready(), so the instructor app no
longer needs to know drop_wd exists. On a host without the instructor
portal's registry (an older in-tree instructor app, or none) nothing is
registered and that host keeps whatever it renders itself.
"""
import importlib
import importlib.util

from django.urls import reverse


def _instructor_registry():
    for module in ('instructor.instructor.registry', 'instructor.registry'):
        try:
            if importlib.util.find_spec(module) is not None:
                return importlib.import_module(module)
        except ModuleNotFoundError:  # parent package missing
            continue
    return None


_registry = _instructor_registry()

if _registry is not None:
    from .forms import DropWDRequestForm

    @_registry.instructor_class_section_tabs.tab(
        slug='drop_wd', title='Drop/WD Request(s)', order=30, lazy=False,
        template='drop_wd/instructor/_class_section_tab.html')
    def instructor_class_section_tab(request, class_section):
        return {
            'class_section': class_section,
            'drop_api_url': reverse(
                'instructor_drop_wd:instructor_drop_wd_requests-list')
                + '?format=datatables&portal=instructor',
            'submit_new_drop_request_form': DropWDRequestForm(class_section=class_section),
        }


# --- HS admin class section page (#16) ---------------------------------------
#
# package-highschool_admin (after v0.0.21) builds the class-section page from
# hsadmin_class_section_tabs. drop_wd registers its Drop Requests tab there,
# so the portal doesn't need to know drop_wd exists. A tenant whose portal
# predates the registry, or has no highschool_admin at all, registers nothing.

HSADMIN_REGISTRY_MODULES = (
    'highschool_admin.highschool_admin.tabs.registry',   # editable submodule
    'highschool_admin.tabs.registry',                    # pip-installed
)


def _module_exists(name):
    try:
        return importlib.util.find_spec(name) is not None
    except ModuleNotFoundError:  # a parent package is missing
        return False


def _hsadmin_registry():
    """The HS admin class-section TabRegistry, or None when the host lacks it.

    find_spec rather than try/except ImportError, so a real error inside a
    present registry module still raises.
    """
    for module in HSADMIN_REGISTRY_MODULES:
        if _module_exists(module):
            return getattr(importlib.import_module(module),
                           'hsadmin_class_section_tabs', None)
    return None


def hs_admins_use_drop_wd(user=None, record=None):
    """Show the tab only when HS admins have a part in drop requests: they
    may start one, or must approve one. Being notified alone isn't enough --
    there is nothing for them to do on the page."""
    from django.urls import NoReverseMatch
    from .settings.drop_wd_email import drop_wd_email
    configs = drop_wd_email.from_db() or {}
    if not ('highschool_admin' in (configs.get('start_new_request') or [])
            or 'highschool_admin' in (configs.get('signatures_required_from') or [])):
        return False
    try:  # rows link into the HS admin drop_wd portal; no portal, no tab
        reverse('highschool_admin_drop_wd:requests')
    except NoReverseMatch:
        return False
    return True


def hsadmin_class_section_requests(request, record):
    """Context for the HS admin Drop Requests tab: this section's requests
    for students at the admin's high schools (the same scope the
    highschool_admin_drop_wd request page enforces)."""
    from .models import DropWDRequest
    from .scoping import HIGHSCHOOL_ADMIN, requests_for
    from .settings.drop_wd_email import drop_wd_email

    requests = (
        requests_for(request.user, role=HIGHSCHOOL_ADMIN)
        .filter(registration__class_section=record)
        .select_related('registration__student__user', 'created_by')
        .order_by('-created_on')
    )
    can_start = (DropWDRequest.can_administrator_submit_request()
                 and bool(drop_wd_email.get_allowed_terms()))
    return {
        'drop_requests': requests,
        'needs_counselor_approval': DropWDRequest.needs_administrator_approval(),
        'start_request_url': (reverse('highschool_admin_drop_wd:requests') + '#add_new'
                              if can_start else ''),
    }


_hsadmin_tabs = _hsadmin_registry()

if _hsadmin_tabs is not None:
    _hsadmin_tabs.tab(
        slug='drop_wd', title='Drop Requests', order=25, lazy=False,
        template='drop_wd/highschool_admin/_class_section_requests.html',
        permission=hs_admins_use_drop_wd,
    )(hsadmin_class_section_requests)
