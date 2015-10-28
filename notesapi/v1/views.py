import logging
import json

from django.conf import settings
from django.core.urlresolvers import reverse
from django.core.exceptions import ValidationError
from django.db.models import Q

from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from haystack.query import SQ

from notesapi.v1.models import Note

if not settings.ES_DISABLED:
    from notesserver.highlight import SearchQuerySet

log = logging.getLogger(__name__)


def get_offset_limit_from_query_params(params):
    offset = int(params.get('offset', 0))
    limit = min(int(params.get('limit', settings.MAX_PAGINATED_RESULTS)), settings.MAX_PAGINATED_RESULTS)

    return offset, limit


class AnnotationSearchView(APIView):
    """
    Search annotations.
    """
    def get(self, *args, **kwargs):  # pylint: disable=unused-argument
        """
        Search annotations in most appropriate storage
        """
        # search in DB when ES is not available or there is no need to bother it
        if settings.ES_DISABLED or 'text' not in self.request.QUERY_PARAMS.dict():
            results = self.get_from_db(*args, **kwargs)
        else:
            results = self.get_from_es(*args, **kwargs)
        return Response({'total': len(results), 'rows': results})

    def get_from_db(self, *args, **kwargs):  # pylint: disable=unused-argument
        """
        Search annotations in database
        """
        params = self.request.QUERY_PARAMS.dict()
        offset, limit = get_offset_limit_from_query_params(params)
        query = Note.objects.filter(
            **{f: v for (f, v) in params.items() if f in ('course_id', 'usage_id')}
        ).order_by('-updated')

        if 'user' in params:
            query = query.filter(user_id=params['user'])

        query = query.filter(permission_type=getattr(params, 'perm', Note.PERM_PERSONAL))

        if 'text' in params:
            query = query.filter(Q(text__icontains=params['text']) | Q(tags__icontains=params['text']))

        return [note.as_dict() for note in query[offset:offset+limit]]

    def get_from_es(self, *args, **kwargs):  # pylint: disable=unused-argument
        """
        Search annotations in ElasticSearch
        """
        params = self.request.QUERY_PARAMS.dict()
        offset, limit = get_offset_limit_from_query_params(params)
        query = SearchQuerySet().models(Note).filter(
            **{f: v for (f, v) in params.items() if f in ('user', 'course_id', 'usage_id')}
        )

        if 'text' in params:
            clean_text = query.query.clean(params['text'])
            query = query.filter(SQ(data=clean_text))

        if params.get('highlight'):
            tag = params.get('highlight_tag', 'em')
            klass = params.get('highlight_class')
            opts = {
                'pre_tags': ['<{tag}{klass_str}>'.format(
                    tag=tag,
                    klass_str=' class=\\"{}\\"'.format(klass) if klass else ''
                )],
                'post_tags': ['</{tag}>'.format(tag=tag)],
            }
            query = query.highlight(**opts)

        results = []
        for item in query[offset:offset+limit]:
            note_dict = item.get_stored_fields()
            note_dict['ranges'] = json.loads(item.ranges)
            # If ./manage.py rebuild_index has not been run after tags were added, item.tags will be None.
            note_dict['tags'] = json.loads(item.tags) if item.tags else []
            note_dict['id'] = str(item.pk)
            if item.highlighted:
                note_dict['text'] = item.highlighted[0].decode('unicode_escape')
            if item.highlighted_tags:
                note_dict['tags'] = json.loads(item.highlighted_tags[0])
            results.append(note_dict)

        return results


class AnnotationListView(APIView):
    """
    List all annotations or create.
    """

    def get(self, *args, **kwargs):  # pylint: disable=unused-argument
        """
        Get a list of all annotations.
        """
        params = self.request.QUERY_PARAMS.dict()
        offset, limit = get_offset_limit_from_query_params(params)

        if 'course_id' not in params or 'user' not in params:
            return Response(status=status.HTTP_400_BAD_REQUEST)

        results = Note.objects.filter(course_id=params['course_id']).order_by('-updated')
        # Users can see the comments they've made, in addition to all course
        # level permissions.
        results = results.filter(Q(user_id=params['user'],
                                   permission_type=Note.PERM_PERSONAL) |
                                 Q(permission_type=Note.PERM_COURSE))

        return Response([result.as_dict() for result in results[offset:offset+limit]])

    def post(self, *args, **kwargs):  # pylint: disable=unused-argument
        """
        Create a new annotation.

        Returns 400 request if bad payload is sent or it was empty object.
        """
        if 'id' in self.request.DATA:
            return Response(status=status.HTTP_400_BAD_REQUEST)

        try:
            note = Note.create(self.request.DATA)
            note.full_clean()
        except ValidationError as error:
            log.debug(error, exc_info=True)
            return Response(status=status.HTTP_400_BAD_REQUEST)

        note.save()

        location = reverse('api:v1:annotations_detail', kwargs={'annotation_id': note.id})

        return Response(note.as_dict(), status=status.HTTP_201_CREATED, headers={'Location': location})


