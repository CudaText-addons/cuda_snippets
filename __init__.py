import os
import shutil
import cudatext as ct
from cuda_snippets import snip as sn

from cudax_lib import get_translation
_   = get_translation(__file__)  # I18N

DATA_DIR = ct.app_path(ct.APP_DIR_DATA)


def safe_open_url(url):
    '''
    On Windows 10, app crashes when webbrowser.open* is called with running LSP server.
    '''
    if os.name=='nt':
        import subprocess
        subprocess.Popen(['start', '', url], shell=True)
    else:
        import webbrowser
        webbrowser.open_new_tab(url)


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
        lex = ct.ed.get_prop(ct.PROP_LEXER_CARET)
        if lex == '':
            lex = '(none)'
        return lex

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
        while True:
            i = ct.dlg_menu(ct.DMENU_LIST+ct.DMENU_NO_FULLFILTER, names, focused=focused, caption=_('Snippets'))
            if i is None:
                return
            key_state = ct.app_proc(ct.PROC_GET_KEYSTATE, '')
            modifier_pressed = 'c' in key_state
            self.last_snippet = items[i]
            self.last_snippet.insert(ct.ed)
            if not modifier_pressed:
                break
            focused = i

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
        if 'cuda_snippets' in [i.get('tag', '') for i in ct.menu_proc('text', ct.MENU_ENUM)]:
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
        safe_open_url(url)

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
        d = ct.dlg_dir(os.path.join(_data, 'snippets'), caption=_('Select snippets package'))
        if not d:
            return
        sn.convert_old_pkg(d, os.path.join(_data, 'snippets_ct'))
