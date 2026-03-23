"""
Unit tests for course details views.
"""
import json
from unittest.mock import patch

import ddt
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from openedx_authz.constants.roles import COURSE_EDITOR

from cms.djangoapps.contentstore.tests.utils import CourseTestCase
from openedx.core.djangoapps.authz.tests.mixins import AuthzTestMixin

from ...mixins import PermissionAccessMixin


@ddt.ddt
class CourseDetailsViewTest(CourseTestCase, PermissionAccessMixin):
    """
    Tests for CourseDetailsView.
    """

    def setUp(self):
        super().setUp()
        self.url = reverse(
            "cms.djangoapps.contentstore:v1:course_details",
            kwargs={"course_id": self.course.id},
        )

    def test_put_permissions_unauthenticated(self):
        """
        Test that an error is returned in the absence of auth credentials.
        """
        self.client.logout()
        response = self.client.put(self.url)
        error = self.get_and_check_developer_response(response)
        self.assertEqual(error, "Authentication credentials were not provided.")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_put_permissions_unauthorized(self):
        """
        Test that an error is returned if the user is unauthorised.
        """
        client, _ = self.create_non_staff_authed_user_client()
        response = client.put(self.url)
        error = self.get_and_check_developer_response(response)
        self.assertEqual(error, "You do not have permission to perform this action.")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    @patch.dict("django.conf.settings.FEATURES", {"ENABLE_PREREQUISITE_COURSES": True})
    def test_put_invalid_pre_requisite_course(self):
        pre_requisite_course_keys = [str(self.course.id), "invalid_key"]
        request_data = {"pre_requisite_courses": pre_requisite_course_keys}
        response = self.client.put(
            path=self.url,
            data=json.dumps(request_data),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.json()["error"], "Invalid prerequisite course key")

    def test_put_course_details(self):
        request_data = {
            "about_sidebar_html": "",
            "banner_image_name": "images_course_image.jpg",
            "banner_image_asset_path": "/asset-v1:edX+E2E-101+course+type@asset+block@images_course_image.jpg",
            "certificate_available_date": "2029-01-02T00:00:00Z",
            "certificates_display_behavior": "end",
            "course_id": "E2E-101",
            "course_image_asset_path": "/static/studio/images/pencils.jpg",
            "course_image_name": "bar_course_image_name",
            "description": "foo_description",
            "duration": "",
            "effort": None,
            "end_date": "2023-08-01T01:30:00Z",
            "enrollment_end": "2023-05-30T01:00:00Z",
            "enrollment_start": "2023-05-29T01:00:00Z",
            "entrance_exam_enabled": "",
            "entrance_exam_id": "",
            "entrance_exam_minimum_score_pct": "50",
            "intro_video": None,
            "language": "creative-commons: ver=4.0 BY NC ND",
            "learning_info": ["foo", "bar"],
            "license": "creative-commons: ver=4.0 BY NC ND",
            "org": "edX",
            "overview": '<section class="about"></section>',
            "pre_requisite_courses": [],
            "run": "course",
            "self_paced": None,
            "short_description": "",
            "start_date": "2023-06-01T01:30:00Z",
            "subtitle": "",
            "syllabus": None,
            "title": "",
            "video_thumbnail_image_asset_path": "/asset-v1:edX+E2E-101+course+type@asset+block@images_course_image.jpg",
            "video_thumbnail_image_name": "images_course_image.jpg",
            "instructor_info": {
                "instructors": [
                    {
                        "name": "foo bar",
                        "title": "title",
                        "organization": "org",
                        "image": "image",
                        "bio": "",
                    }
                ]
            },
        }
        response = self.client.put(
            path=self.url,
            data=json.dumps(request_data),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)


