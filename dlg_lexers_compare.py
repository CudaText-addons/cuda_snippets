import os

import cudatext as ct
from cuda_snippets import vs

from cudax_lib import get_translation
_   = get_translation(__file__)  # I18N

class DlgLexersCompare:
    def __init__(self, data=None):
        self.data = data
        self.items = list(self.data.get('files', {}).keys())
        self.lexers = ct.lexer_proc(ct.LEXER_GET_LEXERS, True)
        self.state = {k: '-1;' + ','*len(self.lexers) for k in self.items}

        w, h = 600, 400
        self.h = ct.dlg_proc(0, ct.DLG_CREATE)
        ct.dlg_proc(self.h, ct.DLG_PROP_SET,
                    prop={'cap': _('Setup snippet lexer(s)'),
                          'w': w,
                          'h': h,
                          'border': ct.DBORDER_DIALOG,
                          "keypreview": True,
                          }
                    )

        self.g1 = ct.dlg_proc(self.h, ct.DLG_CTL_ADD, 'panel')
        ct.dlg_proc(self.h, ct.DLG_CTL_PROP_SET, index=self.g1,
                    prop={
                        'name': 'g1',
                        'h': 40,
                        'align': ct.ALIGN_BOTTOM,
                         }
                    )

        self.ls = ct.dlg_proc(self.h, ct.DLG_CTL_ADD, 'listbox')
        ct.dlg_proc(self.h, ct.DLG_CTL_PROP_SET, index=self.ls,
                    prop={
                        'name': 'ls',
                        'w': w//2,
                        'align': ct.ALIGN_LEFT,
                        'items': '\t'.join(self.items),
                        'val': 0,
                        'sp_a': 4,
                        'on_click': self.load_state,
                         }
                    )

        self.chls = ct.dlg_proc(self.h, ct.DLG_CTL_ADD, 'checklistbox')
        ct.dlg_proc(self.h, ct.DLG_CTL_PROP_SET, index=self.chls,
                    prop={
                        'name': 'chls',
                        'w': w//2,
                        'align': ct.ALIGN_RIGHT,
                        'items': '\t'.join(self.lexers),
                        'sp_a': 4,
                        'on_click': self.update_state,
                         }
                    )

        self.b = ct.dlg_proc(self.h, ct.DLG_CTL_ADD, 'button')
        ct.dlg_proc(self.h, ct.DLG_CTL_PROP_SET, index=self.b,
                    prop={
                        'name': 'b',
                        'w': 100,
                        'a_l': None,
                        'a_r': ('g1', ']'),
                        'a_t': ('g1', '['),
                        'sp_r': 4,
                        'sp_t': 4,
                        'p': 'g1',
                        'cap': 'Ok',
                        'on_change': self.press_ok,
                         }
                    )

    @property
    def selected(self):
        return int(ct.dlg_proc(self.h, ct.DLG_CTL_PROP_GET, index=self.ls)['val'])

    @property
    def checked_items(self):
        return ct.dlg_proc(self.h, ct.DLG_CTL_PROP_GET, index=self.chls)['val']

    @checked_items.setter
    def checked_items(self, val):
        ct.dlg_proc(self.h, ct.DLG_CTL_PROP_SET, index=self.chls,
                    prop={
                        'val': val,
                         }
                    )

    def load_state(self, *args, **kwargs):
        self.checked_items = self.state[self.items[self.selected]]

    def update_state(self, *args, **kwargs):
        chit = self.checked_items.split(';')[1]
        self.state[self.items[self.selected]] = '-1;' + chit

    def press_ok(self, *args, **kwargs):
        # edit data dict
        files = self.data.get('files', {})
        new = {}
        for k, v in self.state.items():
            for n, i in enumerate(v.split(';')[1].split(',')):
                if i == '1':
                    lexer = self.lexers[n]
                    lx = new.get(lexer, [])
                    for x in files[k]:
                        if x not in lx:
                            lx.append(x)
                    new[lexer] = lx

        if not new:
            ct.msg_box(_('You must check at least one CudaText lexer, for snippets to work'), 
                ct.MB_OK+ct.MB_ICONWARNING)
            return

        self.data['files'] = new
        # install
        path = os.path.join(ct.app_path(ct.APP_DIR_DATA), 'snippets_vs')
        vs.install_vs_snips(path, self.data)
        ct.dlg_proc(self.h, ct.DLG_HIDE)

    def show(self):
        ct.dlg_proc(self.h, ct.DLG_SCALE)
        ct.dlg_proc(self.h, ct.DLG_SHOW_MODAL)
        ct.dlg_proc(self.h, ct.DLG_FREE)


# if __name__ == '__main__':
#     _data = {
#         'name': 'js-jsx-snippets',
#         'version': '10.1.0',
#         'display_name': 'JS JSX Snippets',
#         'description': 'Simple extensions for React, Redux in JS with babel and ES6 syntax',
#         'files': {
#             'javascript': ['extension/snippets/snippets.json'],
#             'javascriptreact': ['extension/snippets/snippets.json'],
#             'typescript': ['extension/snippets/snippets.json'],
#             'typescriptreact': ['extension/snippets/snippets.json']
#         }
#     }
#     DlgLexersCompare(_data).show()
