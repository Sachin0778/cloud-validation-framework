"""
snapshot connector file for aws type snapshot. When the 'type' is 'aws', the
resource objects have to be fetched from the AWS interface.
The connection could use python SDK libraries or https calls or other known methods
provided by the provider.
Here in case of AWS, have used boto python SDK released and maintained by AWS.
boto library provides different 'describe_' functions and using this functionality,
the snapshot mentions which describe function has to be called, so 'type' could
be 'security_groups' , 'instances', 'regions' and using python reflection capabilities
a callable from describe_security_groups gets callable for this function to return security groups.
The describe_ functions lots of methods to query AWS resources, since we know what resource we need
we always query by id, so AWS snapshots shall always have {"id": "123de23"} to uniquely
identify the resource object.
"""
import json
import hashlib
import time
from googleapiclient import discovery
from oauth2client.service_account import ServiceAccountCredentials
from processor.helper.file.file_utils import exists_file
from processor.logging.log_handler import getlogger
from processor.helper.config.rundata_utils import put_in_currentdata, get_dbtests
from processor.helper.json.json_utils import get_field_value, json_from_file,\
    collectiontypes, STRUCTURE, save_json_to_file, get_field_value_with_default,\
    make_snapshots_dir, store_snapshot
from processor.connector.vault import get_vault_data
from processor.helper.config.config_utils import config_value, get_test_json_dir, framework_dir
from processor.database.database import insert_one_document, sort_field, get_documents,\
    COLLECTION, DATABASE, DBNAME
from processor.helper.httpapi.restapi_azure import json_source
from processor.connector.snapshot_utils import validate_snapshot_nodes

logger = getlogger()


def get_google_data(snapshot_source):
    """
    The Google source object to be fetched from database or the filesystem
    The initial configuration for database is 'validator' and collection
    is 'structures', whereas for the filesystem the path to fetch the
    'structures' is  $SOLUTIONDIR/realm/<structure>.json
    """
    sub_data = {}
    if json_source():
        dbname = config_value(DATABASE, DBNAME)
        collection = config_value(DATABASE, collectiontypes[STRUCTURE])
        parts = snapshot_source.split('.')
        qry = {'name': parts[0]}
        sort = [sort_field('timestamp', False)]
        docs = get_documents(collection, dbname=dbname, sort=sort, query=qry, limit=1)
        logger.info('Number of Google structure Documents: %d', len(docs))
        if docs and len(docs):
            sub_data = docs[0]['json']
    else:
        json_test_dir = get_test_json_dir()
        file_name = '%s.json' % snapshot_source if snapshot_source and not \
            snapshot_source.endswith('.json') else snapshot_source
        google_source = '%s/../%s' % (json_test_dir, file_name)
        logger.info('Google source: %s', google_source)
        if exists_file(google_source):
            sub_data = json_from_file(google_source)
    return sub_data


def get_call_kwargs_for_crawler(node, project_id):
    """Get argument names and their values in kwargs for Crawler"""
    kwargs = None
    logger.info("Get node's kwargs")
    params_source = config_value('GOOGLE', 'params')
    paramsversions = None
    if json_source():
        dbname = config_value(DATABASE, DBNAME)
        collection = config_value(DATABASE, collectiontypes[STRUCTURE])
        parts = params_source.rsplit('/')
        name = parts[-1].split('.')
        qry = {'name': name[0]}
        sort = [sort_field('timestamp', False)]
        docs = get_documents(collection, dbname=dbname, sort=sort, query=qry, limit=1)
        logger.info('Number of Google Params versions: %s', len(docs))
        if docs and len(docs):
            paramsversions = docs[0]['json']
    else:
        paramsversions_file = '%s/%s' % (framework_dir(), params_source)
        logger.info(paramsversions_file)
        if exists_file(paramsversions_file):
            paramsversions = json_from_file(paramsversions_file)
    if paramsversions:
        if node and 'type' in node:
            aggregated_list = paramsversions['aggregatedList'] if 'aggregatedList' in paramsversions else []
            global_list = paramsversions['globalList'] if 'globalList' in paramsversions else []

            kwargs = {}
            if node['type'] in aggregated_list:
                kwargs['type'] = "aggregated"
                kwargs['param'] = {
                    "project" : project_id
                }

            elif node['type'] in global_list:
                kwargs['type'] = "global"
                kwargs['param'] = {
                    "project" : project_id
                }

            else:
                logger.error("Invalid JSON: '" + node['type'] + "' is not a valid node type")
                
    return kwargs

