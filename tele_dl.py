# -*- coding: utf-8 -*-
from datetime import datetime as dt
from datetime import timedelta as td
from re import findall, match

from requests import request
from telethon import TelegramClient
from telethon.tl.types import DocumentAttributeFilename

from commons import *


class TelethonDL:
    DATE_FMT = '%Y-%m-%d_%H-%M-%S'

    PICS_CHAT = 'P.S.T.N.A.'
    DANBOORU_CHANNEL = 'dnbooru'

    def __init__(self, work_dir=WORK_DIR, history=None):
        self.work_dir = work_dir
        with open(join(BASE_DIR, 'tele_dl.json'), 'r') as fd:
            api_data = load(fd)
        app_name = api_data['app_name']
        del api_data['app_name']
        # https://docs.telethon.dev/en/latest/basic/quick-start.html
        self.client = TelegramClient(join(BASE_DIR, app_name), **api_data)
        self.history = history if history else History(file_name=app_name + '.json')

    async def _get_danbooru_links(self, cnt):
        links = []
        last_msg = self.history.get_item(self.DANBOORU_CHANNEL, 'last_msg', {'id': 0})
        async for msg in self.client.iter_messages(self.DANBOORU_CHANNEL, limit=cnt, min_id=last_msg['id']):
            if last_msg['id'] < msg.id: last_msg['id'] = msg.id
            if not msg.reply_markup: continue
            tags = []
            m = match(r'^(?:Worlds?:(?P<W>.*?))?(?:Characters?:(?P<C>.*?))?(?:Artists?:(?P<A>.*?))?$',
                      msg.text.replace('\n', ' ').replace('#', ''))
            if m:
                if m.group('A'): tags += m.group('A').strip().split(' ')
                if m.group('C'): tags += m.group('C').strip().split(' ')
                if m.group('W'): tags += m.group('W').strip().split(' ')
            links.append({'url': msg.reply_markup.rows[0].buttons[0].url, 'tags': cut_tags(tags)})
            # await msg.mark_read()
        self.history.save()
        return links

    def _dl_danbooru_link(self, link):
        name, ext = link['url'].split('/')[-1].split('.')
        resp = request('GET', link['url'], stream=True, proxies=PROXIES)
        if resp.status_code == 200:
            dl_file(resp, self.work_dir, '%s %s.%s' % (' '.join(link['tags']), name[:8], ext), 0)

    def download_danbooru_arts(self, cnt=50):
        with self.client: links = self.client.loop.run_until_complete(self._get_danbooru_links(cnt))
        for link in links: self._dl_danbooru_link(link)

    def _get_photo_path(self, date):
        file_path = self.work_dir + 'photo_%s.jpg' % date.strftime(self.DATE_FMT)
        return self._get_photo_path(date - td(seconds=1)) if isfile(file_path) else file_path

    def _get_document_path(self, file_name):
        file_path = self.work_dir + file_name
        tg_name = findall(r'(\w+?)_(\d{4}-\d{2}-\d{2}_\d{2}-\d{2}-\d{2})\.(\w{3,4})', file_name)
        if not tg_name or not isfile(file_path): return file_path
        return self._get_document_path('%s_%s.%s' % (tg_name[0][0], (
                dt.strptime(tg_name[0][1], self.DATE_FMT) - td(seconds=1)).strftime(self.DATE_FMT), tg_name[0][2]))

    async def _dl_chat_arts(self, subj, cnt):
        last_msg = self.history.get_item(subj, 'last_msg', {'id': 0})
        async for msg in self.client.iter_messages(subj, limit=cnt, min_id=last_msg['id']):
            if msg.photo:
                p = await msg.download_media(file=(self._get_photo_path(msg.photo.date)))
                print('Photo downloaded to ' + p)
            if msg.document and isinstance(msg.document.attributes[1], DocumentAttributeFilename):
                p = await msg.download_media(file=(self._get_document_path(msg.document.attributes[1].file_name)))
                print('Document downloaded to ' + p)
            # await msg.mark_read()
            if last_msg['id'] < msg.id:
                last_msg['id'] = msg.id
                self.history.save()

    def download_chat_arts(self, subj, cnt=50):
        with self.client: self.client.loop.run_until_complete(self._dl_chat_arts(subj, cnt))

    async def send_file(self, subj, path_to_file):
        await self.client.send_file(subj, path_to_file, caption='It works!')

    def test_send_file(self, subj, path_to_file):
        with self.client: self.client.loop.run_until_complete(self.send_file(subj, path_to_file))

def main():
    teleton = TelethonDL('D:\\_downloads_\\!images!\\')
    teleton.download_danbooru_arts(125)
    # teleton.download_chat_arts(teleton.PICS_CHAT, 100)
    # teleton.test_send_file('Вака ДХС', 'D:\\_downloads_\\VodkaSubs_Selection_Project_02_1080p_AVC_AAC_track3_rus.ass')


if __name__ == '__main__':
    main()
