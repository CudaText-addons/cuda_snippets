# from cuda_dev import dev
# dev.tstart()
import os
import shutil
import webbrowser

from cudatext import *

import cudatext as ct
from cuda_snippets import snip as sn
# dev.tstop()

from cudax_lib import get_translation
_   = get_translation(__file__)  # I18N

DATA_DIR = ct.app_path(ct.APP_DIR_DATA)


class Command:
    def __init__(self):
        # dev.tstart()
        self.vs_exts = None
        self.dlg_search = None
        self.last_snippet = None
        self.loader = sn.Loader(DATA_DIR)
        self.add_menu_items()
        # dev.tstop()

    @property
    def lexer(self):
        return ct.ed.get_prop(ct.PROP_LEXER_CARET)

    @property
    def lex_snippets(self):
        return self.loader.load_by_lexer(self.lexer)
        # return self.snippets.get(lexer, []) + self.glob

    def on_key(self, ed_self, code, state):
        if code != 9:
            return  # tab-key=9
        if state != '':
            return  # pressed any meta keys

        name = sn.get_word(ed_self)
        if not name:
            return

        items = [i for i in self.lex_snippets if name in i.id]  # leave snips for name

        if not items:
            return

        # delete name in text
        carets = ed_self.get_carets()
        x0, y0, x1, y1 = carets[0]
        ed_self.delete(x0 - len(name), y0, x0, y0)
        ed_self.set_caret(x0 - len(name), y0)

        if len(items) > 1:
            self.menu_dlg(items)
            return False  # block tab-key

        # insert
        items[0].insert(ed_self)
        return False  # block tab-key

    def menu_dlg(self, items):
        names = [str(item) for item in items]
        if not names:
            ct.msg_status(_('No snippets for current lexer'))
            return
        try:
            focused = items.index(self.last_snippet)
        except ValueError:
            focused = 0
        i = ct.dlg_menu(ct.DMENU_LIST, names, focused=focused, caption=_('Snippets'))
        if i is None:
            return
        self.last_snippet = items[i]
        self.last_snippet.insert(ct.ed)

    def do_menu(self):
        self.menu_dlg(self.lex_snippets)
        
    def show_snipman(self):
        from cuda_snippets.dlg_snip_manage import DlgSnipMan
        
        lex = ct.ed.get_prop(ct.PROP_LEXER_FILE)
        dlg_add = DlgSnipMan(select_lex=lex)
        changed = dlg_add.show_add_snip()

        # reload loaded snippets
        if changed:
            self.loader = sn.Loader(DATA_DIR)
            
    def install_vs_snip(self):
        # need import here, not at the top, for faster load cudatext
        from cuda_snippets import vs
        from cuda_snippets.dlg_search import DlgSearch
        from cuda_snippets.dlg_lexers_compare import DlgLexersCompare

        if not self.dlg_search:
            self.dlg_search = DlgSearch()

        # load vs snippets list
        if not self.vs_exts:
            ct.msg_status(_("Loading VS Snippets list. Please wait..."), process_messages=True)
            self.vs_exts = vs.get_all_snip_exts()
            if not self.vs_exts:
                print(_("Can't download VS Snippets. Try again later..."))
                return
        # show dlg
        self.dlg_search.set_vs_exts(self.vs_exts)
        data = self.dlg_search.show()
        if not data:
            return
        DlgLexersCompare(data).show()
        self.loader = sn.Loader(DATA_DIR)
        # self.loader.load_all()

    @staticmethod
    def del_markers():
        ct.ed.markers(ct.MARKERS_DELETE_ALL)

    def add_menu_items(self):
        if 'cuda_snippets' in [i['tag'] for i in ct.menu_proc('text', ct.MENU_ENUM)]:
            return

        ct.menu_proc("text", ct.MENU_ADD,
                     caption='-',
                     tag='cuda_snippets'
                     )
        ct.menu_proc("text", ct.MENU_ADD,
                     caption=_('Delete snippet markers'),
                     command=self.del_markers,
                     # hotkey=hotkey,
                     tag='cuda_snippets'
                     )

    def vs_local_dirs(self):
        vs_dir = os.path.join(DATA_DIR, 'snippets_vs')
        if not os.path.isdir(vs_dir):
            return []

        rec = []
        # for folder, data in sn.load_vs_snip_exts(vs_dir):
        for data in self.loader.packages:
            if data['type'] != 1:
                continue
            name = (data.get('display_name') or '') + ' ' + (data.get('version') or '')
            url = ''
            lnk = data.get('links') or ''
            if lnk:
                url = lnk.get('bugs') or lnk.get('repository') or ''
                if url.endswith('.git'):
                    url = url[:-4]
            if name:
                rec.append({'name': name, 'url': url, 'dir': data['path']})

        rec.sort(key=lambda r: r['name'])
        return rec

    def issues_vs(self):
        rec = self.vs_local_dirs()
        if not rec:
            ct.msg_status(_('No VSCode snippets found'))
            return

        mnu = [s['name']+'\t'+s['url'] for s in rec]
        res = ct.dlg_menu(ct.DMENU_LIST_ALT, mnu, caption=_('Visit page of snippets'))
        if res is None:
            return

        url = rec[res]['url']
        if not url:
            ct.msg_status(_("No URL found"))
            return
        ct.msg_status(_('Opened: ')+url)
        webbrowser.open_new_tab(url)

    def remove_vs_snip(self):
        rec = self.vs_local_dirs()

        if not rec:
            ct.msg_status(_('No VSCode snippets found'))
            return

        mnu = [s['name'] for s in rec]
        res = ct.dlg_menu(ct.DMENU_LIST, mnu, caption=_('Remove snippets'))
        if res is None:
            return

        vs_snip_dir = rec[res]['dir']
        shutil.rmtree(vs_snip_dir)
        ct.msg_status(_('Snippets folder removed; restart CudaText to forget about it'))

    def convert_from_old_format(self):
        _data = ct.app_path(ct.APP_DIR_DATA)
        d = ct.dlg_dir(os.path.join(_data, 'snippets'), caption='Select snippets package')
        if not d:
            return
        sn.convert_old_pkg(d, os.path.join(_data, 'snippets_ct'))
    
    def phpstorm_import(self):
        dlg_dir_ = ct.dlg_dir('', "Select folder with live-templates of PhpStorm")
        if (dlg_dir_):
            import xml.etree.ElementTree as ET
            import json
            
            sep_ = os.sep
            
            i = j = 0
            phpstorm_json = {}
            
            files_ = os.listdir(dlg_dir_)
            for dlg_file_ in files_:
                path_ = dlg_dir_ + sep_ + dlg_file_
                tree = ET.parse(path_)
                root = tree.getroot()
            
                res_ = []
                for child in root:
                    value_ = child.get("value").replace("$END$", "${0}")
                    desc_ = child.get("name")
                    name_ = '[' + desc_ + '] ' + child.get("description") 
                    res_.append({
                         name_: {
                            'value': value_,
                            'desc': desc_ 
                        }
                    })
            
                snippets_dir_ = os.path.join(ct.app_path(ct.APP_DIR_DATA), 'snippets_ct') + sep_ + 'phpstorm'
                if not os.path.exists(snippets_dir_):
                    os.makedirs(snippets_dir_)
                
                snippets_dir__ = snippets_dir_ + sep_ + 'snippets'
                if not os.path.exists(snippets_dir__):
                    os.makedirs(snippets_dir__)
            
                config_json = {
                    "name": "phpstorm",
                    "files": {
                        "phpstorm.json": [
                            "PHP",
                            "PHP_",
                            "HTML",
                            "HTML_",
                            "CSS",
                            "JavaScript"
                        ]
                    }
                }
                fout = open(snippets_dir_ + sep_ + 'config.json', 'w')
                json.dump(config_json, fout, indent=4)
                fout.close()
            
                for res__ in res_:
                    for k, v in res__.items():
                        body_ = prefix_ = ''
                        for k_, v_ in v.items():
                            if k_ == 'value':
                                body_ = v_.split("\n")
                            if k_ == 'desc':
                                prefix_ = v_
                            phpstorm_json[k] = {
                                "prefix": prefix_,
                                "body": body_
                            }
                        j += 1
                i += 1
            
            if len(phpstorm_json) > 0:
                fout = open(snippets_dir__ + sep_ + 'phpstorm.json', 'a')
                json.dump(phpstorm_json, fout, indent=4)
                fout.close()
            
            if i > 0:
                msg_box("Files processed: " + str(i) + ".\n" + "Imported snippets: " + str(j) + ".\n\n" + "Please restart CudaText to apply the updates.", MB_OK)
            else:
                msg_box("Live-templates not found!", MB_OK+MB_ICONERROR)
