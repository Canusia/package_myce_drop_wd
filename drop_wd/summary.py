"""Drop/WD request aggregates, shared by the CE Summary tab and the
Drop/WD Requests Summary report (#6).

Everything is counted in the database (values().annotate()), one query per
breakdown, so neither the tab nor the report scales with the number of
requests.
"""
from django.db.models import Count, Q

from .models import DropWDRequest


# key, title, ORM path(s) to group by, column label.
# A tuple of paths groups by all of them and joins the values for display --
# instructors need first and last name or two people share a row.
BREAKDOWNS = (
    ('term',          'Requests by Term',          ('registration__class_section__term__label',),  'Term'),
    ('academic_year', 'Requests by Academic Year', ('registration__class_section__term__academic_year__name',), 'Academic Year'),
    ('highschool',    'Requests by High School',   ('registration__student__highschool__name',),   'High School'),
    ('course',        'Requests by Course',        ('registration__class_section__course__name',), 'Course'),
    ('instructor',    'Requests by Instructor',
     ('registration__class_section__teacher__user__last_name',
      'registration__class_section__teacher__user__first_name'), 'Instructor'),
    ('status',        'Requests by Status',        ('status',),                                    'Status'),
)

BREAKDOWN_KEYS = tuple(b[0] for b in BREAKDOWNS)

# status stores keys; show what the rest of the UI shows.
STATUS_LABELS = dict(DropWDRequest.STATUS_OPTIONS)


def summary_rows(records, group_paths, total, key=None):
    """Aggregate `records` by one or more ORM paths.

    Returns rows of {name, total, requested, processed, pct}, largest first.
    """
    rows = (
        records
        .values(*group_paths)
        .annotate(
            total=Count('id'),
            requested=Count('id', filter=Q(status='requested')),
            processed=Count('id', filter=Q(status='processed')),
        )
        .order_by('-total', *group_paths)
    )

    out = []
    for row in rows:
        parts = [row.get(path) for path in group_paths]
        parts = [str(p) for p in parts if p not in (None, '')]
        name = ', '.join(parts) if parts else '(none)'
        if key == 'status':
            name = STATUS_LABELS.get(name, name)
        out.append({
            'name': name,
            'total': row['total'],
            'requested': row['requested'],
            'processed': row['processed'],
            'pct': round(row['total'] * 100.0 / total, 1) if total else 0.0,
        })
    return out


def breakdowns(records, keys=None, total=None):
    """[{key, title, name_label, rows}] for `keys` (all when None), in
    BREAKDOWNS order."""
    if total is None:
        total = records.count()
    return [
        {
            'key': key,
            'title': title,
            'name_label': name_label,
            'rows': summary_rows(records, paths, total, key=key),
        }
        for key, title, paths, name_label in BREAKDOWNS
        if keys is None or key in keys
    ]
