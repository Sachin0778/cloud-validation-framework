"""
   Common file for vault functionality.
"""
from builtins import input
import os
from processor.logging.log_handler import getlogger
from processor.helper.config.rundata_utils import get_from_currentdata,\
    put_in_currentdata, add_to_exclude_list
from processor.helper.config.config_utils import config_value
from processor.helper.httpapi.restapi_azure import get_vault_access_token,\
    get_keyvault_secret

logger = getlogger()


def get_vault_data(secret_key=None):
    """Read vault data from config"""
    vaulttype = config_value('VAULT', 'type')
    val = None
    if vaulttype:
        if vaulttype == 'azure':
            val = get_azure_vault_data(secret_key)
    return val


def get_config_value(section, key, env_var, prompt_str=None):
    """ Return the client secret used for the current run"""
    client_secret = config_value(section, key)
    if not client_secret and env_var:
        client_secret = os.getenv(env_var, None)
    if not client_secret and prompt_str:
        key_str = '%s_%s' % (section, key)
        client_secret = get_from_currentdata(key_str)
        if not client_secret:
            client_secret = input(prompt_str)
            if client_secret:
                put_in_currentdata(key_str, client_secret)
                logger.info('Key:%s, sec:%s', key_str, client_secret)
                add_to_exclude_list(key_str)
    return client_secret


def get_azure_vault_data(secret_key=None):
    val = None
    client_id = config_value('VAULT', 'client_id')
    client_secret = get_config_value('VAULT', 'client_secret', 'CLIENTKEY',
                                     'Enter the client secret to access keyvault: ')
    # client_secret = config_value('VAULT', 'client_secret')
    tenant_id = config_value('VAULT', 'tenant_id')
    logger.info('Id: %s, secret: %s, tenant: %s', client_id, client_secret, tenant_id)
    vaulttoken = get_vault_access_token(tenant_id, client_id, client_secret)
    logger.debug('Vault Token: %s', vaulttoken)
    if vaulttoken and secret_key:
        keyvault = config_value('VAULT', 'keyvault')
        # secret_key = config_value('VAULT', 'secret_key')
        logger.info('Keyvault: %s, key:%s', keyvault, secret_key)
        secret_data = get_keyvault_secret(keyvault, secret_key, vaulttoken)
        if secret_data and 'value' in secret_data:
            val = secret_data['value']
    logger.info('Secret Value: %s', val)
    return val