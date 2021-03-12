# -*- coding: utf-8 -*-
from json import load, dump
from os import remove, rename, mkdir
from os.path import join, isfile, isdir, dirname, abspath
from random import getrandbits

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


class History:
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
        remove(self.file_path)
        rename(file_path_, self.file_path)

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
