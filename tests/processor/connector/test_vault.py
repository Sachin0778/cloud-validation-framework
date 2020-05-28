""" Tests for vault"""

class Popen:

    def __init__(self, cmd, **kwargs):
        self.cmd = cmd

    def communicate(self, input=None, timeout=None):
        return "secret", None

class Popen1:

    def __init__(self, cmd, **kwargs):
        self.cmd = cmd

    def communicate(self, input=None, timeout=None):
        return "", "Exe not found"


def mock_get_keyvault_secret(keyvault, secret_key, vaulttoken):
    return {'value': 'secret'}


def mock_set_keyvault_secret(keyvault, vaulttoken, secret_key, value):
    return True


def mock_exception_set_keyvault_secret(keyvault, vaulttoken, secret_key, value):
    return False


def mock_delete_keyvault_secret(keyvault, vaulttoken, secret_key):
    return True


def mock_exception_delete_keyvault_secret(keyvault, vaulttoken, secret_key):
    return False


def mock_get_all_secrets(keyvault, vaulttoken):
    return ["hello", "hello2"]


def mock_exception_get_all_secrets(keyvault, vaulttoken):
    return []


def mock_get_vault_access_token(tenant_id, vault_client_id, client_secret=None):
    return 'abcd_token'

def mock_input(text):
    return 'clientSecret'

def mock_config_value(section, key, default=None):
    if key == 'type':
        return 'azure'
    elif key == 'client_id':
        return 'client_id'
    elif key == 'client_secret':
        return 'client_secret'
    elif key == 'tenant_id':
        return 'tenant_id'
    elif key == 'keyvault':
        return 'keyvault'
    return 'pytestdb'

def mock_config_value_cybeark(section, key, default=None):
    if key == 'type':
        return 'cyberark'
    elif key == 'CA_OBJECT':
        return 'CA_OBJECT'
    elif key == 'CA_SAFE':
        return False
    elif key == 'CA_EXE':
        return 'CA_EXE'
    elif key == 'CA_APPID':
        return 'CA_APPID'
    return None

def mock_empty_config_value(section, key, default=None):
    return None

def test_get_config_value(monkeypatch):
    monkeypatch.setattr('processor.connector.vault.input', mock_input)
    monkeypatch.setattr('processor.connector.vault.config_value', mock_empty_config_value)
    from processor.connector.vault import  get_config_value
    client_secret = get_config_value('VAULT', 'client_secret', 'CLIENTKEY',
                                     'Enter the client secret to access keyvault: ')
    assert client_secret is not None


def test_get_vault_data(monkeypatch):
    monkeypatch.setattr('processor.connector.vault.config_value', mock_config_value)
    monkeypatch.setattr('processor.connector.vault.get_vault_access_token', mock_get_vault_access_token)
    monkeypatch.setattr('processor.connector.vault.get_keyvault_secret', mock_get_keyvault_secret)
    from processor.connector.vault import get_vault_data
    val = get_vault_data(None)
    assert val is None
    val = get_vault_data('abcd')
    assert val == 'secret'


def test_get_azure_vault_data(monkeypatch):
    monkeypatch.setattr('processor.connector.vault.config_value', mock_config_value)
    monkeypatch.setattr('processor.connector.vault.get_vault_access_token', mock_get_vault_access_token)
    monkeypatch.setattr('processor.connector.vault.get_keyvault_secret', mock_get_keyvault_secret)
    from processor.connector.vault import get_azure_vault_data
    val = get_azure_vault_data(None)
    assert val is None
    val = get_azure_vault_data('abcd')
    assert val == 'secret'


def test_get_vault_data_cyberark(monkeypatch):
    monkeypatch.setattr('processor.connector.vault.config_value', mock_config_value_cybeark)
    monkeypatch.setattr('processor.connector.vault.Popen', Popen)
    from processor.connector.vault import get_vault_data
    val = get_vault_data(None)
    assert val == 'secret'
    val = get_vault_data('abcd')
    assert val == 'secret'


def test_get_vault_data_cyberark_error(monkeypatch):
    monkeypatch.setattr('processor.connector.vault.config_value', mock_config_value_cybeark)
    monkeypatch.setattr('processor.connector.vault.Popen', Popen1)
    from processor.connector.vault import get_vault_data
    val = get_vault_data('abcd')
    assert val is None


def test_set_vault_data(monkeypatch):
    monkeypatch.setattr('processor.connector.vault.config_value', mock_config_value)
    monkeypatch.setattr('processor.connector.vault.get_vault_access_token', mock_get_vault_access_token)
    monkeypatch.setattr('processor.connector.vault.set_keyvault_secret', mock_set_keyvault_secret)
    from processor.connector.vault import set_vault_data
    val = set_vault_data('hello', 'world')
    assert val == True
    monkeypatch.setattr('processor.connector.vault.set_keyvault_secret', mock_exception_set_keyvault_secret)
    val = set_vault_data('hello', 'world')
    assert val == False


def test_delete_vault_data(monkeypatch):
    monkeypatch.setattr('processor.connector.vault.config_value', mock_config_value)
    monkeypatch.setattr('processor.connector.vault.get_vault_access_token', mock_get_vault_access_token)
    monkeypatch.setattr('processor.connector.vault.delete_keyvault_secret', mock_delete_keyvault_secret)
    from processor.connector.vault import delete_vault_data
    val = delete_vault_data('hello')
    assert val == True
    monkeypatch.setattr('processor.connector.vault.delete_keyvault_secret', mock_exception_delete_keyvault_secret)
    val = delete_vault_data('hello')
    assert val == False

def test_get_all_vault_secrets(monkeypatch):
    monkeypatch.setattr('processor.connector.vault.config_value', mock_config_value)
    monkeypatch.setattr('processor.connector.vault.get_vault_access_token', mock_get_vault_access_token)
    monkeypatch.setattr('processor.connector.vault.get_all_secrets', mock_get_all_secrets)
    from processor.connector.vault import get_all_vault_secrets
    val = get_all_vault_secrets()
    assert val != []
    monkeypatch.setattr('processor.connector.vault.get_all_secrets', mock_exception_get_all_secrets)
    val = get_all_vault_secrets()
    assert val == []