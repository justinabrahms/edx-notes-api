from django.db.models import Manager

class AnnotationManager(Manager):
    """
    Returns Notes which are stand-alone annotations.
    """
    def get_queryset(self, *args, **kwargs):
        qs = super(AnnotationManager, self).get_queryset(*args, **kwargs)
        return qs.filter(parent__isnull=True)


class CommentManager(Manager):
    """
    Returns Notes which are comments on other notes.
    """
    def get_queryset(self, *args, **kwargs):
        qs = super(CommentManager, self).get_queryset(*args, **kwargs)
        return qs.filter(parent__isnull=False)
               
