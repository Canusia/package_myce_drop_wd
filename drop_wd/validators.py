"""Settings-form validators, without requiring a recent cis.

cis.validators has grown over time: tenants still on an in-repo cis lack
validate_json and validate_html_short_code, and some have no cis.validators at
all. Use cis's version of each when it has one, so behaviour matches the rest
of the tenant, and otherwise this bundled copy of it.
"""
import importlib
import json

from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.template import Context, Template

from .portal_text import has_module

_cis = importlib.import_module('cis.validators') if has_module('cis.validators') else None


def _validate_json(value):
    try:
        json.loads(value)
        return value
    except Exception:
        raise ValidationError('Please enter a valid JSON string')


def _validate_html_short_code(value):
    try:
        return Template(value).render(Context())
    except Exception:
        raise ValidationError('The text contains invalid shortcode. Please fix it and try again.')


def _validate_email_list(value):
    emails = value.split(',')
    for email in emails:
        try:
            validate_email(email)
        except ValidationError:
            raise ValidationError(f"'{value}' is not a valid comma email list")
    return ','.join(emails)


validate_json = getattr(_cis, 'validate_json', _validate_json)
validate_html_short_code = getattr(_cis, 'validate_html_short_code', _validate_html_short_code)
validate_email_list = getattr(_cis, 'validate_email_list', _validate_email_list)