@ddt.ddt
class CourseDetailsAuthzViewTest(AuthzTestMixin, CourseTestCase):
    """
    Tests for CourseDetailsView using AuthZ permissions.
    """

    def setUp(self):
        super().setUp()
        self.url = reverse(
            "cms.djangoapps.contentstore:v1:course_details",
            kwargs={"course_id": self.course.id},
        )
        self.request_data = {
            "about_sidebar_html": "",
            "banner_image_name": "images_course_image.jpg",
            "banner_image_asset_path": "/asset-v1:edX+E2E-101+course+type@asset+block@images_course_image.jpg",
            "certificate_available_date": "2029-01-02T00:00:00Z",
            "certificates_display_behavior": "end",
            "course_id": "E2E-101",
            "course_image_asset_path": "/static/studio/images/pencils.jpg",
            "course_image_name": "bar_course_image_name",
            "description": "foo_description",
            "duration": "",
            "effort": None,
            "end_date": "2023-08-01T01:30:00Z",
            "enrollment_end": "2023-05-30T01:00:00Z",
            "enrollment_start": "2023-05-29T01:00:00Z",
            "entrance_exam_enabled": "",
            "entrance_exam_id": "",
            "entrance_exam_minimum_score_pct": "50",
            "intro_video": None,
            "language": "creative-commons: ver=4.0 BY NC ND",
            "learning_info": ["foo", "bar"],
            "license": "creative-commons: ver=4.0 BY NC ND",
            "org": "edX",
            "overview": '<section class="about"></section>',
            "pre_requisite_courses": [],
            "run": "course",
            "self_paced": None,
            "short_description": "",
            "start_date": "2023-06-01T01:30:00Z",
            "subtitle": "",
            "syllabus": None,
            "title": "",
            "video_thumbnail_image_asset_path": "/asset-v1:edX+E2E-101+course+type@asset+block@images_course_image.jpg",
            "video_thumbnail_image_name": "images_course_image.jpg",
            "instructor_info": {
                "instructors": [
                    {
                        "name": "foo bar",
                        "title": "title",
                        "organization": "org",
                        "image": "image",
                        "bio": "",
                    }
                ]
            },
        }

    def test_put_permissions_unauthenticated(self):
        """
        Test that an error is returned in the absence of auth credentials.
        """
        client = APIClient()  # no auth
        response = client.put(self.url)

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_put_permissions_unauthorized(self):
        """
        Test that an error is returned if the user is unauthorised.
        """
        response = self.unauthorized_client.put(self.url)

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_get_course_details_authorized(self):
        """
        Authorized user with COURSE_EDITOR role can access course details.
        """
        self.add_user_to_role(
            self.authorized_user,
            COURSE_EDITOR.external_key,
            self.course.id
        )

        response = self.authorized_client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_get_course_details_unauthorized(self):
        """
        Unauthorized user should receive 403.
        """
        response = self.unauthorized_client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_get_course_details_staff_user(self):
        """
        Django staff user should bypass AuthZ and access course details.
        """
        response = self.staff_client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_get_course_details_super_user(self):
        """
        Superuser should bypass AuthZ and access course details.
        """
        response = self.super_client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_put_authorized_user_can_update_course(self):
        """
        Authorized user with COURSE_EDITOR role can update course details.
        """
        self.add_user_to_role(
            self.authorized_user,
            COURSE_EDITOR.external_key,
            self.course.id
        )

        response = self.authorized_client.put(
            path=self.url,
            data=json.dumps(self.request_data),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_put_user_without_role_then_added_can_update(self):
        """
        Validate dynamic role assignment works for PUT.
        """
        # Initially unauthorized
        response = self.unauthorized_client.put(
            path=self.url,
            data=json.dumps(self.request_data),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

        # Assign role dynamically
        self.add_user_to_role(
            self.unauthorized_user,
            COURSE_EDITOR.external_key,
            self.course.id
        )

        response = self.unauthorized_client.put(
            path=self.url,
            data=json.dumps(self.request_data),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    @patch.dict("django.conf.settings.FEATURES", {"ENABLE_PREREQUISITE_COURSES": True})
    def test_put_invalid_pre_requisite_course_with_authz(self):
        """
        Ensure validation still applies under AuthZ.
        """
        self.add_user_to_role(
            self.authorized_user,
            COURSE_EDITOR.external_key,
            self.course.id
        )

        pre_requisite_course_keys = [str(self.course.id), "invalid_key"]
        request_data = {"pre_requisite_courses": pre_requisite_course_keys}

        response = self.authorized_client.put(
            path=self.url,
            data=json.dumps(request_data),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.json()["error"], "Invalid prerequisite course key")

    def test_staff_user_can_update_without_authz_role(self):
        """
        Django staff user should bypass AuthZ.
        """
        response = self.staff_client.put(
            path=self.url,
            data=json.dumps(self.request_data),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_superuser_can_update_without_authz_role(self):
        """
        Superuser should bypass AuthZ.
        """
        response = self.super_client.put(
            path=self.url,
            data=json.dumps(self.request_data),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
