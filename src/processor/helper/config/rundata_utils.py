"""
   Run time data storage and retrieval.
"""
import time
import datetime
import json
import socket
import os.path
from processor.helper.config.config_utils import framework_currentdata
from processor.helper.json.json_utils import json_from_file, save_json_to_file
from processor.logging.log_handler import getlogger, FWLOGFILENAME
from processor.helper.file.file_utils import remove_file, exists_dir, mkdir_path

exclude_list = ['token', 'clientSecret', 'vaulttoken']
logger = getlogger()


def add_to_exclude_list(key):
    if key not in exclude_list:
        exclude_list.append(key)


def init_currentdata():
    """ Initialises data structure to store runtime data. """
    started = int(time.time() * 1000)
    runctx = framework_currentdata()
    run_dir = os.path.dirname(runctx)
    if not exists_dir(run_dir):
        mkdir_path(run_dir)
    run_data = {
        'start': started,
        'end': started,
        'errors': [],
        'host': socket.gethostname(),
        'timestamp': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    }
    save_currentdata(run_data)


def put_in_currentdata(key, value):
    """Adds a value in the current run data"""
    if key and value:
        curr_data = get_currentdata()
        if key in curr_data:
            val = curr_data[key]
            if isinstance(val, list):
                val.append(value)
            else:
                curr_data[key] = value
        else:
            curr_data[key] = value
        save_currentdata(curr_data)


def delete_from_currentdata(key):
    """Remove a key from the current run data"""
    if key:
        currdata = get_currentdata()
        if key in currdata:
            del currdata[key]
        save_currentdata(currdata)


def get_from_currentdata(key):
    """ Get the data for this key from the rundata"""
    data = None
    currdata = get_currentdata()
    if key and key in currdata:
        data = currdata[key]
    return data


def get_currentdata():
    """Get the current run data, if present else empty json object"""
    runctx = framework_currentdata()
    curr_data = json_from_file(runctx)
    if not curr_data:
        curr_data = {}
    return curr_data


def save_currentdata(curr_data):
    """Save the key value rundata for further access, if None store it empty."""
    if not curr_data:
        curr_data = {}
    runctx = framework_currentdata()
    save_json_to_file(curr_data, runctx)


def delete_currentdata():
    """Delete the rundata file when exiting of the script."""
    runctx = get_currentdata()
    runctx['end'] = int(time.time() * 1000)
    runctx['log'] = FWLOGFILENAME
    runctx['duration'] = '%d seconds' % int((runctx['end'] - runctx['start'])/1000)
    runctx['start'] = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(runctx['start']/1000))
    runctx['end'] = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(runctx['end']/1000))
    for field in exclude_list:
        if field in runctx:
            del runctx[field]
    logger.info("\033[92m Run Stats: %s\033[00m" % json.dumps(runctx, indent=2))
    run_file = framework_currentdata()
    remove_file(run_file)