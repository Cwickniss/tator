import os
import logging
import tempfile
import copy
import tarfile

from django.conf import settings

from kubernetes.client import Configuration
from kubernetes.client import ApiClient
from kubernetes.client import CoreV1Api
from kubernetes.client import CustomObjectsApi
from kubernetes.config import load_incluster_config
import yaml

from .consumers import ProgressProducer
from .version import Git

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

def get_marshal_image_name():
    """ Returns the location and version of the marshal image to use """
    registry = os.getenv('SYSTEM_IMAGES_REGISTRY')
    return f"{registry}/tator_algo_marshal:{Git.sha}"

class JobManagerMixin:
    """ Defines functions for job management.
    """
    def _get_progress_aux(self, job):
        raise NotImplementedError

    def _cancel_message(self):
        raise NotImplementedError

    def _job_type(self):
        raise NotImplementedError

    def find_project(self, selector):
        """ Finds the project associated with a given selector.
        """
        project = None
        response = self.custom.list_namespaced_custom_object(
            group='argoproj.io',
            version='v1alpha1',
            namespace='default',
            plural='workflows',
            label_selector=selector,
        )
        if len(response['items']) > 0:
            project = int(response['items'][0]['metadata']['labels']['project'])
        return project

    def cancel_jobs(self, selector):
        """ Deletes argo workflows by selector.
        """
        cancelled = False

        # Get the object by selecting on uid label.
        response = self.custom.list_namespaced_custom_object(
            group='argoproj.io',
            version='v1alpha1',
            namespace='default',
            plural='workflows',
            label_selector=f'{selector},job_type={self._job_type()}',
        )

        # Delete the object.
        if len(response['items']) > 0:
            for job in response['items']:
                name = job['metadata']['name']
                response = self.custom.delete_namespaced_custom_object(
                    group='argoproj.io',
                    version='v1alpha1',
                    namespace='default',
                    plural='workflows',
                    name=name,
                    body={},
                    grace_period_seconds=0,
                )
                if response['status'] == 'Success':
                    cancelled = True
                    prog = ProgressProducer(
                        self._job_type(),
                        int(job['metadata']['labels']['project']),
                        job['metadata']['labels']['gid'],
                        job['metadata']['labels']['uid'],
                        job['metadata']['annotations']['name'],
                        int(job['metadata']['labels']['user']),
                        self._get_progress_aux(job),
                    )
                    prog.failed(self._cancel_message())
        return cancelled

