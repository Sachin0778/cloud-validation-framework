"""
   Common file for running validator functions.
"""
import json
import tempfile
import requests
import copy
import hashlib
import time
import re
import pymongo
import os
from processor.connector.special_crawler.azure_crawler import AzureCrawler
from processor.connector.special_node_pull.azure_node_pull import AzureNodePull, NODE_PULL_URL
from processor.helper.file.file_utils import exists_file
from processor.logging.log_handler import getlogger
from processor.helper.config.rundata_utils import put_in_currentdata,\
    delete_from_currentdata, get_from_currentdata, get_dbtests
from processor.helper.json.json_utils import get_field_value, json_from_file,\
    collectiontypes, STRUCTURE, make_snapshots_dir, save_json_to_file, store_snapshot
from processor.helper.httpapi.restapi_azure import get_access_token,\
    get_web_client_data, get_client_secret, json_source, GRAPH_TOKEN
from processor.connector.vault import get_vault_data
from processor.helper.httpapi.http_utils import http_get_request
from processor.helper.config.config_utils import config_value, framework_dir, CUSTOMER, EXCLUSION
from processor.database.database import insert_one_document, COLLECTION, get_collection_size, create_indexes, \
     DATABASE, DBNAME, sort_field, get_documents
from processor.connector.snapshot_utils import validate_snapshot_nodes
from processor.templates.azure.azure_parser import AzureTemplateParser


logger = getlogger()
apiversions = None

def get_api_versions():
    """ get api versions dict """
    global apiversions
    if not apiversions:
        api_source = config_value('AZURE', 'api')
        if json_source():
            dbname = config_value(DATABASE, DBNAME)
            collection = config_value(DATABASE, collectiontypes[STRUCTURE])
            parts = api_source.rsplit('/')
            name = parts[-1].split('.')
            qry = {'name': name[0]}
            sort = [sort_field('timestamp', False)]
            docs = get_documents(collection, dbname=dbname, sort=sort, query=qry, limit=1)
            logger.info('Number of Azure API versions: %s', len(docs))
            if docs and len(docs):
                apiversions = docs[0]['json']
        else:
            apiversions_file = '%s/%s' % (framework_dir(), api_source)
            # logger.info(apiversions_file)
            if exists_file(apiversions_file):
                apiversions = json_from_file(apiversions_file)
    return apiversions

def get_version_for_type(node):
    """Url version of the resource."""
    version = None
    apiversions = get_api_versions()
    if apiversions:
        if node and 'type' in node and node['type'] in apiversions:
            version = apiversions[node['type']]['version']
    else:
        logger.error("Azure API versions are not set or invalid path")
    return version

