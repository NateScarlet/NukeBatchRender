# -*- coding=UTF-8 -*-
"""Files manage.  """

__version__ = '0.1.0'


class Files(list):
    """(Single instance)Files that need to be render.  """
    instance = None

    def __new__(cls):
        if not cls.instance:
            cls.instance = super(Files, cls).__new__(cls)
        return cls.instance

    def __init__(self):
        super(Files, self).__init__()
        self.update()

    def update(self):
        """Update self from renderable files in dir.  """

        del self[:]
        _files = sorted([get_unicode(i) for i in os.listdir(
            Config()['DIR']) if i.endswith(('.nk', '.nk.lock'))], key=os.path.getmtime, reverse=False)
        self.extend(_files)
        self.all_locked = self and all(bool(i.endswith('.lock')) for i in self)

    def unlock_all(self):
        """Unlock all .nk.lock files."""

        _files = [i for i in self if i.endswith('.nk.lock')]
        for f in _files:
            self.unlock(f)

    @staticmethod
    def unlock(f):
        """Rename a (raw_name).(ext) file back or delete it.  """

        _unlocked_name = os.path.splitext(f)[0]
        if os.path.isfile(_unlocked_name):
            os.remove(f)
            print(u'因为有更新的文件, 移除: {}'.format(f))
        else:
            os.rename(f, _unlocked_name)
        return _unlocked_name

    @staticmethod
    def lock(f):
        """Duplicate given file with .lock append on name then archive it.  """

        if f.endswith('.lock'):
            return f

        Files.archive(f)
        locked_file = f + '.lock'
        os.rename(f, locked_file)
        return locked_file

    @staticmethod
    def archive(f, dest=u'文件备份'):
        """Archive file in a folder with time struture.  """

        now = datetime.datetime.now()
        weekday = ('周日', '周一', '周二', '周三', '周四', '周五', '周六')
        dest = os.path.join(
            dest,
            get_unicode(now.strftime(u'%Y年%m月')),
            get_unicode(now.strftime(u'%d日%H时%M分_{}/'))
        ).format(weekday[int(now.strftime('%w'))])
        copy(f, dest)

    def remove_old_version(self):
        """Remove all old version nk files.  """

        all_version = {}
        while True:
            for i in self:
                if not os.path.exists(i):
                    continue
                shot, version = self.split_version(i)
                prev_version = all_version.get(shot, -2)
                if version > prev_version:
                    all_version[shot] = version
                    break
                elif version < prev_version:
                    self.archive(i)
                    os.remove(i)
            else:
                break

    @staticmethod
    def split_version(f):
        """Return nuke style _v# (shot, version number) pair.  """

        match = re.match(r'(.+)_v(\d+)', f)
        if not match:
            return (f, -1)
        shot, version = match.groups()
        if version < 0:
            raise ValueError('Negative version number not supported.')
        return (shot, version)
