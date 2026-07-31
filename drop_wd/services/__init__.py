"""Table-config services for the drop_wd package."""


def get_requests_table_config():
    """Tenant override if present, else the packaged default.

    myce_tenant_configs is per-tenant and in-tree; drop_wd is installed into
    every tenant. A hard dependency on the tenant module would 500 any tenant
    that has not added it, so the package ships a working default and lets a
    tenant override it by adding services/drop_wd_requests_table.py.

    `cis.services.table_configs.get_table_config` is a thin
    `importlib.import_module` wrapper, so a missing tenant module surfaces as
    ModuleNotFoundError (a subclass of ImportError); a tenant without the
    `TABLE_CONFIGS_APP` setting at all surfaces as AttributeError. Both mean
    "no override" — fall back to the packaged module.
    """
    try:
        from cis.services.table_configs import get_table_config
        return get_table_config('drop_wd_requests_table')
    except (ImportError, ModuleNotFoundError, AttributeError):
        from . import requests_table
        return requests_table
