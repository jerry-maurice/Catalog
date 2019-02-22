import os
import sys
import random
import string
from sqlalchemy import Column, ForeignKey, Integer, String
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, sessionmaker
from sqlalchemy import create_engine
from itsdangerous import (TimedJSONWebSignatureSerializer as Serializer,
                          BadSignature, SignatureExpired)

Base = declarative_base()


class User(Base):
    # inside User class
    __tablename__ = 'user'
    name = Column(String(250), nullable=False)
    email = Column(String(250), nullable=False)
    picture = Column(String(250))
    id = Column(Integer, primary_key=True)


class Category(Base):
    # inside Category class
    __tablename__ = 'category'
    name = Column(String(80), nullable=False)
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('user.id'))
    user = relationship(User)

    @property
    def serialize(self):
        # Return object data in easily serializeable format
        return{
            'name': self.name,
            'id': self.id,
            }


class Items(Base):
    # inside items class
    __tablename__ = 'items'
    name = Column(String(80), nullable=False)
    description = Column(String(250))
    id = Column(Integer, primary_key=True)
    category_id = Column(Integer, ForeignKey('category.id'))
    category = relationship(Category)
    user_id = Column(Integer, ForeignKey('user.id'))
    user = relationship(User)

    @property
    def serialize(self):
        # Return object data in easily serializeable format
        return{
            'name': self.name,
            'description': self.description,
            'id': self.id,
            }


engine = create_engine('sqlite:///catalog.db')
Base.metadata.create_all(engine)
