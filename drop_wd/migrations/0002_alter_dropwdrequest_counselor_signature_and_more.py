# Generated by Django 4.2 on 2024-11-28 18:26

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('drop_wd', '0001_initial'),
    ]

    operations = [
        migrations.AlterField(
            model_name='dropwdrequest',
            name='counselor_signature',
            field=models.CharField(choices=[('Not Needed', 'Not Needed'), ('Pending', 'Pending'), ('Approved', 'Approved'), ('Not Approved', 'Not Approved')], default='Not Needed', max_length=50),
        ),
        migrations.AlterField(
            model_name='dropwdrequest',
            name='instructor_signature',
            field=models.CharField(choices=[('Not Needed', 'Not Needed'), ('Pending', 'Pending'), ('Approved', 'Approved'), ('Not Approved', 'Not Approved')], default='Not Needed', max_length=50),
        ),
        migrations.AlterField(
            model_name='dropwdrequest',
            name='parent_signature',
            field=models.CharField(choices=[('Not Needed', 'Not Needed'), ('Pending', 'Pending'), ('Approved', 'Approved'), ('Not Approved', 'Not Approved')], default='Not Needed', max_length=50),
        ),
        migrations.AlterField(
            model_name='dropwdrequest',
            name='student_signature',
            field=models.CharField(choices=[('Not Needed', 'Not Needed'), ('Pending', 'Pending'), ('Approved', 'Approved'), ('Not Approved', 'Not Approved')], default='Not Needed', max_length=50),
        ),
    ]
