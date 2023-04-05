import faiss
import os
import pickle
from langchain.embeddings import OpenAIEmbeddings
from langchain.text_splitter import CharacterTextSplitter
from langchain.vectorstores import FAISS
from lib.schema import load_from_file


def index_name(db_name):
    return f'data/db/{db_name}.idx'


def exists(db_name):
    return os.path.exists(index_name(db_name)) and os.path.exists(pickle_name(db_name))


def pickle_name(db_name):
    return f'data/db/{db_name}.pkl'


def build(db_name):
    data = load_from_file(db_name)
    splitter = CharacterTextSplitter(chunk_size=1500, separator=';')
    splits = splitter.split_text(data)

    store = FAISS.from_texts(splits, OpenAIEmbeddings())
    faiss.write_index(store.index, index_name(db_name))
    store.index = None
    with open(pickle_name(db_name), 'wb') as f:
        pickle.dump(store, f)


def load(db_name):
    with open(pickle_name(db_name), 'rb') as f:
        store = pickle.load(f)
    store.index = faiss.read_index(index_name(db_name))
    return store
