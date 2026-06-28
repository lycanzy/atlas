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
    path('', views.index, name = 'index'),
    path('experiment/<int:exp_id>/', views.experiment_detail, name='experiment_detail'),
    path('add_experiment/', views.add_experiment, name='add_experiment'),
    path('experiment/<int:exp_id>/add_flow/', views.add_flow, name='add_flow'),
    path('experiment/<int:exp_id>/delete_flow/<int:flow_id>/', views.delete_flow, name='delete_flow'),
    path('experiment/<int:exp_id>/flow/<int:flow_id>/add_step/', views.add_step, name='add_step'),
    path('experiment/<int:exp_id>/flow/<int:flow_id>/edit_step/<int:step_id>/', views.edit_step, name='edit_step'),
    path('experiment/<int:exp_id>/flow/<int:flow_id>/delete_step/<int:step_id>/', views.delete_step, name='delete_step'),
    path('update_flow_desc/<int:flow_id>/', views.update_flow_desc, name='update_flow_desc'),
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
    path('api/steps/', views.get_all_steps, name='get_all_steps'),
    path('api/raw_materials/', views.get_raw_materials, name='get_raw_materials'),
    path('api/experiments_with_flows/', views.get_experiments_with_flows, name='get_experiments_with_flows'),
    path('admin/', admin.site.urls),
]
