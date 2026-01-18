from sqlalchemy.orm import declarative_base
from sqlalchemy import Column, INT


Base = declarative_base()


class User(Base):

    __tablename__ = 'users'

    id = Column(INT, primary_key=True, autoincrement=True)
    user_tg_id = Column(INT, nullable=True)
    flag = Column(INT, nullable=True)


