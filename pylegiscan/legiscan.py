import bs4
import os
import re
import json
import datetime

# Python 2
import platform

IS_PYTHON2 = (int)(platform.python_version().split(".")[0]) < 3
if (IS_PYTHON2):
    from urllib2 import urlopen
    from urllib import urlencode
# Python 3
else:
    from urllib.request import urlopen
    from urllib.parse import urlencode

try:
    import requests
except:
    print ('\nThis program requires the Python requests module.')
    print ('Install using: pip install requests\n')
    raise

from pylegiscan import codes

"""
Interact with LegiScan API.

"""

# TODO: Sign up for your own Legiscan API key
sLEGISCAN_API_KEY = ""

sDEFAULT_STATE = "ca"

# Twitter Username rules
sTWITTER_REGEX = "^@?([a-zA-Z0-9_]+)"

# Instagram Username rules
sINSTAGRAM_REGEX = "^@?([a-zA-Z0-9._]+)"

# Facebook Username rules
sFACEBOOK_REGEX = "^@?([a-zA-Z0-9.]+)"

iCURR_YEAR = datetime.datetime.now().year
iNEXT_YEAR = iCURR_YEAR + 1

class LegiScanError(Exception):
    pass


class LegiScan(object):
    BASE_URL = 'http://api.legiscan.com/?key={0}&op={1}&{2}'
    SOCIAL_MEDIA_CACHE_FILE = os.path.join(os.path.split(__file__)[0], 'socialMediaCache.json')

    dSocialMediaCache = {}

    def __init__(self, apikey=sLEGISCAN_API_KEY):
        """LegiScan API.  State parameters should always be passed as
           USPS abbreviations.  Bill numbers and abbreviations are case
           insensitive.  Register for API at http://legiscan.com/legiscan
        """
        # see if API key available as environment variable
        if apikey is None:
            apikey = os.environ['LEGISCAN_API_KEY']
        self.key = apikey.strip()

        self.dSocialMediaCache = self.load_data_from_file(self.SOCIAL_MEDIA_CACHE_FILE)
        self._state = sDEFAULT_STATE

    def _url(self, operation, params=None):
        """Build a URL for querying the API."""
        if not isinstance(params, str) and params is not None:
            params = urlencode(params)
        elif params is None:
            params = ''
        return self.BASE_URL.format(self.key, operation, params)

    def _get(self, url):
        """Get and parse JSON from API for a url."""
        req = requests.get(url)
        if not req.ok:
            raise LegiScanError('Request returned {0}: {1}' \
                                .format(req.status_code, url))
        data = json.loads(req.content)
        if data['status'] == "ERROR":
            raise LegiScanError(data['alert']['message'])
        return data

    @property
    def state(self):
        return self._state

    @state.setter
    def state(self, stateStr):
        self._state = stateStr

    def get_session_list(self):
        """Get list of available sessions for a state."""
        url = self._url('getSessionList', {'state': self.state})
        data = self._get(url)
        return data['sessions']

    def get_master_list(self, session_id=None):
        """Get list of bills for the current session in a state or for
           a given session identifier.
        """
        if self.state is not None:
            url = self._url('getMasterList', {'state': self.state})
        elif session_id is not None:
            url = self._url('getMasterList', {'id': session_id})
        else:
            raise ValueError('Must specify session identifier or state.')
        data = self._get(url)
        # return a list of the bills
        return [data['masterlist'][i] for i in data['masterlist']]

    def get_bill(self, bill_id=None, bill_number=None):
        """Get primary bill detail information including sponsors, committee
           references, full history, bill text, and roll call information.

           This function expects either a bill identifier or a state and bill
           number combination.  The bill identifier is preferred, and required
           for fetching bills from prior sessions.
        """
        if bill_id is not None:
            url = self._url('getBill', {'id': bill_id})
        elif self.state is not None and bill_number is not None:
            url = self._url('getBill', {'state': self.state, 'bill': bill_number})
        else:
            raise ValueError('Must specify bill_id or state and bill_number.')
        return self._get(url)['bill']

    def get_bill_text(self, doc_id):
        """Get bill text, including date, draft revision information, and
           MIME type.  Bill text is base64 encoded to allow for PDF and Word
           data transfers.
        """
        url = self._url('getBillText', {'id': doc_id})
        return self._get(url)['text']

    def get_amendment(self, amendment_id):
        """Get amendment text including date, adoption status, MIME type, and
           title/description information.  The amendment text is base64 encoded
           to allow for PDF and Word data transfer.
        """
        url = self._url('getAmendment', {'id': amendment_id})
        return self._get(url)['amendment']

    def get_supplement(self, supplement_id):
        """Get supplement text including type of supplement, date, MIME type
           and text/description information.  Supplement text is base64 encoded
           to allow for PDF and Word data transfer.
        """
        url = self._url('getSupplement', {'id': supplement_id})
        return self._get(url)['supplement']

    def get_roll_call(self, roll_call_id):
        """Roll call detail for individual votes and summary information."""
        data = self._get(self._url('getRollcall', {'id': roll_call_id}))
        return data['roll_call']

    def get_sponsor(self, people_id):
        """Sponsor information including name, role, and a followthemoney.org
           person identifier.
        """
        url = self._url('getSponsor', {'id': people_id})
        return self._get(url)['person']

    def search(self, bill_number=None, query=None, year=2, page=1):
        """Get a page of results for a search against the LegiScan full text
           engine; returns a paginated result set.

           Specify a bill number or a query string.  Year can be an exact year
           or a number between 1 and 4, inclusive.  These integers have the
           following meanings:
               1 = all years
               2 = current year, the default
               3 = recent years
               4 = prior years
           Page is the result set page number to return.
        """
        if bill_number is not None:
            params = {'state': self.state, 'bill': bill_number}
        elif query is not None:
            params = {'state': self.state, 'query': query,
                      'year': year, 'page': page}
        else:
            raise ValueError('Must specify bill_number or query')
        data = self._get(self._url('search', params))['searchresult']
        # return a summary of the search and the results as a dictionary
        summary = data.pop('summary')
        results = {'summary': summary, 'results': [data[i] for i in data]}
        return results

    def __str__(self):
        return '<LegiScan API {0}>'.format(self.key)

    def __repr__(self):
        return str(self)

    ## -------------------------------------------------------------------------------------- ##
    ## Extending
    ## -------------------------------------------------------------------------------------- ##
    def get_new_bill_stubs(self, num_old_bills=0, **kwargs):
        """
        Gets the new bills by comparing against how many were returned last time (just trims against cached len)

        Args:
            num_old_bills: Number of old bills to ignore from master list.
            introduced_only: If True only return bills that have the action code as introduced.

        Returns: list of bills

        """

        new_master = self.get_master_list()
        new_bills = new_master[:len(new_master) - num_old_bills]
        kwargs.update(dict(bill_id='*'))
        new_bills = filter_master(new_bills, **kwargs)
        return new_bills

    def get_gov_url(self, bill_id):

        bill = self.get_bill(bill_id=bill_id)
        legiscan_bill_url = requests.get(bill['url'])
        bs = bs4.BeautifulSoup(legiscan_bill_url.content, 'html.parser')
        gov_href = bs.find(href=re.compile('leginfo.legislature.ca'), id='statelink')
        if gov_href:
            return gov_href['href'].replace('billStatusClient', 'billTextClient')
        else:
            return "https://leginfo.legislature.ca.gov/faces/billTextClient.xhtml?bill_id=%s%s0%s" % (iCURR_YEAR, iNEXT_YEAR, bill[
                'bill_number'])

    def find_social_media(self, sPersonId):
        """
        Try to find a persons social media accounts from legiscan person id.  Cobbles together
        a url for votesmart and scrapes.
        Saves the accounts to a file and by default reads that first.

        Args:
            iPersonId (int): legiscan people_id.

        Returns (dict): Instagram, facebook, twitter account names.

        """

        # Have you already seen this person today?
        if (sPersonId in self.dSocialMediaCache):
            return self.dSocialMediaCache[sPersonId]

        # Query for their votesmart ID from URL
        dPerson = self.get_sponsor(sPersonId)
        print('Finding Social Media for %s' % dPerson['name'])

        dSocialMediaValues = {codes.SOCIAL_MEDIA_INSTAGRAM: None,
                              codes.SOCIAL_MEDIA_FACEBOOK: None,
                              codes.SOCIAL_MEDIA_TWITTER: None,
                              'name': dPerson['name']}

        # Person not listed online
        if not 'votesmart_id' in dPerson:
            print('No votesmart id found for person %s: %s' % (sPersonId, dPerson['name']))
            self.save_data_to_file(self.dSocialMediaCache, self.SOCIAL_MEDIA_CACHE_FILE)
            return dSocialMediaValues

        # Query their votesmart data to get social media data
        bHasInfo = True
        votesmartPage = None
        votesmart_url = 'https://votesmart.org/candidate/biography/{0}/{1}'.format(
            str(dPerson['votesmart_id']), dPerson['name'].lower().replace(' ', '-'))
        try:
            votesmartPage = urlopen(votesmart_url)
        except:
            print(dPerson['name'] + " has no Votesmart page: " + votesmart_url)
            bHasInfo = False

        if(bHasInfo):
            Soup = bs4.BeautifulSoup(votesmartPage, 'html.parser')

            # Instagram
            instagram_tag = Soup.find(href=re.compile('instagram.com'))
            if instagram_tag:
                instagram_url = instagram_tag['href'].strip("/")
                splits = instagram_url.split('/')
                match = re.match(sINSTAGRAM_REGEX, splits[-1].strip("@"))
                if (match != None):
                    dSocialMediaValues[codes.SOCIAL_MEDIA_INSTAGRAM] = "@" + match.groups(0)

            # Facebook
            facebook_tag = Soup.find(href=re.compile('facebook.com'))
            if facebook_tag:
                facebook_url = facebook_tag['href'].strip("/")
                splits = facebook_url.split('/')
                match = re.match(sFACEBOOK_REGEX, splits[-1].strip("@"))
                if (match != None):
                    dSocialMediaValues[codes.SOCIAL_MEDIA_FACEBOOK] = "@" + match.groups(0)

            # Twitter
            twitter_tag = Soup.find(href=re.compile('twitter.com'))
            if twitter_tag:
                twitter_url = twitter_tag['href'].strip("/")
                splits = twitter_url.split('/')
                match = re.match(sTWITTER_REGEX, splits[-1].strip("@"))
                if(match != None):
                    dSocialMediaValues[codes.SOCIAL_MEDIA_TWITTER] = "@" + match.groups(0)


        # Save to our file cache
        print ('Updating file cache for %s (%s): %s (i), %s (f), %s (t)' % (dSocialMediaValues['name'],
                                                                            sPersonId,
                                                                            dSocialMediaValues[
                                                                                codes.SOCIAL_MEDIA_INSTAGRAM],
                                                                            dSocialMediaValues[
                                                                                codes.SOCIAL_MEDIA_FACEBOOK],
                                                                            dSocialMediaValues[
                                                                                codes.SOCIAL_MEDIA_TWITTER]))
        self.dSocialMediaCache[sPersonId] = dSocialMediaValues
        self.save_data_to_file(self.dSocialMediaCache, self.SOCIAL_MEDIA_CACHE_FILE)
        return dSocialMediaValues

    def getKeywordRelevancy(self, bill_ids, relevancy_threshold=51):
        """
        Search for relevant keywords by using legiscan search.
        This results in a LOT of url queries to their api.

        Args:
            bill_ids:
            relevancy_threshold:

        Returns:

        """

        results = {}
        relevancy = {}
        test = ['marijuana']
        # for k in KEYWORDS[:2]:
        for k in test:
            search = self.search('ca', query=k)
            if search['results']:
                relevancy[k] = {}
                for bill in search['results']:
                    print (bill)
                    relevancy[k].update({bill['bill_number']: bill['relevance']})

        print ('=' * 100)
        print (relevancy)

        for bill_id in bill_ids:
            bill = self.get_bill(bill_id)
            for keyword, search_results in relevancy.iteritems():
                if bill['bill_number'] in search_results.keys():
                    results[bill_id] = []
                    if search_results[bill['bill_number']] > relevancy_threshold:
                        results[bill_id].append(keyword)

        return results

    def save_data_to_file(self, data, filePath):

        print ("Writing: " + filePath)
        with open(filePath, 'w') as f:
            json.dump(data, f)
        f.close()

    def load_data_from_file(self, filePath):

        print ("Reading: " + filePath)

        if not os.path.exists(filePath):
            return {}

        with open(filePath, 'r') as f:
            data = json.load(f)
        f.close()
        return data


def filter_master(master_list, **kwargs):
    """
    Filter the master list by checking for key and value data.
    Args:
        master_list: List of bill stubs.
        **kwargs: key an value to search for.

    Returns:
        List of bill stubs

    Example:
        # To filter to only introduced bills
        filter_master(master_list, status='1')

    """

    res = []
    for m in master_list:
        checks = 0

        if (IS_PYTHON2):
            items = kwargs.iteritems()
        else:
            items = kwargs.items()

        for key, val in items:
            if key in m.keys():
                if val == '*':
                    checks += 1
                elif m[key] == val:
                    checks += 1
                if checks == len(kwargs):
                    res.append(m)
    return res
