﻿import threading
import re
import os

import cudatext as ct
from cuda_snippets import vs

# from cuda_dev import dev

PLUG = "snippets"


def simple_search(sub: str, text: str):
    """Simple search

    :return: rating of search
    """
    ln = len(sub)
    f = text.find(sub)
    if f >= 0:
        return sum([(1000 - f - i) * ln for i in range(ln)])
    else:
        return 0


def whole_word_search(sub: str, text: str):
    """Whole word search

    :return: rating of search
    """
    ln = len(sub)
    re_sub = re.compile(r"\b"+sub+r"\b")
    mobj = re_sub.search(text)
    if not mobj:
        return 0
    else:
        f = mobj.start(0)
        return sum([(1000 - f - i) * ln for i in range(ln)])


def fuzzy(sub: str, text: str):
    """Fuzzy search like in ST3

    :return: rating of search
    """
    ln = len(sub)
    rating = 0
    last = -1
    for i in range(ln):
        # try find pair
        if ln >= 2 and i < ln:
            pr = sub[i:] if ln == 2 else sub[i:i+2]
            f = text.find(pr, last+1)
            if f != -1:
                rating += 1000 - f
                last = f
            # try find chr
            else:
                f = text.find(sub[i], last+1)
                if f != -1:
                    rating += 500 - f
                    last = f
                else:
                    return 0
        else:
            f = text.find(sub[i], last+1)
            if f != -1:
                rating += 500 - f
                last = f
    return rating


class Ini:
    def __init__(self, file):
        """Define .ini file"""
        self.file = file

    def read_int(self, section, key, defvalue):
        """Reads single string from .ini file"""
        return int(ct.ini_read(self.file, section, key, str(defvalue)))

    def write_int(self, section, key, value):
        """Write single string to .ini file"""
        ct.ini_write(self.file, section, key, str(value))