def get_call_kwargs(node, params):
    """Get argument names and their values in kwargs"""
    kwargs = {}
    logger.info("Get node's kwargs")
    params_source = config_value('GOOGLE', 'params')
    paramsversions = None
    if json_source():
        dbname = config_value(DATABASE, DBNAME)
        collection = config_value(DATABASE, collectiontypes[STRUCTURE])
        parts = params_source.rsplit('/')
        name = parts[-1].split('.')
        qry = {'name': name[0]}
        sort = [sort_field('timestamp', False)]
        docs = get_documents(collection, dbname=dbname, sort=sort, query=qry, limit=1)
        logger.info('Number of Google Params versions: %s', len(docs))
        if docs and len(docs):
            paramsversions = docs[0]['json']
    else:
        paramsversions_file = '%s/%s' % (framework_dir(), params_source)
        logger.info(paramsversions_file)
        if exists_file(paramsversions_file):
            paramsversions = json_from_file(paramsversions_file)
    if paramsversions:
        if node and 'type' in node and node['type'] in paramsversions:
            # path = get_field_value(node, 'path')
            # path = path[:-1] if path and path.endswith('/') else path
            # path = path[1:] if path and path.startswith('/') else path
            # params = path.split('/')
            pfields = paramsversions[node['type']]
            pcount = 0
            for idx in range(2, len(params), 2):
                index = idx + 1
                if idx == 4 and params[idx] == "global":
                    index += 1

                if index >= len(params):
                    break

                kwargs[pfields[pcount]] = params[index]
                pcount += 1   
    return kwargs


def get_google_call_function(node):
    """Get the callable for the type of compute resource."""
    fn_str = None
    kwargs = {}
    if node and 'type' in node and node['type']:
        path = get_field_value(node, 'path')
        path = path[:-1] if path and path.endswith('/') else path
        path = path[1:] if path and path.startswith('/') else path
        params = path.split('/')
        if ((len(params)%2) != 0 and params[4] == "global") or (len(params)%2) == 0 and params[4] != "global":
            fn_str = params[-2]
        else:
            fn_str = params[-1]
        kwargs = get_call_kwargs(node, params)
    return fn_str, kwargs

def get_google_call_function_for_crawler(node, project_id):
    """Get the callable for the type of compute resource."""
    fn_str = None
    kwargs = None
    if node and 'type' in node and node['type']:
        fn_str = get_field_value(node, 'type')
        kwargs = get_call_kwargs_for_crawler(node, project_id)
    return fn_str, kwargs

def get_node(compute, node, snapshot_source, snapshot):
    """
    Fetch node from google using connection. In this case using google client API's
    functions.
    """
    collection = node['collection'] if 'collection' in node else COLLECTION
    parts = snapshot_source.split('.')
    project_id = get_field_value_with_default(snapshot, 'project-id',"")
    path = get_field_value_with_default(node, 'path',"")
    db_record = {
        "structure": "google",
        "error": None,
        "reference": project_id,
        "source": parts[0],
        "path": path,
        "timestamp": int(time.time() * 1000),
        "queryuser": "",
        "checksum": hashlib.md5("{}".encode('utf-8')).hexdigest(),
        "node": node,
        "snapshotId": node['snapshotId'],
        "collection": collection.replace('.', '').lower(),
        "json": {}  # Refactor when node is absent it should None, when empty object put it as {}
    }
    fn_str, kwargs = get_google_call_function(node)
    if fn_str:
        compute_fn = getattr(compute, fn_str, None)
        if compute_fn and callable(compute_fn):
            try:
                data = compute_fn().get(**kwargs).execute()
                if data:
                    db_record['json'] = data
                    checksum = get_checksum(data)
                    if checksum:
                        db_record['checksum'] = checksum
                else:
                    put_in_currentdata('errors', data)
                    logger.info("Compute function does not exist: %s", fn_str)
                    db_record['error'] = "Compute function does not exist: %s" % fn_str
            except Exception as ex:
                logger.info('Compute function exception: %s', ex)
                db_record['error'] = 'Compute function exception: %s' % ex
        else:
            logger.info('Invalid Compute function exception: %s', fn_str)
            db_record['error'] = 'Invalid Compute function exception: %s' % fn_str
    else:
        logger.info('Missing Compute function')
        db_record['error'] = 'Missing Compute function'
    return db_record


