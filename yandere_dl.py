# -*- coding: utf-8 -*-
from argparse import ArgumentParser
from functools import reduce
from os import listdir
from os.path import split
from re import findall, sub
from subprocess import getstatusoutput
from time import sleep
from urllib import parse

from bs4 import BeautifulSoup as bs
from requests import request

from commons import *


class Yanderer:
    SLEEP_TIME = 0.1

    def __init__(self, work_dir=BASE_DIR, history=None):
        self.work_dir = work_dir
        self.history = history if history else History(file_name='yandere.json')
        self.limit_pages = None
        with open(join(BASE_DIR, 'cookies', 'yandere_.json'), 'r') as f:
            self.cookies = load(f)

    def _get_page(self, page_url, params=None):
        resp = request('GET', page_url, params=params, cookies=self.cookies)
        return bs(resp.text, features='html.parser')

    def _get_last_page(self, page):
        pager = page.find('div', class_='pagination')
        if not pager: return 1
        last_page = int(pager.find_all('a')[-2].text)
        return self.limit_pages if self.limit_pages and self.limit_pages < last_page else last_page

    def _get_items(self, page):
        return []

    def _process_item(self, item):
        return {0: {}}

    def _collect_items(self, paged_url, params=None):
        print('Item[%10d] Grabbing items' % 0)
        page = self._get_page(paged_url % 1, params)
        last_page = self._get_last_page(page)
        print('Item[%10d] Found %d page(s)' % (0, last_page))
        result = {}
        for i in range(2, last_page + 2):
            items = self._get_items(page)
            for item in items: result.update(self._process_item(item))
            print('Item[%10d] Found %d items on page %d' % (0, len(items), i - 1))
            sleep(self.SLEEP_TIME)
            if i <= last_page: page = self._get_page(paged_url % i, params)
        print('Item[%10d] Total items found: %d' % (0, len(result)))
        return result


class Tagger(Yanderer):
    # TAGS_JSON = 'https://yande.re/tag.json?limit=0' #TODO
    TAGS_URL = 'https://yande.re/tag?limit=500&page=%d&type='
    TAGS = {
        'artist': {'id': '1', 'class': 'tag-type-artist', 'tags': set()},
        'character': {'id': '4', 'class': 'tag-type-character', 'tags': set()},
        'copyright': {'id': '3', 'class': 'tag-type-copyright', 'tags': set()},
        'circle': {'id': '5', 'class': 'tag-type-circle', 'tags': set()},
        'faults': {'id': '6', 'class': 'tag-type-faults', 'tags': set()},
        'general': {'id': '0', 'class': 'tag-type-general', 'tags': set()}
    }

    def __init__(self, work_dir=BASE_DIR, history=None):
        super().__init__(work_dir, history)
        self.tag_type = self.TAGS['artist']
        for tag in self.TAGS.keys():
            self.TAGS[tag]['tags'] = set(self.history.get_item('tags', tag, []))

    def _get_items(self, page):
        return page.find_all('td', class_=self.tag_type['class'])

    def _process_item(self, item):
        tag = item.find_all('a')[-1].text
        return {tag: tag}

    def _get_tags(self, limit_pages=None):
        print('Tags[%10d] Grabbing tags' % 0)
        self.limit_pages = limit_pages
        tags = self._collect_items(self.TAGS_URL + self.tag_type['id'])
        print('Tags[%10d] Total tags found: %d' % (0, len(tags)))
        return list(tags.keys())

    def update_tags(self, update_all=False):
        for tag, tag_type in self.TAGS.items():
            print('Tags[%10d] Processing tags: %s' % (0, int(tag_type['id'])))
            self.tag_type = tag_type
            tags = self._get_tags(5 if not update_all else None)
            if not update_all:
                tag_type['tags'] = set(tags).union(tag_type['tags'])
            else:
                tag_type['tags'] = set(tags)
            self.history.set_item('tags', tag, list(sorted(tag_type['tags'])))
            self.history.save()

    def filter_tags(self, tags):
        origin = set(tags.split(' '))
        filtered = reduce(lambda x, y: x + y, [list(sorted(filter(
            lambda c: tags.find('(%s)' % c) == -1, origin.intersection(tags_['tags'])
        ))) for tags_ in self.TAGS.values()])
        if len(filtered) == 0: filtered = tags.split(' ')
        return ' '.join(cut_tags(filtered))


