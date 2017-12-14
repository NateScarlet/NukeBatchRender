# -*- coding=UTF-8 -*-
"""History task info database.  """

import sqlite3
from datetime import datetime, timedelta
from logging import getLogger
from multiprocessing import Lock
from os.path import expanduser

LOGGER = getLogger('database')


class Database(object):
    """Database for rendering.  """

    def __init__(self, path):

        self.path = path
        self.lock = Lock()

        # Init tables.
        tables = {
            'frames': 'filename, frame, cost, timestamp',
            'tasks': 'filename, frames, cost, timestamp',
        }
        with self.connection() as conn:
            c = conn.cursor()
            for table, fileds in tables.items():
                try:
                    c.execute("SELECT {} FROM {}".format(fileds, table))
                    # Drop old records.
                    c.execute(
                        "DELETE FROM ? where timestamp < ? ",
                        (table, datetime.now() - timedelta(days=30),))
                    conn.commit()
                except sqlite3.OperationalError:
                    try:
                        LOGGER.warning(
                            "Can not reconize table, reset: %s", table)
                        c.execute("DROP TABLE {}".format(table))
                    except sqlite3.OperationalError:
                        pass
                    c.execute(
                        "CREATE TABLE {} ({})".format(table, fileds))
                    conn.commit()

    @property
    def averge_task_cost(self):
        """Get averge task time cost for @filename.  """

        with self.lock:
            with self.connection() as conn:
                c = conn.cursor()
                c.execute("SELECT avg(cost) "
                          "FROM tasks")
                ret = c.fetchone()[0]
            return ret[0] if ret is not None else 60 * 20

    def connection(self):
        """Return connection object for this.  """

        return sqlite3.connect(self.path)

    def get_frame_time(self, filename, frame):
        """Get frame time cost for @filename at @frame.  """

        with self.lock:
            with self.connection() as conn:
                c = conn.cursor()
                c.execute("SELECT cost "
                          "FROM frames "
                          "WHERE filename=? AND frame=? "
                          "ORDER BY timestamp DESC",
                          (filename, frame))
                ret = c.fetchone()
            return ret[0] if ret else None

    def get_averge_time(self, filename):
        """Get averge frame time cost for @filename.  """

        with self.lock:
            with self.connection() as conn:
                c = conn.cursor()
                c.execute("SELECT avg(cost) "
                          "FROM frames "
                          "WHERE filename=?",
                          (filename,))
                ret = c.fetchone()[0]
            return ret

    def get_task_frames(self, filename):
        """Get total number of frames in @filename.  """

        with self.lock:
            with self.connection() as conn:
                c = conn.cursor()
                c.execute("SELECT frames "
                          "FROM tasks "
                          "WHERE filename=? "
                          "ORDER BY timestamp DESC",
                          (filename, ))
                ret = c.fetchone()
            return ret[0] if ret else None

    def get_task_cost(self, filename):
        """Set info for a task.  """

        with self.lock:
            with self.connection() as conn:
                c = conn.cursor()
                c.execute("SELECT cost "
                          "FROM tasks "
                          "WHERE filename=? "
                          "ORDER BY timestamp DESC",
                          (filename, ))
                ret = c.fetchone()
            return ret[0] if ret else None

    def set_frame_time(self, filename, frame, cost):
        """Set frame time cost for @filename at @frame.  """

        with self.lock:
            with self.connection() as conn:
                c = conn.cursor()
                c.execute(
                    "INSERT INTO frames VALUES (?,?,?,?)", (filename, frame, cost, datetime.now()))
                conn.commit()
                # LOGGER.debug('Set: %s %s %s', filename, frame, cost)

    def set_task(self, filename, frames, cost=None):
        """Set info for a task.  """

        with self.lock:
            with self.connection() as conn:
                c = conn.cursor()
                c.execute("SELECT * "
                          "FROM tasks "
                          "WHERE filename=?", (filename,))
                if c.fetchone():
                    c.execute(
                        "UPDATE tasks "
                        "SET frames=?, cost=?, timestamp=? "
                        "WHERE filename=?", (frames, cost, datetime.now(), filename))
                else:
                    c.execute(
                        "INSERT INTO tasks VALUES (?,?,?,?)",
                        (filename, frames, cost, datetime.now()))
                conn.commit()
                LOGGER.debug('Set: %s %s %s', filename, frames, cost)


DATABASE = Database(expanduser('~/.nuke/batchrender.db'))
