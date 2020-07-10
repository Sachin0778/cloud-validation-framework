"""
Define an interface for parsing aws template and its parameter files.
"""
import json
import copy
import re
import os
import yaml
from cfn_flip import flip, to_yaml, to_json
from processor.helper.json.json_utils import json_from_file, save_json_to_file
from processor.helper.file.file_utils import exists_file
from processor.logging.log_handler import getlogger
from processor.helper.yaml.yaml_utils import yaml_from_file

logger = getlogger()
gparams = {}
mappings = {}

def handle_reference(value):
    """
    Returns the default value for specified parameter reference
    """
    if value["Ref"] in gparams and "Default" in gparams[value["Ref"]]:
        value = gparams[value["Ref"]]["Default"]
    return value

def handle_find_in_map(value):
    """
    Finding the appropriate value from the Mapping 
    """
    find_values = value["Fn::FindInMap"]

    for item in find_values:
        item = process_resource(item)

    if len(find_values) == 3 and all(isinstance(v, str) for v in find_values):
        map_name = find_values[0]
        top_level_key = find_values[1]
        second_level_key = find_values[2]

        if map_name in mappings and top_level_key in mappings[map_name] and \
            second_level_key in mappings[map_name][top_level_key]:
            value = mappings[map_name][top_level_key][second_level_key]        
    return value

def handle_join(value):
    """
    Performes the `join` operation on set of values with specified delimiter.
    """
    join_values = value["Fn::Join"]
    for i in range(0, len(join_values)):
        join_values[i] = process_resource(join_values[i])
    
    if len(join_values) == 2 and all(isinstance(v, str) for v in join_values[1]):
        value = join_values[0].join(join_values[1])
    if not isinstance(value, str):
        value = process_resource(value)
    
    return value

intrinsic_functions = {
    "FindInMap" : handle_find_in_map,
    "Join" : handle_join
}

def main(template, tosave=False, **kwargs):
    global gparams
    global mappings
    stars = '*' * 25
    gen_template_json = None

    template_json = None
    if template.endswith(".yaml") and exists_file(template):
            with open(template) as yaml_file:
                try:
                    template_json = json.loads(to_json(yaml_file.read()))
                except:
                    file_name = template.split("/")[-1]
                    logger.error("Failed to load yaml file, please check yaml file contains correct content: %s", file_name)
                    return gen_template_json
    elif template.endswith(".json"):
        template_json = json_from_file(template)

    if not template_json:
        logger.error("Invalid path! No file found at : %s", template)
        return gen_template_json

    if "AWSTemplateFormatVersion" not in template_json:
        logger.error("Invalid file content : file does not contains 'AWSTemplateFormatVersion' field.")
        return gen_template_json

    if template_json:
        gen_template_json = copy.deepcopy(template_json)
        if 'Parameters' in template_json:
            gparams = template_json['Parameters']
        if 'Mappings' in template_json:
            mappings = template_json['Mappings']
        if 'Resources' in template_json:
            new_resources = []
            for key, resource in template_json['Resources'].items():
               new_resource = process_resource(resource)
               new_resources.append(new_resource)
            gen_template_json['Resources'] = new_resources
        if tosave:
            save_json_to_file(gen_template_json, template.replace('.json', '_gen.json'))
    return gen_template_json

def process_function(resource):
    """
    Performs the Intrinsic function on given resource
    """
    value = resource
    if isinstance(resource ,dict):
        if "Ref" in resource:
            value = handle_reference(value)
        else: 
            keys = value.keys()
            function = None
            for k in keys:
                if k.startswith("Fn::"):
                    function = k
            if function:
                function = function.split("Fn::")[1]
                if function in intrinsic_functions:
                    value = intrinsic_functions[function](value)
            else:
                value = process_resource(value)
    return value

def process_resource(resource):
    " Process resource object to fill the reference data in it. "
    new_resource = resource
    if isinstance(resource ,dict):
        new_resource = {}
        for key, value in resource.items():
            if isinstance(value, dict):
                new_resource[key] = process_function(value)
            else:
                result = process_resource(value)
                new_resource[key] = result
    elif isinstance(resource ,list):
        new_resource = []
        for value in resource:
            value = process_function(value)
            if isinstance(value, str):
                new_resource.append(value)
            else:
                new_resource.append(process_resource(value))
    return new_resource
