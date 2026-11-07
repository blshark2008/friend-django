"""
Skillspace API integration service.

Handles communication with skillspace.ru platform:
- Adding/removing students via API
- Sending student events via webhooks
- Receiving webhook callbacks with completion data
"""

import logging
import requests
from django.conf import settings
from django.utils import timezone
from datetime import timedelta

logger = logging.getLogger(__name__)


class SkillspaceAPIError(Exception):
    """Exception raised for Skillspace API errors."""
    pass


class SkillspaceClient:
    """Client for Skillspace.ru API."""

    BASE_URL = 'https://api.skillspace.ru'  # Adjust if different
    WEBHOOK_BASE_URL = 'https://skillspace.ru'  # Adjust if different

    def __init__(self, api_key: str = None, base_url: str = None):
        self.api_key = api_key or getattr(settings, 'SKILLSPACE_API_KEY', '')
        self.base_url = base_url or getattr(settings, 'SKILLSPACE_BASE_URL', self.BASE_URL)
        self.webhook_base_url = getattr(settings, 'SKILLSPACE_WEBHOOK_BASE_URL', self.WEBHOOK_BASE_URL)

    def _headers(self):
        return {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {self.api_key}',
        }

    def _get(self, endpoint: str, params: dict = None) -> dict:
        """Make GET request to Skillspace API."""
        url = f'{self.base_url}{endpoint}'
        try:
            response = requests.get(url, headers=self._headers(), params=params, timeout=30)
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            logger.error(f'Skillspace API GET error: {e}')
            raise SkillspaceAPIError(f'API GET error: {e}')

    def _post(self, endpoint: str, data: dict) -> dict:
        """Make POST request to Skillspace API."""
        url = f'{self.base_url}{endpoint}'
        try:
            response = requests.post(url, headers=self._headers(), json=data, timeout=30)
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            logger.error(f'Skillspace API POST error: {e}')
            raise SkillspaceAPIError(f'API POST error: {e}')

    def add_student_to_course(self, course_id: int, student_email: str,
                              first_name: str = '', last_name: str = '') -> dict:
        """
        Add a student to a course.
        According to Skillspace docs: POST /api/v1/students
        """
        data = {
            'course_id': course_id,
            'email': student_email,
            'first_name': first_name,
            'last_name': last_name,
        }
        logger.info(f'Adding student {student_email} to course {course_id}')
        return self._post('/api/v1/students', data)

    def remove_student_from_course(self, course_id: int, student_email: str) -> dict:
        """Remove a student from a course."""
        data = {
            'course_id': course_id,
            'email': student_email,
        }
        logger.info(f'Removing student {student_email} from course {course_id}')
        return self._post('/api/v1/students/remove', data)

    def get_course_students(self, course_id: int) -> list:
        """Get list of students enrolled in a course."""
        return self._get(f'/api/v1/courses/{course_id}/students')

    def get_course_progress(self, course_id: int, student_email: str = None) -> dict:
        """Get course progress for a student or all students."""
        params = {'email': student_email} if student_email else None
        return self._get(f'/api/v1/courses/{course_id}/progress', params=params)

    def get_student_results(self, course_id: int, student_email: str) -> dict:
        """Get test/lesson results for a student in a course."""
        return self._get(f'/api/v1/students/results', {
            'course_id': course_id,
            'email': student_email,
        })

    def sync_students_to_course(self, course_id: int, students: list) -> dict:
        """
        Sync students to a course.
        students: list of dicts with 'email', 'first_name', 'last_name'
        """
        results = {'added': [], 'errors': []}
        for student in students:
            try:
                self.add_student_to_course(
                    course_id,
                    student['email'],
                    student.get('first_name', ''),
                    student.get('last_name', ''),
                )
                results['added'].append(student['email'])
            except SkillspaceAPIError as e:
                results['errors'].append({
                    'email': student['email'],
                    'error': str(e),
                })
                logger.error(f'Failed to add student {student["email"]}: {e}')
        return results

    def generate_webhook_url(self, training_id: int) -> str:
        """Generate webhook URL for receiving events from Skillspace."""
        from training.models import Training
        return f'{self.webhook_base_url}/training/types/{training_id}/sync-webhook/'


def send_webhook_to_skillspace(course_id: int, event_type: str, data: dict):
    """
    Send webhook event to Skillspace platform.
    
    Events: student_enrolled, student_completed, student_test_passed, etc.
    """
    client = SkillspaceClient()
    payload = {
        'event_type': event_type,
        'course_id': course_id,
        'data': data,
        'timestamp': timezone.now().isoformat(),
    }
    try:
        # Skillspace webhook endpoint - adjust URL as needed
        url = f'{client.base_url}/api/v1/webhooks/events'
        response = requests.post(url, json=payload, headers=client._headers(), timeout=30)
        response.raise_for_status()
        logger.info(f'Webhook sent successfully: {event_type}')
    except Exception as e:
        logger.error(f'Failed to send webhook {event_type}: {e}')


def parse_skillspace_webhook(payload: dict) -> dict:
    """
    Parse incoming webhook payload from Skillspace.
    
    Expected payload structure (adjust based on actual Skillspace webhook format):
    {
        "event_type": "student_completed" | "student_test_passed" | "student_started",
        "student_email": "user@example.com",
        "course_id": 123,
        "lesson_id": 456,
        "result": {...},
        "timestamp": "2026-11-06T10:00:00Z"
    }
    """
    event_type = payload.get('event_type', '')
    student_email = payload.get('student_email', '')
    course_id = payload.get('course_id')
    timestamp = payload.get('timestamp', '')

    return {
        'event_type': event_type,
        'student_email': student_email,
        'course_id': course_id,
        'timestamp': timestamp,
        'raw': payload,
    }
