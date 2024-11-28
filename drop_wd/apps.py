from django.apps import AppConfig

class DropWdConfig(AppConfig):
    name = 'drop_wd'

    CONFIGURATORS = [
            {
            'app': 'drop_wd',
            'name': 'drop_wd_email',
            'title': 'Drop/WD Request Settings - Test',
            'description': '-',
            'categories': [
                '3'
            ]
        },
    ]

    REPORTS = [
        {
            'app': 'drop_wd',
            'name': 'drop_wd_requests',
            'title': 'Drop/WD Requests Export',
            'description': '-',
            'categories': [
                'Classes'
            ],
            'available_for': [
                'ce'
            ]
        },
    ]
    def ready(self):
        import drop_wd.signals