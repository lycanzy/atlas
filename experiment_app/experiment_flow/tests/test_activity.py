from datetime import date, datetime
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import RequestFactory, TestCase
from django.urls import reverse
from django.utils import timezone

from experiment_flow.activity import get_activity_board
from experiment_flow.models import AuditLog, Experiment, ExperimentStep, Project, ProjectCategory, ResearchGroup, UserProfile
from experiment_flow.views import get_experiments_for_user


class ActivityTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user('activity-owner')
        cls.teammate = User.objects.create_user('activity-teammate')
        cls.outsider = User.objects.create_user('activity-outsider')
        cls.staff = User.objects.create_user('activity-staff', is_staff=True)
        group = ResearchGroup.objects.create(group_name='Activity A', team_code='ACA')
        other = ResearchGroup.objects.create(group_name='Activity B', team_code='ACB')
        UserProfile.objects.create(user=cls.user, research_group=group)
        UserProfile.objects.create(user=cls.teammate, research_group=group)
        UserProfile.objects.create(user=cls.outsider, research_group=other)
        category = ProjectCategory.objects.create(project_name='Activity A', project_code='ACA', group=group)
        other_category = ProjectCategory.objects.create(project_name='Activity B', project_code='ACB', group=other)
        cls.project = Project.objects.create(exp_name='ACA001', project=category, owner=cls.teammate)
        cls.other_project = Project.objects.create(exp_name='ACB001', project=other_category, owner=cls.outsider)
        cls.experiment = Experiment.objects.create(project=cls.project, experiment_code='AA')
        cls.other_experiment = Experiment.objects.create(project=cls.other_project, experiment_code='AA')
        cls.step = ExperimentStep.objects.create(experiment=cls.experiment, step_name='MX')
        cls.other_step = ExperimentStep.objects.create(experiment=cls.other_experiment, step_name='MX')

    def setUp(self):
        self.now = timezone.make_aware(datetime(2026, 9, 7, 16, 0))
        patcher = patch('experiment_flow.activity.timezone.now', return_value=self.now)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.client.force_login(self.user)

    def event(self, instance=None, actor=None, action='create', changes=None, when=None, **kwargs):
        instance = instance or self.step
        event = AuditLog.objects.create(
            actor=actor or self.user, actor_username=(actor or self.user).username,
            category=kwargs.pop('category', 'step' if isinstance(instance, ExperimentStep) else 'experiment'),
            action=action, entity_type=kwargs.pop('entity_type', instance._meta.verbose_name.title()),
            object_id=kwargs.pop('object_id', str(instance.pk)), object_repr=str(instance),
            summary='Private audit payload must not be rendered', changes=changes or {}, **kwargs,
        )
        AuditLog.objects.filter(pk=event.pk).update(created_on=when or self.now)
        return event

    def board(self, user=None, **params):
        request = RequestFactory().get('/', params)
        request.user = user or self.user
        return get_activity_board(request, get_experiments_for_user(request.user))

    def test_personal_uses_actor_not_project_owner(self):
        self.event()  # User activity in a project owned by teammate.
        self.event(actor=self.teammate)
        self.assertEqual(self.board()['total'], 1)
        self.assertEqual(self.board(activity_scope='overall')['total'], 2)
        self.assertEqual(self.board()['experiment_count'], 1)

    def test_overall_and_date_fragment_enforce_current_object_access(self):
        self.event()
        self.event(self.other_step, actor=self.user)  # Actor team alone is insufficient.
        board = self.board(activity_scope='overall')
        self.assertEqual(board['total'], 1)
        self.assertEqual(self.board(user=self.staff, activity_scope='overall')['total'], 2)
        response = self.client.get(reverse('index'), {'activity_fragment': '1', 'activity_scope': 'overall'})
        self.assertContains(response, self.step.full_step)
        self.assertNotContains(response, self.other_step.full_step)
        self.assertNotContains(response, 'Private audit payload')
        self.assertNotContains(response, '活动记录不等于实验产出')
        self.assertNotContains(response, '实验编号 / 标题')

    def test_explicit_access_grant_and_revocation(self):
        self.event(self.other_step)
        self.assertEqual(self.board()['total'], 0)
        self.other_project.authorized_users.add(self.user)
        self.assertEqual(self.board()['total'], 1)
        self.other_project.authorized_users.remove(self.user)
        self.assertEqual(self.board()['total'], 0)

    def test_no_profile_has_no_access_except_grants(self):
        person = User.objects.create_user('without-profile')
        self.event(actor=person)
        self.assertEqual(self.board(user=person, activity_scope='overall')['total'], 0)
        self.project.authorized_users.add(person)
        self.assertEqual(self.board(user=person)['total'], 1)

    def test_ignored_auth_failed_delete_noop_and_future_events(self):
        self.event(action='login', category='auth')
        self.event(outcome='failed')
        self.event(action='delete')
        self.event(action='update')
        self.event(action='status', changes={'status': {'before': 'Planned', 'after': 'Planned'}})
        self.event(when=timezone.make_aware(datetime(2026, 9, 8)))
        self.event(action='update', changes={'notes': {'before': '', 'after': 'Measured'}})
        self.assertEqual(self.board()['total'], 1)

    def test_bulk_counts_only_changed_accessible_unique_steps(self):
        self.event(action='status', entity_type='Experiment Steps', object_id=f'{self.step.pk},{self.other_step.pk}', changes={
            'steps': [
                {'id': self.step.pk, 'status': 'Planned', 'new_status': 'Completed'},
                {'id': self.step.pk, 'status': 'Planned', 'new_status': 'Completed'},
                {'id': self.other_step.pk, 'status': 'Planned', 'new_status': 'Completed'},
            ],
        })
        self.event(action='status', entity_type='Experiment Steps', changes={
            'steps': [{'id': self.step.pk, 'status': 'Completed', 'new_status': 'Completed'}],
        })
        self.assertEqual(self.board()['total'], 1)
        self.assertEqual(self.board(user=self.staff, activity_scope='overall')['total'], 2)

    def test_copy_uses_created_steps_and_never_source_payload(self):
        self.event(self.experiment, category='step', action='copy', entity_type='Experiment Steps', changes={
            'source_steps': [{'id': self.other_step.pk, 'step_code': self.other_step.full_step}],
            'created_steps': [{'id': self.step.pk, 'step_code': self.step.full_step}],
        })
        board = self.board()
        self.assertEqual(board['total'], 1)
        self.assertEqual(board['page'][0]['code'], self.step.full_step)
        self.assertIn(f'highlight_step={self.step.pk}', board['page'][0]['url'])

    def test_calendar_leap_day_monday_start_future_and_timezone(self):
        self.event(when=timezone.make_aware(datetime(2024, 2, 29, 0, 15)))
        board = self.board(activity_year='2024', activity_date='2024-02-29')
        days = [day for month in board['months'] for day in month['days'] if day]
        self.assertEqual(len(days), 366)
        self.assertEqual(board['selected_count'], 1)
        self.assertEqual(board['active_days'], 1)
        self.assertEqual(board['months'][0]['days'][0]['number'], 1)  # Jan 1 2024 Monday.
        current = self.board()
        september = current['months'][8]['days']
        self.assertIsNone(september[0])  # Sep 1 2026 Tuesday.
        seventh = next(day for day in september if day and day['number'] == 7)
        eighth = next(day for day in september if day and day['number'] == 8)
        self.assertTrue(seventh['today'])
        self.assertTrue(eighth['future'])

    def test_invalid_parameters_and_empty_year(self):
        board = self.board(activity_year='9999', activity_scope='bad', activity_date='2026-02-31', activity_page='x')
        self.assertEqual(board['year'], 2026)
        self.assertEqual(board['scope'], 'mine')
        self.assertEqual(board['selected'], date(2026, 9, 7))
        self.assertEqual(board['total'], 0)
        self.assertEqual(board['active_days'], 0)

    def test_date_pagination_and_parameter_preservation(self):
        for _ in range(10):
            self.event()
        board = self.board(activity_page='2', overview_scope='mine', overview_days='30', search='A&B')
        self.assertEqual(len(board['page']), 2)
        self.assertEqual(board['selected_count'], 10)
        self.assertIn('overview_days=30', board['mine_url'])
        self.assertIn('search=A%26B', board['mine_url'])
        self.assertEqual(board['mine_url'].count('activity_scope='), 1)

    def test_deleted_entities_omitted_and_queries_do_not_grow_per_event(self):
        for _ in range(20):
            self.event()
        # Resolve access once, then assert a fixed number of reads for aggregation.
        projects = get_experiments_for_user(self.user)
        request = RequestFactory().get('/')
        request.user = self.user
        with self.assertNumQueries(3):
            self.assertEqual(get_activity_board(request, projects)['total'], 20)
        self.step.delete()
        self.assertEqual(self.board()['total'], 0)

    def test_fragment_requires_authentication(self):
        self.client.logout()
        response = self.client.get(reverse('index'), {'activity_fragment': '1'})
        self.assertEqual(response.status_code, 302)
        self.assertIn('/login/', response.url)
