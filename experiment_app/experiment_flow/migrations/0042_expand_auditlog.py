from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [('experiment_flow', '0041_auditlog')]

    operations = [
        migrations.AddField(model_name='auditlog', name='actor_team', field=models.CharField(blank=True, db_index=True, max_length=100)),
        migrations.AddField(model_name='auditlog', name='actor_username', field=models.CharField(blank=True, db_index=True, max_length=150)),
        migrations.AddField(model_name='auditlog', name='category', field=models.CharField(choices=[('auth', '认证'), ('project', 'Project'), ('experiment', 'Experiment'), ('step', 'Step'), ('equipment', '设备'), ('raw_material', '原材料'), ('member', '成员'), ('management', '系统管理')], db_index=True, default='management', max_length=30)),
        migrations.AddField(model_name='auditlog', name='ip_address', field=models.GenericIPAddressField(blank=True, null=True)),
        migrations.AddField(model_name='auditlog', name='outcome', field=models.CharField(choices=[('success', '成功'), ('failed', '失败'), ('denied', '拒绝')], db_index=True, default='success', max_length=10)),
        migrations.AddField(model_name='auditlog', name='request_method', field=models.CharField(blank=True, max_length=10)),
        migrations.AddField(model_name='auditlog', name='request_path', field=models.CharField(blank=True, max_length=255)),
        migrations.AlterField(model_name='auditlog', name='action', field=models.CharField(choices=[('create', '新增'), ('update', '修改'), ('delete', '删除'), ('copy', '复制'), ('status', '状态变化'), ('login', '登录'), ('login_failed', '登录失败'), ('logout', '退出'), ('password_change', '修改密码'), ('permission_denied', '权限拒绝')], db_index=True, max_length=30)),
        migrations.AlterField(model_name='auditlog', name='entity_type', field=models.CharField(db_index=True, max_length=50)),
        migrations.RunSQL(
            "UPDATE experiment_flow_auditlog SET actor_username = COALESCE((SELECT username FROM auth_user WHERE auth_user.id = experiment_flow_auditlog.actor_id), '') WHERE actor_username = ''",
            migrations.RunSQL.noop,
        ),
    ]
