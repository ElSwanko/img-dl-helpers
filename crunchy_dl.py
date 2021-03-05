# -*- coding: utf-8 -*-
from argparse import ArgumentParser
from subprocess import getstatusoutput

from commons import *

EXEC = 'D:\\_dl_tools_\\crunchy-dl-nx\\crunchy.exe'


class CrunchyDL:

    def __init__(self, work_dir=WORK_DIR, history=None):
        self.work_dir = work_dir
        self.history = history if history else History(file_name='crunchy_dl.json')

    def _autorize(self):
        auth = self.history.get_category('auth')
        _, res = getstatusoutput(f'{EXEC} --auth --user {auth["user"]} --pass {auth["pass"]}')
        print(f'Auth result: {_} - {res}')

    @staticmethod
    def _dl_episode(item):
        print(f'{"=" * 40}')
        print(f'Downloading {item["ep"]} ep. of "{item["title"]}"')
        cmd = f'{EXEC} --s {item["id"]} -e {item["ep"]} --dlsubs ruRU {"--skipdl" if item["skipdl"] else ""}'
        _, res = getstatusoutput(cmd)
        print(f'Download result:\n{res}')
        return 'Subtitle downloaded' in res

    def download_titles(self):
        self._autorize()
        items = self.history.get_category('items')
        for item in items.values():
            dl_result = True
            while dl_result:
                dl_result = self._dl_episode(item)
                if dl_result:
                    item['ep'] += 1
                    self.history.save(2)

    def search(self, title):
        self._autorize()
        _, res = getstatusoutput(f'{EXEC} --search "{title}"')
        print(f'{res}')
        print(f'{"=" * 40}')
        _, res = getstatusoutput(f'{EXEC} --search2 "{title}"')
        print(f'{res}')


def args_parse():
    parser = ArgumentParser(description='CrunchyRoll download helper')
    parser.add_argument('--work_dir', type=str, default=WORK_DIR)
    parser.add_argument('title', type=str, default='download')
    args = parser.parse_args()
    print(args)
    return args


def main():
    args = args_parse()
    crunchyDl = CrunchyDL()

    if args.title == 'download':
        crunchyDl.download_titles()
    else:
        crunchyDl.search(args.title)


if __name__ == '__main__':
    main()
