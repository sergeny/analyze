import os
import logging
import httplib2
import hello_analytics_api_v3_auth
import argparse
from slugify import slugify
import numpy as np
import pandas as pd
import collections
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
def search(request): # DUPLICATED CODE HERE
  storage = Storage(CredentialsModel, 'id', request.user, 'credential')
  credential = storage.get()
  if credential is None or credential.invalid == True:
    FLOW.params['state'] = xsrfutil.generate_token(settings.SECRET_KEY,
                                                   request.user)
    authorize_url = FLOW.step1_get_authorize_url()
    return HttpResponseRedirect(authorize_url)
  else:
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

# a and b are pandas.Series indexed by e.g. 'san-francisco-california'
# same as in corrcoef_pd_series above
# a should have a metric for each such location (such as ga:visits), whereas
# b should have some statistic, such as average commute time (or vice versa)
# join them on common locations to obtain a list of pairs that can be graphed
def join_pd_series_as_list(a, b):
  w=a.index.intersection(b.index)
  #assuming that a[w] and b[w] already contain numeric data, not strings
  return [list(r) for r in pd.DataFrame({'metric':a[w], 'data':b[w]}).as_matrix()]



# Query Google analytics and return results as a pandas.DataFrame
# @param service      Google analytics API service
# @param profile_id   Google analytics profile id
# @param dt_from      String representing date from which to query data
# @param dt_to        String representing date to which to query data
#
# @returns results, df
#                     results   This is what ga returns. It has one row for each location. Each row is a list of numbers for each metric
#
#                     df   pandas.DataFrame with a column for each metric such as ga:visits and a row for each location,
#                     such as 'san-francisco-california', identified by a pair of dimensions  (ga:region, ga:city)
#                     index has strings such as 'san-francisco-california'; columns have strings such as 'ga:visits'
def get_metrics_from_ga(service, profile_id, dt_from, dt_to):
    query = get_api_query(service, 'ga:'+str(profile_id), dt_from, dt_to)
    results = query.execute()
    r=results['rows']
    rows=[slugify((x[0]+' '+x[1])) for x in r] # ['san-francisco-california', ...]                        
    df=pd.DataFrame([x[2:] for x in r], index=rows, columns=QUERY_METRICS.split(','))
    # Google gives us strings. Convert to numeric type
    # Not strictly necessary to do it here, as numpy correlation calculation will do fine
    # But then we have to convert for graphing...
    # Also, convert_objects probably creates a copy. Instead could replace
    # x[2:] with [double(u) for u in x[2:]] in the line above. Is it faster?
    df = df.convert_objects(convert_numeric=True)
    return results, df
  

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

    ga_results, ga_df = get_metrics_from_ga(service, profile_id, dt_from, dt_to)

    data=df_from_sql.load_all_tables_as_df()

    corrs={}       # e.g. corrs[('region_commute', 'AverageofWalk_to_work')] == 0.5
    insights=[]    # strings
    max_key=collections.defaultdict(list)
    min_key=collections.defaultdict(list)
    chart_lists=collections.defaultdict(list) # for each metric - list of points to plot
    # for all metrics such as ga:visits...
    for c in ga_df.columns:  
      print 'Computing correlations with %s' % c
      u=ga_df[c]
      for category in data.keys(): # e.g. region_commute: 
        dd=data[category]
        for c2 in dd.columns: # e.g. AverageofWalk_to_work
          v=dd[c2]
          
          l=join_pd_series_as_list(u, v)
          value=corrcoef_pd_series(u, v)
          corrs[(category, c2)] = value
          print 'Correlating it with %s/%s, %f' % (category, c2, value)
    
      minkey= min(corrs, key=corrs.get)
      maxkey= max(corrs, key=corrs.get)
      max_key[c] = maxkey
      min_key[c] = minkey
      print 'Min correlation of %s: %s, %f' % (c, str(minkey), corrs[minkey])
      print 'Max correlation of %s: %s, %f' % (c, str(maxkey), corrs[maxkey])
      # let's graph
      min_scattered_list = join_pd_series_as_list(u, data[minkey[0]][minkey[1]])
      max_scattered_list = join_pd_series_as_list(u, data[maxkey[0]][maxkey[1]])
      insights+=['Most of your %s come from %s'%(c,str(minkey)), 'Least of your %s come from %s'%(c, str(maxkey))]
      chart_lists[c] = max_scattered_list

    # np.corrcoef(ga_df['ga:visits'], ga_df['ga:timeOnSite'])[0][1]

    headers=QUERY_DIMENSIONS.split(',') + QUERY_METRICS.split(',')
   
    metrics=QUERY_METRICS.split(',')

    choices = [(m, max_key[m], 'container-%s' % slugify(m), str(chart_lists[m])) for m in metrics] # e.g. [('ga:visits', 'container-ga-visits), ...]

    return render_to_response('plus/results.html', {
                'headers': headers, 'profile_id': profile_id, 'dt_from':dt_from, 'dt_to':dt_to, 'results': ga_results['rows'], 'insights': insights, 'choices': choices
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
