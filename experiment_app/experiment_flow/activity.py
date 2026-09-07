"""Read-only activity calendar built from retained experiment audit events.

One activity is one changed experiment/step; bulk actions count each affected
step once. Deleted or no-longer-accessible objects are deliberately omitted:
an audit snapshot alone cannot establish current project access.
"""

import calendar
from collections import Counter
from datetime import date, datetime, time

from django.core.paginator import Paginator
from django.urls import reverse
from django.utils import timezone
from django.utils.dateparse import parse_date

from .models import AuditLog, Experiment, ExperimentStep


def _targets(event):
    """Normalize single and bulk audit formats without exposing their payloads."""
    changes = event['changes'] if isinstance(event['changes'], dict) else {}
    action = event['action']
    if action in {'update', 'status'} and not changes:
        return []
    if action in {'update', 'status'} and changes and all(
        isinstance(value, dict) and 'before' in value and 'after' in value
        and value['before'] == value['after'] for value in changes.values()
    ):
        return []
    if event['entity_type'] == 'Experiment Steps':
        key = 'created_steps' if action == 'copy' else 'steps'
        items = changes.get(key, [])
        if not isinstance(items, list):
            return []
        return [
            ('step', str(item['id'])) for item in items
            if isinstance(item, dict) and 'id' in item
            and (action != 'status' or item.get('status') != item.get('new_status'))
        ]
    if event['category'] == 'experiment' and event['entity_type'] == 'Experiment':
        return [('experiment', event['object_id'])]
    if event['category'] == 'step' and event['entity_type'] == 'Experiment Step':
        return [('step', event['object_id'])]
    return []


def _level(count):
    return sum(count >= threshold for threshold in (1, 3, 6, 10))


def get_activity_board(request, visible_projects):
    now = timezone.now()
    today = timezone.localdate(now)
    scope = request.GET.get('activity_scope', 'mine')
    if scope not in {'mine', 'overall'}:
        scope = 'mine'
    try:
        year = int(request.GET.get('activity_year', today.year))
    except (ValueError, TypeError):
        year = today.year
    if not 1970 <= year <= today.year:
        year = today.year

    experiments = {
        str(item['id']): item for item in Experiment.objects.filter(project__in=visible_projects)
        .values('id', 'project_id', 'full_experiment_code', 'experiment_description', 'created_on')
    }
    steps = {
        str(item['id']): item for item in ExperimentStep.objects.filter(experiment__project__in=visible_projects)
        .values('id', 'experiment_id', 'full_step')
    }
    earliest_year = min(
        (timezone.localtime(item['created_on']).year for item in experiments.values() if item['created_on']),
        default=today.year,
    )
    years = range(today.year, min(year, earliest_year) - 1, -1)
    try:
        selected = parse_date(request.GET.get('activity_date', ''))
    except ValueError:
        selected = None
    if not selected or selected.year != year or selected > today:
        selected = today if year == today.year else date(year, 12, 31)

    def url(**updates):
        params = request.GET.copy()
        params.pop('activity_fragment', None)
        params.pop('activity_page', None)
        for key, value in {'activity_scope': scope, 'activity_year': year, 'activity_date': selected.isoformat(), **updates}.items():
            params[key] = value
        return '?' + params.urlencode() + '#experiment-activity'

    start = timezone.make_aware(datetime.combine(date(year, 1, 1), time.min))
    end = timezone.make_aware(datetime.combine(date(year + 1, 1, 1), time.min))
    events = AuditLog.objects.filter(
        category__in=('experiment', 'step'), action__in=('create', 'copy', 'update', 'status'),
        outcome='success', created_on__gte=start, created_on__lt=end, created_on__lte=now,
    )
    if scope == 'mine':
        events = events.filter(actor=request.user)

    counts = Counter()
    recent = {}
    day_events = []
    actions = {'create': '创建', 'copy': '复制', 'update': '更新', 'status': '变更状态'}
    for event in events.order_by('-created_on', '-id').values(
        'id', 'actor_username', 'category', 'action', 'entity_type', 'object_id', 'changes', 'created_on',
    ).iterator(chunk_size=1000):
        occurred = timezone.localtime(event['created_on'])
        seen = set()
        for kind, object_id in _targets(event):
            if (kind, object_id) in seen:
                continue
            seen.add((kind, object_id))
            step = steps.get(object_id) if kind == 'step' else None
            experiment = experiments.get(str(step['experiment_id'])) if step else (
                experiments.get(object_id) if kind == 'experiment' else None
            )
            if not experiment:
                continue
            counts[occurred.date()] += 1
            experiment_id = str(experiment['id'])
            detail_url = reverse('experiment_detail', args=[experiment['project_id']])
            detail_url += '?expanded_experiment=' + experiment_id
            if experiment_id not in recent:
                recent[experiment_id] = {
                    'code': experiment['full_experiment_code'],
                    'description': experiment['experiment_description'] or '',
                    'when': occurred, 'url': detail_url,
                }
            if occurred.date() == selected:
                label = actions[event['action']] + ('步骤' if step else '实验')
                status_change = event['changes'].get('status', {}) if isinstance(event['changes'], dict) else {}
                if event['action'] == 'status':
                    label = '变更步骤状态'
                    if isinstance(status_change, dict) and status_change.get('after') == 'Completed':
                        label = '完成步骤'
                day_events.append({
                    'label': label, 'code': step['full_step'] if step else experiment['full_experiment_code'],
                    'actor': event['actor_username'], 'when': occurred,
                    'url': detail_url + ('&highlight_step=' + object_id if step else ''),
                })

    months = []
    for month in range(1, 13):
        days = []
        weeks = calendar.Calendar(firstweekday=0).monthdayscalendar(year, month)
        for week in weeks:
            for day in week:
                if not day:
                    days.append(None)
                    continue
                value = date(year, month, day)
                count = counts[value]
                future = value > today
                days.append({
                    'number': day, 'iso': value.isoformat(), 'count': count, 'level': _level(count),
                    'future': future, 'today': value == today, 'selected': value == selected,
                    'label': f'{year}年{month}月{day}日，' + ('未到日期' if future else f'{count} 次活动'),
                    'url': url(activity_date=value.isoformat()),
                })
        # Six fixed week rows keep both calendar bands aligned across all years.
        days.extend([None] * (42 - len(days)))
        months.append({'number': month, 'days': days, 'future': date(year, month, 1) > today})

    page = Paginator(day_events, 8).get_page(request.GET.get('activity_page'))
    return {
        'scope': scope, 'year': year, 'years': [{'year': item, 'url': url(activity_year=item, activity_date='')} for item in years],
        'title': '我的实验足迹' if scope == 'mine' else '整体实验足迹',
        'scope_label': '全部可访问项目' if scope == 'overall' else '由我操作的实验与步骤',
        'initial': (request.user.get_full_name().strip() or request.user.username)[:1].upper(),
        'mine_url': url(activity_scope='mine'), 'overall_url': url(activity_scope='overall'),
        'total': sum(counts.values()), 'experiment_count': len(recent), 'active_days': len(counts),
        'months': months, 'weekdays': '一二三四五六日', 'selected': selected,
        'selected_count': counts[selected], 'page': page,
        'previous_url': url(activity_page=page.previous_page_number()) if page.has_previous() else None,
        'next_url': url(activity_page=page.next_page_number()) if page.has_next() else None,
        'recent': list(recent.values())[:3],
    }
