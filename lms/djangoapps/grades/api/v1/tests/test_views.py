"""
Tests for v1 views
"""
from __future__ import unicode_literals
from collections import OrderedDict

import ddt
from django.urls import reverse
from mock import MagicMock, patch
from opaque_keys import InvalidKeyError
from rest_framework import status
from rest_framework.test import APITestCase

from lms.djangoapps.grades.api.v1.tests.mixins import GradeViewTestMixin
from lms.djangoapps.grades.api.v1.views import CourseGradesView
from openedx.core.djangoapps.user_authn.tests.utils import AuthAndScopesTestMixin
from student.tests.factories import UserFactory


@ddt.ddt
class SingleUserGradesTests(GradeViewTestMixin, AuthAndScopesTestMixin, APITestCase):
    """
    Tests for grades related to a course and specific user
        e.g. /api/grades/v1/courses/{course_id}/?username={username}
             /api/grades/v1/courses/?course_id={course_id}&username={username}
    """
    default_scopes = CourseGradesView.required_scopes

    @classmethod
    def setUpClass(cls):
        super(SingleUserGradesTests, cls).setUpClass()
        cls.namespaced_url = 'grades_api:v1:course_grades'

    def get_url(self, username):
        """ This method is required by AuthAndScopesTestMixin. """
        base_url = reverse(
            self.namespaced_url,
            kwargs={
                'course_id': self.course_key,
            }
        )
        return "{0}?username={1}".format(base_url, username)

    def assert_success_response_for_student(self, response):
        """ This method is required by AuthAndScopesTestMixin. """
        expected_data = [{
            'username': self.student.username,
            'email': self.student.email,
            'letter_grade': None,
            'percent': 0.0,
            'course_id': str(self.course_key),
            'passed': False
        }]
        self.assertEqual(response.data, expected_data)

    def test_nonexistent_user(self):
        """
        Test that a request for a nonexistent username returns an error.
        """
        self.client.login(username=self.global_staff.username, password=self.password)
        resp = self.client.get(self.get_url('IDoNotExist'))
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

    def test_self_get_grade_not_enrolled(self):
        """
        Test that a user receives an error if she requests
        her own grade in a course where she is not enrolled.
        """
        # a user not enrolled in the course cannot request her grade
        unenrolled_user = UserFactory(password=self.password)
        self.client.login(username=unenrolled_user.username, password=self.password)
        resp = self.client.get(self.get_url(unenrolled_user.username))
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)
        self.assertIn('error_code', resp.data)
        self.assertEqual(
            resp.data['error_code'],
            'user_not_enrolled'
        )

    def test_no_grade(self):
        """
        Test the grade for a user who has not answered any test.
        """
        self.client.login(username=self.student.username, password=self.password)
        resp = self.client.get(self.get_url(self.student.username))
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        expected_data = [{
            'username': self.student.username,
            'email': self.student.email,
            'course_id': str(self.course_key),
            'passed': False,
            'percent': 0.0,
            'letter_grade': None
        }]

        self.assertEqual(resp.data, expected_data)

    def test_wrong_course_key(self):
        """
        Test that a request for an invalid course key returns an error.
        """
        def mock_from_string(*args, **kwargs):  # pylint: disable=unused-argument
            """Mocked function to always raise an exception"""
            raise InvalidKeyError('foo', 'bar')

        self.client.login(username=self.student.username, password=self.password)
        with patch('opaque_keys.edx.keys.CourseKey.from_string', side_effect=mock_from_string):
            resp = self.client.get(self.get_url(self.student.username))

        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)
        self.assertIn('error_code', resp.data)
        self.assertEqual(
            resp.data['error_code'],
            'invalid_course_key'
        )

    def test_course_does_not_exist(self):
        """
        Test that requesting a valid, nonexistent course key returns an error as expected.
        """
        self.client.login(username=self.student.username, password=self.password)
        base_url = reverse(
            self.namespaced_url,
            kwargs={
                'course_id': 'course-v1:MITx+8.MechCX+2014_T1',
            }
        )
        url = "{0}?username={1}".format(base_url, self.student.username)
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)
        self.assertIn('error_code', resp.data)
        self.assertEqual(
            resp.data['error_code'],
            'course_does_not_exist'
        )

    @ddt.data(
        ({'letter_grade': None, 'percent': 0.4, 'passed': False}),
        ({'letter_grade': 'Pass', 'percent': 1, 'passed': True}),
    )
    def test_grade(self, grade):
        """
        Test that the user gets her grade in case she answered tests with an insufficient score.
        """
        self.client.login(username=self.student.username, password=self.password)
        with patch('lms.djangoapps.grades.course_grade_factory.CourseGradeFactory.read') as mock_grade:
            grade_fields = {
                'letter_grade': grade['letter_grade'],
                'percent': grade['percent'],
                'passed': grade['letter_grade'] is not None,

            }
            mock_grade.return_value = MagicMock(**grade_fields)
            resp = self.client.get(self.get_url(self.student.username))

        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        expected_data = {
            'username': self.student.username,
            'email': self.student.email,
            'course_id': str(self.course_key),
        }

        expected_data.update(grade)
        self.assertEqual(resp.data, [expected_data])


