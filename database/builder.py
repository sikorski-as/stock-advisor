import os

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from database import models

DB_PATH = os.environ.get('DB_PATH')
DB = f'sqlite:///{DB_PATH}crypto.db'
ENGINE = create_engine(DB)
Session = sessionmaker(bind=ENGINE)


def create_db():
    models.Base.metadata.create_all(ENGINE)


if __name__ == '__main__':
    create_db()