def get_all_nodes(compute, node, snapshot_source, snapshot, snapshot_data):
    """
    Fetch all nodes from google using connection using google client API's functions.
    """
    collection = node['collection'] if 'collection' in node else COLLECTION
    parts = snapshot_source.split('.')
    project_id = get_field_value_with_default(snapshot, 'project-id',"")
    node_type = get_field_value_with_default(node, 'type',"")
    
    db_record = {
        "structure": "google",
        "error": None,
        "reference": project_id,
        "source": parts[0],
        "path": "",
        "timestamp": int(time.time() * 1000),
        "queryuser": "",
        "checksum": hashlib.md5("{}".encode('utf-8')).hexdigest(),
        "node": node,
        "snapshotId": None,
        "masterSnapshotId": [node['masterSnapshotId']],
        "collection": collection.replace('.', '').lower(),
        "json": {},  # Refactor when node is absent it should None, when empty object put it as {}
        "items": []
    }

    if node_type:
        fn_str, kwargs = get_google_call_function_for_crawler(node, project_id)
        if fn_str and kwargs:
            compute_fn = getattr(compute, fn_str, None)
            if compute_fn and callable(compute_fn):
                try:
                    data = None
                    if 'type' in kwargs and kwargs['type']:
                        if kwargs['type'] == "aggregated":
                            data = compute_fn().aggregatedList(**kwargs['param']).execute()
                        elif kwargs['type'] == "global":
                            data = compute_fn().list(**kwargs['param']).execute()
                    
                    if data:
                        db_record['json'] = data
                        
                        if kwargs['type'] == "aggregated":
                            for name, scoped_dict in data['items'].items():
                                if node_type in scoped_dict:
                                    db_record['items'] = db_record['items'] + scoped_dict[node_type]
                        
                        elif kwargs['type'] == "global":
                            db_record['items'] = data['items']

                        set_snapshot_data(node, db_record['items'], snapshot_data)

                        checksum = get_checksum(data)
                        if checksum:
                            db_record['checksum'] = checksum
                    else:
                        put_in_currentdata('errors', data)
                        logger.info("Compute function does not exist: %s", fn_str)
                        db_record['error'] = "Compute function does not exist: %s" % fn_str
                except Exception as ex:
                    logger.info('Compute function exception: %s', ex)
                    db_record['error'] = 'Compute function exception: %s' % ex
            else:
                logger.info('Invalid Compute function exception: %s', fn_str)
                db_record['error'] = 'Invalid Compute function exception: %s' % fn_str
        else:
            logger.info('Missing Compute function')
            db_record['error'] = 'Missing Compute function'
    return db_record