@ddt.ddt
class CourseGradesViewTest(GradeViewTestMixin, APITestCase):
    """
    Tests for grades related to all users in a course
        e.g. /api/grades/v1/courses/{course_id}/
             /api/grades/v1/courses/?course_id={course_id}
    """

    @classmethod
    def setUpClass(cls):
        super(CourseGradesViewTest, cls).setUpClass()
        cls.namespaced_url = 'grades_api:v1:course_grades'

    def get_url(self, course_key=None):
        """
        Helper function to create the url
        """
        base_url = reverse(
            self.namespaced_url,
            kwargs={
                'course_id': course_key or self.course_key,
            }
        )

        return base_url

    def test_anonymous(self):
        resp = self.client.get(self.get_url())
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_student(self):
        self.client.login(username=self.student.username, password=self.password)
        resp = self.client.get(self.get_url())
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_course_does_not_exist(self):
        self.client.login(username=self.global_staff.username, password=self.password)
        resp = self.client.get(
            self.get_url(course_key='course-v1:MITx+8.MechCX+2014_T1')
        )
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

    def test_course_no_enrollments(self):
        self.client.login(username=self.global_staff.username, password=self.password)
        resp = self.client.get(
            self.get_url(course_key=self.empty_course.id)
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        expected_data = OrderedDict([
            ('next', None),
            ('previous', None),
            ('results', []),
        ])
        self.assertEqual(expected_data, resp.data)

    def test_staff_can_get_all_grades(self):
        self.client.login(username=self.global_staff.username, password=self.password)
        resp = self.client.get(self.get_url())

        # this should have permission to access this API endpoint
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        expected_data = OrderedDict([
            ('next', None),
            ('previous', None),
            ('results', [
                {
                    'username': self.student.username,
                    'email': self.student.email,
                    'course_id': str(self.course.id),
                    'passed': False,
                    'percent': 0.0,
                    'letter_grade': None
                },
                {
                    'username': self.other_student.username,
                    'email': self.other_student.email,
                    'course_id': str(self.course.id),
                    'passed': False,
                    'percent': 0.0,
                    'letter_grade': None
                },
            ]),
        ])

        self.assertEqual(expected_data, resp.data)


# class TestAViewToKill(APITestCase):
#     """
#     Code that we are testing:
# -----------------------------------------------------------------------------
# def get_random_grade_percent():
#     rand = random.Random()
#     percent = rand.random()
#     return round(percent, 2)

#     @verify_course_exists
#     def get(self, request, course_id=None):
#         username = request.GET.get('username')

#         course_key = get_course_key(request, course_id)

#         if username:
#             with self._get_user_or_raise(request, course_key) as grade_user:
#                 percent = get_random_grade_percent()
#                 return Response([
#                     {
#                         'username': grade_user.username,
#                         'letter_grade': '?',
#                         'percent': percent,
#                         'inverse_percent': round(100.0 / percent),
#                         'passed': percent > 0.5,
#                         'course_id': str(course_key),
#                         'email': grade_user.email,
#                     }
#                 ])
#         else:
#             raise self.api_error(
#                 status_code=status.HTTP_404_NOT_FOUND,
#                 developer_message='The user does not exist',
#                 error_code='user_does_not_exist',
#             )
# ----------------------------------------------------------------------------


#     What are the different test cases we have?
#     - @verify_course_exists - ok, we need a course that actually exists (in our test)
#     - ...

#     What tools do we need to write our tests?
#     - We need a test client (which I'm telling you by inheriting from APITestCase).
#     -
#     """
#     def setUp(self):
#         pass


##################################################################################################
# ________              /\ __    .____                  __       ___ ___                         #
# \______ \   ____   ___)//  |_  |    |    ____   ____ |  | __  /   |   \   ___________   ____   #
#  |    |  \ /  _ \ /    \   __\ |    |   /  _ \ /  _ \|  |/ / /    ~    \_/ __ \_  __ \_/ __ \  #
#  |    `   (  <_> )   |  \  |   |    |__(  <_> |  <_> )    <  \    Y    /\  ___/|  | \/\  ___/  #
# /_______  /\____/|___|  /__|   |_______ \____/ \____/|__|_ \  \___|_  /  \___  >__|    \___  > #
#         \/            \/               \/                 \/        \/       \/            \/  #
# ________              /\ __    .____                  __       ___ ___                         #
# \______ \   ____   ___)//  |_  |    |    ____   ____ |  | __  /   |   \   ___________   ____   #
#  |    |  \ /  _ \ /    \   __\ |    |   /  _ \ /  _ \|  |/ / /    ~    \_/ __ \_  __ \_/ __ \  #
#  |    `   (  <_> )   |  \  |   |    |__(  <_> |  <_> )    <  \    Y    /\  ___/|  | \/\  ___/  #
# /_______  /\____/|___|  /__|   |_______ \____/ \____/|__|_ \  \___|_  /  \___  >__|    \___  > #
#         \/            \/               \/                 \/        \/       \/            \/  #
# ________              /\ __    .____                  __       ___ ___                         #
# \______ \   ____   ___)//  |_  |    |    ____   ____ |  | __  /   |   \   ___________   ____   #
#  |    |  \ /  _ \ /    \   __\ |    |   /  _ \ /  _ \|  |/ / /    ~    \_/ __ \_  __ \_/ __ \  #
#  |    `   (  <_> )   |  \  |   |    |__(  <_> |  <_> )    <  \    Y    /\  ___/|  | \/\  ___/  #
# /_______  /\____/|___|  /__|   |_______ \____/ \____/|__|_ \  \___|_  /  \___  >__|    \___  > #
#         \/            \/               \/                 \/        \/       \/            \/  #
# ________              /\ __    .____                  __       ___ ___                         #
# \______ \   ____   ___)//  |_  |    |    ____   ____ |  | __  /   |   \   ___________   ____   #
#  |    |  \ /  _ \ /    \   __\ |    |   /  _ \ /  _ \|  |/ / /    ~    \_/ __ \_  __ \_/ __ \  #
#  |    `   (  <_> )   |  \  |   |    |__(  <_> |  <_> )    <  \    Y    /\  ___/|  | \/\  ___/  #
# /_______  /\____/|___|  /__|   |_______ \____/ \____/|__|_ \  \___|_  /  \___  >__|    \___  > #
#         \/            \/               \/                 \/        \/       \/            \/  #
#                                                                                                #
# ________              /\ __    .____                  __       ___ ___                         #
# \______ \   ____   ___)//  |_  |    |    ____   ____ |  | __  /   |   \   ___________   ____   #
#  |    |  \ /  _ \ /    \   __\ |    |   /  _ \ /  _ \|  |/ / /    ~    \_/ __ \_  __ \_/ __ \  #
#  |    `   (  <_> )   |  \  |   |    |__(  <_> |  <_> )    <  \    Y    /\  ___/|  | \/\  ___/  #
# /_______  /\____/|___|  /__|   |_______ \____/ \____/|__|_ \  \___|_  /  \___  >__|    \___  > #
#         \/            \/               \/                 \/        \/       \/            \/  #
# ________              /\ __    .____                  __       ___ ___                         #
# \______ \   ____   ___)//  |_  |    |    ____   ____ |  | __  /   |   \   ___________   ____   #
#  |    |  \ /  _ \ /    \   __\ |    |   /  _ \ /  _ \|  |/ / /    ~    \_/ __ \_  __ \_/ __ \  #
#  |    `   (  <_> )   |  \  |   |    |__(  <_> |  <_> )    <  \    Y    /\  ___/|  | \/\  ___/  #
# /_______  /\____/|___|  /__|   |_______ \____/ \____/|__|_ \  \___|_  /  \___  >__|    \___  > #
#         \/            \/               \/                 \/        \/       \/            \/  #
#                                                                                                #
# ________              /\ __    .____                  __       ___ ___                         #
# \______ \   ____   ___)//  |_  |    |    ____   ____ |  | __  /   |   \   ___________   ____   #
#  |    |  \ /  _ \ /    \   __\ |    |   /  _ \ /  _ \|  |/ / /    ~    \_/ __ \_  __ \_/ __ \  #
#  |    `   (  <_> )   |  \  |   |    |__(  <_> |  <_> )    <  \    Y    /\  ___/|  | \/\  ___/  #
# /_______  /\____/|___|  /__|   |_______ \____/ \____/|__|_ \  \___|_  /  \___  >__|    \___  > #
#         \/            \/               \/                 \/        \/       \/            \/  #
# ________              /\ __    .____                  __       ___ ___                         #
# \______ \   ____   ___)//  |_  |    |    ____   ____ |  | __  /   |   \   ___________   ____   #
#  |    |  \ /  _ \ /    \   __\ |    |   /  _ \ /  _ \|  |/ / /    ~    \_/ __ \_  __ \_/ __ \  #
#  |    `   (  <_> )   |  \  |   |    |__(  <_> |  <_> )    <  \    Y    /\  ___/|  | \/\  ___/  #
# /_______  /\____/|___|  /__|   |_______ \____/ \____/|__|_ \  \___|_  /  \___  >__|    \___  > #
#         \/            \/               \/                 \/        \/       \/            \/  #
#                                                                                                #
# ________              /\ __    .____                  __       ___ ___                         #
# \______ \   ____   ___)//  |_  |    |    ____   ____ |  | __  /   |   \   ___________   ____   #
#  |    |  \ /  _ \ /    \   __\ |    |   /  _ \ /  _ \|  |/ / /    ~    \_/ __ \_  __ \_/ __ \  #
#  |    `   (  <_> )   |  \  |   |    |__(  <_> |  <_> )    <  \    Y    /\  ___/|  | \/\  ___/  #
# /_______  /\____/|___|  /__|   |_______ \____/ \____/|__|_ \  \___|_  /  \___  >__|    \___  > #
#         \/            \/               \/                 \/        \/       \/            \/  #
# ________              /\ __    .____                  __       ___ ___                         #
# \______ \   ____   ___)//  |_  |    |    ____   ____ |  | __  /   |   \   ___________   ____   #
#  |    |  \ /  _ \ /    \   __\ |    |   /  _ \ /  _ \|  |/ / /    ~    \_/ __ \_  __ \_/ __ \  #
#  |    `   (  <_> )   |  \  |   |    |__(  <_> |  <_> )    <  \    Y    /\  ___/|  | \/\  ___/  #
# /_______  /\____/|___|  /__|   |_______ \____/ \____/|__|_ \  \___|_  /  \___  >__|    \___  > #
#         \/            \/               \/                 \/        \/       \/            \/  #
#                                                                                                #
# ________              /\ __    .____                  __       ___ ___                         #
# \______ \   ____   ___)//  |_  |    |    ____   ____ |  | __  /   |   \   ___________   ____   #
#  |    |  \ /  _ \ /    \   __\ |    |   /  _ \ /  _ \|  |/ / /    ~    \_/ __ \_  __ \_/ __ \  #
#  |    `   (  <_> )   |  \  |   |    |__(  <_> |  <_> )    <  \    Y    /\  ___/|  | \/\  ___/  #
# /_______  /\____/|___|  /__|   |_______ \____/ \____/|__|_ \  \___|_  /  \___  >__|    \___  > #
#         \/            \/               \/                 \/        \/       \/            \/  #
# ________              /\ __    .____                  __       ___ ___                         #
# \______ \   ____   ___)//  |_  |    |    ____   ____ |  | __  /   |   \   ___________   ____   #
#  |    |  \ /  _ \ /    \   __\ |    |   /  _ \ /  _ \|  |/ / /    ~    \_/ __ \_  __ \_/ __ \  #
#  |    `   (  <_> )   |  \  |   |    |__(  <_> |  <_> )    <  \    Y    /\  ___/|  | \/\  ___/  #
# /_______  /\____/|___|  /__|   |_______ \____/ \____/|__|_ \  \___|_  /  \___  >__|    \___  > #
#         \/            \/               \/                 \/        \/       \/            \/  #
#                                                                                                #
# ________              /\ __    .____                  __       ___ ___                         #
# \______ \   ____   ___)//  |_  |    |    ____   ____ |  | __  /   |   \   ___________   ____   #
#  |    |  \ /  _ \ /    \   __\ |    |   /  _ \ /  _ \|  |/ / /    ~    \_/ __ \_  __ \_/ __ \  #
#  |    `   (  <_> )   |  \  |   |    |__(  <_> |  <_> )    <  \    Y    /\  ___/|  | \/\  ___/  #
# /_______  /\____/|___|  /__|   |_______ \____/ \____/|__|_ \  \___|_  /  \___  >__|    \___  > #
#         \/            \/               \/                 \/        \/       \/            \/  #
# ________              /\ __    .____                  __       ___ ___                         #
# \______ \   ____   ___)//  |_  |    |    ____   ____ |  | __  /   |   \   ___________   ____   #
#  |    |  \ /  _ \ /    \   __\ |    |   /  _ \ /  _ \|  |/ / /    ~    \_/ __ \_  __ \_/ __ \  #
#  |    `   (  <_> )   |  \  |   |    |__(  <_> |  <_> )    <  \    Y    /\  ___/|  | \/\  ___/  #
# /_______  /\____/|___|  /__|   |_______ \____/ \____/|__|_ \  \___|_  /  \___  >__|    \___  > #
#         \/            \/               \/                 \/        \/       \/            \/  #
#                                                                                                #
# ________              /\ __    .____                  __       ___ ___                         #
# \______ \   ____   ___)//  |_  |    |    ____   ____ |  | __  /   |   \   ___________   ____   #
#  |    |  \ /  _ \ /    \   __\ |    |   /  _ \ /  _ \|  |/ / /    ~    \_/ __ \_  __ \_/ __ \  #
#  |    `   (  <_> )   |  \  |   |    |__(  <_> |  <_> )    <  \    Y    /\  ___/|  | \/\  ___/  #
# /_______  /\____/|___|  /__|   |_______ \____/ \____/|__|_ \  \___|_  /  \___  >__|    \___  > #
#         \/            \/               \/                 \/        \/       \/            \/  #
# ________              /\ __    .____                  __       ___ ___                         #
# \______ \   ____   ___)//  |_  |    |    ____   ____ |  | __  /   |   \   ___________   ____   #
#  |    |  \ /  _ \ /    \   __\ |    |   /  _ \ /  _ \|  |/ / /    ~    \_/ __ \_  __ \_/ __ \  #
#  |    `   (  <_> )   |  \  |   |    |__(  <_> |  <_> )    <  \    Y    /\  ___/|  | \/\  ___/  #
# /_______  /\____/|___|  /__|   |_______ \____/ \____/|__|_ \  \___|_  /  \___  >__|    \___  > #
#         \/            \/               \/                 \/        \/       \/            \/  #
#                                                                                                #
# ________              /\ __    .____                  __       ___ ___                         #
# \______ \   ____   ___)//  |_  |    |    ____   ____ |  | __  /   |   \   ___________   ____   #
#  |    |  \ /  _ \ /    \   __\ |    |   /  _ \ /  _ \|  |/ / /    ~    \_/ __ \_  __ \_/ __ \  #
#  |    `   (  <_> )   |  \  |   |    |__(  <_> |  <_> )    <  \    Y    /\  ___/|  | \/\  ___/  #
# /_______  /\____/|___|  /__|   |_______ \____/ \____/|__|_ \  \___|_  /  \___  >__|    \___  > #
#         \/            \/               \/                 \/        \/       \/            \/  #
# ________              /\ __    .____                  __       ___ ___                         #
# \______ \   ____   ___)//  |_  |    |    ____   ____ |  | __  /   |   \   ___________   ____   #
#  |    |  \ /  _ \ /    \   __\ |    |   /  _ \ /  _ \|  |/ / /    ~    \_/ __ \_  __ \_/ __ \  #
#  |    `   (  <_> )   |  \  |   |    |__(  <_> |  <_> )    <  \    Y    /\  ___/|  | \/\  ___/  #
# /_______  /\____/|___|  /__|   |_______ \____/ \____/|__|_ \  \___|_  /  \___  >__|    \___  > #
#         \/            \/               \/                 \/        \/       \/            \/  #
#                                                                                                #
# ________              /\ __    .____                  __       ___ ___                         #
# \______ \   ____   ___)//  |_  |    |    ____   ____ |  | __  /   |   \   ___________   ____   #
#  |    |  \ /  _ \ /    \   __\ |    |   /  _ \ /  _ \|  |/ / /    ~    \_/ __ \_  __ \_/ __ \  #
#  |    `   (  <_> )   |  \  |   |    |__(  <_> |  <_> )    <  \    Y    /\  ___/|  | \/\  ___/  #
# /_______  /\____/|___|  /__|   |_______ \____/ \____/|__|_ \  \___|_  /  \___  >__|    \___  > #
#         \/            \/               \/                 \/        \/       \/            \/  #
# ________              /\ __    .____                  __       ___ ___                         #
# \______ \   ____   ___)//  |_  |    |    ____   ____ |  | __  /   |   \   ___________   ____   #
#  |    |  \ /  _ \ /    \   __\ |    |   /  _ \ /  _ \|  |/ / /    ~    \_/ __ \_  __ \_/ __ \  #
#  |    `   (  <_> )   |  \  |   |    |__(  <_> |  <_> )    <  \    Y    /\  ___/|  | \/\  ___/  #
# /_______  /\____/|___|  /__|   |_______ \____/ \____/|__|_ \  \___|_  /  \___  >__|    \___  > #
#         \/            \/               \/                 \/        \/       \/            \/  #
#                                                                                                #
# ________              /\ __    .____                  __       ___ ___                         #
# \______ \   ____   ___)//  |_  |    |    ____   ____ |  | __  /   |   \   ___________   ____   #
#  |    |  \ /  _ \ /    \   __\ |    |   /  _ \ /  _ \|  |/ / /    ~    \_/ __ \_  __ \_/ __ \  #
#  |    `   (  <_> )   |  \  |   |    |__(  <_> |  <_> )    <  \    Y    /\  ___/|  | \/\  ___/  #
# /_______  /\____/|___|  /__|   |_______ \____/ \____/|__|_ \  \___|_  /  \___  >__|    \___  > #
#         \/            \/               \/                 \/        \/       \/            \/  #
# ________              /\ __    .____                  __       ___ ___                         #
# \______ \   ____   ___)//  |_  |    |    ____   ____ |  | __  /   |   \   ___________   ____   #
#  |    |  \ /  _ \ /    \   __\ |    |   /  _ \ /  _ \|  |/ / /    ~    \_/ __ \_  __ \_/ __ \  #
#  |    `   (  <_> )   |  \  |   |    |__(  <_> |  <_> )    <  \    Y    /\  ___/|  | \/\  ___/  #
# /_______  /\____/|___|  /__|   |_______ \____/ \____/|__|_ \  \___|_  /  \___  >__|    \___  > #
#         \/            \/               \/                 \/        \/       \/            \/  #
##################################################################################################

from datetime import datetime

import mock
from pytz import UTC

from lms.djangoapps.courseware.tests.factories import GlobalStaffFactory
from openedx.core.djangoapps.content.course_overviews.tests.factories import CourseOverviewFactory
from student.tests.factories import CourseEnrollmentFactory, UserFactory
from xmodule.modulestore.tests.factories import CourseFactory
from xmodule.modulestore.tests.django_utils import SharedModuleStoreTestCase, TEST_DATA_SPLIT_MODULESTORE

class TestAViewToKill(SharedModuleStoreTestCase, APITestCase):
    """
    Code that we are testing:
-----------------------------------------------------------------------------
def get_random_grade_percent():
    rand = random.Random()
    percent = rand.random()
    return round(percent, 2)

    @verify_course_exists
    def get(self, request, course_id=None):
        username = request.GET.get('username')

        course_key = get_course_key(request, course_id)

        if username:
            with self._get_user_or_raise(request, course_key) as grade_user:
                percent = get_random_grade_percent()
                return Response([
                    {
                        'username': grade_user.username,
                        'letter_grade': '?',
                        'percent': percent,
                        'inverse_percent': round(100.0 / percent),
                        'passed': percent > 0.5,
                        'course_id': str(course_key),
                        'email': grade_user.email,
                    }
                ])
        else:
            raise self.api_error(
                status_code=status.HTTP_404_NOT_FOUND,
                developer_message='The username is required',
                error_code='username_is_required',
            )
----------------------------------------------------------------------------


    What are the different test cases we have?
    - @verify_course_exists - ok, we need a course that actually exists (in our test)
    - with self._get_user_or_raise(request, course_key) as grade_user: - we need a user
    (who is also enrolled in the course)
    - 'inverse_percent': round(100.0 / percent) - check for ZeroDivisionError
    - the whole else clause
    - the happy path

    What tools do we need to write our tests?
    - We need a test client (which I'm telling you by inheriting from APITestCase).
    - a course factory
    - a user factory
    - a course enrollment factory
    - mock (for patching our random function)
    """
    MODULESTORE = TEST_DATA_SPLIT_MODULESTORE

    @classmethod
    def setUpClass(cls):
        super(TestAViewToKill, cls).setUpClass()
        cls.course = CourseFactory.create(display_name='test_course', run='2019T2')
        _ = CourseOverviewFactory.create(id=cls.course.id)

    def setUp(self):
        super(TestAViewToKill, self).setUp()
        self.password = 'test'
        self.global_staff = GlobalStaffFactory.create()
        self.student = UserFactory(password=self.password, username='student')
        self.other_student = UserFactory(password=self.password, username='other_student')
        date = datetime(2013, 1, 22, tzinfo=UTC)
        CourseEnrollmentFactory.create(course_id=self.course.id, user=self.student, created=date)

    def get_url(self, course_id):
        return reverse(
            'grades_api:v1:course_grades_random',
            kwargs={
                'course_id': course_id,
            }
        )

    def test_ok_when_course_does_exist(self):
        self.client.login(username=self.global_staff.username, password=self.password)
        response = self.client.get(self.get_url(self.course.id) + '?username={}'.format(self.student.username))
        self.assertEqual(status.HTTP_200_OK, response.status_code)

    def test_error_when_course_does_not_exist(self):
        self.client.login(username=self.global_staff.username, password=self.password)
        response = self.client.get(self.get_url('course-v1:org.1+somecourse+2030T2'))
        self.assertEqual(status.HTTP_404_NOT_FOUND, response.status_code)
        self.assertTrue('course_does_not_exist' in response.content)

    def test_error_when_username_does_not_exist(self):
        self.client.login(username=self.global_staff.username, password=self.password)
        response = self.client.get(self.get_url(self.course.id) + '?username=foo')
        self.assertEqual(status.HTTP_404_NOT_FOUND, response.status_code)
        self.assertTrue('user_does_not_exist' in response.content)

    def test_error_when_user_not_enrolled(self):
        self.client.login(username=self.global_staff.username, password=self.password)
        response = self.client.get(self.get_url(self.course.id) + '?username={}'.format(self.other_student.username))
        self.assertEqual(status.HTTP_404_NOT_FOUND, response.status_code)
        self.assertTrue('user_not_enrolled' in response.content)

    def test_error_when_username_not_provided(self):
        self.client.login(username=self.global_staff.username, password=self.password)
        response = self.client.get(self.get_url(self.course.id))
        self.assertEqual(status.HTTP_404_NOT_FOUND, response.status_code)
        self.assertTrue('username_is_required' in response.content)

    def test_zero_division_ok(self):
        with mock.patch(
                'lms.djangoapps.grades.api.v1.views.get_random_grade_percent',
                return_value=0
        ):
            self.client.login(username=self.global_staff.username, password=self.password)
            response = self.client.get(self.get_url(self.course.id) + '?username={}'.format(self.student.username))
            self.assertEqual(status.HTTP_200_OK, response.status_code)
            expected_data = [{
                'username': self.student.username,
                'letter_grade': '?',
                'percent': 0,
                'inverse_percent': 'NaN',
                'passed': False,
                'course_id': str(self.course.id),
                'email': self.student.email,
            }]
            self.assertEqual(expected_data, response.data)

    def test_happy_path(self):
        with mock.patch(
                'lms.djangoapps.grades.api.v1.views.get_random_grade_percent',
                return_value=0.5
        ):
            self.client.login(username=self.global_staff.username, password=self.password)
            response = self.client.get(self.get_url(self.course.id) + '?username={}'.format(self.student.username))
            self.assertEqual(status.HTTP_200_OK, response.status_code)
            expected_data = [{
                'username': self.student.username,
                'letter_grade': '?',
                'percent': 0.5,
                'inverse_percent': 2.0,
                'passed': False,
                'course_id': str(self.course.id),
                'email': self.student.email,
            }]
            self.assertEqual(expected_data, response.data)
