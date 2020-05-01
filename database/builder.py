from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, scoped_session

import config
from database import models

DB_PATH = config.DB_PATH
DB = f'sqlite:///{DB_PATH}crypto.db'
ENGINE = create_engine(DB)
session_factory = sessionmaker(bind=ENGINE)
Session = scoped_session(session_factory)


def create_db():
    models.Base.metadata.create_all(ENGINE)


if __name__ == '__main__':
    create_db()
