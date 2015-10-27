# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('v1', '0003_note_parent'),
    ]

    operations = [
        migrations.AddField(
            model_name='note',
            name='permission_type',
            field=models.CharField(default=b'personal', help_text=b'Permission level user must meet to see this.', max_length=100, choices=[(b'personal', b'Personal'), (b'course', b'Course-wide')]),
            preserve_default=True,
        ),
    ]