def get_all_nodes(token, sub_name, sub_id, node, user, snapshot_source):
    """ Fetch all nodes from azure portal using rest API."""
    collection = node['collection'] if 'collection' in node else COLLECTION
    scope = node.get("scope")
    parts = snapshot_source.split('.')
    db_records = []
    d_record = {
        "structure": "azure",
        "reference": sub_name,
        "contentType": "json",
        "source": parts[0],
        "path": '',
        "timestamp": int(time.time() * 1000),
        "queryuser": user,
        "checksum": hashlib.md5("{}".encode('utf-8')).hexdigest(),
        "node": node,
        "snapshotId": None,
        "mastersnapshot": True,
        "masterSnapshotId": [node['masterSnapshotId']],
        "collection": collection.replace('.', '').lower(),
        "json": {}  # Refactor when node is absent it should None, when empty object put it as {}
    }
    # version = get_version_for_type(node)
    version = node.get("version")
    # if sub_id and token and node and version:

    exclude_paths = []
    exclude_regex = []
    include_paths = []
    include_regex = []

    exclude = node.get('exclude')
    if exclude and isinstance(exclude, dict):
        exclude_paths += exclude.get("paths", [])
        exclude_regex += exclude.get("regex", [])
    
    include = node.get('include')
    if include and isinstance(include, dict):
        include_paths += include.get("paths", [])
        include_regex += include.get("regex", [])

    nodetype = None
    if node and 'type' in node and node['type']:
        nodetype = node['type']
    if sub_id and token and nodetype:
        hdrs = {
            'Authorization': 'Bearer %s' % token
        }
        # urlstr = 'https://management.azure.com/subscriptions/%s/providers/%s?api-version=%s'
        # url = urlstr % (sub_id, node['type'], version)
        # db_record['path'] = node['path']
        resources = get_from_currentdata('resources')
        if not resources:
            urlstr = 'https://management.azure.com/subscriptions/%s/resources?api-version=2017-05-10'
            url = urlstr % sub_id
            # logger.info('Get Id REST API invoked!')
            status, data = http_get_request(url, hdrs, name='\tRESOURCE LIST')
            # logger.info('Get Id status: %s', status)
            if status and isinstance(status, int) and status == 200:
                resources = data['value']
                put_in_currentdata('resources', resources)
            else:
                resources = []
                put_in_currentdata('errors', data)
                logger.info("Get Id returned invalid status: %s", status)
        
        azure_crawler = AzureCrawler(resources, token=token, apiversions=get_api_versions(), subscription_id=sub_id, version=version, scope=scope)
        resources = azure_crawler.check_for_special_crawl(nodetype)
        if resources:
            for idx, value in enumerate(resources):
                if nodetype.lower() == value.get('type', "").lower() or \
                    nodetype in azure_crawler.special_node_type_crwler:
                    if value['id'] in exclude_paths:
                        logger.warning("Excluded : %s", value['id'])
                        continue
                    
                    if value['id'] and any(re.match(regex, value['id']) for regex in exclude_regex):
                        logger.warning("Excluded : %s", value['id'])
                        continue

                    if not check_include_path_validation(value["id"], include_paths, include_regex):
                        logger.warning("Path does not exist in include Regex : %s", value['id'])
                        continue

                    db_record = copy.deepcopy(d_record)
                    db_record['snapshotId'] = '%s%s' % (node['masterSnapshotId'], str(idx))
                    db_record['path'] = value['id']
                    db_record['json'] = value
                    data_str = json.dumps(value)
                    db_record['checksum'] = hashlib.md5(data_str.encode('utf-8')).hexdigest()
                    db_records.append(db_record)
    else:
        logger.info('Get requires valid subscription, token and path.!')
    return db_records

def export_template(url, hdrs, path, retry_count=3):
    """
    export template
    """
    hdrs["Content-type"] = "application/json"
    hdrs["cache-control"] = "no-cache"
    request_data = {
        "resources": [ path ],
        "options": "SkipAllParameterization"
    }
    response = requests.post(url, data=json.dumps(request_data), headers=hdrs)
    data = {}
    if response.status_code and isinstance(response.status_code, int) and response.status_code == 202 and retry_count:
        return export_template(url, hdrs, path, retry_count=retry_count-1)
    if response.status_code and isinstance(response.status_code, int) and response.status_code == 200:
        data = response.json().get("template", {})
    return response.status_code, data

