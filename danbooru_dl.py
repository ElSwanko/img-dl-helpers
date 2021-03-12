# -*- coding: utf-8 -*-
from argparse import ArgumentParser
from re import findall
from urllib import parse

from bs4 import BeautifulSoup as bs
from requests import request

from commons import *

MAIN_URL = 'https://danbooru.donmai.us'


def _request_page(page_url):
    resp = request('GET', page_url)
    if resp.status_code == 200:
        return bs(resp.text, features='html.parser')
    print('Page[%10d] Not found: %s' % (0, page_url))


def _get_links(page):
    articles = page.find_all('article', class_='post-preview')
    articles = map(lambda a: int(a.get('data-id')),
                   filter(lambda a: 'duplicate' not in a.get('data-tags'), articles))
    next_page = page.find('a', class_='paginator-next')
    return list(articles), MAIN_URL + next_page.get('href') if next_page else None


def _get_post_data(post_id, page):
    tags = []

    div = page.find('div', class_='tag-list categorized-tag-list')
    ul_a = div.find('ul', class_='artist-tag-list')
    if ul_a: tags += [li.get('data-tag-name') for li in ul_a.find_all('li')]
    ul_c = div.find('ul', class_='character-tag-list')
    if ul_c: tags += [li.get('data-tag-name') for li in ul_c.find_all('li')]
    ul_w = div.find('ul', class_='copyright-tag-list')
    if ul_w: tags += [li.get('data-tag-name') for li in ul_w.find_all('li')]
    # ul_g = div.find('ul', class_='general-tag-list')
    # if ul_g: tags += [li.get('data-tag-name') for li in ul_g.find_all('li')]
    tags = cut_tags(tags)

    url = page.find('li', attrs={'id': 'post-info-size'}).find('a').get('href')
    ext = findall(r'(?:\w*)\.(\w{3,4})', url.split('/')[-1])[0]
    file_name = '%d %s.%s' % (post_id, ' '.join(tags).replace('／', '_').replace('：', ''), ext)

    return {'url': url, 'file': file_name}


class Danbooru:
    PAGE_URL = 'https://danbooru.donmai.us/posts?limit=200&tags=%s'
    POST_URL = 'https://danbooru.donmai.us/posts/%d'

    def __init__(self, work_dir=WORK_DIR, history=None):
        self.work_dir = work_dir
        self.history = history if history else History(file_name='danbooru.json')
        self.limit_pages = None

    def _collect_posts(self, tag):
        result = []
        next_url = self.PAGE_URL % parse.quote_plus(tag)
        while next_url:
            page = _request_page(next_url)
            if not page: break
            posts, next_url = _get_links(page)
            # print('Post[%10d] Found %d posts on page [%s]' % (0, len(posts), next_url))
            result += posts
        print('Post[%10d] Found %d total posts' % (0, len(result)))
        return result

    def _download_post(self, dir_path, post_id):
        resp = request('GET', self.POST_URL % post_id)
        if resp.status_code == 200:
            post = _get_post_data(post_id, bs(resp.text, features='html.parser'))
            if post['url']:
                resp = request('GET', post['url'], stream=True)
                if resp.status_code == 200:
                    return dl_file(resp, dir_path, post['file'], post_id)

    def download_posts(self, tag):
        print('Post[%10d] Downloading tag [%s]' % (0, tag))
        dir_path = make_tag_dir(self.work_dir, tag)
        posts_ = self.history.get_item('posts', tag, [])
        posts = self._collect_posts(tag)
        for post_id in posts:
            if post_id in posts_: continue
            if self._download_post(dir_path, post_id): posts_.append(post_id)
            self.history.save()


def args_parse():
    parser = ArgumentParser(description='danbooru imageboard downloader')
    parser.add_argument('--work_dir', type=str, default=WORK_DIR)
    parser.add_argument('--tags', type=str)
    parser.add_argument('--tag', type=str)
    args = parser.parse_args()
    print(args)
    return args


def main():
    args = args_parse()

    if args.tags:
        poster = Danbooru(args.work_dir)
        for tag in args.tags.split(','):
            poster.download_posts(tag)

    if args.tag:
        poster = Danbooru(args.work_dir)
        poster.download_posts(args.tag)


if __name__ == '__main__':
    main()
