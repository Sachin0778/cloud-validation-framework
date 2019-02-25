""" Utility functions for json."""

import json
import time
import glob
from collections import OrderedDict
from processor.helper.file.file_utils import exists_file
from processor.helper.config.config_utils import get_test_json_dir
from processor.logging.log_handler import getlogger

SNAPSHOT = 'snapshot'
JSONTEST = 'test'
TEST = 'test'
OUTPUT = 'output'
STRUCTURE = 'structure'
collectiontypes = {
    TEST: 'TEST',
    STRUCTURE: 'STRUCTURE',
    SNAPSHOT: 'SNAPSHOT',
    OUTPUT: 'OUTPUT'
}
logger = getlogger()


def save_json_to_file(indata, outfile):
    """Save json data to the file"""
    if indata is not None:
        try:
            instr = json.dumps(indata, indent=2)
            with open(outfile, 'w') as jsonwrite:
                jsonwrite.write(instr)
        except:
            pass


def json_from_string(json_str):
    """Get json from the string."""
    try:
        jsondata = json.loads(json_str)
        return jsondata
    except:
        logger.debug('Failed to load json data: %s', json_str)
    return None


def json_from_file(jsonfile):
    """ Get json data from the file."""
    jsondata = None
    try:
        if exists_file(jsonfile):
            with open(jsonfile) as infile:
                jsondata = json.loads(infile.read(), object_pairs_hook=OrderedDict)
    except:
        logger.debug('Failed to load json from file: %s', jsonfile)
    return jsondata


def valid_json(json_input):
    """ Checks validity of the json """
    try:
        _ = json.loads(json_input)
        return True
    except:
        logger.debug('Not a valid json: %s', json_input)
    return False


def check_field_exists(data, parameter):
    """Utility to check json field is present."""
    present = False
    if data and parameter:
        fields = parameter.split('.')
        curdata = data
        if fields:
            allfields = True
            for field in fields:
                if curdata:
                    if field in curdata and isinstance(curdata, dict):
                        curdata = curdata[field]
                    else:
                        allfields = False
            if allfields:
                present = True
    return present


def get_field_value(data, parameter):
    """get json value for a nested attribute."""
    retval = None
    parameter = parameter[1:] if parameter and parameter.startswith('.') else parameter
    fields = parameter.split('.') if parameter else None
    if data and fields:
        retval = data
        for field in fields:
            retval = retval[field] if retval and field in retval and isinstance(retval, dict) \
                else None
    return retval


def put_value(json_data, field, value):
    """Put the value for a multiple depth key."""
    data = json_data
    field = field[1:] if field and field.startswith('.') else field
    fields = field.split('.') if field else []
    for idx, fld in enumerate(fields):
        if idx == len(fields) - 1:
            data[fld] = value
        else:
            if fld not in data or not isinstance(data[fld], dict):
                data[fld] = {}
        data = data[fld]


def parse_boolean(val):
    """String to boolean type."""
    return True if val and val.lower() == 'true' else False


def set_timestamp(json_data, fieldname='timestamp'):
    """Set the current timestamp for the object."""
    if not isinstance(json_data, dict):
        return False
    timestamp = int(time.time() * 1000)
    json_data[fieldname] = timestamp
    return True


def get_container_dir(container):
    """Translate container name to container directory"""
    json_test_dir = get_test_json_dir()
    logger.info('json_test_dir: %s', json_test_dir)
    container_dir = '%s/%s' % (json_test_dir, container)
    container_dir = container_dir.replace('//', '/')
    logger.info(container_dir)
    return container_dir


def get_container_snapshot_json_files(container):
    """Return list of snapshot files in the container."""
    container_dir = get_container_dir(container)
    snapshot_files = get_json_files(container_dir, SNAPSHOT)
    return container_dir, snapshot_files


def get_json_files(json_dir, file_type):
    """Return list of json files based on the file type."""
    file_list = []
    if json_dir and file_type:
        for filename in glob.glob('%s/*.json' % json_dir.replace('//', '/')):
            json_data = json_from_file(filename)
            if json_data and 'fileType' in json_data and json_data['fileType'] == file_type:
                file_list.append(filename)
    return file_list