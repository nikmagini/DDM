from Apps.popCommon.utils.httpInterface import httpInterface, PopularityHttpInterfaceException
from Apps.popCommon.utils import Lexicon
from Apps.popCommon.PopularityException import PopularityException
from Apps.victorinterface.utils.Victorinterfaceparams import victorinterfaceparams, Paramvalidationexception 
from Apps.victorinterface.database import victorinterfaceDB
import json
import re
import logging
import time
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

class popularityInterfaceException(PopularityException):
    def __init__(self, error):
        self.err = "%s" % error
        PopularityException.__init__(self, 'popularity Interface error: %s' % error)

class popularityInterface(httpInterface):

    def __init__(self, url,lastAcc=False):
        if lastAcc:
            resource = '/popdb/victorinterface/accessedBlocksStatLastAcc/'
        else:
            resource = '/popdb/victorinterface/accessedBlocksStat/'
        httpInterface.__init__(self, url)
        httpInterface.set_resource(self, resource)

    def validateSiteName(self, sitename):
        #pat = re.compile('^T[0-9][a-zA-Z0-9_]+$')
        if  not Lexicon.wildcardtier(sitename):
            raise popularityInterfaceException("Given hostname has not a valid format")

    def get_json_data(self, site, source, timestart=None, timestop=None):
        self.validateSiteName(site)
            
        params  = {'sitename':site, 'tstart': timestart, 'tstop': timestop}
        if not timestart and not timestop:
            params  = {'sitename':site}
   
        if Lexicon.accsource(source):
            params['source'] = source
        else:
            raise popularityInterfaceException("Given source (access data source) is not valid")

        pop_data = httpInterface.get_json_data(self, params)
        try:
            pop_data[site]
        except KeyError:
            logger.warning('WARNING: empty popularity results for %s' % site)
        return pop_data

class popularityDBInterface:

    def __init__(self, lastAcc=False):
        self.lastAcc = lastAcc

    def validateSiteName(self, sitename):
        #pat = re.compile('^T[0-9][a-zA-Z0-9_]+$')
        if  not Lexicon.wildcardtier(sitename):
            raise popularityInterfaceException("Given hostname has not a valid format")

    def get_json_data(self, site='T%', source='', timestart=datetime.now(), timestop=(datetime.now() - timedelta(days=30))):
        
        self.validateSiteName(site)
            
        if not Lexicon.accsource(source):
            raise popularityInterfaceException("Given source (access data source) is not valid")

        par = victorinterfaceparams()
        try:
            par.setSiteName(site)
            logger.info('debug. siteName = %s' % par.SiteName)
    
            if source=='':
                if par.SiteName == 'T2_CH_CERN' or par.SiteName == 'T0_CH_CERN':
                    source = 'xrootd'
                    par.SiteName = 'T2_CH_CERN'
                else:
                    source = 'crab'
            par.setSource(source)

            
            if self.lastAcc:
                pop_data = victorinterfaceDB.WhatInSiteWithStatLastAcc(collType='BlocksStat', params=par)
            else:
                par.setTStart(timestart)
                par.setTStop(timestop)
                pop_data = victorinterfaceDB.WhatInSiteWithStat(collType='BlocksStat', params=par)
        except Paramvalidationexception as e:
            raise popularityInterfaceException(e.getmessage())
        except victorinterfaceDB.PopularityDBException as dbe:
            raise popularityInterfaceException(dbe.getmessage())
        except Exception as ex:
            raise popularityInterfaceException(ex)

        try:
            pop_data[site]
        except KeyError:
            logger.warning('WARNING: empty popularity results for %s' % site)
        return pop_data

class phedexInterfaceException(PopularityException):
    def __init__(self, error):
        self.err = "%s" % error
        PopularityException.__init__(self, 'phedex Interface error: %s' % error)

