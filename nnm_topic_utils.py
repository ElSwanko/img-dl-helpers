# -*- coding: utf-8 -*-
from argparse import ArgumentParser
from re import findall
from time import sleep

from bs4 import BeautifulSoup as bs
from requests import request

from commons import *


class NNMTopicUtils:
    ORIGIN = 'nnmclub.to'
    URL = 'https://%s/forum/' % ORIGIN

    LOGIN = 'login.php'
    CATEGORY = 'index.php'
    FORUM = 'viewforum.php'
    TOPIC = 'viewtopic.php'
    DL = 'download.php'

    RETRIES = 3
    RETRY_TIMEOUT = 15
    WAIT_TIMEOUT = 1.0
    TOPISC_PER_PAGE = 50

    LINE_FMT = '%-50s — %-18s — %-18s'
    STAT_FMT = '%5d (%s)'

    HEADERS = {
        'DNT': '1',
        'Origin': ORIGIN,
        'Referer': URL + CATEGORY,
        'Cache-Control': 'no-cache',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*',
        'Accept-Encoding': 'gzip, deflate, br',
        'Accept-Language': 'ru-RU',
        'Content-Type': 'application/x-www-form-urlencoded',
        'User-Agent': 'Mozilla/5.0 (Windows NT 6.1) AppleWebKit/537.36 (KHTML, like Gecko) '
                      'Chrome/79.0.3945.117 Safari/537.36'
    }

    def __init__(self, work_dir=WORK_DIR, history=None):
        self.work_dir = work_dir
        self.history = history if history else History(file_name='nnm_topic_utils.json')
        self.user, self.password, self.sid, self.cookies = None, None, None, {}
        with open(join(BASE_DIR, 'cookies', 'nnm_.json'), 'r') as f:
            self.users = list(load(f).items())
        self.sizer = Sizer()

    def _select_user(self, idx):
        self.user, self.password = self.users[idx]
        return self._login()

    def _request(self, page_url, referer, params=None, data=None, method='GET'):
        self.HEADERS['Referer'] = referer
        for i in range(0, self.RETRIES):
            try:
                resp = request(method, page_url, params=params, data=data,
                               headers=self.HEADERS, cookies=self.cookies)
                if resp.status_code == 200: return resp
                print('Failed to get page [%s] with params [%s]: %s' % (page_url, params, resp.text))
            except Exception as e:
                print('Failed to get page [%s] with params [%s]: %s' % (page_url, params, e))
            sleep(self.RETRY_TIMEOUT * (i + 1))

    def _get_page(self, page_url, referer, params=None, data=None, method='GET'):
        resp = self._request(page_url, referer, params, data, method)
        return bs(resp.text, features='html.parser') if resp else None

    def _login(self):
        # Get login code
        self.cookies = {'ssl': 'enable_ssl'}
        page = self._get_page(self.URL + self.LOGIN,
                              self.URL + self.CATEGORY + '?redirect=' + self.CATEGORY)
        if not page: return False
        form_data = {
            'username': self.user, 'password': self.password, 'autologin': 'on',
            'redirect': page.find('input', attrs={'name': 'redirect'}).attrs.get('value'),
            'code': page.find('input', attrs={'name': 'code'}).attrs.get('value'),
            'login': page.find('input', attrs={'name': 'login'}).attrs.get('value')
        }
        print('Login[%s] Got login data: %s' % (self.user, form_data))
        sleep(self.WAIT_TIMEOUT)
        # Do login
        resp = self._request(self.URL + self.LOGIN,
                             self.URL + self.LOGIN + '?redirect=' + self.CATEGORY,
                             data=form_data, method='POST')
        if not resp: return False
        print('Login[%s] Login result: %d' % (self.user, resp.status_code))
        if resp.status_code != 200: return False
        page = bs(resp.text, features='html.parser')
        me = page.findAll('a', class_='mainmenu')[12].text[8:-2]
        if not me:
            print('Failed to login')
            return False
        self.cookies = resp.history[0].cookies
        self.cookies = {key: self.cookies.get(key) for key in self.cookies.keys()}
        return True

    @staticmethod
    def _get_id(link):
        return link.split('=')[1]

    @staticmethod
    def _get_medal(h):
        for i in h.parent.findAll('img'):
            if 'раздача' in i.get('alt'): return i.get('src').split('/')[-1].split('.')[0]

    @staticmethod
    def _get_pages_count(page):
        pager = page.find('span', class_='gensmall', text='Часовой пояс: GMT + 3').parent.findAll('a')
        return int(pager[-2].text) if pager else 1

    @staticmethod
    def _calc_size(topics):
        alive, total = 0, 0
        for t in topics.values():
            if t['alive']: alive += t['bytes']
            total += t['bytes']
        return alive, total

    @staticmethod
    def _get_dl_topics(topics):
        return list(filter(lambda t: t['dl_id'] > 0, topics.values()))

    @staticmethod
    def _get_alive_topics(topics):
        return list(filter(lambda t: t['alive'], topics.values()))

    @staticmethod
    def _get_free_topic(topics):
        return list(filter(lambda t: t['medal'] in ('platinum', 'gold'), topics))

    def _get_forums(self, heads):
        forums = {}
        for h in heads:
            f = {'f_id': self._get_id(h.find('a').get('href')), 'name': h.text,
                 'topics_cnt': int(h.parent.parent.findAll('td', class_='row2')[0].text),
                 'alive_cnt': 0, 'total_cnt': 0, 'alive_bytes': 0, 'total_bytes': 0,
                 'alive_size': None, 'total_size': None, 'topics': [], 'forums': []}
            forums[f['f_id']] = f
        return forums

    def _get_topics(self, heads):
        topics = {}
        for h in heads:
            t = {'t_id': self._get_id(h.find('a').get('href')), 'name': h.text,
                 'dl_id': 0, 'alive': False, 'bytes': 0, 'size': None, 'medal': None}
            topics[t['t_id']] = t
            if h.parent.find('span', class_='tDL'):
                seeds = h.parent.parent.findAll('td', class_='row2')[0]
                dl = seeds.find('a')
                if dl:
                    t['dl_id'] = int(self._get_id(dl.get('href')))
                    t['alive'] = int(seeds.find('span', class_='seedmed').text) > 0
                    t['size'] = dl.text.replace('\xa0', ' ')
                    t['bytes'] = self.sizer.get_bytes(t['size'])
                    t['medal'] = self._get_medal(h)
        return topics

    def _get_forum_topics(self, f_id, topics_cnt):
        result = {}
        for i in range(0, int(topics_cnt / self.TOPISC_PER_PAGE) + 1):
            print('Forum[%s] get page %d' % (f_id, i + 1))
            page = self._get_page(self.URL + self.FORUM, self.URL + self.CATEGORY,
                                  params={'f': f_id, 'start': i * self.TOPISC_PER_PAGE})
            topics = self._get_topics(page.findAll('h2', class_='topictitle'))
            print('Forum[%s] found %d topics' % (f_id, len(topics)))
            result.update(topics)
            sleep(self.WAIT_TIMEOUT)
        print('Forum[%s] found %d total topics' % (f_id, len(result)))
        return result

    def _get_category_forum(self, cf_id, c_f):
        page = self._get_page(self.URL + self.FORUM, self.URL + self.CATEGORY, params={'f': cf_id})
        pages_cnt = self._get_pages_count(page)
        c_f['forums'] = self._get_forums(page.findAll('h2', class_='forumlink'))
        c_f['topics'] = self._get_forum_topics(cf_id, pages_cnt * self.TOPISC_PER_PAGE - 1)
        c_f['alive_bytes'], c_f['total_bytes'] = self._calc_size(c_f['topics'])
        c_f['alive_cnt'] = len(self._get_alive_topics(c_f['topics']))
        c_f['total_cnt'] = len(self._get_dl_topics(c_f['topics']))
        c_f['topics_cnt'] = len(c_f['topics'])
        for f_id, f in c_f['forums'].items():
            f['topics'] = self._get_forum_topics(f_id, f['topics_cnt'])
            f['alive_bytes'], f['total_bytes'] = self._calc_size(f['topics'])
            f['alive_size'] = self.sizer.format_size(f['alive_bytes'])
            f['total_size'] = self.sizer.format_size(f['total_bytes'])
            f['alive_cnt'] = len(self._get_alive_topics(f['topics']))
            f['total_cnt'] = len(self._get_dl_topics(f['topics']))
            f['topics_cnt'] = len(f['topics'])
            c_f['alive_cnt'] += len(self._get_alive_topics(f['topics']))
            c_f['total_cnt'] += len(self._get_dl_topics(f['topics']))
            c_f['topics_cnt'] += len(f['topics'])
            c_f['alive_bytes'] += f['alive_bytes']
            c_f['total_bytes'] += f['total_bytes']
        c_f['alive_size'] = self.sizer.format_size(c_f['alive_bytes'])
        c_f['total_size'] = self.sizer.format_size(c_f['total_bytes'])
        return c_f

    def _get_category(self, c_id):
        page = self._get_page(self.URL + self.CATEGORY, self.URL + self.CATEGORY, params={'c': c_id})
        name = page.find('tr', attrs={'onclick': 'CFIG_slideCat(\'%s\', false);' % c_id}).text.strip()
        c = self._get_forums(page.findAll('h3', class_='forumlink'))
        topics_cnt, alive_cnt, total_cnt, alive_bytes, total_bytes = 0, 0, 0, 0, 0
        for f_id, f in c.items():
            f = self._get_category_forum(f_id, f)
            topics_cnt += f['topics_cnt']
            alive_cnt += f['alive_cnt']
            total_cnt += f['total_cnt']
            alive_bytes += f['alive_bytes']
            total_bytes += f['total_bytes']
        return {'c_id': c_id, 'name': name, 'topics_cnt': topics_cnt,
                'alive_cnt': alive_cnt, 'total_cnt': total_cnt,
                'alive_bytes': alive_bytes, 'total_bytes': total_bytes,
                'alive_size': self.sizer.format_size(alive_bytes),
                'total_size': self.sizer.format_size(total_bytes), 'forums': c}

    def _flatten_category(self, c_id, limit=None):
        forums = {}
        category = self.history.get_item('struct', c_id)
        for c_f in category['forums'].values():
            topics = self._get_dl_topics(c_f['topics'])
            if limit: topics = topics[:limit]
            for f in c_f['forums'].values():
                topics_ = self._get_dl_topics(f['topics'])
                forums[f['f_id']] = topics_[:limit] if limit else topics_
                topics += forums[f['f_id']]
            forums[c_f['f_id']] = topics
        return forums

    @staticmethod
    def _list_check(t, history_item):
        return t['dl_id'] in history_item

    @staticmethod
    def _list_commit(t, history_item):
        history_item.append(t['dl_id'])

    def _dl_torrent(self, t):
        resp = self._request(self.URL + self.DL, self.URL + self.TOPIC + '?t=' + t['t_id'],
                             params={'id': t['dl_id']})
        if resp.status_code == 200:
            file_name = findall(r'.*? filename="(.*)"', resp.headers.get('Content-Disposition'))[0]
            return dl_file(resp, self.work_dir, file_name, t['dl_id'])

    def _process_topics(self, topics, exec_func, category, item, **kwargs):
        history_item = self.history.get_item(category, item, kwargs.get('default_item', []))
        for i, t in enumerate(topics):
            if kwargs.get('check_func', self._list_check)(t, history_item): continue
            if exec_func(t, **kwargs):
                kwargs.get('commit_func', self._list_commit)(t, history_item)
                sleep(self.WAIT_TIMEOUT)
            if i % 50 == 0: self.history.save()
        self.history.save()

    def _format_forum(self, f_id, f_, lvl=0):
        return self.LINE_FMT % ((' |' * lvl + '— %s (%s)') % (f_['name'], f_id),
                                self.STAT_FMT % (f_['total_cnt'], f_['total_size']),
                                self.STAT_FMT % (f_['alive_cnt'], f_['alive_size']))

    def print_stats(self, c_id):
        c = self.history.get_item('struct', c_id)
        lines = [self.LINE_FMT % ('Форум', 'Всего раздач', '"Живых" раздач'),
                 self._format_forum(c_id, c, 0)]
        for c_f in c['forums'].values():
            lines.append(self._format_forum(c_f['f_id'], c_f, 1))
            for f in c_f['forums'].values():
                lines.append(self._format_forum(f['f_id'], f, 2))

        for l in lines: print(l)
        with open(join(self.work_dir, 'cat_%s_stats.txt' % c_id), 'w') as f:
            f.writelines([l + '\n' for l in lines])
        return lines

    def update_category(self, c_id, u_id=0):
        if not self._select_user(u_id): return
        c = self._get_category(c_id)
        self.history.set_item('struct', c_id, c)
        self.history.save()
        self.print_stats(c_id)
        return c

    def download_torrents(self, c_id, f_id, free_only=False, u_id=0):
        if not self._select_user(u_id): return
        forums = self._flatten_category(c_id)
        topics = self._get_free_topic(forums[f_id]) if free_only else forums[f_id]
        print('Downloading torrents by %s' % self.user)
        self._process_topics(topics, self._dl_torrent, 'downloads', self.user)


def args_parse():
    parser = ArgumentParser(description='NNM torrents downloader')
    parser.add_argument('--work_dir', type=str, default=WORK_DIR)
    parser.add_argument('--update_category', required=False, action='store_true')
    parser.add_argument('--print_category', required=False, action='store_true')
    parser.add_argument('--free_only', required=False, action='store_true')
    parser.add_argument('--download', required=False, action='store_true')
    parser.add_argument('--dl_idx', required=False, type=int, default=0)
    parser.add_argument('--category', required=False, type=str)
    parser.add_argument('--forum', required=False, type=str)
    args = parser.parse_args()
    print(args)
    return args


def main():
    args = args_parse()
    utils = NNMTopicUtils(args.work_dir)

    if args.update_category:
        utils.update_category(args.category)

    if args.print_category:
        utils.print_stats(args.category)

    if args.download:
        utils.download_torrents(args.category, args.forum, args.free_only, args.dl_idx)


if __name__ == '__main__':
    main()
