from django.conf.urls import patterns, url
from notesapi.v1.views import (
    AnnotationListView, AnnotationDetailView, AnnotationSearchView,
    ReplyListView
)

urlpatterns = patterns(
    '',
    url(r'^annotations/$', AnnotationListView.as_view(), name='annotations'),
    url(
        r'^annotations/(?P<annotation_id>[a-zA-Z0-9_-]+)/?$',
        AnnotationDetailView.as_view(),
        name='annotations_detail'
    ),
    url(
        r'^annotations/(?P<annotation_id>[a-zA-Z0-9_-]+)/replies/?$',
        ReplyListView.as_view(),
        name='annotations_comments'
    ),
    url(
        r'^annotations/(?P<annotation_id>[a-zA-Z0-9_-]+)/replies/(?P<reply_id>[a-zA-Z0-9_-]+)?$',
        AnnotationDetailView.as_view(),
        name='annotations_comments_detail'
    ),
    url(r'^search/$', AnnotationSearchView.as_view(), name='annotations_search'),
)