class TatorTranscode(JobManagerMixin):
    """ Interface to kubernetes REST API for starting transcodes.
    """

    def __init__(self):
        """ Intializes the connection. If environment variables for
            remote transcode are defined, connect to that cluster.
        """
        host = os.getenv('REMOTE_TRANSCODE_HOST')
        port = os.getenv('REMOTE_TRANSCODE_PORT')
        token = os.getenv('REMOTE_TRANSCODE_TOKEN')
        cert = os.getenv('REMOTE_TRANSCODE_CERT')

        if host:
            conf = Configuration()
            conf.api_key['authorization'] = token
            conf.host = f'https://{host}:{port}'
            conf.verify_ssl = True
            conf.ssl_ca_cert = cert
            api_client = ApiClient(conf)
            self.corev1 = CoreV1Api(api_client)
            self.custom = CustomObjectsApi(api_client)
        else:
            load_incluster_config()
            self.corev1 = CoreV1Api()
            self.custom = CustomObjectsApi()

        self.setup_common_steps()

    def setup_common_steps(self):
        """ Sets up the basic steps for a transcode pipeline.

            TODO: Would be nice if this was just in a yaml file.
        """
        # Setup common pipeline steps
        # Define persistent volume claim.
        self.pvc = {
            'metadata': {
                'name': 'transcode-scratch',
            },
            'spec': {
                'storageClassName': 'nfs-client',
                'accessModes': [ 'ReadWriteOnce' ],
                'resources': {
                    'requests': {
                        'storage': '10Gi',
                    }
                }
            }
        }

        def spell_out_params(params):
            yaml_params = [{"name": x} for x in params]
            return yaml_params

        # Define each task in the pipeline.

        # Download task exports the human readable filename a
        # workflow global to support the onExit handler
        self.download_task = {
            'name': 'download',
            'retryStrategy': {
                'limit': 3,
                'retryOn': "Always",
                'backoff': {
                    'duration': 1,
                    'factor': 2,
                    'maxDuration': "1m",
                },
            },
            'inputs': {'parameters' : spell_out_params(['original',
                                                        'url'])},
            'container': {
                'image': '{{workflow.parameters.transcoder_image}}',
                'imagePullPolicy': 'IfNotPresent',
                'command': ['curl',],
                'args': ['-o', '{{inputs.parameters.original}}', '{{inputs.parameters.url}}'],
                'volumeMounts': [{
                    'name': 'transcode-scratch',
                    'mountPath': '/work',
                }],
                'resources': {
                    'limits': {
                        'memory': '512Mi',
                        'cpu': '500m',
                    },
                },
            },
        }

        # Deletes the remote TUS file
        self.delete_task = {
            'name': 'delete',
            'inputs': {'parameters' : spell_out_params(['url'])},
            'container': {
                'image': '{{workflow.parameters.transcoder_image}}',
                'imagePullPolicy': 'IfNotPresent',
                'command': ['curl',],
                'args': ['-X', 'DELETE', '{{inputs.parameters.url}}'],
                'resources': {
                    'limits': {
                        'memory': '128Mi',
                        'cpu': '500m',
                    },
                },
            },
        }


        # Unpacks a tarball and sets up the work products for follow up
        # dags or steps
        self.unpack_task = {
            'name': 'unpack',
            'inputs': {'parameters' : spell_out_params(['original'])},
            'outputs': {'parameters' : [{'name': 'videos',
                                         'valueFrom': {'path': '/work/videos.json'}},
                                        {'name': 'images',
                                         'valueFrom': {'path': '/work/images.json'}},
                                        {'name': 'localizations',
                                         'valueFrom': {'path': '/work/localizations.json'}},
                                        {'name': 'states',
                                         'valueFrom': {'path': '/work/states.json'}},
            ]},
            'container': {
                'image': '{{workflow.parameters.transcoder_image}}',
                'imagePullPolicy': 'IfNotPresent',
                'env': [{'name': 'TATOR_URL', 'value': '{{workflow.parameters.rest_url}}'},
                        {'name': 'TATOR_PROJECT', 'value': '{{workflow.parameters.project}}'},
                        {'name': 'TATOR_TOKEN', 'value': '{{workflow.parameters.token}}'}],
                'command': ['bash',],
                'args': ['unpack.sh', '{{inputs.parameters.original}}', '/work'],
                'volumeMounts': [{
                    'name': 'transcode-scratch',
                    'mountPath': '/work',
                }],
                'resources': {
                    'limits': {
                        'memory': '512Mi',
                        'cpu': '1000m',
                    },
                },
            },
        }

        self.data_import = {
            'name': 'data-import',
            'inputs': {'parameters' : spell_out_params(['md5', 'file', 'mode'])},
            'container': {
                'image': '{{workflow.parameters.transcoder_image}}',
                'imagePullPolicy': 'IfNotPresent',
                'command': ['python3',],
                'args': ['importDataFromCsv.py',
                         '--url', '{{workflow.parameters.rest_url}}',
                         '--token', '{{workflow.parameters.token}}',
                         '--project', '{{workflow.parameters.project}}',
                         '--mode', '{{inputs.parameters.mode}}',
                         '--media-md5', '{{inputs.parameters.md5}}',
                         '{{inputs.parameters.file}}'],
                'volumeMounts': [{
                    'name': 'transcode-scratch',
                    'mountPath': '/work',
                }],
                'resources': {
                    'limits': {
                        'memory': '512Mi',
                        'cpu': '1000m',
                    },
                },
            },
        }

        self.transcode_task = {
            'name': 'transcode',
            'inputs': {'parameters' : spell_out_params(['original','transcoded'])},
            'container': {
                'image': '{{workflow.parameters.transcoder_image}}',
                'imagePullPolicy': 'IfNotPresent',
                'command': ['python3',],
                'args': [
                    'transcode.py',
                    '--output', '{{inputs.parameters.transcoded}}',
                    '{{inputs.parameters.original}}'
                ],
                'workingDir': '/scripts',
                'volumeMounts': [{
                    'name': 'transcode-scratch',
                    'mountPath': '/work',
                }],
                'resources': {
                    'limits': {
                        'memory': '2Gi',
                        'cpu': '4000m',
                    },
                },
            },
        }
        self.thumbnail_task = {
            'name': 'thumbnail',
            'inputs': {'parameters' : spell_out_params(['original','thumbnail', 'thumbnail_gif'])},
            'container': {
                'image': '{{workflow.parameters.transcoder_image}}',
                'imagePullPolicy': 'IfNotPresent',
                'command': ['python3',],
                'args': [
                    'makeThumbnails.py',
                    '--output', '{{inputs.parameters.thumbnail}}',
                    '--gif', '{{inputs.parameters.thumbnail_gif}}',
                    '{{inputs.parameters.original}}',
                ],
                'workingDir': '/scripts',
                'volumeMounts': [{
                    'name': 'transcode-scratch',
                    'mountPath': '/work',
                }],
                'resources': {
                    'limits': {
                        'memory': '500Mi',
                        'cpu': '1000m',
                    },
                },
            },
        }

        self.image_upload_task = {
            'name': 'image-upload',
            'inputs': {'parameters' : spell_out_params(['url',
                                                        'original',
                                                        'entity_type',
                                                        'name',
                                                        'md5'])},
            'container': {
                'image': '{{workflow.parameters.transcoder_image}}',
                'imagePullPolicy': 'IfNotPresent',
                'command': ['python3',],
                'args': [
                    'uploadImage.py',
                    '--original_path', '{{inputs.parameters.original}}',
                    '--original_url', '{{inputs.parameters.url}}',
                    '--tus_url', '{{workflow.parameters.tus_url}}',
                    '--url', '{{workflow.parameters.rest_url}}',
                    '--token', '{{workflow.parameters.token}}',
                    '--project', '{{workflow.parameters.project}}',
                    '--type', '{{inputs.parameters.entity_type}}',
                    '--gid', '{{workflow.parameters.gid}}',
                    '--uid', '{{workflow.parameters.uid}}',
                    # TODO: If we made section a DAG argument, we could
                    # conceviably import a tar across multiple sections
                    '--section', '{{workflow.parameters.section}}',
                    '--name', '{{inputs.parameters.name}}',
                    '--md5', '{{inputs.parameters.md5}}',
                    '--progressName', '{{workflow.parameters.upload_name}}',
                ],
                'workingDir': '/scripts',
                'volumeMounts': [{
                    'name': 'transcode-scratch',
                    'mountPath': '/work',
                }],
                'resources': {
                    'limits': {
                        'memory': '500Mi',
                        'cpu': '1000m',
                    },
                },
            },
        }

        self.upload_task = {
            'name': 'upload',
            'inputs': {'parameters' : spell_out_params(['url',
                                                        'original',
                                                        'transcoded',
                                                        'thumbnail',
                                                        'thumbnail_gif',
                                                        'segments',
                                                        'entity_type',
                                                        'name',
                                                        'md5'])},
            'container': {
                'image': '{{workflow.parameters.transcoder_image}}',
                'imagePullPolicy': 'IfNotPresent',
                'command': ['python3',],
                'args': [
                    'uploadTranscodedVideo.py',
                    '--original_path', '{{inputs.parameters.original}}',
                    '--original_url', '{{inputs.parameters.url}}',
                    '--transcoded_path', '{{inputs.parameters.transcoded}}',
                    '--thumbnail_path', '{{inputs.parameters.thumbnail}}',
                    '--thumbnail_gif_path', '{{inputs.parameters.thumbnail_gif}}',
                    '--tus_url', '{{workflow.parameters.tus_url}}',
                    '--url', '{{workflow.parameters.rest_url}}',
                    '--token', '{{workflow.parameters.token}}',
                    '--project', '{{workflow.parameters.project}}',
                    '--type', '{{inputs.parameters.entity_type}}',
                    '--gid', '{{workflow.parameters.gid}}',
                    '--uid', '{{workflow.parameters.uid}}',
                    # TODO: If we made section a DAG argument, we could
                    # conceviably import a tar across multiple sections
                    '--section', '{{workflow.parameters.section}}',
                    '--name', '{{inputs.parameters.name}}',
                    '--md5', '{{inputs.parameters.md5}}',
                    '--progressName', '{{workflow.parameters.upload_name}}',
                ],
                'workingDir': '/scripts',
                'volumeMounts': [{
                    'name': 'transcode-scratch',
                    'mountPath': '/work',
                }],
                'resources': {
                    'limits': {
                        'memory': '500Mi',
                        'cpu': '1000m',
                    },
                },
            },
        }

        # Define task to send progress message in case of failure.
        self.progress_task = {
            'name': 'progress',
            'inputs': {'parameters' : spell_out_params(['state',
                                                        'message',
                                                        'progress'])},
            'container': {
                'image': '{{workflow.parameters.marshal_image}}',
                'imagePullPolicy': 'IfNotPresent',
                'command': ['python3',],
                'args': [
                    'sendProgress.py',
                    '--url', '{{workflow.parameters.rest_url}}',
                    '--token', '{{workflow.parameters.token}}',
                    '--project', '{{workflow.parameters.project}}',
                    '--job_type', 'upload',
                    '--gid', '{{workflow.parameters.gid}}',
                    '--uid', '{{workflow.parameters.uid}}',
                    '--state', '{{inputs.parameters.state}}',
                    '--message', '{{inputs.parameters.message}}',
                    '--progress', '{{inputs.parameters.progress}}',
                    # Pull the name from the upload parameter
                    '--name', '{{workflow.parameters.upload_name}}',
                    '--section', '{{workflow.parameters.section}}',
                ],
                'workingDir': '/',
                'resources': {
                    'limits': {
                        'memory': '32Mi',
                        'cpu': '100m',
                    },
                },
            },
        }

        # Define a exit handler.
        self.exit_handler = {
            'name': 'exit-handler',
            'steps': [[
                {
                    'name': 'send-fail',
                    'template': 'progress',
                    'when': '{{workflow.status}} != Succeeded',
                    'arguments' : {'parameters':
                                   [
                                       {'name': 'state', 'value': 'failed'},
                                       {'name': 'message', 'value': 'Media Import Failed'},
                                       {'name': 'progress', 'value': '0'},
                                   ]
                    }
                },
                {
                    'name': 'send-success',
                    'template': 'progress',
                    'when': '{{workflow.status}} == Succeeded',
                    'arguments' : {'parameters':
                                   [
                                       {'name': 'state', 'value': 'finished'},
                                       {'name': 'message', 'value': 'Media Import Complete'},
                                       {'name': 'progress', 'value': '100'},
                                   ]
                    }
                }
            ]],
        }

    def get_unpack_and_transcode_tasks(self, paths, url):
        """ Generate a task object describing the dependencies of a transcode from tar"""

        # Generate an args structure for the DAG
        args = [{'name': 'url', 'value': url}]
        for key in paths:
            args.append({'name': key, 'value': paths[key]})
        parameters = {"parameters" : args}

        def make_item_arg(name):
            return {'name': name,
                    'value': f'{{{{item.{name}}}}}'}

        instance_args = ['url',
                         'original',
                         'transcoded',
                         'thumbnail',
                         'thumbnail_gif',
                         'segments',
                         'entity_type',
                         'name',
                         'md5']

        item_parameters = {"parameters" : [make_item_arg(x) for x in instance_args]}
        state_import_parameters = {"parameters" : [make_item_arg(x) for x in ["md5", "file"]]}
        localization_import_parameters = {"parameters" : [make_item_arg(x) for x in ["md5", "file"]]}

        state_import_parameters["parameters"].append({"name": "mode", "value": "state"})
        localization_import_parameters["parameters"].append({"name": "mode", "value": "localizations"})

        unpack_task = {
            'name': 'unpack-pipeline',
            'dag': {
                # First download, unpack and delete archive. Then Iterate over each video and upload
                # Lastly iterate over all localization and state files.
                'tasks' : [{'name': 'download-task',
                            'template': 'download',
                            'arguments': parameters},
                           {'name': 'unpack-task',
                            'template': 'unpack',
                            'arguments': parameters,
                            'dependencies' : ['download-task']},
                           {'name': 'delete-task',
                            'template': 'delete',
                            'arguments': parameters,
                            'dependencies' : ['unpack-task']},
                           # Loop over unpacked archive
                           {'name': 'transcode-task',
                            'template': 'transcode-pipeline',
                            'arguments' : item_parameters,
                            'withParam' : '{{tasks.unpack-task.outputs.parameters.videos}}',
                            'dependencies' : ['unpack-task']},
                           {'name': 'image-upload-task',
                            'template': 'image-upload',
                            'arguments' : item_parameters,
                            'withParam' : '{{tasks.unpack-task.outputs.parameters.images}}',
                            'dependencies' : ['unpack-task']},
                           {'name': 'state-import-task',
                            'template': 'data-import',
                            'arguments' : state_import_parameters,
                            'dependencies' : ['transcode-task', 'image-upload-task'],
                            'withParam': '{{tasks.unpack-task.outputs.parameters.states}}'},
                           {'name': 'localization-import-task',
                            'template': 'data-import',
                            'arguments' : localization_import_parameters,
                            'dependencies' : ['transcode-task', 'image-upload-task'],
                            'withParam': '{{tasks.unpack-task.outputs.parameters.localizations}}'}
                           ]

            } # end of dag
        }

        return unpack_task

    def get_transcode_dag(self):
        """ Return the DAG that describes transcoding a single media file """
        def make_passthrough_arg(name):
            return {'name': name,
                    'value': f'{{{{inputs.parameters.{name}}}}}'}

        instance_args = ['url',
                         'original',
                         'transcoded',
                         'thumbnail',
                         'thumbnail_gif',
                         'segments',
                         'entity_type',
                         'name',
                         'md5']
        passthrough_parameters = {"parameters" : [make_passthrough_arg(x) for x in instance_args]}

        pipeline_task = {
            'name': 'transcode-pipeline',
            'inputs': passthrough_parameters,
            'dag': {
                'tasks': [{
                    'name': 'transcode-task',
                    'template': 'transcode',
                    'arguments': passthrough_parameters
                }, {
                    'name': 'thumbnail-task',
                    'template': 'thumbnail',
                    'arguments': passthrough_parameters
                }, {
                    'name': 'upload-task',
                    'template': 'upload',
                    'arguments': passthrough_parameters,
                    'dependencies': ['transcode-task', 'thumbnail-task'],
                }],
            },
        }

        return pipeline_task
    def get_transcode_task(self, item, url):
        """ Generate a task object describing the dependencies of a transcode """
        # Generate an args structure for the DAG
        args = [{'name': 'url', 'value': url}]
        for key in item:
            args.append({'name': key, 'value': item[key]})
        parameters = {"parameters" : args}

        pipeline = {
            'name': 'single-file-pipeline',
            'dag': {
                # First download, unpack and delete archive. Then Iterate over each video and upload
                # Lastly iterate over all localization and state files.
                'tasks' : [{'name': 'download-task',
                            'template': 'download',
                            'arguments': parameters},
                            {'name': 'transcode-task',
                            'template': 'transcode-pipeline',
                            'arguments' : parameters,
                            'dependencies' : ['download-task']}]
                }
            }

        return pipeline


    def _get_progress_aux(self, job):
        return {'section': job['metadata']['annotations']['section']}

    def _cancel_message(self):
        return 'Transcode aborted!'

    def _job_type(self):
        return 'upload'

    def start_tar_import(self,
                         project,
                         entity_type,
                         token,
                         url,
                         name,
                         section,
                         md5,
                         gid,
                         uid,
                         user):
        """ Initiate a transcode based on the contents on an archive """
        comps = name.split('.')
        base = comps[0]
        ext = '.'.join(comps[1:])

        if entity_type != -1:
            raise Exception("entity type is not -1!")

        args = {'original': '/work/' + name,
                'name': name}
        docker_registry = os.getenv('SYSTEM_IMAGES_REGISTRY')
        global_args = {'upload_name': name,
                       'rest_url': f'https://{os.getenv("MAIN_HOST")}/rest',
                       'tus_url' : f'https://{os.getenv("MAIN_HOST")}/files/',
                       'project' : str(project),
                       'token' : str(token),
                       'section' : section,
                       'gid': gid,
                       'uid': uid,
                       'user': str(user),
                       'transcoder_image' : f"{docker_registry}/tator_transcoder:{Git.sha}",
                       'marshal_image': get_marshal_image_name()}
        global_parameters=[{"name": x, "value": global_args[x]} for x in global_args]

        pipeline_task = self.get_unpack_and_transcode_tasks(args, url)
        # Define the workflow spec.
        manifest = {
            'apiVersion': 'argoproj.io/v1alpha1',
            'kind': 'Workflow',
            'metadata': {
                'generateName': 'transcode-workflow-',
                'labels': {
                    'job_type': 'upload',
                    'project': str(project),
                    'gid': gid,
                    'uid': uid,
                    'user': str(user),
                },
                'annotations': {
                    'name': name,
                    'section': section,
                },
            },
            'spec': {
                'entrypoint': 'unpack-pipeline',
                'arguments': {'parameters' : global_parameters},
                'onExit': 'exit-handler',
                'ttlSecondsAfterFinished': 300,
                'volumeClaimTemplates': [self.pvc],
                'parallelism': 4,
                'templates': [
                    self.download_task,
                    self.delete_task,
                    self.transcode_task,
                    self.thumbnail_task,
                    self.upload_task,
                    self.image_upload_task,
                    self.unpack_task,
                    self.get_transcode_dag(),
                    pipeline_task,
                    self.progress_task,
                    self.exit_handler,
                    self.data_import
                ],
            },
        }

        # Create the workflow
        response = self.custom.create_namespaced_custom_object(
            group='argoproj.io',
            version='v1alpha1',
            namespace='default',
            plural='workflows',
            body=manifest,
        )

    def start_transcode(self, project, entity_type, token, url, name, section, md5, gid, uid, user):
        """ Creates an argo workflow for performing a transcode.
        """
        # Define paths for transcode outputs.
        base, _ = os.path.splitext(name)
        args = {
            'original': '/work/' + name,
            'transcoded': '/work/' + base + '_transcoded',
            'thumbnail': '/work/' + base + '_thumbnail.jpg',
            'thumbnail_gif': '/work/' + base + '_thumbnail_gif.gif',
            'segments': '/work/' + base + '_segments.json',
            'entity_type': str(entity_type),
            'md5' : md5,
            'name': name,
        }

        docker_registry = os.getenv('SYSTEM_IMAGES_REGISTRY')
        global_args = {'upload_name': name,
                       'rest_url': f'https://{os.getenv("MAIN_HOST")}/rest',
                       # WARNING: This trailing slash is required
                       'tus_url' : f'https://{os.getenv("MAIN_HOST")}/files',
                       'project' : str(project),
                       'token' : str(token),
                       'section' : section,
                       'gid': gid,
                       'uid': uid,
                       'user': str(user),
                       'transcoder_image' : f"{docker_registry}/tator_transcoder:{Git.sha}",
                       'marshal_image': get_marshal_image_name()}
        global_parameters=[{"name": x, "value": global_args[x]} for x in global_args]

        pipeline_task = self.get_transcode_task(args, url)
        # Define the workflow spec.
        manifest = {
            'apiVersion': 'argoproj.io/v1alpha1',
            'kind': 'Workflow',
            'metadata': {
                'generateName': 'transcode-workflow-',
                'labels': {
                    'job_type': 'upload',
                    'project': str(project),
                    'gid': gid,
                    'uid': uid,
                    'user': str(user),
                },
                'annotations': {
                    'name': name,
                    'section': section,
                },
            },
            'spec': {
                'entrypoint': 'single-file-pipeline',
                'onExit': 'exit-handler',
                'arguments': {'parameters' : global_parameters},
                'ttlSecondsAfterFinished': 300,
                'volumeClaimTemplates': [self.pvc],
                'templates': [
                    self.download_task,
                    self.transcode_task,
                    self.thumbnail_task,
                    self.upload_task,
                    self.image_upload_task,
                    self.get_transcode_dag(),
                    pipeline_task,
                    self.progress_task,
                    self.exit_handler,
                ],
            },
        }

        # Create the workflow
        response = self.custom.create_namespaced_custom_object(
            group='argoproj.io',
            version='v1alpha1',
            namespace='default',
            plural='workflows',
            body=manifest,
        )