class Pooler(Yanderer):
    POOL_URL = 'https://yande.re/pool/%s/%s'
    POOL_PAGE = 'https://yande.re/pool?limit=200&page=%d'

    def __init__(self, work_dir=BASE_DIR, history=None, tagger=None):
        super().__init__(work_dir, history)
        self.tagger = tagger if tagger else Tagger()
        self.pool_name = ''
        self.pool_id = 0

    def _get_items(self, page):
        return page.find('table', class_='highlightable').find('tbody').find_all('tr')

    def _process_item(self, item):
        link = item.find('a')
        return {link.get('href').split('/')[-1]: {
            'name': normalize(link.text.strip()),
            'downloaded': False,
            'posts': int(item.find_all('td')[2].text)
        }}

    def _get_image_tags_page(self, page=1):
        resp = request('GET', (self.POOL_URL + '?page=%d' % page) % ('show', self.pool_id), cookies=self.cookies)
        if resp.status_code != 200: return [], True
        page = bs(resp.text, features='html.parser')
        links = page.find_all('a', class_='thumb')
        result = []
        for link in links:
            img_id = link.get('href').split('/')[-1]
            title = link.find('img').get('title')
            tags = findall(r'Rating: .*? Tags: (.*?) User: .*?', title)
            result.append(img_id + ' ' + (normalize(self.tagger.filter_tags(tags[0])) if tags else 'tagme'))
        return result, page.find('a', class_='next_page') is None

    def _get_image_tags(self):
        result = []
        for i in range(1, 100):
            tags, do_break = self._get_image_tags_page(i)
            result += tags
            if do_break: break
        print('Pool[%10d] Received images tags' % self.pool_id)
        return result

    def _dl_archive(self):
        print('Pool[%10d] Downloading archive: %s' % (self.pool_id, self.pool_name))
        resp = request('GET', self.POOL_URL % ('zip', self.pool_id),
                       params={'png': 1}, cookies=self.cookies, stream=True)
        if resp.status_code == 200:
            print('Pool[%10d] Found PNG archive' % self.pool_id)
        else:
            resp = request('GET', self.POOL_URL % ('zip', self.pool_id),
                           params={'jpeg': 1}, cookies=self.cookies, stream=True)
            if resp.status_code == 200:
                print('Pool[%10d] Found JPG archive' % self.pool_id)
            else:
                print('Pool[%10d] archive not found' % self.pool_id)
                return False
        return dl_file(resp, self.work_dir, '%d.zip' % self.pool_id, self.pool_id)

    def _unzip_archive(self):
        file_name = '%d.zip' % self.pool_id
        file_path = join(self.work_dir, file_name)
        dir_path = join(self.work_dir, str(self.pool_id))
        code, error = getstatusoutput(
            '"%s" x -o"%s" "%s"' % ('C:\\Program Files\\7-Zip\\7z', dir_path, file_path))
        if code != 0:
            print('Pool[%10d] Failed to unzip archive "%s": %s' % (self.pool_id, file_name, error))
            return False
        print('Pool[%10d] Archive uzipped: "%s"' % (self.pool_id, dir_path))
        remove(file_path)
        print('Pool[%10d] Archive removed: "%s"' % (self.pool_id, file_path))
        return True

    def _fix_file_names(self):
        dir_path = join(self.work_dir, str(self.pool_id))
        files = listdir(dir_path)
        broken = list(map(lambda f: (f[0], (f[0][0], '%04d' % int(f[0][1]), f[0][2])), filter(
            lambda f: len(f) > 0 and len(f[0][1]) > 0, map(
                lambda f: findall(r'([-~^&\w]*?)(?: \((\d{1,3})\))?\.(\w{3,4})', f), files))))
        for file, file_ in broken:
            rename(join(dir_path, '%s (%s).%s' % file), join(dir_path, '%s (%s).%s' % file_))
        broken_ = set(map(lambda f: f[0][0], broken))
        broken_ = list(map(lambda f: (f, sub(r'([-~^&\w]*?)\.(\w{3,4})', r'\1 (0001).\2', f)),
                           filter(lambda f: f.split('.')[0] in broken_, files)))
        for file, file_ in broken_:
            rename(join(dir_path, file), join(dir_path, file_))
        if broken: print('Pool[%10d] Fixed %d broken file names' % (self.pool_id, len(broken) + len(broken_)))

    def _rename_images(self, tags):
        posts = []
        dir_path = join(self.work_dir, str(self.pool_id))
        files = listdir(dir_path)
        for i, file in enumerate(files):
            name, ext = findall(r'([-~^&\w]*?)(?: \(\d{4}\))?\.(\w{3,4})', file)[0]
            file_ = '%s %s.%s' % (name, tags[i], ext)
            rename(join(dir_path, file), join(dir_path, file_))
            posts.append(file_)
        posts = self._print_info(dir_path, posts)
        rename(dir_path, join(self.work_dir, self.pool_name))
        print('Pool[%10d] Folder and images renamed' % self.pool_id)
        return posts

    def _print_info(self, dir_path, names):
        posts = []
        file_path = join(dir_path, '.nomedia')
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write('Pool Name  : %s\n' % self.pool_name)
            f.write('Pool URL   : ' + self.POOL_URL % ('show', self.pool_id))
            f.write('\n\nPages:\n\n')
            for name in names:
                f.write(name + '\n')
                posts.append(int(name.split(' ')[1]))
        return posts

    def _process_pool(self, pool_id, pool_name):
        self.pool_id = int(pool_id)
        self.pool_name = pool_name
        if not self._dl_archive(): return []
        tags = self._get_image_tags()
        if not tags: return []
        if not self._unzip_archive(): return []
        self._fix_file_names()
        return self._rename_images(tags)

    def _merge_history(self, pools):
        pools_ = self.history.get_category('pools')
        for pool_id, pool in pools.items():
            pool_ = pools_.get(pool_id)
            if pool_ is None or pool['posts'] > pool_['posts']:
                pools_[pool_id] = pool
            else:
                pool_['name'] = pool['name']
        pools_ = {pool_id: pools_[str(pool_id)] for pool_id in sorted(map(int, pools_.keys()), reverse=True)}
        self.history.set_category('pools', pools_)

    def load_info(self, load_all=False):
        print('Pool[%10d] Grabbing pools' % 0)
        if not load_all: self.limit_pages = 5
        pools = self._collect_items(self.POOL_PAGE)
        print('Pool[%10d] Total pools found: %d' % (0, len(pools)))
        self._merge_history(pools)
        self.history.save()

    def download_pools(self):
        pools = self.history.get_category('pools')
        for pool_id, pool in pools.items():
            if not pool['downloaded'] and pool['posts'] > 0:
                pool['pool_posts'] = self._process_pool(pool_id, pool['name'])
                pool['downloaded'] = len(pool['pool_posts']) > 0
                self.history.save()

    def download_pool(self, pool_id):
        if not self.history.get_item('pools', pool_id): self.load_info()
        pool = self.history.get_item('pools', pool_id)
        pool['pool_posts'] = self._process_pool(pool_id, pool['name'])
        pool['downloaded'] = len(pool['pool_posts']) > 0
        self.history.save()


