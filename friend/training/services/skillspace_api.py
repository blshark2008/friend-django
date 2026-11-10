"""
Skillspace Open API integration service.

Uses the open API (token-based authentication) for:
- Inviting students to courses
- Checking student progress
- Managing enrollments
"""

import logging
import requests
from django.conf import settings
from django.utils import timezone

logger = logging.getLogger(__name__)


class SkillspaceAPIError(Exception):
    """Exception raised for Skillspace API errors."""
    pass


class SkillspaceClient:
    """Client for Skillspace Open API (token-based)."""

    def __init__(self, api_key: str = None, school_domain: str = None):
        self.api_key = api_key or getattr(settings, 'SKILLSPACE_API_KEY', '')
        self.school_domain = school_domain or getattr(
            settings, 'SKILLSPACE_SCHOOL_DOMAIN', 'kemcardio.skillspace.ru'
        )
        self.base_url = f'https://{self.school_domain}/api/open/v1'

    def _build_url(self, endpoint: str) -> str:
        """Build full URL with token parameter."""
        return f'{self.base_url}/{endpoint}?token={self.api_key}'

    def _get(self, endpoint: str, params: dict = None) -> dict:
        """Make GET request to Skillspace Open API."""
        url = self._build_url(endpoint)
        try:
            response = requests.get(url, params=params, timeout=30)
            response.raise_for_status()
            data = response.json()
            if data is None:
                return {}
            return data
        except requests.RequestException as e:
            logger.error(f'Skillspace API GET error: {e}')
            raise SkillspaceAPIError(f'API GET error: {e}')

    def _post(self, endpoint: str, params: dict = None) -> dict:
        """Make POST request to Skillspace Open API (params in body as form data)."""
        url = self._build_url(endpoint)
        try:
            response = requests.post(url, data=params, timeout=30)
            response.raise_for_status()
            data = response.json()
            if data is None:
                return {}
            return data
        except requests.RequestException as e:
            logger.error(f'Skillspace API POST error: {e}')
            raise SkillspaceAPIError(f'API POST error: {e}')

    def invite_student(self, email: str, course_id: int,
                       first_name: str = '', last_name: str = '',
                       patronymic: str = '', comment: str = '',
                       disable_notification: bool = False,
                       group_id: str = '') -> dict:
        """
        Invite a student to a course.
        
        Args:
            email: Student email (required)
            course_id: Course ID on Skillspace (required)
            first_name: Student first name
            last_name: Student last name
            patronymic: Student patronymic
            comment: Comment for the student
            disable_notification: Don't send email to student
            group_id: Group ID (UUID) to add student to. Empty = default group
            
        Returns:
            dict with 'password' and 'passwordSetupLink' for new users,
            or empty dict for existing users
        """
        if group_id:
            params = {
                'email': email,
                f'courses[{course_id}]': group_id,  # Specific group
            }
        else:
            params = {
                'email': email,
                f'courses[{course_id}]': '',  # Empty group = default group
            }
        
        # Full FIO for name
        full_name = f'{last_name} {first_name} {patronymic}'.strip()
        if full_name:
            params['name'] = full_name
        
        if comment:
            params['comment'] = comment
        if disable_notification:
            params['disableNotification'] = True
        
        logger.info(f'Inviting student {email} to course {course_id}' + (f' group {group_id}' if group_id else ''))
        return self._post('course/student-invite', params)

    def invite_students_bulk(self, students: list, course_id: int, group_id: str = '') -> dict:
        """
        Invite multiple students to a course.
        
        Args:
            students: list of dicts with 'email', 'first_name', 'last_name', 'patronymic', 'tab_number'
            course_id: Course ID on Skillspace
            group_id: Group ID (UUID) to add students to. Empty = default group
            
        Returns:
            dict with 'added' and 'errors' lists
        """
        results = {'added': [], 'errors': []}
        
        for student in students:
            try:
                self.invite_student(
                    email=student['email'],
                    course_id=course_id,
                    first_name=student.get('first_name', ''),
                    last_name=student.get('last_name', ''),
                    patronymic=student.get('patronymic', ''),
                    comment=f"Табельный номер: {student.get('tab_number', '')}" if student.get('tab_number') else '',
                    disable_notification=True,
                    group_id=group_id,
                )
                results['added'].append(student['email'])
            except SkillspaceAPIError as e:
                # Check if already enrolled (empty response)
                error_msg = str(e)
                if '400' in error_msg or '403' in error_msg:
                    results['errors'].append({
                        'email': student['email'],
                        'error': error_msg,
                    })
                    logger.warning(f'Skipped student {student["email"]}: {e}')
                else:
                    results['errors'].append({
                        'email': student['email'],
                        'error': error_msg,
                    })
                    logger.error(f'Failed to invite student {student["email"]}: {e}')
        
        return results

    def get_course_list(self) -> list:
        """
        Get list of all courses in the school.
        
        Returns:
            List of course objects with id, name, isPublished, visibility, categories
        """
        try:
            data = self._get('school/course/list')
            return data if isinstance(data, list) else []
        except SkillspaceAPIError as e:
            logger.error(f'Failed to get course list: {e}')
            raise

    def get_course_structure(self, course_id: str) -> list:
        """
        Get course structure (modules and lessons).
        
        Args:
            course_id: UUID of the course
            
        Returns:
            List of modules with lessons
        """
        try:
            data = self._get('course/structure', params={'courseId': course_id})
            return data if isinstance(data, list) else []
        except SkillspaceAPIError as e:
            logger.error(f'Failed to get course structure for {course_id}: {e}')
            raise

    def get_groups(self) -> list:
        """
        Get list of all groups for all courses.
        
        Returns:
            List of group objects with id, courseId, name, studentsCount
        """
        try:
            data = self._get('school/group/list')
            return data if isinstance(data, list) else []
        except SkillspaceAPIError as e:
            logger.error(f'Failed to get groups: {e}')
            raise

    def get_groups_by_course(self, course_id: str) -> list:
        """
        Get list of groups for a specific course.
        
        Args:
            course_id: UUID of the course
            
        Returns:
            List of group objects filtered by course_id
        """
        try:
            all_groups = self.get_groups()
            return [g for g in all_groups if g.get('courseId') == course_id]
        except SkillspaceAPIError as e:
            logger.error(f'Failed to get groups for course {course_id}: {e}')
            raise

    def get_user_fields(self) -> list:
        """
        Get list of custom fields for students.
        
        Returns:
            List of custom field objects with id, title, type, placeholder, order
        """
        try:
            data = self._get('school/user-fields/list')
            return data if isinstance(data, list) else []
        except SkillspaceAPIError as e:
            logger.error(f'Failed to get user fields: {e}')
            raise

    def set_access_end_date(self, email: str, course_id: str, access_end_date: str) -> dict:
        """
        Set or modify access end date for a student in a course.
        
        Args:
            email: Student email
            course_id: Course ID (UUID)
            access_end_date: ISO 8601 datetime with timezone, or 'none' for unlimited
            
        Returns:
            dict with 'accessEndDate' (Unix timestamp in ms, or null for unlimited)
        """
        params = {
            'email': email,
            'courseId': course_id,
            'accessEndDate': access_end_date,
        }
        try:
            result = self._post('course/student-access', params)
            return result
        except SkillspaceAPIError as e:
            logger.error(f'Failed to set access end date for {email}: {e}')
            raise

    def update_student(self, email: str, name: str = None, comment: str = None,
                       fields: dict = None) -> dict:
        """
        Update student information (name, comment, custom fields).
        
        Args:
            email: Student email
            name: New student name
            comment: New comment
            fields: Custom fields dict {field_uuid: value}
            
        Returns:
            Empty dict on success
        """
        params = {'email': email}
        if name:
            params['name'] = name
        if comment:
            params['comment'] = comment
        if fields:
            for field_uuid, value in fields.items():
                params[f'fields[{field_uuid}]'] = value
        
        try:
            result = self._post('course/student-update', params)
            return result
        except SkillspaceAPIError as e:
            logger.error(f'Failed to update student {email}: {e}')
            raise

    def check_student_status(self, email: str, course_id: str) -> str:
        """
        Check if student is enrolled in course by trying to get access.
        
        Returns:
            'enrolled', 'not_enrolled', or 'error'
        """
        try:
            # Try to get course structure - if it works, course exists
            self.get_course_structure(course_id)
            return 'enrolled'
        except SkillspaceAPIError as e:
            if 'COURSE_NOT_FOUND' in str(e):
                return 'not_enrolled'
            return 'error'


