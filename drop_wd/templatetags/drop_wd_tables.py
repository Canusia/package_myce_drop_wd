"""Template tags for the drop_wd DataTables.

A Django template cannot call build_config(), and the CE requests table is
{% include %}d from seven cis detail-page tabs whose call sites must not change.
So the shim template `drop_wd/ce/requests_table.html` loads this library and
calls the tag, which does the config building the view would otherwise do.
"""
from django import template

from ..services import get_requests_table_config

register = template.Library()


@register.inclusion_tag('drop_wd/_ce_requests_table.html', takes_context=True)
def drop_wd_requests_table(context, type=None, record=None, api_url=None,
                           details_prefix='/ce/drop_wd/request/'):
    """Render the CE Drop/WD requests table.

    `type` is the cis detail-page tab scope ('student', 'course', ...); absent
    on the CE index page. `record` is the record that tab is scoped to — its id
    becomes the API query param.
    """
    module = get_requests_table_config()

    base_url = api_url or context.get('api_url') or module.CE_DEFAULT_API_URL
    scope_type = type or None
    record_id = getattr(record, 'id', None) if record else None

    config = module.build_config(
        variant='ce_record_tab' if scope_type else 'ce_index',
        api_url=module.scoped_api_url(base_url, scope_type, record_id),
        details_prefix=details_prefix,
        filter_form_selector='form#all_req_filter',
        scope_type=scope_type,
    )
    return {
        'config': config,
        # The cis tabs do not pass `terms`; the select then holds only its
        # placeholder option, exactly as before.
        'terms': context.get('terms'),
    }
