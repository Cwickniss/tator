import logging
import os
import mimetypes
from uuid import uuid1

from rest_framework.authtoken.models import Token
from django.conf import settings

from ..kube import TatorMove
from ..models import Media
from ..schema import MoveVideoSchema
from ..cache import TatorCache

from ._base_views import BaseListView
from ._permissions import ProjectTransferPermission

logger = logging.getLogger(__name__)

def get_destination_path(default):
    media_shards = os.getenv('MEDIA_SHARDS')
    if media_shards is None:
        return default
    else:
        return f"/{random.choice(media_shards.split(','))}"

def get_upload_uid(url):
    return TatorCache().get_upload_uid_cache(url)

class MoveVideoAPI(BaseListView):
    """ Moves a video file.

        This endpoint creates an Argo workflow that moves an uploaded video file into the
        appropriate project directory. When the move is complete, the workflow will make
        a PATCH request to the Media endpoint for the given media ID using the given 
        `media_files` definitions.

        Videos in Tator must be transcoded to a multi-resolution streaming format before they
        can be viewed or annotated. To launch a transcode on raw uploaded video, use the
        `Transcode` endpoint, which will create an Argo workflow to perform the transcode
        and save the video using this endpoint; no further REST calls are required. However,
        if you would like to perform transcodes locally, this endpoint enables that. The
        module `tator.transcode` in the tator pip package provides local transcode capability
        using this endpoint.
    """
    schema = MoveVideoSchema()
    permission_classes = [ProjectTransferPermission]
    http_method_names = ['post']

    def _post(self, params):
        # Get the project
        media = Media.objects.get(pk=params['id'])
        project = media.project.pk

        # Get the token
        token, _ = Token.objects.get_or_create(user=self.request.user)

        # Determine the move paths and update media_files with new paths.
        media_files = params['media_files']
        move_list = []
        if 'archival' in media_files:
            for video_def in media_files['archival']:

                # Determine extension based on codec_mime field, if present. If it is
                # not present, assume the file is a copy of the original with a name
                # matching the name of the media record.
                if 'codec_mime' in video_def:
                    ext = mimetypes.guess_extension(video_def['codec_mime'].split(';')[0])
                else:
                    ext = os.path.splitext(media.name)[1]
                upload_base = os.path.basename(video_def['url'])
                path = f"{project}/{str(uuid1())}{ext}"
                dst = os.path.join(get_destination_path(settings.RAW_ROOT), path)
                upload_uid = get_upload_uid(video_def['url'])
                move_list.append({
                    'url': upload_base,
                    'dst': dst,
                    'upload_uid': upload_uid,
                })
                video_def['path'] = dst
                del video_def['url']
                logger.info(f"ARCHIVAL UPLOAD")
                logger.info(f"URL: {upload_base}")
                logger.info(f"DST: {dst}")
                logger.info(f"UPLOAD_UID: {upload_uid}")
        if 'streaming' in media_files:
            for video_def in media_files['streaming']:
                upload_base = os.path.basename(video_def['url'])
                segment_upload_base = os.path.basename(video_def['segments_url'])
                uuid = str(uuid1())
                path = f"{project}/{uuid}.mp4"
                segment_info = f"{project}/{uuid}_segments.json"
                dst = os.path.join(get_destination_path(settings.MEDIA_ROOT), path)
                segment_dst = os.path.join(get_destination_path(settings.MEDIA_ROOT), segment_info)
                upload_uid = get_upload_uid(video_def['url'])
                segment_upload_uid = get_upload_uid(video_def['segments_url'])
                move_list += [{
                    'url': upload_base,
                    'dst': dst,
                    'upload_uid': upload_uid,
                }, {
                    'url': segment_upload_base,
                    'dst': segment_dst,
                    'upload_uid': segment_upload_uid,
                }]
                video_def['path'] = '/media/' + path
                video_def['segment_info'] = '/media/' + segment_info
                del video_def['url']
                del video_def['segments_url']
                logger.info(f"STREAMING UPLOAD")
                logger.info(f"URL: {upload_base}")
                logger.info(f"DST: {dst}")
                logger.info(f"UPLOAD_UID: {upload_uid}")
                logger.info(f"URL: {segment_upload_base}")
                logger.info(f"DST: {segment_dst}")
                logger.info(f"UPLOAD_UID: {segment_upload_uid}")
        if 'audio' in media_files:
            for audio_def in media_files['audio']:
                upload_base = os.path.basename(audio_def['url'])
                path = f"{project}/{str(uuid1())}.m4a"
                dst = os.path.join(get_destination_path(settings.MEDIA_ROOT), path)
                upload_uid = get_upload_uid(audeo_def['url'])
                move_list.append({
                    'url': audio_def['url'],
                    'dst': dst,
                    'upload_uid': upload_uid,
                })
                audio_def['path'] = '/media/' + path
                del audio_def['url']
                logger.info(f"AUDIO UPLOAD")
                logger.info(f"URL: {upload_base}")
                logger.info(f"DST: {dst}")
                logger.info(f"UPLOAD_UID: {upload_uid}")

        # Create the move workflow
        """
        response = TatorMove().move_video(project, params['id'], str(token), move_list,
                                          media_files, media.gid, media.uid)

        """
        response_data = {'message': f"Moving video for media {params['id']} in workflow "
                                    f"{response['metadata']['name']}!",
                         'id': params['id']}
        return response_data
        
    def get_queryset(self):
        return Media.objects.all()