def invite_student_to_training(training, user, enrollment=None):
    """
    Convenience function to invite a user to a training via Skillspace.
    
    Args:
        training: Training model instance
        user: User model instance
        enrollment: TrainingEnrollment instance (optional, for group_id)
        
    Returns:
        dict with success/error status
    """
    if not training.training_type.skillspace_course_id:
        return {'success': False, 'error': 'Не указан ID курса на Skillspace'}
    
    email = user.corporate_email or user.personal_email
    if not email:
        return {'success': False, 'error': f'У пользователя {user.get_full_name()} нет email'}
    
    client = SkillspaceClient()
    
    # Use group_id from enrollment
    group_id = enrollment.group.skillspace_id if enrollment and enrollment.group else ''
    
    try:
        result = client.invite_student(
            email=email,
            course_id=training.training_type.skillspace_course_id,
            first_name=user.first_name,
            last_name=user.last_name,
            patronymic=user.patronymic,
            comment=f"Табельный номер: {user.tab_number}" if user.tab_number else '',
            disable_notification=True,
            group_id=group_id,
        )
        
        # Empty response means user already enrolled
        if result == {}:
            return {'success': True, 'message': 'Ученик уже записан на курс'}
        
        return {'success': True, 'message': 'Ученик успешно записан', 'result': result}
        
    except SkillspaceAPIError as e:
        return {'success': False, 'error': str(e)}