class TatorAlgorithm(JobManagerMixin):
    """ Interface to kubernetes REST API for starting algorithms.
    """

    def __init__(self, alg):
        """ Intializes the connection. If algorithm object includes
            a remote cluster, use that. Otherwise, use this cluster.
        """
        if alg.cluster:
            host = alg.cluster.host
            port = alg.cluster.port
            token = alg.cluster.token
            fd, cert = tempfile.mkstemp(text=True)
            with open(fd, 'w') as f:
                f.write(alg.cluster.cert)
            conf = Configuration()
            conf.api_key['authorization'] = token
            conf.host = f'https://{host}:{port}'
            conf.verify_ssl = True
            conf.ssl_ca_cert = cert
            api_client = ApiClient(conf)
            self.corev1 = CoreV1Api(api_client)
            self.custom = CustomObjectsApi(api_client)
        else:
            load_incluster_config()
            self.corev1 = CoreV1Api()
            self.custom = CustomObjectsApi()

        # Read in the mainfest.
        if alg.manifest:
            self.manifest = yaml.safe_load(alg.manifest.open(mode='r'))

        # Save off the algorithm name.
        self.name = alg.name

    def _get_progress_aux(self, job):
        return {
            'sections': job['metadata']['annotations']['sections'],
            'media_ids': job['metadata']['annotations']['media_ids'],
        }

    def _cancel_message(self):
        return 'Algorithm aborted!'

    def _job_type(self):
        return 'algorithm'

    def start_algorithm(self, media_ids, sections, gid, uid, token, project, user):
        """ Starts an algorithm job, substituting in parameters in the
            workflow spec.
        """
        # Make a copy of the manifest from the database.
        manifest = copy.deepcopy(self.manifest)

        # Add in workflow parameters.
        manifest['spec']['arguments'] = {'parameters': [
            {
                'name': 'name',
                'value': self.name,
            }, {
                'name': 'media_ids',
                'value': media_ids,
            }, {
                'name': 'sections',
                'value': sections,
            }, {
                'name': 'gid',
                'value': gid,
            }, {
                'name': 'uid',
                'value': uid,
            }, {
                'name': 'rest_url',
                'value': f'https://{os.getenv("MAIN_HOST")}/rest',
            }, {
                'name': 'rest_token',
                'value': str(token),
            }, {
                'name': 'tus_url',
                'value': f'https://{os.getenv("MAIN_HOST")}/files/',
            }, {
                'name': 'project_id',
                'value': str(project),
            },
        ]}

        # If no exit process is defined, add one to close progress.
        if 'onExit' not in manifest['spec']:
            failed_task = {
                'name': 'tator-failed',
                'container': {
                    'image': get_marshal_image_name(),
                    'imagePullPolicy': 'Always',
                    'command': ['python3',],
                    'args': [
                        'sendProgress.py',
                        '--url', f'https://{os.getenv("MAIN_HOST")}/rest',
                        '--token', str(token),
                        '--project', str(project),
                        '--job_type', 'algorithm',
                        '--gid', gid,
                        '--uid', uid,
                        '--state', 'failed',
                        '--message', 'Algorithm failed!',
                        '--progress', '0',
                        '--name', self.name,
                        '--sections', sections,
                        '--media_ids', media_ids,
                    ],
                    'resources': {
                        'limits': {
                            'memory': '32Mi',
                            'cpu': '100m',
                        },
                    },
                },
            }
            succeeded_task = {
                'name': 'tator-succeeded',
                'container': {
                    'image': get_marshal_image_name(),
                    'imagePullPolicy': 'Always',
                    'command': ['python3',],
                    'args': [
                        'sendProgress.py',
                        '--url', f'https://{os.getenv("MAIN_HOST")}/rest',
                        '--token', str(token),
                        '--project', str(project),
                        '--job_type', 'algorithm',
                        '--gid', gid,
                        '--uid', uid,
                        '--state', 'finished',
                        '--message', 'Algorithm complete!',
                        '--progress', '100',
                        '--name', self.name,
                        '--sections', sections,
                        '--media_ids', media_ids,
                    ],
                    'resources': {
                        'limits': {
                            'memory': '32Mi',
                            'cpu': '100m',
                        },
                    },
                },
            }
            exit_handler = {
                'name': 'tator-exit-handler',
                'steps': [[{
                    'name': 'send-fail',
                    'template': 'tator-failed',
                    'when': '{{workflow.status}} != Succeeded',
                }, {
                    'name': 'send-succeed',
                    'template': 'tator-succeeded',
                    'when': '{{workflow.status}} == Succeeded',
                }]],
            }
            manifest['spec']['onExit'] = 'tator-exit-handler'
            manifest['spec']['templates'] += [
                failed_task,
                succeeded_task,
                exit_handler
            ]

        # Set labels and annotations for job management
        if 'labels' not in manifest['metadata']:
            manifest['metadata']['labels'] = {}
        if 'annotations' not in manifest['metadata']:
            manifest['metadata']['annotations'] = {}
        manifest['metadata']['labels'] = {
            **manifest['metadata']['labels'],
            'job_type': 'algorithm',
            'project': str(project),
            'gid': gid,
            'uid': uid,
            'user': str(user),
        }
        manifest['metadata']['annotations'] = {
            **manifest['metadata']['annotations'],
            'name': self.name,
            'sections': sections,
            'media_ids': media_ids,
        }

        response = self.custom.create_namespaced_custom_object(
            group='argoproj.io',
            version='v1alpha1',
            namespace='default',
            plural='workflows',
            body=manifest,
        )

        return response
