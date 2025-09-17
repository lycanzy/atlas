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
    path('admin/', admin.site.urls),
]
