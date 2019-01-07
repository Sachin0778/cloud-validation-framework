"""
   http utils using urllib default packaged with python3.
"""
import json
import copy
from urllib import request, parse
from urllib.error import HTTPError
from processor.helper.json.json_utils import json_from_string
from processor.logging.log_handler import getlogger
from processor.helper.config.rundata_utils import put_in_currentdata

logger = getlogger()
hdrs = {
    "Cache-Control": "no-cache",
    "Accept": "application/json"
}


def check_and_add_error(status, errmsg):
    """Add error based on the status code of the http response"""
    if status and isinstance(status, int) and status != 200:
        if status >= 400:
            put_in_currentdata('errors', errmsg)
        logger.info(errmsg)


def get_request_headers(headers=None):
    """Add json and no cache headers to the existing headers if passed."""
    req_headers = copy.copy(headers) if headers else {}
    req_headers.update(hdrs)
    return req_headers


def urlopen_request(urlreq, method):
    """Common utility to trigger the http request."""
    try:
        urlresp = request.urlopen(urlreq)
        respdata = urlresp.read()
        st_code = urlresp.status
        logger.debug("%s status: %d, response: %s", method, st_code, respdata)
        check_and_add_error(st_code, "%s Status: %d" % (method, st_code))
        if isinstance(respdata, bytes):
            respdata = respdata.decode()
        data = json_from_string(respdata)
        logger.info("%s status: %d", method, st_code)
    except HTTPError as ex:
        st_code = ex.code if method == "POST" else None
        data = ex.msg if method == "POST" else None
        logger.info("HTTP %s: status: %d", method, st_code)
    return st_code, data


def http_delete_request(url, deldata=None, headers=None, name='DELETE'):
    """Delete method sends and accepts JSON format with basic authentication"""
    logger.info("HTTP %s %s  .......", name, url)
    if not url:
        return None, None
    if deldata:
        encdata = parse.urlencode(deldata).encode()
        logger.info('%s: data: %s', name, encdata)
        urlreq = request.Request(url, data=encdata, headers=get_request_headers(headers),
                                 method=name)
    else:
        urlreq = request.Request(url, headers=get_request_headers(headers), method=name)
    return urlopen_request(urlreq, name)


def http_get_request(url, headers=None, name='GET'):
    """Get method sends and accepts JSON format."""
    logger.info("HTTP %s %s  .......", name, url)
    if not url:
        return None, None
    urlreq = request.Request(url, headers=get_request_headers(headers), method=name)
    return urlopen_request(urlreq, name)


def http_put_request(url, mapdata, headers=None, name='PUT'):
    """Put method sends and accepts JSON format."""
    logger.info("HTTP %s %s  .......", name, url)
    if not url:
        return None, None
    putdata = parse.urlencode(mapdata).encode()
    logger.info('%s: data: %s', name, putdata)
    urlreq = request.Request(url, data=putdata, headers=get_request_headers(headers),
                             method='PUT')
    return urlopen_request(urlreq, name)


def http_post_request(url, mapdata, headers=None, json_type=False, name='POST'):
    """Post method sends and accepts JSON format"""
    logger.info("HTTP %s %s  .......", name, url)
    if not url:
        return None, None
    if json_type:
        postdata = str.encode(json.dumps(mapdata))
    else:
        postdata = parse.urlencode(mapdata).encode()
    logger.debug('%s: data: %s', name, postdata)
    urlreq = request.Request(url, data=postdata, headers=get_request_headers(headers),
                             method='POST')
    return urlopen_request(urlreq, name)