def sync_training_to_skillspace(training):
    """
    Sync all pending enrollments to Skillspace.
    
    Args:
        training: Training model instance
        
    Returns:
        dict with 'added', 'errors', 'already_enrolled' counts
    """
    if not training.training_type.skillspace_course_id:
        return {'error': 'Не указан ID курса на Skillspace'}
    
    client = SkillspaceClient()
    course_id = training.training_type.skillspace_course_id
    
    added = []
    errors = []
    already_enrolled = []
    
    # Get all not_started enrollments
    enrollments = training.enrollments.filter(status='not_started')
    
    students = []
    for enrollment in enrollments:
        user = enrollment.user
        email = user.corporate_email or user.personal_email
        group_id = enrollment.group.skillspace_id if enrollment.group else ''
        
        if not email:
            errors.append({
                'user': user.get_full_name(),
                'error': 'Нет email',
            })
            continue
        
        students.append({
            'email': email,
            'first_name': user.first_name,
            'last_name': user.last_name,
            'patronymic': user.patronymic,
            'tab_number': user.tab_number,
            'enrollment_id': enrollment.pk,
            'group_id': group_id,
        })
    
    # Bulk invite
    if students:
        # Group students by group_id
        groups = {}
        for s in students:
            gid = s.pop('group_id', '')
            groups.setdefault(gid, []).append(s)
        
        for group_id, group_students in groups.items():
            if group_students:
                result = client.invite_students_bulk(group_students, course_id, group_id)
                
                for email in result.get('added', []):
                    enrollment = next(
                        (s for s in group_students if s['email'] == email), None
                    )
                    if enrollment:
                        enrollment_obj = training.enrollments.get(pk=enrollment['enrollment_id'])
                        enrollment_obj.status = 'in_progress'
                        enrollment_obj.display_status = TrainingEnrollment.DisplayStatus.COURSE_STARTED
                        enrollment_obj.save(update_fields=['status', 'display_status'])
                        added.append(enrollment['user'])
                
                for err in result.get('errors', []):
                    enrollment = next(
                        (s for s in group_students if s['email'] == err['email']), None
                    )
                    if enrollment:
                        # Check if already enrolled
                        user = User.objects.get(pk=enrollment['user'].pk)
                        email = user.corporate_email or user.personal_email
                        try:
                            client.invite_student(
                                email=email,
                                course_id=course_id,
                                first_name=user.first_name,
                                last_name=user.last_name,
                                disable_notification=True,
                                group_id=group_id,
                            )
                            # Empty response = already enrolled
                            already_enrolled.append(enrollment['user'])
                        except SkillspaceAPIError:
                            errors.append({
                                'user': enrollment['user'],
                                'error': err['error'],
                            })
    
    # Update training status
    if added or already_enrolled:
        training.status = Training.Status.ACTIVE
        training.last_sync_at = timezone.now()
        training.save(update_fields=['status', 'last_sync_at'])
    
    return {
        'added': [u.get_full_name() for u in added],
        'errors': errors,
        'already_enrolled': [u.get_full_name() for u in already_enrolled],
    }


from accounts.models import User
from ..models import Training, TrainingEnrollment
