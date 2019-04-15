import sys

sys.path.append("..")
sys.path.append("./mdx_resolve")
from mdx_resolve.mdict_query import IndexBuilder
from flask import Flask
from flask_restful import reqparse, abort, Api, Resource

from sqlalchemy import ForeignKey
import sqlalchemy.orm
import sqlalchemy.ext.declarative

import functools

engine = sqlalchemy.create_engine("mysql+pymysql://root:SSZZhh~~!!22@47.103.3.131:3306/word_chain", encoding="utf8",
                                  echo=False)
BaseModel = sqlalchemy.ext.declarative.declarative_base()

DBSession = sqlalchemy.orm.sessionmaker(bind=engine)
session = DBSession()

class Word(BaseModel):
    __tablename__ = 'word'

    id = sqlalchemy.Column("id", sqlalchemy.Integer, primary_key=True, autoincrement=True)
    word_name = sqlalchemy.Column("word_name", sqlalchemy.String(50), nullable=False)


def main():
    builder = IndexBuilder('./mdx_resolve/mdx/Collins.mdx')
    words = builder.get_mdx_keys()
    for word in words:
        print(word)
        db_word = Word(word_name=word)
        session.add(db_word)
    session.commit()



main()