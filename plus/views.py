import os
import logging
import httplib2
import hello_analytics_api_v3_auth
import argparse
from slugify import slugify
import numpy as np
import pandas as pd
import df_from_sql

from apiclient.discovery import build
from django.contrib.auth.decorators import login_required
from django.core.urlresolvers import reverse
from django.http import HttpResponse
from django.http import HttpResponseBadRequest
from django.http import HttpResponseRedirect
from django.shortcuts import render_to_response
from plus.models import CredentialsModel
from . import settings
from oauth2client import xsrfutil
from oauth2client.client import flow_from_clientsecrets
from oauth2client.django_orm import Storage

# CLIENT_SECRETS, name of a file containing the OAuth 2.0 information for this
# application, including client_id and client_secret, which are found
# on the API Access tab on the Google APIs
# Console <http://code.google.com/apis/console>
CLIENT_SECRETS = os.path.join(os.path.dirname(__file__), '..', 'client_secrets.json')


FLOW = flow_from_clientsecrets(
    CLIENT_SECRETS,
    scope='https://www.googleapis.com/auth/analytics.readonly', 
#    redirect_uri='http://localhost:8000/oauth2callback')
     redirect_uri='http://li643-60.members.linode.com:7999/oauth2callback')


def get_first_profile_id(service):
  # Get a list of all Google Analytics accounts for this user
  accounts = service.management().accounts().list().execute()

  if accounts.get('items'):
    # Get the first Google Analytics account
    firstAccountId = accounts.get('items')[0].get('id')

    # Get a list of all the Web Properties for the first account
    webproperties = service.management().webproperties().list(accountId=firstAccountId).execute()

    if webproperties.get('items'):
      # Get the first Web Property ID
      firstWebpropertyId = webproperties.get('items')[0].get('id')

      # Get a list of all Views (Profiles) for the first Web Property of the first Account
      profiles = service.management().profiles().list(
          accountId=firstAccountId,
          webPropertyId=firstWebpropertyId).execute()

      if profiles.get('items'):
        # return the first View (Profile) ID
        return profiles.get('items')[0].get('id')

  return None



QUERY_DIMENSIONS='ga:city,ga:region'
QUERY_METRICS='ga:visits,ga:timeOnSite,ga:pageviewsPerVisit,ga:bounces'

def get_api_query(service, table_id, dt_from, dt_to):
  """Returns a query object to retrieve data from the Core Reporting API.

  Args:
    service: The service object built by the Google API Python client library.
    table_id: str The table ID form which to retrieve data.
  """

  return service.data().ga().get(
      ids=table_id,
      start_date=dt_from, #'2013-10-01',
      end_date=dt_to, #'2013-11-30',
      metrics=QUERY_METRICS,
      dimensions=QUERY_DIMENSIONS,
      sort='-ga:visits',
      filters='ga:country==United States',
      start_index='1',
      max_results='5000')



@login_required
def index(request):
  return render_to_response('plus/welcome.html', {})

@login_required
def search(request):
  return render_to_response('plus/search.html', {})

def conv_dt(s): # 16-10-2013 to 2013-10-16
  l=[int(x) for x in s.split('-')] 
  return '%04d-%02d-%02d' % (l[2],l[1],l[0])


# compute the correlation coefficient between two panda series
# after alinging the entries with equal indices and discarding others
# TODO:test
def corrcoef_pd_series(a, b):
  w=a.index.intersection(b.index)
  return np.corrcoef(a[w], b[w])[0][1]

@login_required
def analyze(request):
  dt_from = conv_dt(request.GET['dt_from'])
  dt_to = conv_dt(request.GET['dt_to'])
  
  storage = Storage(CredentialsModel, 'id', request.user, 'credential')
  credential = storage.get()
  if credential is None or credential.invalid == True:
    FLOW.params['state'] = xsrfutil.generate_token(settings.SECRET_KEY,
                                                   request.user)
    authorize_url = FLOW.step1_get_authorize_url()
    return HttpResponseRedirect(authorize_url)
  else:
    http = httplib2.Http()
    http = credential.authorize(http)
    service = build("analytics", "v3", http=http)
    # alternative option to build a service, which is better???
    #service = hello_analytics_api_v3_auth.initialize_service(argparse.Namespace(auth_host_name='localhost', auth_host_port=[8080, 8090], logging_level='ERROR', noauth_local_webserver=False)    
    profile_id = get_first_profile_id(service)
#    logging.info(activitylist)

    query = get_api_query(service, 'ga:'+str(profile_id), dt_from, dt_to)
    results = query.execute()
    r=results['rows']
    
    rows=[slugify((x[0]+' '+x[1])) for x in r] # ['san-francisco-california', ...]

    df=pd.DataFrame([x[2:] for x in r], index=rows, columns=QUERY_METRICS.split(','))
    

    data=df_from_sql.load_all_tables_as_df()

    corrs={}
    insights=[]
    for c in df.columns:
      print 'Computing correlations with %s' % c
      u=df[c]
      for category in data.keys(): # e.g. region_politics: 
        dd=data[category]
        for c2 in dd.columns:
          v=dd[c2]
          value=corrcoef_pd_series(u, v)
          corrs[(category, c2)] = value
          print 'Correlating it with %s/%s, %f' % (category, c2, value)
    
      minkey= min(corrs, key=corrs.get)
      maxkey= max(corrs, key=corrs.get)
      print 'Min correlation of %s: %s, %f' % (c, str(minkey), corrs[minkey])
      print 'Max correlation of %s: %s, %f' % (c, str(maxkey), corrs[maxkey])
      insights+=['Most of your %s come from %s'%(c,str(minkey)), 'Least of your %s come from %s'%(c, str(maxkey))]


    # np.corrcoef(df['ga:visits'], df['ga:timeOnSite'])[0][1]

    headers=QUERY_DIMENSIONS.split(',') + QUERY_METRICS.split(',')
    return render_to_response('plus/results.html', {
                'headers': headers, 'profile_id': profile_id, 'dt_from':dt_from, 'dt_to':dt_to, 'results': results['rows'], 'insights': insights
                })


@login_required
def auth_return(request):
  if not xsrfutil.validate_token(settings.SECRET_KEY, request.REQUEST['state'],
                                 request.user):
    return  HttpResponseBadRequest()
  credential = FLOW.step2_exchange(request.REQUEST)
  storage = Storage(CredentialsModel, 'id', request.user, 'credential')
  storage.put(credential)
  return HttpResponseRedirect("/search/")