def get_node(token, sub_name, sub_id, node, user, snapshot_source, all_data_records):
    """ Fetch node from azure portal using rest API."""
    collection = node['collection'] if 'collection' in node else COLLECTION
    parts = snapshot_source.split('.')
    session_id = get_from_currentdata("session_id")
    db_record = {
        "structure": "azure",
        "reference": sub_name,
        "contentType": "json",
        "source": parts[0],
        "path": '',
        "timestamp": int(time.time() * 1000),
        "queryuser": user,
        "checksum": hashlib.md5("{}".encode('utf-8')).hexdigest(),
        "node": node,
        "snapshotId": node['snapshotId'],
        "mastersnapshot": False,
        "masterSnapshotId": None,
        "collection": collection.replace('.', '').lower(),
        "region" : "",
        "session_id": session_id,
        "json": {"resources": []}  # Refactor when node is absent it should None, when empty object put it as {}
    }
            
    version = node["version"] if node.get("version") else get_version_for_type(node)
    if sub_id and token and node and node['path'] and version:
        hdrs = {
            'Authorization': 'Bearer %s' % token
        }
        
        status = None 
        data = None
        if node['path'].startswith('/subscriptions'):
            urlstr = 'https://management.azure.com%s?api-version=%s'
            url = urlstr % (node['path'], version)
        elif node.get('type', "") in NODE_PULL_URL:
            urlstr = 'https://%s%s'
            url = urlstr % (NODE_PULL_URL[node.get('type')], node['path'])
            graph_token = get_access_token("https://graph.microsoft.com", token_key=GRAPH_TOKEN)
            hdrs["Authorization"] = 'Bearer %s' % graph_token
        else:
            parent_resource_json = {}
            urlstr = 'https://management.azure.com/subscriptions/%s%s?api-version=%s'
            url = urlstr % (sub_id, node['path'], version)
         
        resource_group = ""
        exmatch = re.search(r'/subscriptions.*/resourceGroups/(.*?)/', node['path'], re.I)
        if exmatch:
            resource_group = exmatch.group(1)
         
        child_resource_type_list = node.get('type', "").split("/")   
        if len(child_resource_type_list) == 2:
            exmatch = re.search(r'/subscriptions.*/resourceGroups/.*?/', node['path'], re.I)
            if exmatch:
                export_template_url = 'https://management.azure.com%sexportTemplate?api-version=2021-04-01' % (exmatch.group(0).lower())
                status, data = export_template(export_template_url, hdrs, node['path'], retry_count=0)
                
        db_record['path'] = node['path']
        
        if status and isinstance(status, int) and status == 200:
            if data and data.get("resources"):
                try:
                    temp_dir = tempfile.mkdtemp()
                    resource_file = ("%s/%s") % (temp_dir, "resource_file.json")
                
                    save_json_to_file(data, resource_file)
    
                    azure_template_parser = AzureTemplateParser(resource_file, parameter_file=[])
                    template_json = azure_template_parser.parse()
                
                    os.remove(resource_file)
                except Exception as e:
                    logger.info("Exception: %s, Snapshot: %s", str(e), node['snapshotId'])
                    template_json = data

                db_record['json']['resources'] = template_json.get("resources")
                db_record['json']["subscription_id"] = sub_id
                db_record['json']["resource_group"] = resource_group
        else:
            status, data = http_get_request(url, hdrs, name='\tRESOURCE:')
        
            if status and isinstance(status, int) and status == 200:    
                # parent_resource_json = {}
                # child_resource_type_list = node.get('type', "").split("/")
                # if len(child_resource_type_list) > 2:
                #     child_resource_type = "/".join(child_resource_type_list[2:])
                #     main_resource_type = "/".join(child_resource_type_list[:2])
                #     for all_data_record in all_data_records:
                #         if all_data_record["json"]["resources"][0].get("type") == main_resource_type:
                #             if "%s/" % all_data_record["json"]["resources"][0].get("id") in node["path"]:
                #                 all_data_record["json"]["resources"].append(data)

                azure_node_pull = AzureNodePull(data, token=token, apiversions=get_api_versions())
                data = azure_node_pull.check_for_node_pull(node.get('type', ""))
            
                db_record['json']["subscription_id"] = sub_id
                db_record['json']["resource_group"] = resource_group
                db_record['json']['resources'].append(data)
                db_record['region'] = data.get("location")
                data_str = json.dumps(data)
                db_record['checksum'] = hashlib.md5(data_str.encode('utf-8')).hexdigest()
            else:
                put_in_currentdata('errors', data)
                logger.info("Get Id returned invalid status: %s, response: %s", status, data)
                logger.error("Failed to get Azure resourse with given path : %s, please verify your azure connector detail and path given in snapshot.", node['path'])
    else:
        db_record = {}
        logger.info('Get requires valid subscription, token and path.!')
    return db_record

