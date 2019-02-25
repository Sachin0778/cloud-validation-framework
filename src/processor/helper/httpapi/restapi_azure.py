"""Rest API utils and calls. Fetch access token and make http calls."""

from builtins import input
import json
import os
from processor.logging.log_handler import getlogger
from processor.helper.file.file_utils import exists_file
from processor.helper.config.rundata_utils import get_from_currentdata, put_in_currentdata
from processor.helper.httpapi.http_utils import http_post_request, http_get_request
from processor.helper.json.json_utils import get_field_value, json_from_file, collectiontypes, STRUCTURE
from processor.helper.config.config_utils import get_test_json_dir, config_value
from processor.database.database import DATABASE, DBNAME, sort_field, get_documents


ACCESSTOKEN = 'token'
VAULTACCESSTOKEN = 'vaulttoken'
SUBSCRIPTION = 'subscriptionId'
TENANT = 'tenant_id'
RESOURCEGROUP = 'rg'
STORAGE = 'storageid'
CLIENTID = 'clientId'
CLIENTSECRET = 'clientSecret'
VAULTCLIENTSECRET = 'vaultClientSecret'
JSONSOURCE = 'jsonsource'


logger = getlogger()

def get_azure_data(snapshot_source):
    sub_data = {}
    if json_source():
        dbname = config_value(DATABASE, DBNAME)
        collection = config_value(DATABASE, collectiontypes[STRUCTURE])
        parts = snapshot_source.split('.')
        qry = {'name': parts[0]}
        sort = [sort_field('timestamp', False)]
        docs = get_documents(collection, dbname=dbname, sort=sort, query=qry, limit=1)
        logger.info('Number of Snapshot Documents: %s', len(docs))
        if docs and len(docs):
            sub_data = docs[0]['json']
    else:
        json_test_dir = get_test_json_dir()
        azure_source = '%s/../%s' % (json_test_dir, snapshot_source)
        logger.info('Azure source: %s', azure_source)
        if exists_file(azure_source):
            sub_data = json_from_file(azure_source)
    return sub_data


def get_web_client_data(snapshot_type, snapshot_source, snapshot_user):
    client_id = None
    client_secret = None
    sub_id = None
    sub_name = None
    tenant_id = None
    found = False
    if snapshot_type == 'azure':
        sub_data = get_azure_data(snapshot_source)
        if sub_data:
            accounts = get_field_value(sub_data, 'accounts')
            for account in accounts:
                subscriptions = get_field_value(account, 'subscription')
                for subscription in subscriptions:
                    users = get_field_value(subscription, 'users')
                    if users:
                        for user in users:
                            name = get_field_value(user, 'name')
                            if name and name == snapshot_user:
                                client_id = get_field_value(user, 'client_id')
                                client_secret = get_field_value(user, 'client_secret')
                                sub_id = get_field_value(subscription, 'subscription_id')
                                sub_name = get_field_value(subscription, 'subscription_name')
                                tenant_id = get_field_value(sub_data, 'tenant_id')
                                found = True
                            if found:
                                break
                    if found:
                        break
                if found:
                    break
    return client_id, client_secret, sub_name, sub_id, tenant_id


def get_subscription_id():
    """ Return the subscription Id used for the current run"""
    return get_from_currentdata(SUBSCRIPTION)


def get_tenant_id():
    """ Return the tenant_id"""
    return get_from_currentdata(TENANT)


def get_client_id():
    """ Return the client Id used for the current run"""
    return get_from_currentdata(CLIENTID)


def get_resource_group():
    """ Return the resource group"""
    return get_from_currentdata(RESOURCEGROUP)


def json_source():
    """Return the json source, file system or mongo """
    val = get_from_currentdata(JSONSOURCE)
    return val if val else False


def get_client_secret():
    """ Return the client secret used for the current run"""
    client_secret = get_from_currentdata(CLIENTSECRET)
    if not client_secret:
        client_secret = os.getenv('CLIENTKEY', None)
    if not client_secret:
        client_secret = input('Enter the client secret for the app: ')
    return client_secret


def get_access_token():
    """
    Get the access token if stored in rundata, otherwise get the token from
    management.azure.com portal for the webapp.
    """
    token = get_from_currentdata(ACCESSTOKEN)
    if not token:
        tenant_id = get_tenant_id()
        client_id = get_client_id()
        if client_id:
            client_secret = get_client_secret()
        else:
            logger.info('client Id required for REST API access!')
            return None
        data = {
            'grant_type': 'client_credentials',
            'client_id': client_id,
            'client_secret': client_secret,
            'resource': 'https://management.azure.com'
        }
        hdrs = {
            'Cache-Control': "no-cache",
            "Accept": "application/json"
        }
        if tenant_id:
            url = 'https://login.microsoftonline.com/%s/oauth2/token' % tenant_id
            logger.info('Get Azure token REST API invoked!')
            status, data = http_post_request(url, data, headers=hdrs)
            if status and isinstance(status, int) and status == 200:
                token = data['access_token']
                put_in_currentdata(ACCESSTOKEN, token)
            else:
                put_in_currentdata('errors', data)
                logger.info("Get Azure token returned invalid status: %s", status)
    return token


def get_vault_client_secret():
    """ Return the vault client secret used."""
    vault_client_secret = get_from_currentdata(VAULTCLIENTSECRET)
    if not vault_client_secret:
        vault_client_secret = os.getenv('VAULTCLIENTKEY', None)
    if not vault_client_secret:
        vault_client_secret = input('Enter the vault client secret: ')
    return vault_client_secret


def get_vault_access_token(tenant_id, vault_client_id, client_secret=None):
    """
    Get the vault access token to get all the other passwords/secrets.
    """
    vaulttoken = get_from_currentdata(VAULTACCESSTOKEN)
    if not vaulttoken:
        vault_client_secret = client_secret if client_secret else get_vault_client_secret()
        data = {
            'grant_type': 'client_credentials',
            'client_id': vault_client_id,
            'client_secret': vault_client_secret,
            'resource': 'https://vault.azure.net'
        }
        hdrs = {
            'Cache-Control': "no-cache",
            "Accept": "application/json"
        }
        if tenant_id:
            url = 'https://login.microsoftonline.com/%s/oauth2/token' % tenant_id
            logger.info('Get Azure token REST API invoked!')
            status, data = http_post_request(url, data, headers=hdrs)
            if status and isinstance(status, int) and status == 200:
                vaulttoken = data['access_token']
                put_in_currentdata(VAULTACCESSTOKEN, vaulttoken)
            else:
                put_in_currentdata('errors', data)
                logger.info("Get Azure token returned invalid status: %s", status)
    return vaulttoken


def get_keyvault_secret(keyvault, secret_key, vaulttoken):
    hdrs = {
        'Authorization': 'Bearer %s' % vaulttoken
    }
    logger.info('Get Id REST API invoked!')
    urlstr = 'https://%s.vault.azure.net/secrets/%s?api-version=7.0'
    url = urlstr % (keyvault, secret_key)
    status, data = http_get_request(url, hdrs)
    logger.info('Get Id status: %s', status)
    if status and isinstance(status, int) and status == 200:
        logger.debug('Data: %s', data)
    else:
        put_in_currentdata('errors', data)
        logger.info("Get Id returned invalid status: %s", status)
    return data