class Poster(Yanderer):
    POST_URL = 'https://yande.re/post?limit=200&page=%d'

    def __init__(self, work_dir=BASE_DIR, history=None, tagger=None):
        super().__init__(work_dir, history)
        self.tagger = tagger if tagger else Tagger()
        self.post_dir = work_dir
        self.pooled_posts = []
        for pool_id, pool in self.history.get_category('pools').items():
            self.pooled_posts += pool.get('pool_posts', [])
        self.pooled_posts = set(self.pooled_posts)

    def _get_items(self, page):
        return page.find_all('a', class_='directlink largeimg')

    def _process_item(self, item):
        link = item.get('href')
        post_link = parse.urlparse(link)
        path_parts = parse.unquote_plus(post_link.path).split('/')
        post_id, tags, ext = findall(r'^yande\.re (\d+) (.+?)\.(\w{3,4})$', path_parts[-1])[0]
        tags = normalize(self.tagger.filter_tags(tags))
        post = {
            'downloaded': False, 'raw': {'url': link, 'file': '%s %s.%s' % (post_id, tags, ext)}
        }
        if path_parts[1] != 'image':
            path_parts[1] = 'image'
            path_parts[-1] = path_parts[-1].replace(ext, 'png')
            post['png'] = {
                'url': link.replace(post_link.path, parse.unquote('/'.join(path_parts))),
                'file': '%s %s.%s' % (post_id, tags, 'png')
            }
        return {int(post_id): post}

    def _download_post(self, post_id, post):
        if post.get('png'):
            resp = request('GET', post['png']['url'], cookies=self.cookies)
            if resp.status_code == 200:
                print('Post[%10d] Found PNG post' % post_id)
                return dl_file(resp, self.post_dir, post['png']['file'], post_id)
        else:
            resp = request('GET', post['raw']['url'], cookies=self.cookies)
            if resp.status_code == 200:
                return dl_file(resp, self.post_dir, post['raw']['file'], post_id)

    def download_posts(self, tag):
        self.post_dir = make_tag_dir(self.work_dir, tag)

        posts_ = self.history.get_item('posts', tag, [])

        print('Post[%10d] Grabbing posts' % 0)
        posts = self._collect_items(self.POST_URL, {'tags': tag})
        print('Post[%10d] Total posts found: %d' % (0, len(posts)))

        for post_id, post in posts.items():
            if post_id in posts_ or post_id in self.pooled_posts: continue
            if self._download_post(post_id, post): posts_.append(post_id)
            sleep(self.SLEEP_TIME)

        self.history.set_item('posts', tag, list(sorted(posts_, reverse=True)))
        self.history.save()


