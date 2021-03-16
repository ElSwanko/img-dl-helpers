# -*- coding: utf-8 -*-
from json import load, dump
from os import remove, rename, mkdir
from os.path import join, exists, isfile, isdir, dirname, abspath
from random import getrandbits
from math import pow

BASE_DIR = dirname(abspath(__file__))
WORK_DIR = 'D:\\_downloads_'

MAX_TAGS_LEN = 130


def normalize(name):
    return name.replace('*', '＊').replace(':', '：').replace('?', '？'). \
        replace('/', '／').replace('|', '-').replace('\\', '_'). \
        replace('"', '\'').replace('<', '\'').replace('>', '\'')


def cut_tags(tags):
    if len(' '.join(tags)) <= MAX_TAGS_LEN: return tags
    return cut_tags(tags[:-1])


def make_tag_dir(work_dir, tag):
    tag_dir = join(work_dir, normalize(tag))
    if not isdir(tag_dir): mkdir(tag_dir)
    return tag_dir


def dl_file(resp, work_dir, file, file_id):
    with open(join(work_dir, normalize(file)), 'wb') as fd:
        for chunk in resp.iter_content(50 * 1024 * 1024): fd.write(chunk)
    print('File[%10d] Downloaded file: %s' % (file_id, file))
    return True


class JsonData:
    def __init__(self, work_dir=BASE_DIR, file_name='history.json'):
        self.work_dir = work_dir
        self.file_name = file_name
        self.file_path = join(work_dir, file_name)
        self.data = {}
        self.load()

    def load(self):
        if isfile(self.file_path):
            with open(self.file_path, 'r') as f: self.data = load(f)

    def save(self, indent=None):
        file_path_ = join(self.work_dir, 'tmp_%s.json' % getrandbits(16))
        with open(file_path_, 'w') as f: dump(self.data, f, indent=indent)
        if exists(self.file_path): remove(self.file_path)
        rename(file_path_, self.file_path)


class History(JsonData):
    def __init__(self, work_dir=BASE_DIR, file_name='history.json'):
        super().__init__(work_dir, file_name)

    def get_category(self, category):
        if category not in self.data.keys(): self.data[category] = {}
        return self.data[category]

    def set_category(self, category, data):
        self.data[category] = data

    def get_item(self, category, item, default=None):
        category_ = self.get_category(category)
        if item not in category_.keys(): category_[item] = default
        return category_[item]

    def set_item(self, category, item, data):
        self.get_category(category)[item] = data


class Cookie(JsonData):
    def __init__(self, work_dir=join(BASE_DIR, 'cookies'), file_name='cookie.json'):
        super().__init__(work_dir, file_name)

    def read_cookie(self, file_name):
        with open(file_name, 'r') as f: lines = f.readlines()
        self.data = {ll[0]:ll[1] for ll in [l.strip().split('\t')[:2] for l in lines]}
        self.save()

    def cookie(self):
        return dict(self.data)


class Sizer:
    _B = {'v': pow(2, 0), 's': 'B'}
    kB = {'v': pow(2, 10), 's': 'kB'}
    MB = {'v': pow(2, 20), 's': 'MB'}
    GB = {'v': pow(2, 30), 's': 'GB'}
    TB = {'v': pow(2, 40), 's': 'TB'}
    PB = {'v': pow(2, 50), 's': 'PB'}

    def get_bytes(self, size):
        if size:
            v, s = size.split(' ')
            if s == self.PB['s']: return int(self.PB['v'] * float(v))
            if s == self.TB['s']: return int(self.TB['v'] * float(v))
            if s == self.GB['s']: return int(self.GB['v'] * float(v))
            if s == self.MB['s']: return int(self.MB['v'] * float(v))
            if s == self.kB['s']: return int(self.kB['v'] * float(v))
            return int(v)
        return 0

    def format_size(self, size):
        if size < self.kB['v']: return '%.2f %s' % (size / self._B['v'], self._B['s'])
        if size < self.MB['v']: return '%.2f %s' % (size / self.kB['v'], self.kB['s'])
        if size < self.GB['v']: return '%.2f %s' % (size / self.MB['v'], self.MB['s'])
        if size < self.TB['v']: return '%.2f %s' % (size / self.GB['v'], self.GB['s'])
        if size < self.PB['v']: return '%.2f %s' % (size / self.TB['v'], self.TB['s'])
        return '%2f %s' % (size / self.PB['v'], self.PB['s'])