def check_include_path_validation(path, include_paths, include_regex_list):

    if include_paths or include_regex_list:
        include_path = False
        include_regex = False
    else:
        include_path = True
        include_regex = True

    if include_paths and path and \
        any((include_path in path or path in include_path) for include_path in include_paths):
        include_path = True

    if include_regex_list and path and any(re.match(regex, path) for regex in include_regex_list):
        include_regex = True

    return include_path or include_regex


def populate_client_secret(client_id, client_secret, snapshot_user):
    if not client_id:
        # logger.info("No client_id in the snapshot to access azure resource!...")
        raise Exception("No client id in the snapshot to access azure resource!...")

    # Read the client secrets from envirnment variable
    if not client_secret:
        client_secret = os.getenv(snapshot_user, None)
        if client_secret:
            logger.info('Client Secret from environment variable, Secret: %s', '*' * len(client_secret))
        
    # Read the client secrets from the vault
    if not client_secret:
        client_secret = get_vault_data(client_id)
        if client_secret:
            logger.info('Client Secret from Vault, Secret: %s', '*' * len(client_secret))
        elif get_from_currentdata(CUSTOMER):
            logger.error("Client Secret key does not set in a vault")
            raise Exception("Client Secret key does not set in a vault")

    if not client_secret:
        raise Exception("No `client_secret` key in the connector file to access azure resource!...")
    
    return client_secret

