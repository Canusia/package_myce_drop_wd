"""Drop/WD sidebar items, one per role namespace (cis.menu_registry).

Id `drop_wd_requests` in every role. ce: the 60 of `students`.
On a cis without the registry nothing registers.
"""
try:
    from cis.menu_registry import menu
except ImportError:   # cis without the registry: the menu migrations still apply
    menu = None

if menu is not None:
    for _role, _url, _order, _parent in [
        ('ce', 'ce_drop_wd:requests', 60, 'students'),
        ('highschool_admin', 'highschool_admin_drop_wd:requests', 90, None),
        ('instructor', 'instructor_drop_wd:requests', 50, None),
        ('student', 'student_drop_wd:requests', 50, None),
    ]:
        menu.register(_role, 'drop_wd_requests', 'Drop/WD Requests', url=_url,
                      icon=None if _parent else 'fas fa-fw fa-file',
                      parent=_parent, order=_order)