def rename_posts(work_dir=WORK_DIR, file_list='yandere.rename.txt'):
    tagger = Tagger()
    with open(join(work_dir, file_list), 'r', encoding='utf-8') as f:
        files = [line[:-1] for line in f.readlines()[1:]]
    for file in files:
        path = split(file)
        found = findall(r'yande\.re (\d+) (.+?)\.(\w{3,4})', path[1])
        if not found: continue
        post_id, tags, ext = found[0]
        rename(join(path[0], file), join(path[0], '%s %s.%s' % (post_id, tagger.filter_tags(tags), ext)))


def rename_pools(work_dir):
    pools = listdir(work_dir)
    for pool in pools:
        pp = findall(r'(?:\(.+?\)\s)?\[(.+?)\](?:\s*)?(.+)', pool)
        if pp:  # noinspection PyStringFormat
            rename(join(work_dir, pool), join(work_dir, '%s — %s' % pp[0]))


def args_parse():
    parser = ArgumentParser(description='yande.re imageboard downloader')
    parser.add_argument('--update_tags', required=False, action='store_true')
    parser.add_argument('--update_pools', required=False, action='store_true')
    parser.add_argument('--update_all', required=False, action='store_true')
    parser.add_argument('--rename_pools', required=False, action='store_true')
    parser.add_argument('--rename_posts', required=False, action='store_true')
    parser.add_argument('--work_dir', type=str, default=WORK_DIR)
    parser.add_argument('--rename_file', type=str)
    parser.add_argument('--pool_id', type=str)
    parser.add_argument('--tags', type=str)
    parser.add_argument('--tag', type=str)
    args = parser.parse_args()
    print(args)
    return args


def main():
    args = args_parse()

    if args.update_tags:
        tagger = Tagger()
        tagger.update_tags(args.update_all)

    if args.update_pools:
        pooler = Pooler(args.work_dir)
        pooler.load_info(args.update_all)

    if args.pool_id:
        pooler = Pooler(args.work_dir)
        if args.pool_id == 'ALL':
            pooler.download_pools()
        else:
            pooler.download_pool(args.pool_id)

    if args.tags:
        poster = Poster(args.work_dir)
        for tag in args.tags.split(','):
            poster.download_posts(tag)

    if args.tag:
        poster = Poster(args.work_dir)
        poster.download_posts(args.tag)

    if args.rename_pools:
        rename_pools(args.work_dir)

    if args.rename_posts:
        rename_posts(args.work_dir, args.rename_file)


if __name__ == '__main__':
    main()