class AnnotationDetailView(APIView):
    """
    Annotation detail view.
    """

    UPDATE_FILTER_FIELDS = ('updated', 'created', 'user', 'consumer')

    def _fetch(self, annotation_id, reply_id=None, user_id=None):
        """
        Annotation-type or Comment-type agnostic Note fetcher.

        Returns a Note instance if found or throws Note.DoesNotExist.
        """

        if reply_id:
            note = Note.comments.get(id=reply_id, parent_id=annotation_id)
        else:
            qs = Note.objects
            if user_id:
                # When you're driving via the web API browser, there is no
                # user_id because we don't have authentication there.
                qs = qs.filter(Q(user_id=user_id, permission_type=Note.PERM_PERSONAL) |
                               Q(permission_type=Note.PERM_COURSE))
            note = qs.get(id=annotation_id)

        return note

    def get(self, *args, **kwargs):  # pylint: disable=unused-argument
        """
        Get an existing annotation.
        """
        user = self.request.QUERY_PARAMS.get('user', None)
        
        try:
            note = self._fetch(self.kwargs.get('annotation_id'), self.kwargs.get('reply_id'), user_id=user)
        except Note.DoesNotExist:
            return Response('Annotation not found!', status=status.HTTP_404_NOT_FOUND)

        return Response(note.as_dict())

    def put(self, *args, **kwargs):  # pylint: disable=unused-argument
        """
        Update an existing annotation.
        """
        user = self.request.data.get('user', None)
        try:
            note = self._fetch(self.kwargs.get('annotation_id'), self.kwargs.get('reply_id'), user_id=user)
        except Note.DoesNotExist:
            return Response('Annotation not found! No update performed.', status=status.HTTP_404_NOT_FOUND)

        try:
            note.text = self.request.data['text']
            note.tags = json.dumps(self.request.data['tags'])
            note.full_clean()
        except KeyError as error:
            log.debug(error, exc_info=True)
            return Response(status=status.HTTP_400_BAD_REQUEST)

        note.save()
        return Response(note.as_dict())

    def delete(self, *args, **kwargs):  # pylint: disable=unused-argument
        """
        Delete an annotation.
        """
        user = self.request.data.get('user', None)
        try:
            note = self._fetch(self.kwargs.get('annotation_id'), self.kwargs.get('reply_id'), user_id=user)
        except Note.DoesNotExist:
            return Response('Annotation not found! No update performed.', status=status.HTTP_404_NOT_FOUND)

        if note.user_id != user:
            return Response("You cannot delete annotations you didn't create.", status=status.HTTP_403_FORBIDDEN)

        note.delete()

        # Annotation deleted successfully.
        return Response(status=status.HTTP_204_NO_CONTENT)


class ReplyListView(APIView):
    """
    List all comments on a particular annotation or create.
    """
    def get(self, *args, **kwargs):    # pylint: disable=unused-argument
        """
        Fetch list of comments for a particular annotation.
        """

        params = self.request.QUERY_PARAMS.dict()
        offset, limit = get_offset_limit_from_query_params(params)

        note_id = self.kwargs.get('annotation_id')
        results = Note.comments.filter(parent_id=note_id).order_by('-created')

        return Response([result.as_dict() for result in results[offset:offset+limit]])

    def post(self, *args, **kwargs):  # pylint: disable=unused-argument
        """
        Create a new reply for an annotation.

        Returns 400 request if bad payload is sent or it was empty object.
        """
        if 'id' in self.request.DATA:
            return Response(status=status.HTTP_400_BAD_REQUEST)

        # Copy some data from the original Note object.
        ann = Note.objects.get(id=self.kwargs.get('annotation_id'))
        self.request.DATA['parent_id'] = ann.id
        self.request.DATA['course_id'] = ann.course_id
        self.request.DATA['usage_id'] = ann.usage_id

        try:
            note = Note.create(self.request.DATA)
            note.full_clean()
        except ValidationError as error:
            log.debug(error, exc_info=True)
            return Response(status=status.HTTP_400_BAD_REQUEST)

        note.save()

        location = reverse('api:v1:annotations_comment_detail', kwargs={'annotation_id': note.parent_id, 'reply_id': note.id})
        return Response(note.as_dict(), status=status.HTTP_201_CREATED, headers={'Location': location})
