# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('v1', '0002_note_tags'),
    ]

    operations = [
        migrations.AddField(
            model_name='note',
            name='parent',
            field=models.ForeignKey(blank=True, to='v1.Note', help_text=b'Parent note, if this is a comment', null=True),
            preserve_default=True,
        ),
    ]