def set_snapshot_data(node, items, snapshot_data):
    if node['masterSnapshotId'] not in snapshot_data or not isinstance(snapshot_data[node['masterSnapshotId']], list):
        snapshot_data[node['masterSnapshotId']] =  []

    count = 0
    for item in items:
        count += 1
        path = item['selfLink'].split('https://www.googleapis.com')[1]

        found_old_record = False
        for masterSnapshotId, snapshot_list in snapshot_data.items():
            old_record = None
            if isinstance(snapshot_list, list):
                for item in snapshot_list:
                    if item["path"] == path:
                        old_record = item

                if old_record:
                    found_old_record = True
                    if node['masterSnapshotId'] not in old_record['masterSnapshotId']:
                        old_record['masterSnapshotId'].append(
                            node['masterSnapshotId'])

        if not found_old_record:
            snapshot_data[node['masterSnapshotId']].append(
                {
                    "masterSnapshotId" : [node['masterSnapshotId']],
                    "snapshotId": '%s%s' % (node['masterSnapshotId'], str(count)),
                    "type": node['type'],
                    "collection": node['collection'],
                    "path": path,
                    "status" : "active",
                    "validate" : True
                })
    return snapshot_data

def get_checksum(data):
    """ Get the checksum for the Google data fetched."""
    checksum = None
    try:
        data_str = json.dumps(data)
        checksum = hashlib.md5(data_str.encode('utf-8')).hexdigest()
    except:
        pass
    return checksum


def populate_google_snapshot(snapshot, container=None):
    """
    This is an entrypoint for populating a snapshot of type google.
    All snapshot connectors should take snapshot object and based on
    'source' field create a method to connect to the service for the
    connector.
    The 'source' field could be used by more than one snapshot, so the
    'testuser' attribute should match to the user the 'source'
    """
    dbname = config_value('MONGODB', 'dbname')
    snapshot_source = get_field_value(snapshot, 'source')
    snapshot_user = get_field_value(snapshot, 'testUser')
    sub_data = get_google_data(snapshot_source)
    snapshot_nodes = get_field_value(snapshot, 'nodes')
    snapshot_data, valid_snapshotids = validate_snapshot_nodes(snapshot_nodes)
    if valid_snapshotids and sub_data and snapshot_nodes:
        logger.debug(sub_data)
        compute = get_google_client_data(sub_data, snapshot_user)
        if not compute:
            logger.info("No  GCE connection in the snapshot to access Google resource!...")
            return snapshot_data
        try:
            for node in snapshot['nodes']:
                logger.info(node)
                if 'snapshotId' in node:
                    data = get_node(compute, node, snapshot_source, snapshot)
                    if data:
                        error_str = data.pop('error', None)
                        if get_dbtests():
                            insert_one_document(data, data['collection'], dbname)
                        else:
                            snapshot_dir = make_snapshots_dir(container)
                            if snapshot_dir:
                                store_snapshot(snapshot_dir, data)
                    
                        if 'masterSnapshotId' in node:
                            snapshot_data[node['snapshotId']] = node['masterSnapshotId']
                        else:
                            snapshot_data[node['snapshotId']] = False if error_str else True
                elif 'masterSnapshotId' in node:
                        data = get_all_nodes(compute, node, snapshot_source, snapshot, snapshot_data)
                        logger.debug('Type: %s', type(data))
        except Exception as ex:
            logger.info('Unable to create Google client: %s', ex)
    return snapshot_data


def get_google_client_data(google_data, snapshot_user):
    """
    AWS client information as required by the Boto client, viz access_key
    access_secret, AWS command type like EC2, S3 etc and region
    The access_secret is either read from structure json or env variable or keyvault
    """
    compute = None
    if google_data and snapshot_user:
        org_units = get_field_value(google_data, "organization-unit")
        if org_units:
            found = False
            for org_unit in org_units:
                accounts = get_field_value(org_unit, 'accounts')
                if accounts:
                    for account in accounts:
                        users = get_field_value(account, 'users')
                        if users:
                            for user in users:
                                username = get_field_value(user, 'name')
                                if username and username == snapshot_user:
                                    found = True
                                    gce = get_field_value(user, 'gce')
                                    if gce:
                                        save_json_to_file(gce, '/tmp/gce.json')
                                        scopes = ['https://www.googleapis.com/auth/compute']
                                        credentials = ServiceAccountCredentials.from_json_keyfile_name('/tmp/gce.json', scopes)
                                        compute = discovery.build('compute', 'v1', credentials=credentials, cache_discovery=False)
                                    
                                    break
                        if found:
                            break
                if found:
                    break
    return compute
