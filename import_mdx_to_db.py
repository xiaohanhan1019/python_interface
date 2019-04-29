import sys

sys.path.append("..")
sys.path.append("./mdx_resolve")
from mdx_resolve.mdict_query import IndexBuilder
from flask import Flask
from flask_restful import reqparse, abort, Api, Resource

from sqlalchemy import ForeignKey
import sqlalchemy.orm
import sqlalchemy.ext.declarative
import requests

import json

import functools

engine = sqlalchemy.create_engine("mysql+pymysql://root:SSZZhh~~!!22@47.103.3.131:3306/word_chain", encoding="utf8",
                                  echo=False)
BaseModel = sqlalchemy.ext.declarative.declarative_base()

DBSession = sqlalchemy.orm.sessionmaker(bind=engine)
session = DBSession()

class Word(BaseModel):
    __tablename__ = 'word'

    id = sqlalchemy.Column("id", sqlalchemy.Integer, primary_key=True, autoincrement=True)
    name = sqlalchemy.Column("name", sqlalchemy.String(50), nullable=False)
    meaning = sqlalchemy.Column("meaning", sqlalchemy.String(255), nullable=False)


def main():
    builder = IndexBuilder('./mdx_resolve/mdx/Collins.mdx')
    words = builder.get_mdx_keys()
    url = "https://ireading.site/word/list/"
    cnt = 30900
    for word in words[30900:]:
        payload = {'word': word, 'json': True}
        r = requests.get(url, params=payload)
        r.encoding = 'utf-8'
        json_object = json.loads(r.text)
        try:
            meaning = json_object['wordBriefs'][0]['chnDefinitions'][0]['meaning']
            db_word = session.query(Word).filter(Word.name == word).one()
            db_word.meaning = meaning
            print(meaning)
        except:
            try:
                meaning = json_object['wordSuggestions'][0]['chnDefinitions'][0]['meaning']
                db_word = session.query(Word).filter(Word.name == word).one()
                db_word.meaning = meaning
                print("try"+meaning)
            except Exception as e:
                session.rollback()
                print(e)
        print(str(cnt)+":"+word)
        cnt = cnt+1
        session.commit()




main()