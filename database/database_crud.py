from sqlalchemy import create_engine
import sqlite3
from sqlalchemy.orm import sessionmaker
from database.scheme import Base, User
import os


"""
This module contains two classes for managing Telegram user information.
The Database class performs CRUD operations on an SQLite database file. It inherits from the DBCache class.
The DBCache class maintains an in-memory cache of data from the database.
At the end of the module, an instance is created. 
This single instance is used for all interactions with both the database and its cache.
"""


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATABASE_URL = f"sqlite:///{os.path.join(BASE_DIR, 'users_db.db')}"


class DBCash:
    cash = {}  # key: user_tg_id (int), value: flag (int)

    def _add_to_cash(self, user_tg_id, flag):
        self.cash[user_tg_id] = flag

    def _del_from_cash(self, user_tg_id):
        if self.cash.get(user_tg_id):
            del self.cash[user_tg_id]


class Database(DBCash):
    def __init__(self, db_url: str = DATABASE_URL):
        database_path = os.path.join(BASE_DIR, 'users_db.db')
        if not os.path.exists(database_path):
            conn = sqlite3.connect(database_path)
            conn.close()

        self.engine = create_engine(
            db_url,
            echo=False,
            connect_args={"check_same_thread": False}  # важно для SQLite + Telegram
        )
        self.session = sessionmaker(
            bind=self.engine,
            autocommit=False,
            autoflush=False
        )
        self.__create_table()
        self.cash = {item.user_tg_id: item.flag for item in self.__select_all()}

    def __create_table(self):
        Base.metadata.create_all(bind=self.engine)

    def __select_all(self):
        """Get all from a database table"""
        with self.session() as s:
            return s.query(User).all()

    def insert(self, user_tg_id, flag) -> None:
        """
        Add new USER to database table and DBCash.cash. The <flag> argument indicates whether the user is banned
        or has read/write access.
        """
        if self.cash.get(user_tg_id):
            return
        with self.session() as s:
            new_user = User(
                user_tg_id=user_tg_id,
                flag=flag
            )
            s.add(new_user)
            s.commit()
        self._add_to_cash(user_tg_id, flag)

    def delete(self, user_tg_id):
        """Remove user from database table and DBCash.cash"""
        if not self.cash.get(user_tg_id):
            return
        with self.session() as s:
            user = s.query(User).filter(User.user_tg_id == user_tg_id).first()
            if user:
                s.delete(user)
                s.commit()

        self._del_from_cash(user_tg_id)


users_database = Database()