class phedexInterface(httpInterface):

    def __init__(self, url):
        resource = '/phedex/datasvc/json/prod/blockreplicas'
        httpInterface.__init__(self, url)
        httpInterface.set_resource(self, resource)

    def validateSiteName(self, sitename):
        #pat = re.compile('^T[0-9][a-zA-Z0-9_]+$')
        if  not Lexicon.wildcardtier(sitename):
            raise phedexInterfaceException("Given hostname has not a valid format")

    def format_response(self, phedex_data, sitename):
        try:
            phedexReplicaList=phedex_data[u'phedex'][u'block']
            if not phedexReplicaList:
                logger.warning('WARNING: no replicas found at %s' % sitename)
                msg='WARNING: no replicas found at %s' % sitename
                raise dasInterfaceException(msg)
            dasData = []
            for block in phedexReplicaList:
                dasRecord={}
                dasRecord['name']=block['name']
                dasRecord['replica']={}
                for val in ('group', 'custodial', 'complete'):
                    dasRecord['replica'][val]=block['replica'][0][val]
                dasRecord['replica']['nfiles']=int(block['replica'][0]['files'])
                dasRecord['replica']['size']=int(block['replica'][0]['bytes'])
                dasRecord['replica']['creation_time']=int(float(block['replica'][0]['time_create']))
                dasBlockRecord={'block': [dasRecord]}
                dasData.append(dasBlockRecord)
            formatted_data={'data':dasData}
            return formatted_data

        except KeyError as err:
            msg = 'empty PhEDEx datasvc results for %s' % site
            logger.error(msg)
            raise phedexInterfaceException(msg)

    def get_json_data(self, site):
        self.validateSiteName(site)
        if site == 'T1_US_FNAL':
            site = 'T1_US_FNAL_Buffer'
            logger.info('changing name of T1_US_FNAL to T1_US_FNAL_Buffer for the PhEDEx query')
        params = {'node':site}
        phedex_data = httpInterface.get_json_data(self, params)
        formatted_data = self.format_response(phedex_data, site)
        return formatted_data

class dasInterfaceException(PopularityException):
    def __init__(self, error):
        self.err = "%s" % error
        PopularityException.__init__(self, 'das Interface error: %s' % error)

class dasInterface(httpInterface):

    def __init__(self, url):
        resource = '/das/cache'
        httpInterface.__init__(self, url)
        httpInterface.set_resource(self, resource)

    def isDasPid(self, data):
        pidPattern = re.compile(r'^[a-z0-9]{32}')
        if data and isinstance(data, str) and pidPattern.match(data) and len(data) == 32:
            return True
        return False

    def decodeDasData(self, data):
        try:
            dataDict = json.loads(data)
        except ValueError as err:
            msg = "data from DAS could not be decoded to JSON"
            logger.debug(msg)
            logger.debug(err)
            raise dasInterfaceException(msg)
        try:
            queryStatus = dataDict['status']
        except KeyError as err:
            msg = "no status key in DAS record"
            logger.debug(msg)
            logger.debug(err)
            raise dasInterfaceException(msg)
        if queryStatus == 'ok':
            try:
                if (dataDict['nresults']==0 or not dataDict['data']):
                    logger.warning('query did not return any result')
            except KeyError as err:
                msg = "missing key in DAS record"
                logger.debug(msg)
                logger.debug(err)
                raise dasInterfaceException(msg)
            return dataDict
        elif queryStatus == 'fail':
            msg='DAS query failed'
            logger.info(msg)
            try:
                msg+=' - Failure reason: \n'+dataDict['reason']+'\n'
                logger.info(msg)
            except KeyError:
                msg+='No reason provided'
                logger.info(msg)
            raise dasInterfaceException(msg)
        else:
            msg='Unrecognized DAS query status: %s' % queryStatus
            raise dasInterfaceException(msg)


    def get_json_data(self, sitename, idx=0, limit=0):
        dasQuery='block site=%s' % sitename
        params  = {'input':dasQuery, 'idx':idx, 'limit':limit}

        data = httpInterface.get_data(self, params)

        if self.isDasPid(data):
            pid = data
        else:
            pid = None
        count = 5 # initial waiting time in seconds
        while pid:
            params.update({'pid': data})
            #encoded_data = urllib.urlencode(params, doseq=True)
            #url  = host + path + '?%s' % encoded_data

            data = httpInterface.get_data(self, params)
            if self.isDasPid(data):
                pid = data
            else:
                pid = None
            time.sleep(count)
            if  count < 30:
                count *= 2
            else:
                count = 30

        return self.decodeDasData(data)
