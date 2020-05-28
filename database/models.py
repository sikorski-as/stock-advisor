import datetime

from sqlalchemy import Integer, Column, String, Float, UniqueConstraint
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()


class Record(Base):
    __tablename__ = 'records'

    id = Column(Integer, primary_key=True)
    currency = Column(String)
    time = Column(Integer)
    high = Column(Float)
    low = Column(Float)
    open = Column(Float)
    close = Column(Float)

    __table_args__ = (UniqueConstraint('currency', 'time', name='_currency_time_uc_'),)

    def __repr__(self):
        return f"{self.id} {self.currency} {datetime.datetime.fromtimestamp(self.time)} {self.high}"


class Model(Base):
    __tablename__ = 'models'

    id = Column(Integer, primary_key=True)
    currency = Column(String)
    long_mean = Column(Integer)
    short_mean = Column(Integer)

    __table_args__ = (UniqueConstraint('currency', name='_currency_uc_'),)

    def __repr__(self):
        return f"{self.id} {self.currency} {self.long_mean} {self.short_mean}"
