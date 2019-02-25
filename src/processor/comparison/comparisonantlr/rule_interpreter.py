import ast
import re
import pymongo
from processor.database.database import COLLECTION, get_documents
from processor.logging.log_handler import getlogger
from processor.comparison.comparisonantlr.compare_types import EQ, NEQ, GT, GTE, LT, LTE
from processor.comparison.comparisonantlr.compare_types import compare_none, compare_int,\
    compare_float, compare_boolean, compare_str, compare_list


comparefuncs = {
    type(None): compare_none,
    type(0): compare_int,
    type(0.1): compare_float,
    type(True): compare_boolean,
    type('abcd'): compare_str,
    type([]): compare_list
}

COMP = [EQ, NEQ, GT, LT, GTE, LTE]
STAR = '*'
PLUS = '+'
OPS = [STAR, PLUS]

logger = getlogger()


class RuleInterpreter:

    def __init__(self, children, **otherargs):
        self.children = children if children and isinstance(children, list) else []
        self.kwargs = otherargs
        self.lhs_operand, self.op, self.rhs_operand = self.rule_operands()
        self.snapshots = []
        logger.debug(self.kwargs)
        logger.debug(type(self.kwargs))

    def get_snapshots(self):
        return self.snapshots

    def rule_operands(self):
        lhs = self.children
        op = EQ
        rhs = ['True']
        for idx, child in enumerate(self.children):
            if child in COMP:
                lhs = self.children[:idx]
                rhs = self.children[idx+1:]
                op = child
                break
        return lhs, op, rhs


    def match_method(self, value):
        method = None
        method_args = value
        if '(' in value and ')' in value:
            method = value[:value.index('(')]
            method_args = value[value.index('(') + 1 : value.rfind(')')]
        return method, method_args


    def match_expression(self, value):
        actions = (
            (r'(\d+)(\.\d+)?', self.match_number),
            (r'true|false', self.match_boolean),
            (r'\'.*\'', self.match_string),
            (r'\[.*\]', self.match_array_string),
            (r'\{(\d+)\}(\[.*\].*)', self.match_array_attribute),
            (r'\{(\d+)\}(\..*)*', self.match_attribute_array),
            (r'\{.*\}', self.match_dictionary_string)
        )
        val = None
        for regex, action in actions:
            m = re.match(regex, value, re.I)
            if m:
                logger.debug("Regex match- groups:%s, regex:%s, value: %s, function: %s ",
                             m.groups(), regex, value, action)
                val = action(value, m)
                break
        return val


    def match_number(self, value, m):
        grps = m.groups()
        if grps[1]:
            return float(value)
        else:
            return int(grps[0])


    def match_boolean(self, value, _):
        return True if value.lower() == 'true' else False


    def match_string(self, value, _):
        return value.replace("'", '')

    def match_array_string(self, value, _):
        str_val = value.replace("'", '')
        array_vals_str = str_val[1:-1]
        array_vals_str = array_vals_str.replace(' ', '')
        return array_vals_str.split(',')

    def match_dictionary_string(self, value, _):
        val = ast.literal_eval(value)
        return val

    def match_array_attribute(self, value, m):
        grps = m.groups()
        logger.info('matched grps: %s, type(grp0): %s', grps, type(grps[0]))
        doc = self.get_snaphotid_doc(grps[0])
        value = None
        if doc and grps[1]:
            value = self.get_field_value(doc, grps[1])
        return value


    def match_attribute_array(self, value, m):
        grps = m.groups()
        logger.debug('matched grps: %s, type(grp0): %s', grps, type(grps[0]))
        doc = self.get_snaphotid_doc(grps[0])
        value = None
        if doc:
            if grps[1]:
                value = self.get_field_value(doc, grps[1])
            else:
                value = doc
        return value


    def get_snaphotid_doc(self, sid):
        dbname = self.kwargs['dbname']
        coll = self.kwargs['snapshots'][sid] if sid in self.kwargs['snapshots'] else COLLECTION
        docs = get_documents(coll, {'snapshotId': sid}, dbname,
                             sort=[('timestamp', pymongo.DESCENDING)], limit=1)
        # docs = [{
        # "_id": "5c24af787456217c485ad1e6",
        # "checksum": "7d814f2f82a32ea91ef37de9e11d0486",
        # "collection": "microsoftcompute",
        # "json":{
        #     "id": 124,
        #     "location": "eastus2",
        #     "name": "mno-nonprod-shared-cet-eastus2-tab-as03"
        # },
        # "queryuser": "ajeybk1@kbajeygmail.onmicrosoft.com",
        # "snapshotId": 1,
        # "timestamp": 1545908086831
        # }]
        logger.debug('Number of Snapshot Documents: %s', len(docs))
        doc = None
        if docs and len(docs):
            doc = docs[0]['json']
            self.snapshots.append({
                'id': docs[0]['snapshotId'],
                'path': docs[0]['path'],
                'structure': docs[0]['structure'],
                'reference': docs[0]['reference'],
                'source': docs[0]['source']
            })
            # print(doc)
        return doc

    def compare(self):
        lhs_value = self.get_value(self.lhs_operand)
        # print('LHS value: ', lhs_value)
        rhs_value = self.get_value(self.rhs_operand)
        # print('RHS value: ', rhs_value)
        logger.info('LHS: %s, OP: %s, RHS: %s', lhs_value, self.op, rhs_value)
        retval = False
        if type(lhs_value) == type(rhs_value):
            if type(lhs_value) in comparefuncs:
                return comparefuncs[type(lhs_value)](lhs_value, rhs_value, self.op)
        return retval


    def get_value(self, value):
        retval = None
        vals = []
        last_idx = 0
        ops = None
        for idx, child in enumerate(value):
            if child in OPS:
                vals.append((value[last_idx:idx], ops))
                last_idx = idx + 1
                ops = child
        if last_idx:
            vals.append((value[last_idx:], ops))
        if not vals:
            vals.append((value, None))
        for val in vals:
            expression_val = self.eval_expression(''.join(val[0]))
            if val[1]:
                retval = self.apply_op(val[1], retval, expression_val)
                # retval = expression_val
            else:
                retval = expression_val
        return retval

    def apply_op(self, op, val1, val2):
        retval = val2
        if op in OPS and val1 and val2 and type(val1) == type(val2):
            retval = val1 + val2
        return retval

    def is_method(self, value):
        return True if '(' in value and ')' in value else False


    def eval_expression(self, expr):
        if self.is_method(expr):
            method, method_args = self.match_method(expr)
            if method == 'exist':
                new_args = method_args.rsplit('.', 1)[0]
                val = self.eval_expression(new_args)
            else:
                val = self.eval_expression(method_args)
            return self.apply_method(method, val, method_args)
        else:
            return self.match_expression(expr);


    def apply_method(self, method, val, method_args):
        if method == 'exist':
            new_args = method_args.rsplit('.', 1)[-1]
            new_args = re.sub(r'\[(.*)\]', '', new_args)
            val = True if val and new_args in val else False
        elif method == 'count':
            val = len(val) if hasattr(val, '__len__') else 0
        return val

    @staticmethod
    def get_field_value(data, parameter):
        """Utility to get json value from a nested structure."""
        retval = None
        parameter = parameter[1:] if parameter.startswith('.') else parameter
        parameter = parameter[:-1] if parameter.endswith('.') else parameter
        parameter = parameter[:-2] if parameter.endswith('[]') else parameter
        if '[]' in parameter:
            return None
        if data and parameter:
            fields = parameter.split('.')
            retval = data
            for field in fields:
                if retval:
                    is_array = False
                    indexval = None
                    if '[' in field and ']':
                        is_array = True
                        start = field.index('[')
                        indexval = field[start+1:-1]
                        newfield = field[:start]
                        if newfield and newfield in retval and isinstance(retval, dict):
                            retval = retval[newfield]
                    if is_array:
                        if isinstance(retval, list):
                            if re.match(r'^\d+$', indexval, re.I):
                                indexval = int(indexval)
                                if indexval < len(retval):
                                    retval = retval[indexval]
                                else:
                                    retval = None
                            elif '=' in indexval:
                                index_fields = indexval.split('=')
                                name = index_fields[0].replace("'", '').strip()
                                value = index_fields[-1].replace("'", '').strip()
                                arrretval = None
                                for index_doc in retval:
                                    if name in index_doc and index_doc[name] == value:
                                        arrretval = index_doc
                                        break
                                retval = arrretval
                            else:
                                retval = None
                        else:
                            retval = None
                    elif field in retval and isinstance(retval, dict):
                        retval = retval[field]
                    else:
                        retval = None
        return retval


