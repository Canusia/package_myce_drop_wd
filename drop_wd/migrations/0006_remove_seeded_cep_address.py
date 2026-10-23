# Data only. cis dependency is __first__: drop_wd ships to tenants whose cis
# migration graphs differ (submod-migration-deps).
from django.db import migrations

# Seeded as the "To CE Office" address by every install() before #15, so a
# tenant that never edited the field still mails a personal inbox.
SEEDED_ADDRESS = 'kadaji@gmail.com'

# The key is the settings module path, which differs between the installed
# and the nested editable layouts.
KEYS = (
    'drop_wd.settings.drop_wd_email',
    'drop_wd.drop_wd.settings.drop_wd_email',
)


def remove_seeded_address(apps, schema_editor):
    Setting = apps.get_model('cis', 'Setting')
    for setting in Setting.objects.filter(key__in=KEYS):
        value = setting.value
        if not isinstance(value, dict):
            continue
        stored = value.get('email_address_to_cep')
        if not isinstance(stored, str) or SEEDED_ADDRESS not in stored.lower():
            continue
        addresses = [
            a.strip() for a in stored.replace(';', ',').replace('\n', ',').split(',')
            if a.strip() and a.strip().lower() != SEEDED_ADDRESS
        ]
        value['email_address_to_cep'] = ', '.join(addresses)
        setting.value = value
        setting.save(update_fields=['value'])


class Migration(migrations.Migration):

    dependencies = [
        ('cis', '__first__'),
        ('drop_wd', '0005_historicaldropwdrequest'),
    ]

    operations = [
        migrations.RunPython(remove_seeded_address, migrations.RunPython.noop),
    ]
