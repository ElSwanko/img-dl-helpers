# -*- coding: utf-8 -*-
from argparse import ArgumentParser
from json import loads
from re import sub
from time import sleep

from bs4 import BeautifulSoup as bs
from requests import request

from commons import *


class Pixiv:
    POST_URL = 'https://www.pixiv.net/en/artworks/%s'
    HEADERS = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 6.1) '
                      'AppleWebKit/537.36 (KHTML, like Gecko) '
                      'Chrome/79.0.3945.117 Safari/537.36',
        'Referer': None
    }
    EXCLUDE_TAGS = {'bookmarks', 'congratulation', 'congratulations', 'ugoira', 'manga'}

    UGOIRA_DL_URL = 'http://ugoira.dataprocessingclub.org/convert'
    UGOIRA_PARAMS = {'url': POST_URL, 'format': 'gif'}

    def __init__(self, work_dir=WORK_DIR, history=None):
        self.work_dir = work_dir
        self.history = history if history else History(file_name='pixiv.json')
        with open(join(BASE_DIR, 'cookies', 'pixiv_.json'), 'r') as fd:
            self.cookies = load(fd)

    def _get_page(self, post_id):
        self.HEADERS['Referer'] = self.POST_URL % post_id
        resp = request('GET', self.HEADERS['Referer'], cookies=self.cookies, headers=self.HEADERS, proxies=PROXIES)
        if resp.status_code == 200:
            return bs(resp.text, features='html.parser')
        else:
            print('Post %s not found' % post_id)

    @staticmethod
    def _get_meta(page, post_id):
        meta = page.find_all('meta')
        for m in meta:
            if m.attrs['content'].find('{') == 0:
                m = loads(m.attrs['content'])
                if m.get('illust'):
                    return m
        print('Meta not found for post %s' % post_id)

    @staticmethod
    def _save_meta(meta, post_id):
        with open(join(BASE_DIR, '%d.json' % post_id), 'w', encoding='utf-8') as fd:
            dump(meta, fd, ensure_ascii=False, indent=2)

    @staticmethod
    def _gen_urls(base_url, page_count):
        idx = base_url.rfind('.')
        path, ext = base_url[:idx], base_url[idx + 1:]
        path = path[:-1] + '%d'
        return ['%s.%s' % (path % i, ext) for i in range(0, page_count)], ext

    def _get_tag(self, tag):
        value = (tag['translation']['en'] if tag.get('translation') else tag.get('romaji', tag['tag']))
        value = sub(r'[^a-zA-Z0-9\s\-~_.,()\[\]]*', '', value.lower()).strip()
        return '' if self.EXCLUDE_TAGS.intersection(set(value.split(' '))) else value.replace(' ', '_')

    def _get_tags(self, post):
        return list(filter(lambda t: t, [self._get_tag(tag) for tag in post['tags']['tags']]))

    def _download_post(self, posts_dir, post_id, post=None):
        page = self._get_page(post_id)
        if page is None: return True
        if not post: post = self._get_meta(page, post_id).get('illust', {}).get(post_id)
        if not post: return True
        links, ext = self._gen_urls(post['urls']['original'], post['userIllusts'][post_id]['pageCount'])
        tags = self._get_tags(post)
        self.HEADERS['Referer'] = self.POST_URL % post_id
        result = True
        for i, link in enumerate(links):
            if link.find('ugoira') > 0:
                print('Post[%10s] Found GIF art: %s' % (post_id, link))
                resp = request('GET', self.UGOIRA_DL_URL,
                               params={'url': self.HEADERS['Referer'], 'format': 'gif'})
                if resp.status_code != 200:
                    print('Post[%10s] Failed to convert post to GIF: %s' % (post_id, resp.text))
                    return False
                else:
                    link, ext = resp.json()['url'], 'gif'
            resp = request('GET', link, cookies=self.cookies, headers=self.HEADERS, proxies=PROXIES)
            if resp.status_code == 200:
                result &= dl_file(resp, posts_dir, '%s p%03d %s.%s' %
                                  (post_id, i + 1, ' '.join(cut_tags(tags)), ext), int(post_id))
        return result

    def download_posts(self, post_id, load_all=False):
        page = self._get_page(post_id)
        if page is None: return
        post = self._get_meta(page, post_id)['illust'][post_id]

        posts_ = self.history.get_item('posts', post['userId'], [])
        posts_dir = make_tag_dir(self.work_dir, post['userName'] + ' ' + post['userAccount'])

        if load_all:
            for post_id_ in post['userIllusts'].keys():
                if post_id_ in posts_: continue
                if self._download_post(posts_dir, post_id_): posts_.append(post_id_)
                self.history.save()
                sleep(0.3)
        else:
            if int(post_id) not in posts_:
                if self._download_post(posts_dir, post_id, post): posts_.append(post_id)
            self.history.save()


def args_parse():
    parser = ArgumentParser(description='pixiv imageboard downloader')
    parser.add_argument('--work_dir', type=str, default=WORK_DIR)
    parser.add_argument('--dl_all', required=False, action='store_true')
    parser.add_argument('post_id', type=str)
    args = parser.parse_args()
    print(args)
    return args


def main():
    args = args_parse()
    pixiv = Pixiv(args.work_dir)
    for post_id in args.post_id.split(','):
        pixiv.download_posts(post_id, args.dl_all)


if __name__ == '__main__':
    main()