def populate_azure_snapshot(snapshot, container=None, snapshot_type='azure'):
    """ Populates the resources from azure."""
    dbname = config_value('MONGODB', 'dbname')
    snapshot_source = get_field_value(snapshot, 'source')
    snapshot_user = get_field_value(snapshot, 'testUser')
    snapshot_nodes = get_field_value(snapshot, 'nodes')
    snapshot_data, valid_snapshotids = validate_snapshot_nodes(snapshot_nodes)
    client_id, client_secret, sub_name, sub_id, tenant_id = \
        get_web_client_data(snapshot_type, snapshot_source, snapshot_user, container)
    
    client_secret = populate_client_secret(client_id, client_secret, snapshot_user)

    logger.info('\t\tSubscription: %s', sub_id)
    logger.info('\t\tTenant: %s', tenant_id)
    logger.info('\t\tclient: %s', client_id)
    put_in_currentdata('clientId', client_id)
    put_in_currentdata('clientSecret', client_secret)
    put_in_currentdata('subscriptionId', sub_id)
    put_in_currentdata('tenant_id', tenant_id)
    token = get_access_token()
    # logger.debug('TOKEN: %s', token)
    if not token:
        logger.info("Unable to get access token, will not run tests....")
        raise Exception("Unable to get access token, will not run tests....")
        # return {}

    # snapshot_nodes = get_field_value(snapshot, 'nodes')
    # snapshot_data, valid_snapshotids = validate_snapshot_nodes(snapshot_nodes)
    if valid_snapshotids and token and snapshot_nodes:
        all_data_records = []
        for node in snapshot_nodes:
            validate = node['validate'] if 'validate' in node else True
            if 'path' in  node:
                data = get_node(token, sub_name, sub_id, node, snapshot_user, snapshot_source, all_data_records)
                if data:
                    if validate:
                        all_data_records.append(data)
                        # if get_dbtests():
                        #     if get_collection_size(data['collection']) == 0:
                        #         # Creating indexes for collection
                        #         create_indexes(
                        #             data['collection'], 
                        #             config_value(DATABASE, DBNAME), 
                        #             [
                        #                 ('snapshotId', pymongo.ASCENDING),
                        #                 ('timestamp', pymongo.DESCENDING)
                        #             ]
                        #         )

                        #         create_indexes(
                        #             data['collection'], 
                        #             config_value(DATABASE, DBNAME), 
                        #             [
                        #                 ('_id', pymongo.DESCENDING),
                        #                 ('timestamp', pymongo.DESCENDING),
                        #                 ('snapshotId', pymongo.ASCENDING)
                        #             ]
                        #         )
                        #     insert_one_document(data, data['collection'], dbname, check_keys=False)
                        # else:
                        #     snapshot_dir = make_snapshots_dir(container)
                        #     if snapshot_dir:
                        #         store_snapshot(snapshot_dir, data)
                        if 'masterSnapshotId' in node:
                            snapshot_data[node['snapshotId']] = node['masterSnapshotId']
                        else:
                            snapshot_data[node['snapshotId']] = True
                    # else:
                    #     snapshot_data[node['snapshotId']] = False
                    node['status'] = 'active'
                else:
                    # TODO alert if notification enabled or summary for inactive.
                    node['status'] = 'inactive'
                logger.debug('Type: %s', type(data))
            else:
                alldata = get_all_nodes(
                    token, sub_name, sub_id, node, snapshot_user, snapshot_source)
                if alldata:
                    includeSnapshotConfig = get_from_currentdata("INCLUDESNAPSHOTS")
                    includeSnapshots = get_from_currentdata("SNAPHSHOTIDS")
                    ignoreExclusion = False
                    ignoreNode = False
                    if includeSnapshotConfig:
                        if node['masterSnapshotId'] in includeSnapshots:
                            ignoreExclusion = True
                            ignoreNode = False
                        else:
                            ignoreNode  = True
                    exclusions = get_from_currentdata(EXCLUSION).get('exclusions', [])
                    resourceExclusions = {}
                    if not ignoreExclusion:
                        for exclusion in exclusions:
                            if 'exclusionType' in exclusion and exclusion['exclusionType'] and exclusion['exclusionType'] == 'resource':
                                if 'paths' in exclusion and isinstance(exclusion['paths'], list):
                                    resourceExclusions[tuple(exclusion['paths'])] = exclusion

                    snapshot_data[node['masterSnapshotId']] = []
                    for data in alldata:
                        # insert_one_document(data, data['collection'], dbname)
                        found_old_record = False
                        for masterSnapshotId, snapshot_list in snapshot_data.items():
                            old_record = None
                            if isinstance(snapshot_list, list):
                                for item in snapshot_list:
                                    if item["path"] == data['path']:
                                        old_record = item

                                if old_record:
                                    found_old_record = True
                                    if node['masterSnapshotId'] not in old_record['masterSnapshotId']:
                                        old_record['masterSnapshotId'].append(
                                            node['masterSnapshotId'])

                        if not found_old_record:
                            if isinstance(data['path'], str):
                                key = tuple([data['path']])
                            elif isinstance(data['path'], list):
                                key = tuple(data['path'])
                            else:
                                key = None
                            if key and key in resourceExclusions:
                                logger.warning("Excluded from resource exclusions: %s", data['path'])
                                continue
                            if not ignoreNode:
                                snapshot_data[node['masterSnapshotId']].append(
                                    {
                                        'masterSnapshotId': [node['masterSnapshotId']],
                                        'snapshotId': data['snapshotId'],
                                        'path': data['path'],
                                        'validate': validate,
                                        'status': 'active',
                                        'subscriptionId': sub_id
                                    })

        for data in all_data_records:
            if get_dbtests():
                if get_collection_size(data['collection']) == 0:
                    # Creating indexes for collection
                    create_indexes(
                        data['collection'], 
                        config_value(DATABASE, DBNAME), 
                        [
                            ('snapshotId', pymongo.ASCENDING),
                            ('timestamp', pymongo.DESCENDING)
                        ]
                    )

                    create_indexes(
                        data['collection'], 
                        config_value(DATABASE, DBNAME), 
                        [
                            ('_id', pymongo.DESCENDING),
                            ('timestamp', pymongo.DESCENDING),
                            ('snapshotId', pymongo.ASCENDING)
                        ]
                    )
                insert_one_document(data, data['collection'], dbname, check_keys=False)
            else:
                snapshot_dir = make_snapshots_dir(container)
                if snapshot_dir:
                    store_snapshot(snapshot_dir, data)
        
        delete_from_currentdata('resources')
        delete_from_currentdata('clientId')
        delete_from_currentdata('client_secret')
        delete_from_currentdata('subscriptionId')
        delete_from_currentdata('tenant_id')
        delete_from_currentdata('token')
    return snapshot_data
