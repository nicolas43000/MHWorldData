from collections.abc import Mapping
from mhdata import typecheck

from .bidict import bidict
from .orderedset import OrderedSet
from .sharpness import Sharpness


def ensure(field, error_message):
    "Tests that the field is truthy, throwing an Exception if its not"
    if not field:
        raise Exception("ERROR: " + error_message)


def ensure_warn(field, error_message):
    "Tests that the field is truthy, printing a warning message if its not"
    if not field:
        print("WARNING: " + error_message)


def get_duplicates(iterable):
    "Checks the iterable for duplicate entries, and returns them"
    seen = set()
    duplicates = []
    for item in iterable:
        if item in seen:
            duplicates.append(item)
        else:
            seen.add(item)

    return duplicates


def joindicts(dest, *dictlist, prefix=''):
    """Merges one or more dictionaries into dest recursively.
    Dictionaries are merged, lists are merged. Scalars and strings are ignored.
    Returns the generated result.

    To merge with overwrite, use the native dict update method.
    """
    result = dest
    for inputdict in dictlist:
        for key, value in inputdict.items():
            # If this is a new value, take as is
            if key not in result:
                result[key] = value
                continue
            
            # Handle collision
            existing_value = dest[key]
            if typecheck.is_dict(existing_value) and typecheck.is_dict(value):
                result[key] = joindicts(existing_value, value, prefix=prefix+key+'.')
            elif typecheck.is_list(existing_value) and typecheck.is_list(value):
                result[key] = existing_value + value
            elif existing_value != value:
                raise Exception("Failed to merge dictionaries: " +
                    f"unresolved collision and mismatch on key '{prefix + key}', {value} into {existing_value}")

    return result


def extract_fields(obj : dict, *fieldnames) -> dict:
    "Extract a subset of fields from an object. Only those fields are pulled"
    result = {}
    for fieldname in fieldnames:
        if fieldname not in obj:
            continue
        result[fieldname] = obj[fieldname]
    return result

def check_not_grouped(obj, groups):
    "Checks if any fields have already been grouped, and returns the ones that aren't"
    results = []
    for group in groups:
        if group in obj and isinstance(obj[group], Mapping):
            continue
        results.append(group)
    return results


def group_fields(obj, groups=[]):
    "Returns a new dictionary where the items that start with groupname_ are consolidated"
    if not typecheck.is_list(groups):
        raise TypeError("groups needs to be a list or tuple")
    
    groups = check_not_grouped(obj, groups)
    result = {}
    for key, value in obj.items():
        group_results = list(filter(lambda g: key.startswith(g+'_'), groups))
        if not group_results:
            result[key] = value
            continue

        group_name = group_results[0]
        subkey = key[len(group_name)+1:]
        
        group = result.setdefault(group_name, {})
        group[subkey] = value

    return result


def ungroup_fields(obj, groups=[]):
    "Returns a new dictionary where keys that are in group are flattened"
    result = {}
    for key, value in obj.items():
        if key not in groups:
            result[key] = value
            continue

        # This is a "group" item, so iterate over it
        for subkey, subvalue in value.items():
            result[f"{key}_{subkey}"] = subvalue

    return result

def flatten_dict(d, prefix='', result=None):
    "Flattens a dictionary using path separators"
    # recursive algorithm where each pass gives the result object to the next patch
    # The key algorithm boils down to:
    # - If its not a scalar (dict or list), build the prefix
    # - If its a scalar (string or number), assign the value

    result = {} if result is None else result

    if typecheck.is_dict(d):
        # dictionaries add a / behind them for non-root ones
        if prefix:
            prefix = prefix + '/'

        for key, value in d.items():
            if typecheck.is_scalar(value):
                result[f"{prefix}{key}"] = value
            else:
                flatten_dict(value, prefix=prefix + key, result=result)
    elif typecheck.is_list(d):
        for idx, value in enumerate(d):
            if typecheck.is_scalar(value):
                result[f'{prefix}[{idx}]'] = value
            else:
                flatten_dict(value, prefix=f'{prefix}[{idx}]', result=result)
    else:
        raise Exception('Unsupported type ' + str(type(d)))

    return result