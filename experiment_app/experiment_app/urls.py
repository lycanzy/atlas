"""
URL configuration for experiment_app project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
from experiment_flow import views

urlpatterns = [
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('change_password/', views.change_password, name='change_password'),
    path('search/', views.global_search, name='global_search'),
    path('insights/', views.insights, name='insights'),
    path('', views.index, name = 'index'),
    path('experiment/<int:exp_id>/', views.experiment_detail, name='experiment_detail'),
    path('add_experiment/', views.add_experiment, name='add_experiment'),
    path('experiment/<int:exp_id>/add_project_experiment/', views.add_project_experiment, name='add_project_experiment'),
    path('experiment/<int:exp_id>/delete_project_experiment/<int:experiment_id>/', views.delete_project_experiment, name='delete_project_experiment'),
    path('experiment/<int:exp_id>/project_experiment/<int:experiment_id>/add_step/', views.add_step, name='add_step'),
    path('experiment/<int:exp_id>/project_experiment/<int:experiment_id>/edit_step/<int:step_id>/', views.edit_step, name='edit_step'),
    path('experiment/<int:exp_id>/project_experiment/<int:experiment_id>/delete_step/<int:step_id>/', views.delete_step, name='delete_step'),
    path('update_experiment_desc/<int:experiment_id>/', views.update_experiment_desc, name='update_experiment_desc'),
    path('update_step_desc/<int:step_id>/', views.update_step_desc, name='update_step_desc'),
    path('update_step_status/<int:step_id>/', views.update_step_status, name='update_step_status'),
    path('step/<int:step_id>/genealogy/', views.step_genealogy, name='step_genealogy'),
    path('experiment/<int:exp_id>/bulk_update_status/', views.bulk_update_status, name='bulk_update_status'),
    path('experiment/<int:exp_id>/copy_steps/', views.copy_steps, name='copy_steps'),
    path('experiment/<int:exp_id>/delete_steps/', views.delete_steps, name='delete_steps'),
    path('equipment/', views.equipment_list, name='equipment_list'),
    path('equipment/<int:equipment_id>/', views.equipment_detail, name='equipment_detail'),
    path('add_equipment/', views.add_equipment, name='add_equipment'),
    path('equipment/<int:equipment_id>/edit/', views.edit_equipment, name='edit_equipment'),
    path('raw_materials/', views.raw_material_list, name='raw_material_list'),
    path('raw_materials/<int:raw_material_id>/', views.raw_material_detail, name='raw_material_detail'),
    path('add_raw_material/', views.add_raw_material, name='add_raw_material'),
    path('raw_materials/<int:raw_material_id>/edit/', views.edit_raw_material, name='edit_raw_material'),
    path('management/', views.management_dashboard, name='management_dashboard'),
    path('management/teams/add/', views.add_team, name='add_team'),
    path('management/teams/<int:team_id>/edit/', views.edit_team, name='edit_team'),
    path('management/teams/<int:team_id>/delete/', views.delete_team, name='delete_team'),
    path('management/members/<int:user_id>/team/', views.assign_member_team, name='assign_member_team'),
    path('management/members/add/', views.add_managed_user, name='add_managed_user'),
    path('management/members/<int:user_id>/edit/', views.edit_managed_user, name='edit_managed_user'),
    path('management/members/<int:user_id>/delete/', views.delete_managed_user, name='delete_managed_user'),
    path('management/projects/add/', views.add_managed_project, name='add_managed_project'),
    path('management/projects/<int:project_id>/edit/', views.edit_managed_project, name='edit_managed_project'),
    path('management/projects/<int:project_id>/delete/', views.delete_managed_project, name='delete_managed_project'),
    path('management/steps/add/', views.add_step_template, name='add_step_template'),
    path('management/steps/<int:template_id>/edit/', views.edit_step_template, name='edit_step_template'),
    path('management/steps/<int:template_id>/delete/', views.delete_step_template, name='delete_step_template'),
    path('management/material-types/add/', views.add_raw_material_type, name='add_raw_material_type'),
    path('management/material-types/<int:type_id>/edit/', views.edit_raw_material_type, name='edit_raw_material_type'),
    path('management/material-types/<int:type_id>/delete/', views.delete_raw_material_type, name='delete_raw_material_type'),
    path('api/steps/', views.get_all_steps, name='get_all_steps'),
    path('api/raw_materials/', views.get_raw_materials, name='get_raw_materials'),
    path('api/experiments_with_items/', views.get_experiments_with_items, name='get_experiments_with_items'),
    path('admin/', admin.site.urls),
]
