import os
import json
import random
import datetime
import logging
import string
import functools
import time
from uuid import uuid1
from math import sin, cos, sqrt, atan2, radians

from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.files.base import ContentFile
from django.contrib.gis.geos import Point

from rest_framework import status
from rest_framework.test import APITestCase

from dateutil.parser import parse as dateutil_parse

from .models import *

from .search import TatorSearch

logger = logging.getLogger(__name__)

def create_test_user():
    return User.objects.create(
        username="jsnow",
        password="jsnow",
        first_name="Jon",
        last_name="Snow",
        email="jon.snow@gmail.com",
        middle_initial="A",
        initials="JAS",
    )

def create_test_project(user):
    return Project.objects.create(
        name="asdf",
        creator=user,
    )

def create_test_membership(user, project):
    return Membership.objects.create(
        user=user,
        project=project,
        permission=Permission.FULL_CONTROL,
    )

def create_test_algorithm(user, name, project):
    obj = Algorithm.objects.create(
        name=name,
        project=project,
        user=user,
        files_per_job=1,
        max_concurrent=1,
    )
    obj.manifest.save(
        name='asdf.yaml',
        content=ContentFile(
"""
apiVersion: argoproj.io/v1alpha1
kind: Workflow                  # new type of k8s spec
metadata:
  generateName: hello-world-    # name of the workflow spec
spec:
  entrypoint: whalesay          # invoke the whalesay template
  ttlSecondsAfterFinished: 30
  templates:
  - name: whalesay              # name of the template
    container:
      image: docker/whalesay
      command: [cowsay]
      args: ["hello world"]
      resources:                # limit the resources
        limits:
          memory: 32Mi
          cpu: 100m
""",
        ),
    )
    return obj


def create_test_image_file():
    this_path = os.path.dirname(os.path.abspath(__file__))
    img_path = os.path.join(this_path, 'static', 'images',
                            'cvision_horizontal.png')
    return SimpleUploadedFile(name='test.png',
                              content=open(img_path, 'rb').read(),
                              content_type='image/png')

def create_test_video(user, name, entity_type, project):
    return EntityMediaVideo.objects.create(
        name=name,
        meta=entity_type,
        project=project,
        uploader=user,
        upload_datetime=datetime.datetime.now(datetime.timezone.utc),
        original='',
        md5='',
        file=SimpleUploadedFile(name='asdf.mp4', content=b'asdfasdf'),
        thumbnail=create_test_image_file(),
        thumbnail_gif=create_test_image_file(),
        num_frames=1,
        fps=30.0,
        codec='H264',
        width='640',
        height='480',
    )

def create_test_image(user, name, entity_type, project):
    return Media.objects.create(
        name=name,
        meta=entity_type,
        project=project,
        md5='',
        file=create_test_image_file(),
        thumbnail=create_test_image_file(),
        width='640',
        height='480',
    )

def create_test_box(user, entity_type, project, media, frame):
    x = random.uniform(0.0, float(media.width))
    y = random.uniform(0.0, float(media.height))
    w = random.uniform(0.0, float(media.width) - x)
    h = random.uniform(0.0, float(media.height) - y)
    return EntityLocalizationBox.objects.create(
        user=user,
        meta=entity_type,
        project=project,
        version=project.version_set.all()[0],
        media=media,
        frame=frame,
        x=x,
        y=y,
        width=w,
        height=h,
    )
        
def create_test_line(user, entity_type, project, media, frame):
    x0 = random.uniform(0.0, float(media.width))
    y0 = random.uniform(0.0, float(media.height))
    x1 = random.uniform(0.0, float(media.width) - x0)
    y1 = random.uniform(0.0, float(media.height) - y0)
    return EntityLocalizationLine.objects.create(
        user=user,
        meta=entity_type,
        project=project,
        media=media,
        frame=frame,
        x0=x0, y0=y0, x1=x1, y1=y1,
    )
        
def create_test_dot(user, entity_type, project, media, frame):
    x = random.uniform(0.0, float(media.width))
    y = random.uniform(0.0, float(media.height))
    return EntityLocalizationDot.objects.create(
        user=user,
        meta=entity_type,
        project=project,
        media=media,
        frame=frame,
        x=x,
        y=y,
    )

def create_test_treeleaf(name, entity_type, project):
    return TreeLeaf.objects.create(
        name=name,
        meta=entity_type,
        project=project,
        path=''.join(random.choices(string.ascii_lowercase, k=10)),
    )
        
def create_test_attribute_types():
    """Create one of each attribute type.
    """
    return [
        dict(
            name='bool_test',
            dtype='bool',
            default=False,
        ),
        dict(
            name='int_test',
            dtype='int',
            default=42,
        ),
        dict(
            name='float_test',
            dtype='float',
            default=42.0,
        ),
        dict(
            name='enum_test',
            dtype='enum',
            choices=['enum_val1', 'enum_val2', 'enum_val3'],
            default='enum_val1',
        ),
        dict(
            name='string_test',
            dtype='string',
            default='asdf_default',
        ),
        dict(
            name='datetime_test',
            dtype='datetime',
            use_current=True,
        ),
        dict(
            name='geoposition_test',
            dtype='geopos',
            default=[-179.0, -89.0],
        ),
    ]

def create_test_version(name, description, number, project, media):
    return Version.objects.create(
        name=name,
        description=description,
        number=number,
        project=project,
    )

def random_datetime(start, end):
    """Generate a random datetime between `start` and `end`"""
    return start + datetime.timedelta(
        seconds=random.randint(0, int((end - start).total_seconds())),
    )

def random_latlon():
    return (random.uniform(-90.0, 90.0), random.uniform(-180.0, 180.0))

def latlon_distance(lat0, lon0, lat1, lon1):
    R = 6373.0 # Radius of earth in km
    rlat0 = radians(lat0)
    rlon0 = radians(lon0)
    rlat1 = radians(lat1)
    rlon1 = radians(lon1)
    dlon = rlon1 - rlon0
    dlat = rlat1 - rlat0
    a = sin(dlat / 2)**2 + cos(rlat0) * cos(rlat1) * sin(dlon / 2)**2
    c = 2 * atan2(sqrt(a), sqrt(1 - a))
    distance = R * c
    return distance

permission_levels = [
    Permission.VIEW_ONLY,
    Permission.CAN_EDIT,
    Permission.CAN_TRANSFER,
    Permission.CAN_EXECUTE,
    Permission.FULL_CONTROL
]

