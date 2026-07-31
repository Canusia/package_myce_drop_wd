"""Shared helpers for *_table service modules.

DELIBERATE COPY of myce_tenant_configs/services/_base.py.

`myce_tenant_configs` is per-tenant and lives in-tree in each tenant repo;
`drop_wd` is a pip package installed into *all* of them. The package must not
import another app's private module — a tenant that renamed, diverged, or has
not yet added that app would break at import time. The helper is small and
stable, so it is bundled here instead. Keep the two in sync by hand if the
shared version changes.

The opts shape varies per service, so each service still builds its own
opts dict; this helper handles the repetitive skeleton: column_headers,
column_footers (when footer_html supplied), filter_form, bulk_actions,
and the final json.dumps of opts.
"""
import json


def build_table_config(*, profile, header_html, partial_template, opts,
                       footer_html=None,
                       filter_form_html=None,
                       include_bulk_actions=False,
                       include_bulk_actions_url=True,
                       gate_bulk_on_action_scope=False,
                       bulk_actions=None,
                       bulk_actions_url=None):
    """Construct the table-config context dict.

    Args:
      profile: looked-up _PROFILES[variant] dict.
      header_html: mapping of column key -> <th> HTML.
      partial_template: template path of the partial for this service.
      opts: dict the caller built; will be JSON-encoded as 'opts_json'.
      footer_html: when supplied, adds 'column_footers' (built from columns
        when profile['footer_search'] is True, else []) and 'footer_search'.
      filter_form_html: when not None, adds 'filter_form' to the config dict.
        (Empty string is preserved as-is; only None means "no filter form".)
      include_bulk_actions: when True, adds 'bulk_actions' (and conditionally
        'bulk_actions_url') to the config dict.
      include_bulk_actions_url: when True (default), 'bulk_actions_url' is also
        added. Set False for callers that historically omit the key.
      gate_bulk_on_action_scope: when True (and include_bulk_actions=True),
        bulk_actions is set to None unless profile['action_scope'] == 'bulk'.
    """
    columns = profile['columns']

    config = {
        'partial_template': partial_template,
        'table_id':        profile['table_id'],
        'column_headers': [header_html[k] for k in columns],
    }

    if footer_html is not None:
        footer_search = profile.get('footer_search', False)
        config['column_footers'] = (
            [footer_html.get(k, '<th></th>') for k in columns]
            if footer_search else []
        )
        config['footer_search'] = footer_search

    if filter_form_html is not None:
        config['filter_form'] = filter_form_html

    if include_bulk_actions:
        if gate_bulk_on_action_scope and profile.get('action_scope') != 'bulk':
            config['bulk_actions'] = None
        else:
            config['bulk_actions'] = bulk_actions
        if include_bulk_actions_url:
            config['bulk_actions_url'] = bulk_actions_url

    config['opts_json'] = json.dumps(opts)
    return config
