"""The one place Drop/WD emails are sent from (#15).

Applies the `is_active` switch (Yes / Debug / No) and the `debug_email_list`,
replacing the hard-coded personal address each sender used to fall back to
(mirrors package-grades#2 and package-class_visit). With `settings.DEBUG` on,
Yes is treated as Debug, so a dev or misconfigured server cannot mail real
students, parents or staff: mail goes to the debug list, or nowhere when the
list is empty. There is no other fallback address.
"""
import logging

from django.conf import settings
from django.core.validators import validate_email

from mailer import send_html_mail

YES, DEBUG, NO = 'Yes', 'Debug', 'No'

logger = logging.getLogger(__name__)


def parse_addresses(value):
    """Comma/semicolon/newline-separated text (or a list) -> stripped, non-empty addresses."""
    if not value:
        return []
    if isinstance(value, (list, tuple)):
        items = value
    else:
        items = str(value).replace('\n', ',').replace(';', ',').split(',')
    return [str(a).strip() for a in items if a and str(a).strip()]


def invalid_addresses(value):
    bad = []
    for address in parse_addresses(value):
        try:
            validate_email(address)
        except Exception:
            bad.append(address)
    return bad


def email_mode(configs):
    mode = (configs or {}).get('is_active') or YES
    if mode == YES and getattr(settings, 'DEBUG', False):
        return DEBUG
    return mode


def resolve_recipients(configs, to):
    """The addresses a Drop/WD email should actually go to; [] means don't send."""
    mode = email_mode(configs)
    if mode == NO:
        return []
    if mode == DEBUG:
        recipients = parse_addresses((configs or {}).get('debug_email_list'))
        if not recipients:
            # A setting saved in Debug before debug_email_list existed: it used
            # to reach a hard-coded address and now reaches no one. Say so.
            logger.warning(
                'Drop/WD email not sent: Debug mode with an empty Debug Email List.')
        return recipients
    return [a for a in parse_addresses(to) if not invalid_addresses([a])]


def send_drop_wd_mail(configs, subject, text_body, html_body, to):
    """Send through the switch. Returns the recipients used ([] = nothing sent)."""
    recipients = resolve_recipients(configs, to)
    if recipients:
        send_html_mail(
            subject, text_body, html_body, settings.DEFAULT_FROM_EMAIL, recipients)
    return recipients