# if __name__ == "__main__":
#     # data = [{
#     #         "id": 124,
#     #         "location": "eastus2",
#     #         "name": "mno-nonprod-shared-cet-eastus2-tab-as03"
#     #     },
#     #         {
#     #             "id": 125,
#     #             "location": "eastus",
#     #             "name": "mno-nonprod-shared-cet-eastus2-tab-as04"
#     #         }
#     # ]
#     # parameter = '[0].location'
#     # value = RuleInterpreter.get_field_value(data, parameter)
#     # print(value)
#
#     otherdata = {'dbname': 'validator', 'snapshots': {}}
#     children = ["{1}[0].location", "=", "'eastus'"]
#     r_i = RuleInterpreter(children, **otherdata)
#     val = r_i.get_value(r_i.lhs_operand)
#     print(val)
#     otherdata = {'dbname': 'validator', 'snapshots': {}}
#     # children = ["{1}.location", "=", "'eastus'"]
#     children = ["{1}.location", "+", "{1}.location", "=", "'eastus'"]
#     r_i = RuleInterpreter(children, **otherdata)
#     val = r_i.get_value(r_i.lhs_operand)
#     print(val)otherdata = {'dbname': 'validator', 'snapshots': {}}
#     children = ["exist", "(", "{1}.location", ")"]
#     r_i = RuleInterpreter(children, **otherdata)
#     val = r_i.eval_expression(''.join(r_i.lhs_operand))
#     otherdata = {'dbname': 'validator', 'snapshots': {}}
#     children = ["exist", "(", "{1}.location", ")"]
#     r_i = RuleInterpreter(children, **otherdata)
#     data = {'a': 1, 'b': [{'c': 'd'}, {'c': 'f'}]}
#     val = RuleInterpreter.get_field_value(data, 'b[2]')
#     print(val)
