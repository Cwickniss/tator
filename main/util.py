import logging
import os
import time
import subprocess
import json
import datetime
import shutil

from progressbar import progressbar,ProgressBar
from dateutil.parser import parse

from main.models import *
from main.search import TatorSearch
from main.search import mediaFileSizes

from django.conf import settings
from django.db.models import F

from elasticsearch import Elasticsearch
from elasticsearch.helpers import streaming_bulk

logger = logging.getLogger(__name__)

""" Utility scripts for data management in django-shell """

def clearDataAboutMedia(id):
    """
    Given an id Delete all states, localizations that apply.

    :param id: The id of the media element to purge metadata about.
    """
    #Delete all states by hitting associations which auto delete states
    qs=State.objects.filter(media__in=[id])
    qs.delete()

    #Delete all localizations
    qs=Localization.objects.filter(media=id)
    qs.delete()

def updateProjectTotals(force=False):
    projects=Project.objects.all()
    for project in projects:
        temp_files = TemporaryFile.objects.filter(project=project)
        files = Media.objects.filter(project=project)
        if (files.count() + temp_files.count() != project.num_files) or force:
            project.num_files = files.count() + temp_files.count()
            project.size = 0
            for file in temp_files.iterator():
                if file.path:
                    if os.path.exists(file.path):
                        project.size += os.path.getsize(file.path)
            for file in files.iterator():
                project.size += mediaFileSizes(file)[0]
            logger.info(f"Updating {project.name}: Num files = {project.num_files}, Size = {project.size}")
            project.save()

def waitForMigrations():
    """Sleeps until database objects can be accessed.
    """
    while True:
        try:
            list(Project.objects.all())
            break
        except:
            time.sleep(10)

def buildSearchIndices(project_number, section, mode='index'):
    """ Builds search index for a project.
        section must be one of:
        'index' - create the index for the project if it does not exist
        'mappings' - create mappings for the project if they do not exist
        'media' - create documents for media
        'states' - create documents for states
        'localizations' - create documents for localizations
        'treeleaves' - create documents for treeleaves
    """
    project_name = Project.objects.get(pk=project_number).name
    logger.info(f"Building search indices for project {project_number}: {project_name}")

    if section == 'index':
        # Create indices
        logger.info("Building index...")
        TatorSearch().create_index(project_number)
        logger.info("Build index complete!")
        return

    if section == 'mappings':
        # Create mappings
        logger.info("Building mappings for media types...")
        for type_ in progressbar(list(MediaType.objects.filter(project=project_number))):
            TatorSearch().create_mapping(type_)
        logger.info("Building mappings for localization types...")
        for type_ in progressbar(list(LocalizationType.objects.filter(project=project_number))):
            TatorSearch().create_mapping(type_)
        logger.info("Building mappings for state types...")
        for type_ in progressbar(list(StateType.objects.filter(project=project_number))):
            TatorSearch().create_mapping(type_)
        logger.info("Building mappings for leaf types...")
        for type_ in progressbar(list(LeafType.objects.filter(project=project_number))):
            TatorSearch().create_mapping(type_)
        logger.info("Build mappings complete!")
        return

    class DeferredCall:
        def __init__(self, qs):
            self._qs = qs
        def __call__(self):
            for entity in self._qs.iterator():
                for doc in TatorSearch().build_document(entity, mode):
                    yield doc

    if section == 'media':
        # Create media documents
        logger.info("Building media documents...")
        qs = Media.objects.filter(project=project_number)

    if section == 'localizations':
        # Create localization documents
        logger.info("Building localization documents")
        qs = Localization.objects.filter(project=project_number)

    if section == 'states':
        # Create state documents
        logger.info("Building state documents...")
        qs = State.objects.filter(project=project_number)

    if section == 'treeleaves':
        # Create treeleaf documents
        logger.info("Building tree leaf documents...")
        qs = Leaf.objects.filter(project=project_number)

    batch_size = 500
    count = 0
    bar = ProgressBar(redirect_stderr=True, redirect_stdout=True)
    dc = DeferredCall(qs)
    total = qs.count()
    bar.start(max_value=total)
    for ok, result in streaming_bulk(TatorSearch().es, dc(),chunk_size=batch_size, raise_on_error=False):
        action, result = result.popitem()
        if not ok:
            print(f"Failed to {action} document! {result}")
        bar.update(min(count, total))
        count += 1
        if count > total:
            print(f"Count exceeds list size by {total - count}")
    bar.finish()

def makeDefaultVersion(project_number):
    """ Creates a default version for a project and sets all localizations
        and states to that version. Meant for usage on projects that were
        not previously using versions.
    """
    project = Project.objects.get(pk=project_number)
    version = Version.objects.filter(project=project, number=0)
    if version.exists():
        version = version[0]
    else:
        version = make_default_version(project)
    logger.info("Updating localizations...")
    qs = Localization.objects.filter(project=project)
    qs.update(version=version)
    logger.info("Updating states...")
    qs = State.objects.filter(project=project)
    qs.update(version=version)

def clearStaleProgress(project, ptype):
    from redis import Redis
    if ptype not in ['upload', 'algorithm', 'transcode']:
        print("Unknown progress type")

    Redis(host=os.getenv('REDIS_HOST')).delete(f'{ptype}_latest_{project}')

from pprint import pprint