class DefaultCreateTestMixin:
    def _check_object(self, response, is_default):
        # Get the created objects.
        if isinstance(response.data['id'], list):
            id_ = response.data['id'][0]
        else:
            id_ = response.data['id']
        obj = EntityBase.objects.get(pk=id_)
        # Assert it has all the expected values.
        attr_types = AttributeTypeBase.objects.filter(applies_to=obj.meta)
        for attr_type in attr_types:
            field = attr_type.name
            if is_default:
                if not isinstance(attr_type, AttributeTypeDatetime):
                    default = attr_type.default
                    if isinstance(default, Point):
                        default = [default.x, default.y]
                    self.assertTrue(obj.attributes[field]==default)
            else:
                self.assertTrue(obj.attributes[field]==self.create_json[field])
        # Delete the object
        obj.delete()

    def test_create_default(self):
        endpoint = f'/rest/{self.list_uri}/{self.project.pk}'
        # Remove attribute values.
        create_json = dict(self.create_json)
        delete_fields = []
        for key in create_json:
            if key.endswith('_test'):
                delete_fields.append(key)
        for field in delete_fields:
            del create_json[field]
        # Post the json with no attribute values.
        response = self.client.post(endpoint, create_json, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self._check_object(response, True)
        # Post the json with attribute values.
        response = self.client.post(endpoint, self.create_json, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self._check_object(response, False)

class PermissionCreateTestMixin:
    def test_create_permissions(self):
        permission_index = permission_levels.index(self.edit_permission)
        for index, level in enumerate(permission_levels):
            self.membership.permission = level
            self.membership.save()
            if index >= permission_index:
                expected_status = status.HTTP_201_CREATED
            else:
                expected_status = status.HTTP_403_FORBIDDEN
            endpoint = f'/rest/{self.list_uri}/{self.project.pk}'
            response = self.client.post(endpoint, self.create_json, format='json')
            self.assertEqual(response.status_code, expected_status)
            if hasattr(self, 'entities'):
                obj_type = type(self.entities[0])
            if expected_status == status.HTTP_200_OK:
                if isinstance(response.data['id'], list):
                    created_id = response.data['id'][0]
                else:
                    created_id = response.data['id']
                if hasattr(self, 'entities'):
                    self.entities.append(obj_type.objects.get(pk=created_id))
        self.membership.permission = Permission.FULL_CONTROL
        self.membership.save()

class PermissionListTestMixin:
    def test_list_patch_permissions(self):
        permission_index = permission_levels.index(self.edit_permission)
        for index, level in enumerate(permission_levels):
            self.membership.permission = level
            self.membership.save()
            if index >= permission_index:
                expected_status = status.HTTP_200_OK
            else:
                expected_status = status.HTTP_403_FORBIDDEN
            test_val = random.random() > 0.5
            response = self.client.patch(
                f'/rest/{self.list_uri}/{self.project.pk}'
                f'?type={self.entity_type.pk}',
                {'attributes': {'bool_test': test_val}},
                format='json')
            self.assertEqual(response.status_code, expected_status)
        self.membership.permission = Permission.FULL_CONTROL
        self.membership.save()

    def test_list_delete_permissions(self):
        # Wait for ES
        time.sleep(1)
        permission_index = permission_levels.index(self.edit_permission)
        for index, level in enumerate(permission_levels):
            self.membership.permission = level
            self.membership.save()
            if index >= permission_index:
                expected_status = status.HTTP_204_NO_CONTENT
            else:
                expected_status = status.HTTP_403_FORBIDDEN
            response = self.client.delete(
                f'/rest/{self.list_uri}/{self.project.pk}'
                f'?type={self.entity_type.pk}')
            self.assertEqual(response.status_code, expected_status)
        self.membership.permission = Permission.FULL_CONTROL
        self.membership.save()

class PermissionDetailTestMixin:
    def test_detail_patch_permissions(self):
        permission_index = permission_levels.index(self.edit_permission)
        for index, level in enumerate(permission_levels):
            self.membership.permission = level
            self.membership.save()
            if index >= permission_index:
                expected_status = status.HTTP_200_OK
            else:
                expected_status = status.HTTP_403_FORBIDDEN
            response = self.client.patch(
                f'/rest/{self.detail_uri}/{self.entities[0].pk}',
                self.patch_json,
                format='json')
            self.assertEqual(response.status_code, expected_status)
        self.membership.permission = Permission.FULL_CONTROL
        self.membership.save()

    def test_detail_delete_permissions(self):
        permission_index = permission_levels.index(self.edit_permission)
        for index, level in enumerate(permission_levels):
            self.membership.permission = level
            self.membership.save()
            if index >= permission_index:
                expected_status = status.HTTP_204_NO_CONTENT
            else:
                expected_status = status.HTTP_403_FORBIDDEN
            test_val = random.random() > 0.5
            response = self.client.delete(
                f'/rest/{self.detail_uri}/{self.entities[0].pk}',
                format='json')
            self.assertEqual(response.status_code, expected_status)
            if expected_status == status.HTTP_204_NO_CONTENT:
                del self.entities[0]
        self.membership.permission = Permission.FULL_CONTROL
        self.membership.save()

class PermissionListMembershipTestMixin:
    def test_list_not_a_member_permissions(self):
        self.membership.delete()
        url = f'/rest/{self.list_uri}/{self.project.pk}'
        if hasattr(self, 'entity_type'):
            url += f'?type={self.entity_type.pk}'
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.membership.save()

    def test_list_is_a_member_permissions(self):
        self.membership.permission = Permission.VIEW_ONLY
        self.membership.save()
        url = f'/rest/{self.list_uri}/{self.project.pk}'
        if hasattr(self, 'entity_type'):
            url += f'?type={self.entity_type.pk}'
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.membership.permission = Permission.FULL_CONTROL
        self.membership.save()

class PermissionDetailMembershipTestMixin:
    def test_detail_not_a_member_permissions(self):
        self.membership.delete()
        url = f'/rest/{self.detail_uri}/{self.entities[0].pk}'
        if hasattr(self, 'entity_type'):
            url += f'?type={self.entity_type.pk}'
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.membership.save()

    def test_detail_is_a_member_permissions(self):
        self.membership.permission = Permission.VIEW_ONLY
        self.membership.save()
        url = f'/rest/{self.detail_uri}/{self.entities[0].pk}'
        if hasattr(self, 'entity_type'):
            url += f'?type={self.entity_type.pk}'
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.membership.permission = Permission.FULL_CONTROL
        self.membership.save()

class AttributeMediaTestMixin:
    def test_media_with_attr(self):
        response = self.client.get(
            f'/rest/{self.list_uri}/{self.project.pk}?media_id={self.media_entities[0].pk}'
            f'&type={self.entity_type.pk}&attribute=bool_test::true'
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

class AttributeTestMixin:
    def test_query_no_attributes(self):
        response = self.client.get(
            f'/rest/{self.list_uri}/{self.project.pk}?type={self.entity_type.pk}&format=json'
        )
        self.assertEqual(len(response.data), len(self.entities))
        this_ids = [e.pk for e in self.entities]
        rest_ids = [e['id'] for e in response.data]
        for this_id, rest_id in zip(sorted(this_ids), sorted(rest_ids)):    
            self.assertEqual(this_id, rest_id)

    def test_multiple_attribute(self):
        response = self.client.get(
            f'/rest/{self.list_uri}/{self.project.pk}'
            f'?type={self.entity_type.pk}&attribute=bool_test::true&attribute=int_test::0'
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_pagination(self):
        test_vals = [random.random() > 0.5 for _ in range(len(self.entities))]
        for idx, test_val in enumerate(test_vals):
            pk = self.entities[idx].pk
            response = self.client.patch(f'/rest/{self.detail_uri}/{pk}',
                                         {'attributes': {'bool_test': test_val}},
                                         format='json')
            self.assertEqual(response.status_code, status.HTTP_200_OK)
        TatorSearch().refresh(self.project.pk)
        response = self.client.get(
            f'/rest/{self.list_uri}/{self.project.pk}'
            f'?format=json'
            f'&attribute=bool_test::true'
            f'&type={self.entity_type.pk}'
            f'&start=0'
            f'&stop=2'
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), max(0, min(sum(test_vals), 2)))
        response1 = self.client.get(
            f'/rest/{self.list_uri}/{self.project.pk}'
            f'?format=json'
            f'&attribute=bool_test::true'
            f'&type={self.entity_type.pk}'
            f'&start=1'
            f'&stop=4'
        )
        self.assertEqual(response1.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response1.data), max(0, min(sum(test_vals) - 1, 3)))
        if len(response.data) >= 2 and len(response1.data) >= 1:
            self.assertEqual(response.data[1], response1.data[0])

    def test_list_patch(self):
        test_val = random.random() > 0.5
        response = self.client.patch(
            f'/rest/{self.list_uri}/{self.project.pk}'
            f'?type={self.entity_type.pk}',
            {'attributes': {'bool_test': test_val}},
            format='json')
        print(f"RESPONSE: {response.data}")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        for entity in self.entities:
            response = self.client.get(f'/rest/{self.detail_uri}/{entity.pk}')
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            self.assertEqual(response.data['attributes']['bool_test'], test_val)

    def test_list_delete(self):
        test_val = random.random() > 0.5
        to_delete = [self.create_entity() for _ in range(5)]
        obj_ids = list(map(lambda x: str(x.pk), to_delete))
        for obj_id in obj_ids:
            response = self.client.get(f'/rest/{self.detail_uri}/{obj_id}')
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            # Update objects with a string so we know which to delete
            response = self.client.patch(
                f'/rest/{self.detail_uri}/{obj_id}',
                {'attributes': {'string_test': 'DELETE ME!!!'}},
                format='json')
        TatorSearch().refresh(self.project.pk)
        response = self.client.delete(
            f'/rest/{self.list_uri}/{self.project.pk}'
            f'?type={self.entity_type.pk}'
            f'&attribute=string_test::DELETE ME!!!')
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        for obj_id in obj_ids:
            response = self.client.get(f'/rest/{self.detail_uri}/{obj_id}')
            self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        for entity in self.entities:
            response = self.client.get(f'/rest/{self.detail_uri}/{entity.pk}')
            self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_null_attr(self):
        test_vals = [random.random() > 0.5 for _ in range(len(self.entities))]
        for idx, test_val in enumerate(test_vals):
            pk = self.entities[idx].pk
            response = self.client.patch(f'/rest/{self.detail_uri}/{pk}',
                                         {'attributes': {'bool_test': test_val}},
                                         format='json')
            self.assertEqual(response.status_code, status.HTTP_200_OK)
        TatorSearch().refresh(self.project.pk)
        response = self.client.get(
            f'/rest/{self.list_uri}/{self.project.pk}?attribute_null=bool_test::false'
            f'&type={self.entity_type.pk}', # needed for localizations
            format='json'
        )
        self.assertEqual(len(response.data), len(self.entities))
        response = self.client.get(
            f'/rest/{self.list_uri}/{self.project.pk}?attribute_null=bool_test::true'
            f'&type={self.entity_type.pk}', # needed for localizations
            format='json'
        )
        self.assertEqual(len(response.data), 0)
        response = self.client.get(
            f'/rest/{self.list_uri}/{self.project.pk}?attribute_null=asdf::true'
            f'&type={self.entity_type.pk}', # needed for localizations
            format='json'
        )
        self.assertEqual(len(response.data), len(self.entities))
        response = self.client.get(
            f'/rest/{self.list_uri}/{self.project.pk}?attribute_null=asdf::false'
            f'&type={self.entity_type.pk}', # needed for localizations
            format='json'
        )
        self.assertEqual(len(response.data), 0)
    
    def test_bool_attr(self):
        test_vals = [random.random() > 0.5 for _ in range(len(self.entities))]
        # Test setting an invalid bool
        response = self.client.patch(
            f'/rest/{self.detail_uri}/{self.entities[0].pk}',
            {'attributes': {'bool_test': 'asdfasdf'}},
            format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        for idx, test_val in enumerate(test_vals):
            pk = self.entities[idx].pk
            response = self.client.patch(f'/rest/{self.detail_uri}/{pk}',
                                         {'attributes': {'bool_test': test_val}},
                                         format='json')
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            # Do this again to test after the attribute object has been created.
            response = self.client.patch(f'/rest/{self.detail_uri}/{pk}',
                                         {'attributes': {'bool_test': test_val}},
                                         format='json')
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            response = self.client.get(f'/rest/{self.detail_uri}/{pk}?format=json')
            self.assertEqual(response.data['id'], pk)
            self.assertEqual(response.data['attributes']['bool_test'], test_val)
        TatorSearch().refresh(self.project.pk)
        response = self.client.get(f'/rest/{self.list_uri}/{self.project.pk}?attribute=bool_test::true&type={self.entity_type.pk}&format=json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), sum(test_vals))
        response = self.client.get(f'/rest/{self.list_uri}/{self.project.pk}?attribute=bool_test::false&type={self.entity_type.pk}&format=json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), len(test_vals) - sum(test_vals))
        response = self.client.get(f'/rest/{self.list_uri}/{self.project.pk}?attribute_gt=bool_test::false&type={self.entity_type.pk}&format=json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        response = self.client.get(f'/rest/{self.list_uri}/{self.project.pk}?attribute_gte=bool_test::false&type={self.entity_type.pk}&format=json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        response = self.client.get(f'/rest/{self.list_uri}/{self.project.pk}?attribute_lt=bool_test::false&type={self.entity_type.pk}&format=json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        response = self.client.get(f'/rest/{self.list_uri}/{self.project.pk}?attribute_lte=bool_test::false&type={self.entity_type.pk}&format=json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        response = self.client.get(f'/rest/{self.list_uri}/{self.project.pk}?attribute_contains=bool_test::false&type={self.entity_type.pk}&format=json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        response = self.client.get(f'/rest/{self.list_uri}/{self.project.pk}?attribute_distance=bool_test::false&type={self.entity_type.pk}&format=json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_int_attr(self):
        test_vals = [random.randint(-1000, 1000) for _ in range(len(self.entities))]
        # Test setting an invalid int
        response = self.client.patch(
            f'/rest/{self.detail_uri}/{self.entities[0].pk}',
            {'attributes': {'int_test': 'asdfasdf'}},
            format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        for idx, test_val in enumerate(test_vals):
            pk = self.entities[idx].pk
            response = self.client.patch(f'/rest/{self.detail_uri}/{pk}',
                                         {'attributes': {'int_test': test_val}},
                                         format='json')
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            response = self.client.get(f'/rest/{self.detail_uri}/{pk}?format=json')
            self.assertEqual(response.data['id'], pk)
            self.assertEqual(response.data['attributes']['int_test'], test_val)
        TatorSearch().refresh(self.project.pk)
        for test_val in test_vals:
            response = self.client.get(f'/rest/{self.list_uri}/{self.project.pk}?attribute=int_test::{test_val}&type={self.entity_type.pk}&format=json')
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            self.assertEqual(len(response.data), sum([t == test_val for t in test_vals]))
        for lbound, ubound in [(-1000, 1000), (-500, 500), (-500, 0), (0, 500)]:
            response = self.client.get(f'/rest/{self.list_uri}/{self.project.pk}?attribute_gt=int_test::{lbound}&attribute_lt=int_test::{ubound}&type={self.entity_type.pk}&format=json')
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            self.assertEqual(len(response.data), sum([(t > lbound) and (t < ubound) for t in test_vals]))
            response = self.client.get(f'/rest/{self.list_uri}/{self.project.pk}?attribute_gte=int_test::{lbound}&attribute_lte=int_test::{ubound}&type={self.entity_type.pk}&format=json')
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            self.assertEqual(len(response.data), sum([(t >= lbound) and (t <= ubound) for t in test_vals]))
        response = self.client.get(f'/rest/{self.list_uri}/{self.project.pk}?attribute_contains=int_test::1&type={self.entity_type.pk}&format=json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        response = self.client.get(f'/rest/{self.list_uri}/{self.project.pk}?attribute_distance=int_test::false&type={self.entity_type.pk}&format=json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_float_attr(self):
        test_vals = [random.uniform(-1000.0, 1000.0) for _ in range(len(self.entities))]
        # Test setting an invalid float
        response = self.client.patch(
            f'/rest/{self.detail_uri}/{self.entities[0].pk}',
            {'attributes': {'float_test': 'asdfasdf'}},
            format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        for idx, test_val in enumerate(test_vals):
            pk = self.entities[idx].pk
            response = self.client.patch(f'/rest/{self.detail_uri}/{pk}',
                                         {'attributes': {'float_test': test_val}},
                                         format='json')
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            response = self.client.get(f'/rest/{self.detail_uri}/{pk}?format=json')
            self.assertEqual(response.data['id'], pk)
            self.assertEqual(response.data['attributes']['float_test'], test_val)
        TatorSearch().refresh(self.project.pk)
        # Equality on float not recommended but is allowed.
        response = self.client.get(f'/rest/{self.list_uri}/{self.project.pk}?attribute=float_test::{test_val}&type={self.entity_type.pk}&format=json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        for lbound, ubound in [(-1000.0, 1000.0), (-500.0, 500.0), (-500.0, 0.0), (0.0, 500.0)]:
            response = self.client.get(f'/rest/{self.list_uri}/{self.project.pk}?attribute_gt=float_test::{lbound}&attribute_lt=float_test::{ubound}&type={self.entity_type.pk}&format=json')
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            self.assertEqual(len(response.data), sum([(t > lbound) and (t < ubound) for t in test_vals]))
            response = self.client.get(f'/rest/{self.list_uri}/{self.project.pk}?attribute_gte=float_test::{lbound}&attribute_lte=float_test::{ubound}&type={self.entity_type.pk}&format=json')
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            self.assertEqual(len(response.data), sum([(t >= lbound) and (t <= ubound) for t in test_vals]))
        # Contains on float not recommended but is allowed.
        response = self.client.get(f'/rest/{self.list_uri}/{self.project.pk}?attribute_contains=float_test::false&type={self.entity_type.pk}&format=json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        response = self.client.get(f'/rest/{self.list_uri}/{self.project.pk}?attribute_distance=float_test::false&type={self.entity_type.pk}&format=json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_enum_attr(self):
        test_vals = [random.choice(['enum_val1', 'enum_val2', 'enum_val3']) for _ in range(len(self.entities))]
        # Test setting an invalid choice
        response = self.client.patch(
            f'/rest/{self.detail_uri}/{self.entities[0].pk}',
            {'attributes': {'enum_test': 'asdfasdf'}},
            format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        for idx, test_val in enumerate(test_vals):
            pk = self.entities[idx].pk
            response = self.client.patch(f'/rest/{self.detail_uri}/{pk}',
                                         {'attributes': {'enum_test': test_val}},
                                         format='json')
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            response = self.client.get(f'/rest/{self.detail_uri}/{pk}?format=json')
            self.assertEqual(response.data['id'], pk)
            self.assertEqual(response.data['attributes']['enum_test'], test_val)
        TatorSearch().refresh(self.project.pk)
        response = self.client.get(f'/rest/{self.list_uri}/{self.project.pk}?attribute_gt=enum_test::0&type={self.entity_type.pk}&format=json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        response = self.client.get(f'/rest/{self.list_uri}/{self.project.pk}?attribute_gte=enum_test::0&type={self.entity_type.pk}&format=json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        response = self.client.get(f'/rest/{self.list_uri}/{self.project.pk}?attribute_lt=enum_test::0&type={self.entity_type.pk}&format=json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        response = self.client.get(f'/rest/{self.list_uri}/{self.project.pk}?attribute_lte=enum_test::0&type={self.entity_type.pk}&format=json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        for _ in range(10):
            subs = ''.join(random.choices(string.ascii_lowercase, k=2))
            response = self.client.get(f'/rest/{self.list_uri}/{self.project.pk}?attribute_contains=enum_test::{subs}&type={self.entity_type.pk}&format=json')
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            self.assertEqual(len(response.data), sum([subs.lower() in t.lower() for t in test_vals]))
        response = self.client.get(f'/rest/{self.list_uri}/{self.project.pk}?attribute_distance=enum_test::0&type={self.entity_type.pk}&format=json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_string_attr(self):
        test_vals = [''.join(random.choices(string.ascii_uppercase + string.digits, k=random.randint(1, 64)))
            for _ in range(len(self.entities))]
        for idx, test_val in enumerate(test_vals):
            pk = self.entities[idx].pk
            response = self.client.patch(f'/rest/{self.detail_uri}/{pk}',
                                         {'attributes': {'string_test': test_val}},
                                         format='json')
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            response = self.client.get(f'/rest/{self.detail_uri}/{pk}?format=json')
            self.assertEqual(response.data['id'], pk)
            self.assertEqual(response.data['attributes']['string_test'], test_val)
        TatorSearch().refresh(self.project.pk)
        response = self.client.get(f'/rest/{self.list_uri}/{self.project.pk}?attribute_gt=string_test::0&type={self.entity_type.pk}&format=json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        response = self.client.get(f'/rest/{self.list_uri}/{self.project.pk}?attribute_gte=string_test::0&type={self.entity_type.pk}&format=json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        response = self.client.get(f'/rest/{self.list_uri}/{self.project.pk}?attribute_lt=string_test::0&type={self.entity_type.pk}&format=json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        response = self.client.get(f'/rest/{self.list_uri}/{self.project.pk}?attribute_lte=string_test::0&type={self.entity_type.pk}&format=json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        for _ in range(10):
            subs = ''.join(random.choices(string.ascii_lowercase, k=2))
            response = self.client.get(f'/rest/{self.list_uri}/{self.project.pk}?attribute_contains=string_test::{subs}&type={self.entity_type.pk}&format=json')
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            self.assertEqual(len(response.data), sum([subs.lower() in t.lower() for t in test_vals]))
        response = self.client.get(f'/rest/{self.list_uri}/{self.project.pk}?attribute_distance=string_test::0&type={self.entity_type.pk}&format=json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_datetime_attr(self):
        def to_string(dt):
            return dt.isoformat().replace('+00:00', 'Z')
        end_dt = datetime.datetime.now(datetime.timezone.utc)
        start_dt = end_dt - datetime.timedelta(days=5 * 365)
        test_vals = [
            random_datetime(start_dt, end_dt)
            for _ in range(len(self.entities))
        ]
        # Test setting an invalid datetime
        response = self.client.patch(
            f'/rest/{self.detail_uri}/{self.entities[0].pk}',
            {'attributes': {'datetime_test': 'asdfasdf'}},
            format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        for idx, test_val in enumerate(test_vals):
            pk = self.entities[idx].pk
            response = self.client.patch(
                f'/rest/{self.detail_uri}/{pk}',
                {'attributes': {'datetime_test': to_string(test_val)}},
                format='json'
            )
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            response = self.client.get(f'/rest/{self.detail_uri}/{pk}?format=json')
            self.assertEqual(response.data['id'], pk)
            self.assertEqual(dateutil_parse(response.data['attributes']['datetime_test']), test_val)
        TatorSearch().refresh(self.project.pk)
        response = self.client.get(
            f'/rest/{self.list_uri}/{self.project.pk}?attribute=datetime_test::{to_string(test_val)}&'
            f'type={self.entity_type.pk}&format=json'
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK) 
        delta_dt = datetime.timedelta(days=365)
        for lbound, ubound in [
                (start_dt, end_dt),
                (start_dt + delta_dt, end_dt - delta_dt),
                (start_dt + delta_dt, end_dt - 2 * delta_dt),
                (start_dt + 2 * delta_dt, end_dt - delta_dt),
            ]:
            lbound_iso = to_string(lbound)
            ubound_iso = to_string(ubound)
            response = self.client.get(
                f'/rest/{self.list_uri}/{self.project.pk}?attribute_gt=datetime_test::{lbound_iso}&'
                f'attribute_lt=datetime_test::{ubound_iso}&type={self.entity_type.pk}&'
                f'format=json'
            )
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            self.assertEqual(
                len(response.data),
                sum([(t > lbound) and (t < ubound) for t in test_vals])
            )
            response = self.client.get(
                f'/rest/{self.list_uri}/{self.project.pk}?attribute_gte=datetime_test::{lbound_iso}&'
                f'attribute_lte=datetime_test::{ubound_iso}&type={self.entity_type.pk}&'
                f'format=json'
            )
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            self.assertEqual(
                len(response.data),
                sum([(t >= lbound) and (t <= ubound) for t in test_vals])
            )
        response = self.client.get(
            f'/rest/{self.list_uri}/{self.project.pk}?attribute_contains=datetime_test::asdf&'
            f'type={self.entity_type.pk}&format=json'
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        response = self.client.get(
            f'/rest/{self.list_uri}/{self.project.pk}?attribute_distance=datetime_test::asdf&'
            f'type={self.entity_type.pk}&format=json'
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_geoposition_attr(self):
        test_vals = [random_latlon() for _ in range(len(self.entities))]
        # Test setting invalid geopositions
        response = self.client.patch(
            f'/rest/{self.detail_uri}/{self.entities[0].pk}',
            {'attributes': {'geoposition_test': [0.0, -91.0]}},
            format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        response = self.client.patch(
            f'/rest/{self.detail_uri}/{self.entities[0].pk}',
            {'attributes': {'geoposition_test': [-181.0, 0.0]}},
            format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        for idx, test_val in enumerate(test_vals):
            pk = self.entities[idx].pk
            lat, lon = test_val
            response = self.client.patch(
                f'/rest/{self.detail_uri}/{pk}',
                {'attributes': {'geoposition_test': [lon, lat]}},
                format='json',
            )
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            response = self.client.get(f'/rest/{self.detail_uri}/{pk}?format=json')
            self.assertEqual(response.data['id'], pk)
            attrs = response.data['attributes']['geoposition_test']
            self.assertEqual(response.data['attributes']['geoposition_test'], [lon, lat])
        TatorSearch().refresh(self.project.pk)
        response = self.client.get(
            f'/rest/{self.list_uri}/{self.project.pk}?attribute=geoposition_test::10::{lat}::{lon}&'
            f'type={self.entity_type.pk}&format=json'
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        response = self.client.get(
            f'/rest/{self.list_uri}/{self.project.pk}?attribute_lt=geoposition_test::10::{lat}::{lon}&'
            f'type={self.entity_type.pk}&format=json'
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        response = self.client.get(
            f'/rest/{self.list_uri}/{self.project.pk}?attribute_lte=geoposition_test::10::{lat}::{lon}&'
            f'type={self.entity_type.pk}&format=json'
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        response = self.client.get(
            f'/rest/{self.list_uri}/{self.project.pk}?attribute_gt=geoposition_test::10::{lat}::{lon}&'
            f'type={self.entity_type.pk}&format=json'
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        response = self.client.get(
            f'/rest/{self.list_uri}/{self.project.pk}?attribute_gte=geoposition_test::10::{lat}::{lon}&'
            f'type={self.entity_type.pk}&format=json'
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        response = self.client.get(
            f'/rest/{self.list_uri}/{self.project.pk}?attribute_contains=geoposition_test::10::{lat}::{lon}&'
            f'type={self.entity_type.pk}&format=json'
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        test_lat, test_lon = random_latlon()
        for dist in [1.0, 100.0, 1000.0, 5000.0, 10000.0, 43000.0]:
            response = self.client.get(
                f'/rest/{self.list_uri}/{self.project.pk}?attribute_distance=geoposition_test::'
                f'{dist}::{test_lat}::{test_lon}&'
                f'type={self.entity_type.pk}&format=json'
            )
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            self.assertEqual(len(response.data), sum([
                latlon_distance(test_lat, test_lon, lat, lon) < dist
                for lat, lon in test_vals
            ]))

class CurrentUserTestCase(APITestCase):
    def test_get(self):
        self.user = create_test_user()
        self.client.force_authenticate(self.user)
        response = self.client.get('/rest/User/GetCurrent')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['id'], self.user.id)

class ProjectDeleteTestCase(APITestCase):
    def setUp(self):
        self.user = create_test_user()
        self.project = create_test_project(self.user)
        self.video_type = EntityTypeMediaVideo.objects.create(
            name="video",
            project=self.project,
            keep_original=False,
        )
        self.box_type = EntityTypeLocalizationBox.objects.create(
            name="boxes",
            project=self.project,
        )
        self.state_type = EntityTypeState.objects.create(
            name="state_type",
            project=self.project,
        )
        self.videos = [
            create_test_video(self.user, f'asdf{idx}', self.video_type, self.project)
            for idx in range(random.randint(6, 10))
        ]
        self.boxes = [
            create_test_box(self.user, self.box_type, self.project, random.choice(self.videos), 0)
            for idx in range(random.randint(6, 10))
        ]
        self.associations = [
            MediaAssociation.objects.create()
            for _ in range(random.randint(6, 10))
        ]
        self.states = []
        for media_association in self.associations:
            for media in random.choices(self.videos):
                media_association.media.add(media)
            self.states.append(
                EntityState.objects.create(
                    meta=self.state_type,
                    project=self.project,
                    association=media_association,
                )
            )

    def test_delete(self):
        self.client.delete(f'/rest/Project/{self.project.pk}')

class AlgorithmLaunchTestCase(
        APITestCase,
        PermissionCreateTestMixin):
    def setUp(self):
        self.user = create_test_user()
        self.client.force_authenticate(self.user)
        self.project = create_test_project(self.user)
        self.membership = create_test_membership(self.user, self.project)
        self.algorithm = create_test_algorithm(self.user, 'algtest', self.project)
        self.list_uri = 'AlgorithmLaunch'
        self.create_json = {
            'algorithm_name': self.algorithm.name,
            'media_ids': [1,2,3],
        }
        self.edit_permission = Permission.CAN_EXECUTE

    def tearDown(self):
        self.project.delete()

class AlgorithmTestCase(
        APITestCase,
        PermissionListMembershipTestMixin):
    def setUp(self):
        self.user = create_test_user()
        self.client.force_authenticate(self.user)
        self.project = create_test_project(self.user)
        self.membership = create_test_membership(self.user, self.project)
        self.algorithm = create_test_algorithm(self.user, 'algtest', self.project)
        self.list_uri = 'Algorithms'
        self.entities = [
            create_test_algorithm(self.user, f'result{idx}', self.project)
            for idx in range(random.randint(6, 10))
        ]

    def tearDown(self):
        self.project.delete()

class VideoTestCase(
        APITestCase,
        AttributeTestMixin,
        AttributeMediaTestMixin,
        PermissionListMembershipTestMixin,
        PermissionDetailMembershipTestMixin,
        PermissionDetailTestMixin):
    def setUp(self):
        self.user = create_test_user()
        self.client.force_authenticate(self.user)
        self.project = create_test_project(self.user)
        self.membership = create_test_membership(self.user, self.project)
        self.entity_type = EntityTypeMediaVideo.objects.create(
            name="video",
            project=self.project,
            keep_original=False,
        )
        self.entities = [
            create_test_video(self.user, f'asdf{idx}', self.entity_type, self.project)
            for idx in range(random.randint(6, 10))
        ]
        self.media_entities = self.entities
        self.attribute_types = create_test_attribute_types(self.entity_type, self.project)
        self.list_uri = 'Medias'
        self.detail_uri = 'Media'
        self.create_entity = functools.partial(
            create_test_video, self.user, 'asdfa', self.entity_type, self.project)
        self.edit_permission = Permission.CAN_EDIT
        self.patch_json = {'name': 'video1', 'last_edit_start': '2017-07-21T17:32:28Z'}
        TatorSearch().refresh(self.project.pk)

    def tearDown(self):
        self.project.delete()

class ImageTestCase(
        APITestCase,
        AttributeTestMixin,
        AttributeMediaTestMixin,
        PermissionListMembershipTestMixin,
        PermissionDetailMembershipTestMixin,
        PermissionDetailTestMixin):
    def setUp(self):
        self.user = create_test_user()
        self.client.force_authenticate(self.user)
        self.project = create_test_project(self.user)
        self.membership = create_test_membership(self.user, self.project)
        self.entity_type = MediaType.objects.create(
            name="images",
            dtype='image',
            project=self.project,
            attribute_types=create_test_attribute_types(),
        )
        self.entities = [
            create_test_image(self.user, f'asdf{idx}', self.entity_type, self.project)
            for idx in range(random.randint(6, 10))
        ]
        self.media_entities = self.entities
        self.list_uri = 'Medias'
        self.detail_uri = 'Media'
        self.create_entity = functools.partial(
            create_test_image, self.user, 'asdfa', self.entity_type, self.project)
        self.edit_permission = Permission.CAN_EDIT
        self.patch_json = {'name': 'image1'}
        TatorSearch().refresh(self.project.pk)

    def tearDown(self):
        self.project.delete()

class LocalizationBoxTestCase(
        APITestCase,
        AttributeTestMixin,
        AttributeMediaTestMixin,
        DefaultCreateTestMixin,
        PermissionCreateTestMixin,
        PermissionListTestMixin,
        PermissionListMembershipTestMixin,
        PermissionDetailMembershipTestMixin,
        PermissionDetailTestMixin):
    def setUp(self):
        self.user = create_test_user()
        self.client.force_authenticate(self.user)
        self.project = create_test_project(self.user)
        self.membership = create_test_membership(self.user, self.project)
        media_entity_type = EntityTypeMediaVideo.objects.create(
            name="video",
            project=self.project,
            keep_original=False,
        )
        self.entity_type = EntityTypeLocalizationBox.objects.create(
            name="boxes",
            project=self.project,
        )
        self.entity_type.media.add(media_entity_type)
        self.media_entities = [
            create_test_video(self.user, f'asdf{idx}', media_entity_type, self.project)
            for idx in range(random.randint(3, 10))
        ]
        self.entities = [
            create_test_box(self.user, self.entity_type, self.project, random.choice(self.media_entities), 0)
            for idx in range(random.randint(6, 10))
        ]
        self.attribute_types = create_test_attribute_types(self.entity_type, self.project)
        self.list_uri = 'Localizations'
        self.detail_uri = 'Localization'
        self.create_entity = functools.partial(
            create_test_box, self.user, self.entity_type, self.project, self.media_entities[0], 0)
        self.create_json = {
            'type': self.entity_type.pk,
            'name': 'asdf',
            'media_id': self.media_entities[0].pk,
            'frame': 0,
            'x': 0,
            'y': 0,
            'width': 0.5,
            'height': 0.5,
            'bool_test': True,
            'int_test': 1,
            'float_test': 0.0,
            'enum_test': 'enum_val1',
            'string_test': 'asdf',
            'datetime_test': datetime.datetime.now(datetime.timezone.utc).isoformat(),
            'geoposition_test': [0.0, 0.0],
        }
        self.edit_permission = Permission.CAN_EDIT
        self.patch_json = {'name': 'box1', 'resourcetype': 'EntityLocalizationBox'}
        TatorSearch().refresh(self.project.pk)

    def tearDown(self):
        self.project.delete()

class LocalizationLineTestCase(
        APITestCase,
        AttributeTestMixin,
        AttributeMediaTestMixin,
        DefaultCreateTestMixin,
        PermissionCreateTestMixin,
        PermissionListTestMixin,
        PermissionListMembershipTestMixin,
        PermissionDetailMembershipTestMixin,
        PermissionDetailTestMixin):
    def setUp(self):
        self.user = create_test_user()
        self.client.force_authenticate(self.user)
        self.project = create_test_project(self.user)
        self.membership = create_test_membership(self.user, self.project)
        media_entity_type = EntityTypeMediaVideo.objects.create(
            name="video",
            project=self.project,
            keep_original=False,
        )
        self.entity_type = EntityTypeLocalizationLine.objects.create(
            name="lines",
            project=self.project,
        )
        self.entity_type.media.add(media_entity_type)
        self.media_entities = [
            create_test_video(self.user, f'asdf{idx}', media_entity_type, self.project)
            for idx in range(random.randint(3, 10))
        ]
        self.entities = [
            create_test_line(self.user, self.entity_type, self.project, random.choice(self.media_entities), 0)
            for idx in range(random.randint(6, 10))
        ]
        self.attribute_types = create_test_attribute_types(self.entity_type, self.project)
        self.list_uri = 'Localizations'
        self.detail_uri = 'Localization'
        self.create_entity = functools.partial(
            create_test_line, self.user, self.entity_type, self.project, self.media_entities[0], 0)
        self.create_json = {
            'type': self.entity_type.pk,
            'name': 'asdf',
            'media_id': self.media_entities[0].pk,
            'frame': 0,
            'x0': 0,
            'y0': 0,
            'x1': 0.5,
            'y1': 0.5,
            'bool_test': True,
            'int_test': 1,
            'float_test': 0.0,
            'enum_test': 'enum_val1',
            'string_test': 'asdf',
            'datetime_test': datetime.datetime.now(datetime.timezone.utc).isoformat(),
            'geoposition_test': [0.0, 0.0],
        } 
        self.edit_permission = Permission.CAN_EDIT
        self.patch_json = {'name': 'line1', 'resourcetype': 'EntityLocalizationLine'}
        TatorSearch().refresh(self.project.pk)

    def tearDown(self):
        self.project.delete()

class LocalizationDotTestCase(
        APITestCase,
        AttributeTestMixin,
        AttributeMediaTestMixin,
        DefaultCreateTestMixin,
        PermissionCreateTestMixin,
        PermissionListTestMixin,
        PermissionListMembershipTestMixin,
        PermissionDetailMembershipTestMixin,
        PermissionDetailTestMixin):
    def setUp(self):
        self.user = create_test_user()
        self.client.force_authenticate(self.user)
        self.project = create_test_project(self.user)
        self.membership = create_test_membership(self.user, self.project)
        media_entity_type = EntityTypeMediaVideo.objects.create(
            name="video",
            project=self.project,
            keep_original=False,
        )
        self.entity_type = EntityTypeLocalizationDot.objects.create(
            name="lines",
            project=self.project,
        )
        self.entity_type.media.add(media_entity_type)
        self.media_entities = [
            create_test_video(self.user, f'asdf{idx}', media_entity_type, self.project)
            for idx in range(random.randint(3, 10))
        ]
        self.entities = [
            create_test_dot(self.user, self.entity_type, self.project, random.choice(self.media_entities), 0)
            for idx in range(random.randint(6, 10))
        ]
        self.attribute_types = create_test_attribute_types(self.entity_type, self.project)
        self.list_uri = 'Localizations'
        self.detail_uri = 'Localization'
        self.create_entity = functools.partial(
            create_test_dot, self.user, self.entity_type, self.project, self.media_entities[0], 0)
        self.create_json = {
            'type': self.entity_type.pk,
            'name': 'asdf',
            'media_id': self.media_entities[0].pk,
            'frame': 0,
            'x': 0,
            'y': 0,
            'bool_test': True,
            'int_test': 1,
            'float_test': 0.0,
            'enum_test': 'enum_val1',
            'string_test': 'asdf',
            'datetime_test': datetime.datetime.now(datetime.timezone.utc).isoformat(),
            'geoposition_test': [0.0, 0.0],
        } 
        self.edit_permission = Permission.CAN_EDIT
        self.patch_json = {'name': 'dot1', 'resourcetype': 'EntityLocalizationDot'}
        TatorSearch().refresh(self.project.pk)

    def tearDown(self):
        self.project.delete()

class StateTestCase(
        APITestCase,
        AttributeTestMixin,
        AttributeMediaTestMixin,
        DefaultCreateTestMixin,
        PermissionCreateTestMixin,
        PermissionListTestMixin,
        PermissionListMembershipTestMixin,
        PermissionDetailMembershipTestMixin,
        PermissionDetailTestMixin):
    def setUp(self):
        self.user = create_test_user()
        self.client.force_authenticate(self.user)
        self.project = create_test_project(self.user)
        self.version = self.project.version_set.all()[0]
        self.membership = create_test_membership(self.user, self.project)
        media_entity_type = EntityTypeMediaVideo.objects.create(
            name="video",
            project=self.project,
            keep_original=False,
        )
        self.entity_type = EntityTypeState.objects.create(
            name="lines",
            project=self.project,
        )
        self.entity_type.media.add(media_entity_type)
        self.media_entities = [
            create_test_video(self.user, f'asdf', media_entity_type, self.project)
            for idx in range(random.randint(3, 10))
        ]
        media_associations = [
            MediaAssociation.objects.create()
            for _ in range(random.randint(6, 10))
        ]
        self.entities = []
        for media_association in media_associations:
            for media in random.choices(self.media_entities):
                media_association.media.add(media)
            self.entities.append(
                EntityState.objects.create(
                    meta=self.entity_type,
                    project=self.project,
                    association=media_association,
                    version=self.version,
                )
            )
        self.attribute_types = create_test_attribute_types(self.entity_type, self.project)
        self.list_uri = 'States'
        self.detail_uri = 'State'
        self.create_entity = functools.partial(EntityState.objects.create,
            meta=self.entity_type,
            project=self.project,
            association=media_association,
            version=self.version
        )
        self.create_json = {
            'type': self.entity_type.pk,
            'name': 'asdf',
            'media_ids': [m.id for m in random.choices(self.media_entities)],
            'bool_test': True,
            'int_test': 1,
            'float_test': 0.0,
            'enum_test': 'enum_val1',
            'string_test': 'asdf',
            'datetime_test': datetime.datetime.now(datetime.timezone.utc).isoformat(),
            'geoposition_test': [0.0, 0.0],
        }
        self.edit_permission = Permission.CAN_EDIT
        self.patch_json = {'name': 'state1'}
        TatorSearch().refresh(self.project.pk)

    def tearDown(self):
        self.project.delete()

class TreeLeafTestCase(
        APITestCase,
        AttributeTestMixin,
        DefaultCreateTestMixin,
        PermissionCreateTestMixin,
        PermissionListTestMixin,
        PermissionListMembershipTestMixin,
        PermissionDetailMembershipTestMixin,
        PermissionDetailTestMixin):
    def setUp(self):
        self.user = create_test_user()
        self.client.force_authenticate(self.user)
        self.project = create_test_project(self.user)
        self.membership = create_test_membership(self.user, self.project)
        self.entity_type = EntityTypeTreeLeaf.objects.create(
            project=self.project,
        )
        self.entities = [
            create_test_treeleaf(f'leaf{idx}', self.entity_type, self.project)
            for idx in range(random.randint(6, 10))
        ]
        self.attribute_types = create_test_attribute_types(self.entity_type, self.project)
        self.list_uri = 'TreeLeaves'
        self.detail_uri = 'TreeLeaf'
        self.create_entity = functools.partial(
            create_test_treeleaf, 'leafasdf', self.entity_type, self.project)
        self.create_json = {
            'type': self.entity_type.pk,
            'name': 'asdf',
            'path': 'asdf',
            'bool_test': True,
            'int_test': 1,
            'float_test': 0.0,
            'enum_test': 'enum_val1',
            'string_test': 'asdf',
            'datetime_test': datetime.datetime.now(datetime.timezone.utc).isoformat(),
            'geoposition_test': [0.0, 0.0],
        }
        self.edit_permission = Permission.FULL_CONTROL 
        self.patch_json = {'name': 'leaf1', 'resourcetype': 'TreeLeaf'}
        TatorSearch().refresh(self.project.pk)

    def tearDown(self):
        self.project.delete()

class TreeLeafTypeTestCase(
        APITestCase,
        PermissionCreateTestMixin,
        PermissionListMembershipTestMixin,
        PermissionDetailMembershipTestMixin,
        PermissionDetailTestMixin):
    def setUp(self):
        self.user = create_test_user()
        self.client.force_authenticate(self.user)
        self.project = create_test_project(self.user)
        self.membership = create_test_membership(self.user, self.project)
        self.entities = [
            EntityTypeTreeLeaf.objects.create(project=self.project)
            for _ in range(random.randint(6, 10))
        ]
        self.list_uri = 'TreeLeafTypes'
        self.detail_uri = 'TreeLeafType'
        self.create_json = {
            'name': 'tree leaf type',
        }
        self.patch_json = {'name': 'tree leaf asdf'}
        self.edit_permission = Permission.FULL_CONTROL

    def tearDown(self):
        self.project.delete()

class StateTypeTestCase(
        APITestCase,
        PermissionCreateTestMixin,
        PermissionListMembershipTestMixin,
        PermissionDetailMembershipTestMixin,
        PermissionDetailTestMixin):
    def setUp(self):
        self.user = create_test_user()
        self.client.force_authenticate(self.user)
        self.project = create_test_project(self.user)
        self.membership = create_test_membership(self.user, self.project)
        self.media_type = MediaType.objects.create(
            name="video",
            project=self.project,
            keep_original=False,
        )
        self.entities = [
            StateType.objects.create(
                name="state1",
                project=self.project,
                association='Localization',
                attribute_types=create_test_attribute_types(),
            ),
            StateType.objects.create(
                name="state2",
                project=self.project,
                association='Media',
                attribute_types=create_test_attribute_types(),
            ),
        ]
        self.list_uri = 'StateTypes'
        self.detail_uri = 'StateType'
        self.create_json = {
            'name': 'frame state type',
            'association': 'Frame',
            'media_types': [self.media_type.pk],
            'attribute_types': create_test_attribute_types(),
        }
        self.patch_json = {'name': 'state asdf'}
        self.edit_permission = Permission.FULL_CONTROL

    def tearDown(self):
        self.project.delete()
        
class MediaTypeTestCase(
        APITestCase,
        PermissionCreateTestMixin,
        PermissionListMembershipTestMixin,
        PermissionDetailMembershipTestMixin,
        PermissionDetailTestMixin):
    def setUp(self):
        self.user = create_test_user()
        self.client.force_authenticate(self.user)
        self.project = create_test_project(self.user)
        self.membership = create_test_membership(self.user, self.project)
        self.detail_uri = 'MediaType'
        self.list_uri = 'MediaTypes'
        self.entities = [
            MediaType.objects.create(
                name="videos",
                keep_original=True,
                project=self.project,
                attribute_types=create_test_attribute_types(),
            ),
            MediaType.objects.create(
                name="images",
                project=self.project,
                attribute_types=create_test_attribute_types(),
            ),
        ]
        self.edit_permission = Permission.FULL_CONTROL
        self.patch_json = {
            'name': 'asdf',
        }
        self.create_json = {
            'name': 'videos',
            'keep_original': True,
            'dtype': 'video',
            'attribute_types': create_test_attribute_types(),
        }

    def tearDown(self):
        self.project.delete()

class EntityTypeSchemaTestCase(
        APITestCase,
        PermissionDetailMembershipTestMixin):
    def setUp(self):
        self.user = create_test_user()
        self.client.force_authenticate(self.user)
        self.project = create_test_project(self.user)
        self.membership = create_test_membership(self.user, self.project)
        self.detail_uri = 'EntityTypeSchema'
        self.entities = [
            EntityTypeMediaVideo.objects.create(
                name="videos",
                keep_original=True,
                project=self.project,
            ),
            EntityTypeMediaImage.objects.create(
                name="images",
                project=self.project,
            ),
        ]
        for entity_type in self.entities:
            create_test_attribute_types(entity_type, self.project)

    def tearDown(self):
        self.project.delete()

class LocalizationAssociationTestCase(
        APITestCase,
        PermissionDetailMembershipTestMixin,
        PermissionDetailTestMixin):
    def setUp(self):
        self.user = create_test_user()
        self.client.force_authenticate(self.user)
        self.project = create_test_project(self.user)
        self.membership = create_test_membership(self.user, self.project)
        media_entity_type = EntityTypeMediaVideo.objects.create(
            name="video",
            project=self.project,
            keep_original=False,
        )
        self.media_entities = [
            create_test_video(self.user, f'asdf', media_entity_type, self.project)
            for idx in range(random.randint(3, 10))
        ]
        localization_type = EntityTypeLocalizationBox.objects.create(
            name="boxes",
            project=self.project,
        )
        self.localizations = [
            create_test_box(
                self.user, localization_type, self.project,
                random.choice(self.media_entities), random.randint(0, 1000)
            ) for _ in range(6, 10)
        ]
        self.entities = [
            LocalizationAssociation.objects.create()
            for _ in range(random.randint(6, 10))
        ]
        state_type = EntityTypeState.objects.create(
            name="lines",
            project=self.project,
        )
        self.states = [
            EntityState.objects.create(
                meta=state_type,
                project=self.project,
                association=entity,
            ) for entity in self.entities
        ]
        for entity in self.entities:
            for localization in random.choices(self.localizations):
                entity.localizations.add(localization)
        self.detail_uri = 'LocalizationAssociation'
        self.edit_permission = Permission.CAN_EDIT
        self.patch_json = {
            'localizations': [loc.pk for loc in self.localizations[:2]],
            'color': 'aabbcc',
        }

    def tearDown(self):
        self.project.delete()

class FrameAssociationTestCase(
        APITestCase,
        PermissionDetailMembershipTestMixin,
        PermissionDetailTestMixin):
    def setUp(self):
        self.user = create_test_user()
        self.client.force_authenticate(self.user)
        self.project = create_test_project(self.user)
        self.membership = create_test_membership(self.user, self.project)
        media_entity_type = EntityTypeMediaVideo.objects.create(
            name="video",
            project=self.project,
            keep_original=False,
        )
        image_type = EntityTypeMediaImage.objects.create(
            name="images",
            project=self.project,
        )
        image = create_test_image(self.user, "asdf", image_type, self.project)
        self.media_entities = [
            create_test_video(self.user, f'asdf', media_entity_type, self.project)
            for idx in range(random.randint(3, 10))
        ]
        self.entities = [
            FrameAssociation.objects.create(frame=random.randint(0, 1000))
            for _ in range(random.randint(6, 10))
        ]
        state_type = EntityTypeState.objects.create(
            name="lines",
            project=self.project,
        )
        self.states = [
            EntityState.objects.create(
                meta=state_type,
                project=self.project,
                association=entity,
            ) for entity in self.entities
        ]
        self.detail_uri = 'FrameAssociation'
        self.edit_permission = Permission.CAN_EDIT
        self.patch_json = {
            'frame': 100,
            'extracted': image.pk,
        }

    def tearDown(self):
        self.project.delete()

class LocalizationTypeTestCase(
        APITestCase,
        PermissionCreateTestMixin,
        PermissionListMembershipTestMixin,
        PermissionDetailMembershipTestMixin,
        PermissionDetailTestMixin):
    def setUp(self):
        self.user = create_test_user()
        self.client.force_authenticate(self.user)
        self.project = create_test_project(self.user)
        self.membership = create_test_membership(self.user, self.project)
        self.media_type = MediaType.objects.create(
            name="video",
            project=self.project,
            keep_original=False,
        )
        self.entities = [
            LocalizationType.objects.create(
                name="box",
                dtype='box',
                project=self.project,
                attribute_types=create_test_attribute_types(),
            ),
            LocalizationType.objects.create(
                name="line",
                dtype='line',
                project=self.project,
                attribute_types=create_test_attribute_types(),
            ),
            LocalizationType.objects.create(
                name="dot asdf",
                dtype='dot',
                project=self.project,
                attribute_types=create_test_attribute_types(),
            ),
        ]
        self.list_uri = 'LocalizationTypes'
        self.detail_uri = 'LocalizationType'
        self.create_json = {
            'name': 'box type',
            'dtype': 'box',
            'media_types': [self.media_type.pk],
            'attribute_types': create_test_attribute_types(),
        }
        self.patch_json = {'name': 'box asdf'}
        self.edit_permission = Permission.FULL_CONTROL

    def tearDown(self):
        self.project.delete()

class MembershipTestCase(
        APITestCase,
        PermissionCreateTestMixin,
        PermissionListMembershipTestMixin,
        PermissionDetailTestMixin):
    def setUp(self):
        self.user = create_test_user()
        self.client.force_authenticate(self.user)
        self.project = create_test_project(self.user)
        self.membership = create_test_membership(self.user, self.project)
        self.entities = [self.membership,]
        self.list_uri = 'Memberships'
        self.detail_uri = 'Membership'
        self.patch_json = {
            'permission': 'Full Control',
        }
        self.create_json = {
            'user': self.user.pk,
            'permission': 'Full Control',
        }
        self.edit_permission = Permission.FULL_CONTROL

    def tearDown(self):
        self.project.delete()

class ProjectTestCase(APITestCase):
    def setUp(self):
        self.user = create_test_user()
        self.client.force_authenticate(self.user)
        self.entities = [
            create_test_project(self.user)
            for _ in range(random.randint(6, 10))
        ]
        memberships = [
            create_test_membership(self.user, entity)
            for entity in self.entities
        ]
        self.detail_uri = 'Project'
        self.list_uri = 'Projects'
        self.patch_json = {
            'name': 'aaasdfasd',
            'section_order': ['asdf1', 'asdf2', 'asdf3']
        }
        self.create_json = {
            'name': 'asdfasd',
            'summary': 'asdfa summary',
        }
        self.edit_permission = Permission.FULL_CONTROL

    def test_create(self):
        endpoint = f'/rest/{self.list_uri}'
        response = self.client.post(endpoint, self.create_json, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_detail_patch_permissions(self):
        permission_index = permission_levels.index(self.edit_permission)
        for index, level in enumerate(permission_levels):
            obj = Membership.objects.filter(project=self.entities[0], user=self.user)[0]
            obj.permission = level
            obj.save()
            del obj
            if index >= permission_index:
                expected_status = status.HTTP_200_OK
            else:
                expected_status = status.HTTP_403_FORBIDDEN
            response = self.client.patch(
                f'/rest/{self.detail_uri}/{self.entities[0].pk}',
                self.patch_json,
                format='json')
            self.assertEqual(response.status_code, expected_status)

    def test_detail_delete_permissions(self):
        permission_index = permission_levels.index(self.edit_permission)
        for index, level in enumerate(permission_levels):
            obj = Membership.objects.filter(project=self.entities[0], user=self.user)[0]
            obj.permission = level
            obj.save()
            del obj
            if index >= permission_index:
                expected_status = status.HTTP_204_NO_CONTENT
            else:
                expected_status = status.HTTP_403_FORBIDDEN
            test_val = random.random() > 0.5
            response = self.client.delete(
                f'/rest/{self.detail_uri}/{self.entities[0].pk}',
                format='json')
            self.assertEqual(response.status_code, expected_status)
            if expected_status == status.HTTP_204_NO_CONTENT:
                del self.entities[0]

    def test_delete_non_creator(self):
        other_user = User.objects.create(
            username="other",
            password="user",
            first_name="other",
            last_name="user",
            email="other.user@gmail.com",
            middle_initial="A",
            initials="OAU",
        )
        create_test_membership(other_user, self.entities[0])
        self.client.force_authenticate(other_user)
        response = self.client.delete(
            f'/rest/{self.detail_uri}/{self.entities[0].pk}',
            format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def tearDown(self):
        for project in self.entities:
            project.delete()
        
class TranscodeTestCase(
        APITestCase,
        PermissionCreateTestMixin):
    def setUp(self):
        self.user = create_test_user()
        self.client.force_authenticate(self.user)
        self.project = create_test_project(self.user)
        self.membership = create_test_membership(self.user, self.project)
        self.list_uri = 'Transcode'
        self.entity_type = EntityTypeMediaVideo.objects.create(
            name="video",
            project=self.project,
            keep_original=False,
        )
        self.create_json = {
            'type': self.entity_type.pk,
            'gid': str(uuid1()),
            'uid': str(uuid1()),
            'url': 'http://asdf.com',
            'name': 'asdf.mp4',
            'section': 'asdf section',
            'md5': '',
        }
        self.edit_permission = Permission.CAN_TRANSFER

    def tearDown(self):
        self.project.delete()

class AnalysisCountTestCase(
        APITestCase,
        PermissionCreateTestMixin,
        PermissionListMembershipTestMixin):
    def setUp(self):
        self.user = create_test_user()
        self.client.force_authenticate(self.user)
        self.project = create_test_project(self.user)
        self.membership = create_test_membership(self.user, self.project)
        self.entity_type = EntityTypeMediaVideo.objects.create(
            name="video",
            project=self.project,
            keep_original=False,
        )
        self.entities = [
            create_test_video(self.user, f'asdf{idx}', self.entity_type, self.project)
            for idx in range(random.randint(3, 10))
        ]
        self.analysis = AnalysisCount.objects.create(
            project=self.project,
            name="count_test",
            data_type=self.entity_type,
            data_query='enum_test:enum_val1',
        )
        self.attribute_type = AttributeTypeEnum.objects.create(
            name='enum_test',
            choices=['enum_val1', 'enum_val2', 'enum_val3'],
            applies_to=self.entity_type,
            project=self.project,
        )
        self.list_uri = 'Analyses'
        self.create_json = {
            'name': 'count_create_test',
            'data_type': self.entity_type.pk,
            'data_query': 'enum_test:enum_val2',
        }
        self.edit_permission = Permission.FULL_CONTROL

    def tearDown(self):
        self.project.delete()

class VersionTestCase(
        APITestCase,
        PermissionCreateTestMixin,
        PermissionListMembershipTestMixin,
        PermissionDetailMembershipTestMixin,
        PermissionDetailTestMixin):
    def setUp(self):
        self.user = create_test_user()
        self.client.force_authenticate(self.user)
        self.project = create_test_project(self.user)
        self.membership = create_test_membership(self.user, self.project)
        self.entity_type = EntityTypeMediaVideo.objects.create(
            name="video",
            project=self.project,
            keep_original=False,
        )
        self.media = create_test_video(self.user, f'asdf', self.entity_type, self.project)
        self.entities = [
            create_test_version(f'asdf{idx}', f'desc{idx}', idx, self.project, self.media)
            for idx in range(random.randint(6, 10))
        ]
        self.list_uri = 'Versions'
        self.detail_uri = 'Version'
        self.create_json = {
            'project': self.project.pk,
            'name': 'version_create_test',
            'media_id': self.media.pk,
            'description': 'asdf',
        }
        self.patch_json = {
            'description': 'asdf123',
        }
        self.edit_permission = Permission.CAN_EDIT

    def tearDown(self):
        self.project.delete()

class AttributeTypeTestCase(
        APITestCase,
        PermissionCreateTestMixin,
        PermissionListMembershipTestMixin,
        PermissionDetailMembershipTestMixin,
        PermissionDetailTestMixin):
    def setUp(self):
        self.user = create_test_user()
        self.client.force_authenticate(self.user)
        self.project = create_test_project(self.user)
        self.membership = create_test_membership(self.user, self.project)
        self.entity_type = EntityTypeMediaVideo.objects.create(
            name="video",
            project=self.project,
            keep_original=False,
        )
        attribute_types = create_test_attribute_types(self.entity_type, self.project)
        self.entities = list(attribute_types.values())
        self.list_uri = 'AttributeTypes'
        self.detail_uri = 'AttributeType'
        self.create_json = {
            'project': self.project.pk,
            'name': 'attribute_type_create_test',
            'description': 'asdf',
            'dtype': 'enum',
            'choices': ['asdf', 'asdfas', 'asdfasaa'],
            'applies_to': self.entity_type.pk,
        }
        self.patch_json = {
            'description': 'asdf123',
        }
        self.edit_permission = Permission.FULL_CONTROL

    def tearDown(self):
        self.project.delete()