class DlgSearch:
    def __init__(self):
        self.data = None
        self.cfg = Ini(os.path.join(ct.app_path(ct.APP_DIR_SETTINGS), "plugins.ini"))

        w, h = 600, 400
        GUI_HEIGHT = ct.app_proc(ct.PROC_GET_GUI_HEIGHT, '')
        self.h = ct.dlg_proc(0, ct.DLG_CREATE)
        ct.dlg_proc(self.h, ct.DLG_PROP_SET,
                    prop={'cap': 'Search snippets',
                          'w': w,
                          'h': h,
                          # 'resize': False,
                          'border': ct.DBORDER_SIZE,
                          "keypreview": True,
                          'on_key_up': self.press_key,
                          }
                    )

        self.g1 = ct.dlg_proc(self.h, ct.DLG_CTL_ADD, 'panel')
        ct.dlg_proc(self.h, ct.DLG_CTL_PROP_SET, index=self.g1,
                    prop={
                        'name': 'g1',
                        'h': 30,
                        'a_l': ('', '['),
                        'a_r': ('', ']'),
                        'a_t': ('', '['),
                         }
                    )

        self.g2 = ct.dlg_proc(self.h, ct.DLG_CTL_ADD, 'panel')
        ct.dlg_proc(self.h, ct.DLG_CTL_PROP_SET, index=self.g2,
                    prop={
                        'name': 'g2',
                        'a_l': ('', '['),
                        'a_r': ('', ']'),
                        'a_t': ('g1', ']'),
                        'a_b': ('', ']'),
                         }
                    )

        self.ls = ct.dlg_proc(self.h, ct.DLG_CTL_ADD, 'listbox')
        ct.dlg_proc(self.h, ct.DLG_CTL_PROP_SET, index=self.ls,
                    prop={
                        'name': 'ls',
                        'p': 'g2',
                        'align': ct.ALIGN_CLIENT,
                        'sp_l': 5,
                        'sp_r': 5,
                        'sp_t': 5,
                        'on_click_dbl': self.install,
                        'on_click': self.load_description,
                         }
                    )

        self.sp = ct.dlg_proc(self.h, ct.DLG_CTL_ADD, 'splitter')
        ct.dlg_proc(self.h, ct.DLG_CTL_PROP_SET, index=self.sp,
                    prop={
                        'name': 'sp',
                        'p': 'g2',
                        'align': ct.ALIGN_BOTTOM,
                         }
                    )

        self.memo = ct.dlg_proc(self.h, ct.DLG_CTL_ADD, 'memo')
        ct.dlg_proc(self.h, ct.DLG_CTL_PROP_SET, index=self.memo,
                    prop={
                        'name': 'ls',
                        'h': 60,
                        'ex0': True,
                        'ex1': True,
                        'p': 'g2',
                        'align': ct.ALIGN_BOTTOM,
                        'sp_l': 5,
                        'sp_r': 5,
                        'sp_b': 5,
                        'tab_stop': False,
                         }
                    )

        self.b = ct.dlg_proc(self.h, ct.DLG_CTL_ADD, 'button')
        ct.dlg_proc(self.h, ct.DLG_CTL_PROP_SET, index=self.b,
                    prop={
                        'name': 'b',
                        'w': 32,
                        'a_l': None,
                        'a_r': ('g1', ']'),
                        'a_t': ('g1', '['),
                        'sp_a': 5,
                        'p': 'g1',
                        'cap': '=',
                        'tab_stop': False,
                        'on_change': self.menu_show
                         }
                    )

        self.edit = ct.dlg_proc(self.h, ct.DLG_CTL_ADD, 'edit')
        ct.dlg_proc(self.h, ct.DLG_CTL_PROP_SET, index=self.edit,
                    prop={
                        'name': 'edit',
                        'a_l': ('g1', '['),
                        'a_r': ('b', '['),
                        'a_t': ('g1', '['),
                        'sp_a': 5,
                        'p': 'g1',
                        'tab_order': 0,
                         }
                    )

        # make options
        self.is_fuzzy_search = True
        self.is_whole_word_search = False
        self.is_search_in_descriptions = False

        # make menu
        self.menu_hndl = ct.menu_proc(0, ct.MENU_CREATE)

        self.mi_fuzzy_search = ct.menu_proc(self.menu_hndl, ct.MENU_ADD,
                                            caption="Fuzzy search",
                                            command=self.togle_fuzzy_search
                                            )
        ct.menu_proc(self.mi_fuzzy_search, ct.MENU_SET_CHECKED, command=self.is_fuzzy_search)

        self.mi_whole_word_search = ct.menu_proc(self.menu_hndl, ct.MENU_ADD,
                                                 caption="Whole word search",
                                                 command=self.togle_whole_word_search
                                                 )

        self.mi_search_in_descriptions = ct.menu_proc(self.menu_hndl, ct.MENU_ADD,
                                                      caption="Search in descriptions",
                                                      command=self.togle_search_in_descriptions
                                                      )

    def togle_fuzzy_search(self, *args, **kwargs):
        self.is_fuzzy_search = not self.is_fuzzy_search
        ct.menu_proc(self.mi_fuzzy_search, ct.MENU_SET_CHECKED, command=self.is_fuzzy_search)
        self.search()

    def togle_whole_word_search(self, *args, **kwargs):
        self.is_whole_word_search = not self.is_whole_word_search
        ct.menu_proc(self.mi_whole_word_search, ct.MENU_SET_CHECKED, command=self.is_whole_word_search)
        ct.menu_proc(self.mi_fuzzy_search, ct.MENU_SET_ENABLED, command=not self.is_whole_word_search)
        self.search()

    def togle_search_in_descriptions(self, *args, **kwargs):
        self.is_search_in_descriptions = not self.is_search_in_descriptions
        ct.menu_proc(self.mi_search_in_descriptions, ct.MENU_SET_CHECKED, command=self.is_search_in_descriptions)
        self.search()

    def menu_show(self, *args, **kwargs):
        """Shows popup-menu."""
        p = ct.dlg_proc(self.h, ct.DLG_PROP_GET)
        base_point = (p["x"]+p["w"]-190, p["y"]+50)
        ct.menu_proc(self.menu_hndl, ct.MENU_SHOW, command=base_point)

    def set_vs_exts(self, vs_exts):
        self.vs_exts = vs_exts
        self.vs_exts.sort(key=lambda i: i['stat'], reverse=True)
        self.exts = self.vs_exts.copy()

    def show(self):
        self.data = None
        self.search()
        # set last dlg size
        p = {
            "w": self.cfg.read_int(PLUG, 'w', 600),
            "h": self.cfg.read_int(PLUG, 'h', 400)
        }
        ct.dlg_proc(self.h, ct.DLG_PROP_SET, prop=p)
        p = {'h': self.cfg.read_int(PLUG, 'spt', 60)}
        ct.dlg_proc(self.h, ct.DLG_CTL_PROP_SET, index=self.memo, prop=p)

        ct.dlg_proc(self.h, ct.DLG_SHOW_MODAL)

        # save last dlg size
        p = ct.dlg_proc(self.h, ct.DLG_PROP_GET)
        self.cfg.write_int(PLUG, 'w', p['w'])
        self.cfg.write_int(PLUG, 'h', p['h'])
        p = ct.dlg_proc(self.h, ct.DLG_CTL_PROP_GET, index=self.memo)
        self.cfg.write_int(PLUG, 'spt', p['h'])

        return self.data

    def press_key(self, id_dlg, id_ctl, data='', info=''):
        # dev(id_ctl)
        if id_ctl == 13:
            if self.is_focused(self.edit):
                self.search()
            elif self.is_focused(self.ls) and self.item_index >= 0:
                self.install()
        elif id_ctl == 40 and not self.is_focused(self.ls):
            self.set_focus(self.ls)
            self.item_index += 1
            self.load_description()
        elif id_ctl == 38 and self.item_index == 0:
            self.set_focus(self.edit)
        elif self.is_focused(self.edit):
            self.search()

    def is_focused(self, ctl):
        return ct.dlg_proc(self.h, ct.DLG_CTL_PROP_GET, index=ctl)['focused']

    def set_focus(self, ctl):
        ct.dlg_proc(self.h, ct.DLG_CTL_FOCUS, index=ctl)

    @property
    def text(self):
        return ct.dlg_proc(self.h, ct.DLG_CTL_PROP_GET, index=self.edit)['val']

    @property
    def item_index(self):
        return int(ct.dlg_proc(self.h, ct.DLG_CTL_PROP_GET, index=self.ls)['val'])

    @item_index.setter
    def item_index(self, v):
        ct.dlg_proc(self.h, ct.DLG_CTL_PROP_SET, index=self.ls, prop={'val': v})

    def set_items(self, items):
        items = '\t'.join(items)
        ct.dlg_proc(self.h, ct.DLG_CTL_PROP_SET, index=self.ls, prop={'items': items})

    def load_description(self, *args, **kwargs):
        descr = self.exts[self.item_index]['description']
        ct.dlg_proc(self.h, ct.DLG_CTL_PROP_SET, index=self.memo, prop={'val': descr})

    def install(self, *args, **kwargs):
        ext = self.exts[self.item_index]
        ct.dlg_proc(self.h, ct.DLG_HIDE)
        ct.msg_status(' '.join(["Installing: ", ext['display_name'], ext['version']]), process_messages=True)

        self.data = vs.download(ext['url'])
        if not self.data:
            ct.msg_box(' '.join(["Can't download: ", ext['display_name'], ext['version']]), ct.MB_OK+ct.MB_ICONERROR)
            return

    def search(self, *args, **kwargs):
        """Find extensions."""
        name = self.text
        if name:
            name = name.lower()
            self.exts = []
            if self.is_whole_word_search:
                search_engine = whole_word_search
            else:
                if self.is_fuzzy_search:
                    search_engine = fuzzy
                else:
                    search_engine = simple_search

            for i in self.vs_exts:
                if self.is_search_in_descriptions:
                    text = i['description'].lower()
                else:
                    text = i['display_name'].lower()
                fz = search_engine(name, text)
                i['rating'] = fz
                if fz > 0:
                    self.exts.append(i)

            self.exts.sort(key=lambda x: x['rating'], reverse=True)

        items = [' '.join([e['display_name'], e['version']]) for e in self.exts]
        self.set_items(items)


if __name__ == '__main__':
    dlg = DlgSearch()
    dlg.set_vs_exts(vs.get_all_snip_exts())
    dlg.show()
