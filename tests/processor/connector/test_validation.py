""" Tests for validation"""
import os


frameworkdir = '/tmp'


def mock_framework_dir():
    return frameworkdir


def mock_config_value(key, default=None):
    return 'pytestdb'


def mock_get_documents(collection, query=None, dbname=None, sort=None, limit=10):
    return [{
        "_id": "5c24af787456217c485ad1e6",
        "checksum": "7d814f2f82a32ea91ef37de9e11d0486",
        "collection": "microsoftcompute",
        "json":{
            "id": 124,
            "location": "eastus2",
            "name": "mno-nonprod-shared-cet-eastus2-tab-as03"
        },
        "queryuser": "ajeybk1@kbajeygmail.onmicrosoft.com",
        "snapshotId": 1,
        "timestamp": 1545908086831
    }]


def mock_create_indexes(sid, dbname, flds):
    return None


def test_get_snapshot_id_to_collection_dict1(monkeypatch):
    monkeypatch.setattr('processor.connector.validation.create_indexes', mock_create_indexes)
    from processor.connector.validation import get_snapshot_id_to_collection_dict
    val = get_snapshot_id_to_collection_dict('snapshot.json', 'container', 'abcd')
    assert True == isinstance(val, dict)
    val = get_snapshot_id_to_collection_dict('snapshot.json', 'container1', 'abcd')
    assert True == isinstance(val, dict)


def test_run_validation_test(monkeypatch):
    monkeypatch.setattr('processor.comparison.interpreter.get_documents',
                        mock_get_documents)
    from processor.connector.validation import run_validation_test
    result = run_validation_test('0.1', 'validator', {}, {
        "testId": "4",
        "snapshotId": "1",
        "attribute": "id",
        "comparison": "gt 10"
    })
    assert result is not None
    assert type(result) is dict
    assert result['result'] == 'passed'


def test_run_file_validation_tests(create_temp_dir, create_temp_json, monkeypatch):
    monkeypatch.setattr('processor.connector.validation.config_value', mock_config_value)
    from processor.connector.validation import run_file_validation_tests
    newpath = create_temp_dir()
    json_data = {
        "$schema": "",
        "contentVersion": "1.0.0.0",
        "fileType": "test",
        "snapshot": "snapshot.json",
        "testSet": []
    }
    testfile = create_temp_json(newpath, data=json_data)
    assert False == run_file_validation_tests(testfile, 'abcd')
    assert False == run_file_validation_tests('%s/%s' % (newpath, testfile), 'abcd')
    testset = {
        "testName": "test1",
        "version": "0.1",
        "cases": []
    }
    json_data['testSet'].clear()
    json_data['testSet'].append(testset)
    testfile = create_temp_json(newpath, data=json_data)
    assert True == run_file_validation_tests('%s/%s' % (newpath, testfile), 'abcd')
    testset = {
        "testName": "test1",
        "version":"0.1",
        "cases": [
            {
                "testId": "1",
                "snapshotId": "1",
                "attribute": "location",
                "comparison":"exist"
            }
        ]
    }
    json_data['testSet'].clear()
    json_data['testSet'].append(testset)
    testfile = create_temp_json(newpath, data=json_data)
    assert True == run_file_validation_tests('%s/%s' % (newpath, testfile), 'abcd')


def test_get_snapshot_id_to_collection_dict(create_temp_dir, create_temp_json, monkeypatch):
    global frameworkdir
    monkeypatch.setattr('processor.connector.validation.config_value', mock_config_value)
    monkeypatch.setattr('processor.connector.validation.get_test_json_dir', mock_framework_dir)
    from processor.connector.validation import get_snapshot_id_to_collection_dict
    frameworkdir = create_temp_dir()
    json_data = {
        "$schema": "",
        "contentVersion": "1.0.0.0",
        "fileType":"snapshot",
        "snapshots": [
            {
                "source": "azureStructure.json",
                "type": "azure",
                "testUser": "ajeybk1@kbajeygmail.onmicrosoft.com",
                "subscriptionId": "37f11aaf-0b72-44ef-a173-308e990279da",
                "nodes": []
            }
        ]
    }
    container = 'abcd'
    container_dir = '%s/%s' % (frameworkdir, container)
    os.makedirs(container_dir)
    testfile = create_temp_json(container_dir, data=json_data)
    assert {} == get_snapshot_id_to_collection_dict(testfile, container, 'abcd')


def test_run_container_validation_tests(create_temp_dir, create_temp_json, monkeypatch):
    global frameworkdir
    monkeypatch.setattr('processor.connector.validation.config_value', mock_config_value)
    monkeypatch.setattr('processor.connector.validation.framework_dir', mock_framework_dir)
    from processor.connector.validation import run_container_validation_tests
    frameworkdir = create_temp_dir()
    json_data = {
        "$schema": "",
        "contentVersion": "1.0.0.0",
        "fileType": "test",
        "snapshot": "snapshot.json",
        "testSet": []
    }
    container = 'abcd'
    container_dir = '%s/%s/%s' % (frameworkdir, mock_config_value(''), container)
    os.makedirs(container_dir)
    testfile = create_temp_json(container_dir, data=json_data)
    run_container_validation_tests(container)