def make_video_definition(disk_file, url_path):
        cmd = [
        "ffprobe",
        "-v","error",
        "-show_entries", "stream",
        "-print_format", "json",
        disk_file,
        ]
        output = subprocess.run(cmd, stdout=subprocess.PIPE, check=True).stdout
        video_info = json.loads(output)
        stream_idx=0
        for idx, stream in enumerate(video_info["streams"]):
            if stream["codec_type"] == "video":
                stream_idx=idx
                break
        stream = video_info["streams"][stream_idx]
        video_def = getVideoDefinition(
            url_path,
            stream["codec_name"],
            (stream["height"], stream["width"]),
            codec_description=stream["codec_long_name"])

        return video_def

def migrateVideosToNewSchema(project):
    videos = Media.objects.filter(project=project, meta__dtype='video')
    for video in progressbar(videos):
        streaming_definition = make_video_definition(
            os.path.join(settings.MEDIA_ROOT,
                         video.file.name),
            os.path.join(settings.MEDIA_URL,
                         video.file.name))
        if video.segment_info:
            streaming_definition['segment_info'] = os.path.relpath(
                video.segment_info,
                '/data')
        if video.original:
            archival_definition = make_video_definition(video.original,
                                                        video.original)
        media_files = {"streaming" : [streaming_definition]}

        if archival_definition:
            media_files.update({"archival": [archival_definition]})
        video.media_files = media_files
        pprint(media_files)
        video.save()

def fixVideoDims(project):
    videos = Media.objects.filter(project=project, meta__dtype='video')
    for video in progressbar(videos):
        try:
            if video.original:
                archival_definition = make_video_definition(video.original,
                                                            video.original)
                video.height = archival_definition["resolution"][0]
                video.width = archival_definition["resolution"][1]
                video.save()
        except:
            print(f"Error on {video.pk}")

def clearOldFilebeatIndices():
    es = Elasticsearch([os.getenv('ELASTICSEARCH_HOST')])
    for index in es.indices.get('filebeat-*'):
        tokens = str(index).split('-')
        if len(tokens) < 3:
            continue
        dt = parse(tokens[2])
        delta = datetime.datetime.now() - dt
        if delta.days > 7:
            logger.info(f"Deleting old filebeat index {index}")
            es.indices.delete(str(index))


def soft_link_media(source, section_list, dest):
    dest_proj = Project.objects.get(pk=dest)
    dest_type = MediaType.objects.filter(project=dest_proj,dtype="video")[0]
    for section in section_list:
        original_videos=Media.objects.filter(project=source, attributes__tator_user_sections=section)
        print(f"copying {original_videos.count()} {source}:{section} to {dest}")
        for video in original_videos:
            new_obj=video
            new_obj.pk=None
            new_obj.project = dest_proj
            new_obj.meta=dest_type
            originals = new_obj.media_files["archival"]
            for idx,orig in enumerate(originals):
                name=os.path.basename(orig['path'])
                new_path=os.path.join("/data/raw", str(dest), name)
                try:
                    os.symlink(orig['path'], new_path)
                except Exception as e:
                    print("Already copied")
                new_obj.media_files["archival"][idx]['path']=new_path
                Resource.add_resource(new_path)
            streaming = new_obj.media_files["streaming"]
            for idx,stream in enumerate(streaming):
                name=os.path.basename(stream['path'])
                new_path=os.path.join("media", str(dest), name)
                try:
                    if os.path.isabs(stream['path']):
                        source=f"/data{stream['path']}"
                    else:
                        source=os.path.join("/data", stream['path'])
                    os.symlink(source, os.path.join('/data',new_path))
                except Exception as e:
                    print(f"Already copied {e}")
                Resource.add_resource(os.path.join('/data',new_path))
                new_obj.media_files["streaming"][idx]['path']="/"+new_path
                name=os.path.basename(stream['segment_info'])
                new_path=os.path.join("media", str(dest), name)
                try:
                    if os.path.isabs(stream['segment_info']):
                        source=f"/data{stream['segment_info']}"
                    else:
                        source=os.path.join("/data", stream['segment_info'])
                    os.symlink(source, os.path.join('/data',new_path))
                except Exception as e:
                    print(f"Already copied {e}")
                Resource.add_resource(os.path.join('/data',new_path))
                new_obj.media_files["streaming"][idx]['segment_info']=new_path

            #Handle thumbnail
            orig_thumb = new_obj.thumbnail.name
            name = os.path.basename(orig_thumb)
            orig_thumb_path = os.path.join("/data/media", orig_thumb)
            new_thumb = os.path.join("/data/media/",str(dest), name)
            try:
                shutil.copyfile(orig_thumb_path, new_thumb)
            except Exception as e:
                print(f"Already copied thumbnail {e}")
            new_obj.thumbnail = os.path.join(str(dest),name)

            rig_thumb = new_obj.thumbnail_gif.name
            name = os.path.basename(orig_thumb)
            orig_thumb_path = os.path.join("/data/media", orig_thumb)
            new_thumb = os.path.join("/data/media/",str(dest), name)
            try:
                shutil.copyfile(orig_thumb_path, new_thumb)
            except Exception as e:
                print(f"Already copied thumbnail {e}")
            new_obj.thumbnail_gif = os.path.join(str(dest),name)

            new_obj.save()
