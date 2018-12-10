import collections
import json
import hashlib
from pymongo import MongoClient, TEXT
from bson.objectid import ObjectId
from processor.helper.config.config_utils import get_config


MONGO = None
COLLECTION = 'resources'


def mongoconnection(dbport=27017):
    """ Global connection handle for mongo """
    global MONGO
    if not MONGO:
        MONGO = MongoClient(port=dbport)
    return MONGO


def mongodb(dbname=None):
   """ Get the dbhandle for the database, if none then default database, 'test' """
   dbconnection = mongoconnection()
   if dbname:
      db = dbconnection[dbname]
   else:
      db = dbconnection['test']
   return db


def init_db():
    dbname = get_config('MONGODB', 'dbname')
    create_indexes(COLLECTION, dbname, [('timestamp', TEXT)])


def get_collection(dbname, collection):
   """ Get the collection new or existing. """
   coll = None
   db = mongodb(dbname)
   if db and collection:
       coll = db[collection]
   return coll


def collection_names(dbname):
   """ Find all the collections in the databases. """
   db = mongodb(dbname)
   colls = db.collection_names(include_system_collections=False)
   return  colls


def sort_dict(data):
    vals = []
    for key, val in data.items():
        if isinstance(val, dict):
            sub_dict = sort_dict(val)
            vals.append((key, sub_dict))
        else:
            vals.append((key, val))
    sorted_vals = sorted(vals, key=lambda x: x[0])
    return collections.OrderedDict(sorted_vals)


def insert_one_document(doc, collection, dbname):
   """ Insert one document into the collection. """
   doc_id_str = None
   coll = get_collection(dbname, collection)
   if coll and doc:
       doc_id = coll.insert_one(sort_dict(doc))
       doc_id_str = str(doc_id.inserted_id)
   return doc_id_str


def insert_documents(docs, collection, dbname):
   """ Insert multiple documents into the collection. """
   doc_ids = []
   coll = get_collection(dbname, collection)
   if coll and docs:
       result = coll.insert_many(docs)
       doc_ids = [str(inserted_id) for inserted_id in result.inserted_ids]
   return doc_ids


def check_document(collection, docid, dbname=None):
   """ Find the document based on the docid """
   doc = None
   db = mongodb(dbname)
   collection = db[collection] if db and collection else None
   if collection:
       objId = docid if isinstance(docid, ObjectId) else ObjectId(docid)
       doc = collection.find_one({'_id': objId})
   return doc


def get_documents(collection, query=None, dbname=None, sort=None, limit=10):
   """ Find the documents based on the query """
   docs = None
   db = mongodb(dbname)
   collection = db[collection] if db and collection else None
   if collection:
       query = {} if query is None else query
       if sort:
           results = collection.find(query).sort(sort).limit(limit)
       else:
           results = collection.find(query).limit(limit)
       docs = [result for result in results]
   return docs


def count_documents(collection, query=None, dbname=None):
   """ Count the documents based on the query """
   count = None
   db = mongodb(dbname)
   collection = db[collection] if db and collection else None
   if collection:
       query = {} if query is None else query
       count = collection.count_documents(query)
   return count


def create_indexes(collection, dbname, fields):
   """ The fields to be indexed """
   result = None
   db = mongodb(dbname)
   collection = db[collection] if db and collection else None
   if collection:
       # index_fields = [(field, ASCENDING) for field in fields]
       result = collection.create_index(fields, unique=True)
   return result


def index_information(collection, dbname):
   """ index information of the collection """
   index_info = None
   db = mongodb(dbname)
   collection = db[collection] if db and collection else None
   if collection:
       index_info = sorted(list(collection.index_information()))
   return  index_info


def main():
  # dbname = 'business'
  # coll = 'reviews'
  # # mongodb(dbname)
  # obj_str = "5bfe2aef7456213682bebaa6"
  # doc = check_document(coll, obj_str, dbname)
  # print(doc)
  # obj_id = ObjectId(obj_str)
  # doc = check_document(coll, obj_id, dbname)
  # print(doc)
  # doc = check_document(coll, None, dbname)
  # print(doc)
  # colls = collection_names(dbname)
  # print(colls)
  # doc = {'name': 'Test name', 'gender': True}
  # newcoll = 'users'
  # user_id = insert_one_document(doc, newcoll, dbname)
  # print(user_id)
  # doc = check_document(newcoll, user_id, dbname)
  # print(doc)
  # docs = [
  #         {'name': 'Test1 name', 'gender': True},
  #         {'name': 'Test2 name', 'gender': False}
  #        ]
  # doc_ids = insert_documents(docs, newcoll, dbname)
  # print(doc_ids)
  # colls = collection_names(dbname)
  # print(colls)
  # docs = get_documents(newcoll, None, dbname)
  # print(docs)
  # count = count_documents(newcoll, None, dbname)
  # print(count)
  # count = count_documents(newcoll, query={'gender': False}, dbname=dbname)
  # print(count)
  # print(index_information(coll, dbname))
  # # print(create_indexes(newcoll, dbname, ['name']))
  # print(index_information(newcoll, dbname))

  a = {'a': 1, 'b': 2, 'f': 5, 'c': 3, 'd': 4}
  b = {'z': a, 'y': {'x': 1, 'a': a}, 'm': 2, 'n': 'abc'}
  c = { 'n': 'abc', 'y': {'x': 1, 'a': a}, 'z': a, 'm': 2}
  d = sort_dict(b)
  e = sort_dict(c)
  d_str = json.dumps(d)
  e_str = json.dumps(e)
  is_match = True if d_str == e_str else False
  print(b)
  print(c)
  print(hashlib.md5(json.dumps(b).encode('utf-8')).hexdigest())
  print(hashlib.md5(json.dumps(c).encode('utf-8')).hexdigest())
  print(d_str)
  print(e_str)
  print(is_match)

  


if __name__ == "__main__":
    main()

