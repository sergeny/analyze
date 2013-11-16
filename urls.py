import os
#from django.conf.urls.defaults import *
from django.conf.urls import patterns, include, url


# Uncomment the next two lines to enable the admin:
from django.contrib import admin
admin.autodiscover()

urlpatterns = patterns('',
    # Example:
    (r'^$', 'plus.views.index'),
    (r'^search/$', 'plus.views.search'),
    (r'^analyze/$', 'plus.views.analyze'),
    (r'^oauth2callback', 'plus.views.auth_return'),
     

    # Uncomment the admin/doc line below and add 'django.contrib.admindocs'
    # to INSTALLED_APPS to enable admin documentation:
    # (r'^admin/doc/', include('django.contrib.admindocs.urls')),

    # Uncomment the next line to enable the admin:
    (r'^admin/', include(admin.site.urls)),
    (r'^accounts/login/$', 'django.contrib.auth.views.login',
                        {'template_name': 'plus/login.html'}),
    (r'^accounts/logout/$', 'django.contrib.auth.views.logout',
                        {'template_name': 'plus/logout.html'}),

    (r'^static/(?P<path>.*)$', 'django.views.static.serve',
        {'document_root': os.path.join(os.path.dirname(__file__), 'static')
}),
)
