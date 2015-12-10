from django.conf.urls import patterns, include, url
from django.contrib import admin

admin.autodiscover()

urlpatterns = patterns('',
    # Examples:
    # url(r'^$', 'xbill.views.home', name='home'),
    # url(r'^xbill/', include('xbill.foo.urls')),

    url(r'^', include('intro.urls', namespace="intro")),

    #Admin Urls
    url(r'^admin/doc/', include('django.contrib.admindocs.urls')),
    url(r'^admin/', include(admin.site.urls)),
)
