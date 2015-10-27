import json
from django.db import models
from django.core.exceptions import ValidationError

from .managers import AnnotationManager, CommentManager



class Note(models.Model):
    """
    Annotation model.
    """

    # Permission types for a note.
    PERM_PERSONAL = 'personal'
    PERM_COURSE = 'course'
    PERM_TYPES = (
        (PERM_PERSONAL, 'Personal'),
        (PERM_COURSE, 'Course-wide'),
    )

    user_id = models.CharField(max_length=255, db_index=True, help_text="Anonymized user id, not course specific")
    course_id = models.CharField(max_length=255, db_index=True)
    usage_id = models.CharField(max_length=255, help_text="ID of XBlock where the text comes from")
    parent = models.ForeignKey('Note', blank=True, null=True, help_text="Parent note, if this is a comment")
    quote = models.TextField(default="")
    text = models.TextField(default="", blank=True, help_text="Student's thoughts on the quote")
    ranges = models.TextField(help_text="JSON, describes position of quote in the source text")
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)
    tags = models.TextField(help_text="JSON, list of comma-separated tags", default="[]")
    permission_type = models.CharField(
        max_length=100, choices=PERM_TYPES, default=PERM_PERSONAL, help_text="Permission level user must meet to see this.")


    objects = AnnotationManager()
    comments = CommentManager()

    @classmethod
    def create(cls, note_dict):
        """
        Create the note object.
        """
        if not isinstance(note_dict, dict):
            raise ValidationError('Note must be a dictionary.')

        if len(note_dict) == 0:
            raise ValidationError('Note must have a body.')

        ranges = note_dict.get('ranges', list())

        if len(ranges) < 1:
            raise ValidationError('Note must contain at least one range.')

        note_dict['ranges'] = json.dumps(ranges)
        note_dict['user_id'] = note_dict.pop('user', None)
        note_dict['tags'] = json.dumps(note_dict.get('tags', list()))

        return cls(**note_dict)

    @property
    def is_comment(self):
        return self.parent_id is not None

    def as_dict(self):
        """
        Returns the note object as a dictionary.
        """
        created = self.created.isoformat() if self.created else None
        updated = self.updated.isoformat() if self.updated else None
        result = {
            'id': str(self.pk),
            'user': self.user_id,
            'course_id': self.course_id,
            'usage_id': self.usage_id,
            'text': self.text,
            'created': created,
            'updated': updated,
        }

        if not self.is_comment:
            result.update({
                'quote': self.quote,
                'ranges': json.loads(self.ranges),
                'tags': json.loads(self.tags),
                'permission_type': self.permission_type,
            })
        return result
