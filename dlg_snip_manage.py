import os
import json

#DBG
import datetime

import cudatext as ct
from cuda_snippets import vs

from cudax_lib import get_translation
_   = get_translation(__file__)  # I18N


ALLOW_FILE_MODIFICATION = False
        
DATA_DIR = ct.app_path(ct.APP_DIR_DATA)
MAIN_SNIP_DIR = os.path.join(DATA_DIR, 'snippets_ct')
SNIP_DIRS = [
    MAIN_SNIP_DIR,
    os.path.join(DATA_DIR, 'snippets_vs'),
]

TYPE_PKG = 101
TYPE_GROUP = 102 

#TODO check for proper filenames for filesystem
#TODO handle same name packages
#TODO sort modifieds before saving

def log(s):
    if True:
        now = datetime.datetime.now()
        with open('/media/q/cu.log', 'a', encoding='utf-8') as f:
            f.write(now.strftime("%H:%M:%S ") + s + '\n')

#class DlgLexersCompare:
class DlgSnipMan:
    def __init__(self, select_lex=None):
        self.select_lex = select_lex # select first group with this lexer, mark in menus
        
        self.packages = self._load_packages()
        self._sort_pkgs()
        self.file_snippets = {} # tuple (<pkg path>,<group>) : snippet dict
        self.modified = [] # (type, name)

        w, h = 500, 400
        self.h = ct.dlg_proc(0, ct.DLG_CREATE)
        ct.dlg_proc(self.h, ct.DLG_PROP_SET, 
                    prop={'cap': _('Add snippet'),
                        'w': w,
                        'h': h,
                        'resize': True,
                        #"keypreview": True,
                        }
                    )
                    
 
        ### Controls
        
        # Cancel | Ok
        self.n_ok = ct.dlg_proc(self.h, ct.DLG_CTL_ADD, 'button')
        ct.dlg_proc(self.h, ct.DLG_CTL_PROP_SET, index=self.n_ok,
                    prop={
                        'name': 'ok',
                        'a_l': None,
                        'a_t': None,
                        'a_r': ('', ']'),
                        'a_b': ('',']'),
                        'w': 30,
                        #'h_max': 30,
                        'w_min': 60,
                        'sp_a': 6,
                        #'sp_t': 6,
                        'autosize': True,
                        'cap': 'OK',  
                        'on_change': self._save_changes,
                        }
                    )
                    
        self.n_cancel = ct.dlg_proc(self.h, ct.DLG_CTL_ADD, 'button')
        ct.dlg_proc(self.h, ct.DLG_CTL_PROP_SET, index=self.n_cancel,
                    prop={
                        'name': 'cancel',
                        'a_l': None,
                        'a_t': ('ok', '-'),
                        'a_r': ('ok', '['),
                        'a_b': ('',']'),
                        'w': 30,
                        #'h_max': 30,
                        'w_min': 60,
                        'sp_a': 6,
                        #'sp_t': 6,
                        'autosize': True,
                        'cap': 'Cancel',  
                        'on_change': self._dismiss_dlg,
                        }
                    )
                    
        ### Main
        n = ct.dlg_proc(self.h, ct.DLG_CTL_ADD, 'group')
        ct.dlg_proc(self.h, ct.DLG_CTL_PROP_SET, index=n,
                    prop={
                        'name': 'parent',
                        'a_l': ('','['),
                        'a_t': ('','['),
                        'a_r': ('',']'),
                        'a_b': ('cancel','['),
                        #'align': ct.ALIGN_CLIENT,
                        'sp_a': 3,
                        #'sp_b': 40,
                        }
                    )
        # package
        n = ct.dlg_proc(self.h, ct.DLG_CTL_ADD, 'label')
        ct.dlg_proc(self.h, ct.DLG_CTL_PROP_SET, index=n,
                    prop={
                        'name': 'pkg_label',
                        'p': 'parent',
                        'a_l': ('', '['),
                        'a_t': ('','['),
                        'w_min': 80,
                        'sp_a': 3,
                        'sp_t': 6,
                        'cap': 'Package: ',  
                        }
                    )
                    
        self.n_del_pkg = ct.dlg_proc(self.h, ct.DLG_CTL_ADD, 'button')
        ct.dlg_proc(self.h, ct.DLG_CTL_PROP_SET, index=self.n_del_pkg,
                    prop={
                        'name': 'del_pkg',
                        'p': 'parent',
                        'a_l': None,
                        'a_t': ('pkg_label','-'),
                        'a_r': ('',']'),
                        #'a_b': ('',']'),
                        #'w_min': 60,
                        #'w': 60,
                        'sp_a': 3,
                        #'sp_t': 6,
                        'cap': 'Delete...',  
                        'en': False,
                        'on_change': self._dlg_del_pkg,
                        }
                    )
                    
        self.n_package = ct.dlg_proc(self.h, ct.DLG_CTL_ADD, 'combo_ro')
        ct.dlg_proc(self.h, ct.DLG_CTL_PROP_SET, index=self.n_package,
                    prop={
                        'name': 'packages',
                        'p': 'parent',
                        'a_l': ('pkg_label', ']'),
                        'a_t': ('pkg_label','-'),
                        'a_r': ('del_pkg','['),
                        'sp_a': 3,
                        'act': True,
                        'on_change': self._on_package_selected,
                        #'on_change': lambda *args, **vargs: print(f' --sel'),
                        #'on_change': 'module=cuda_snippets;cmd=_del;',
                        }
                    )
                    
        '!!! WRIOK'   
        # group
        n = ct.dlg_proc(self.h, ct.DLG_CTL_ADD, 'label')
        ct.dlg_proc(self.h, ct.DLG_CTL_PROP_SET, index=n,
                    prop={
                        'name': 'grp_label',
                        'p': 'parent',
                        'a_l': ('', '['),
                        'a_t': ('packages',']'),
                        'w_min': 80,
                        'sp_a': 3,
                        'sp_t': 6,
                        'cap': 'Group: ',  
                        }
                    )
                    
        self.n_del_group = ct.dlg_proc(self.h, ct.DLG_CTL_ADD, 'button')
        ct.dlg_proc(self.h, ct.DLG_CTL_PROP_SET, index=self.n_del_group,
                    prop={
                        'name': 'del_group',
                        'p': 'parent',
                        'a_l': None,
                        'a_t': ('grp_label','-'),
                        'a_r': ('',']'),
                        #'a_b': ('',']'),
                        #'w_min': 60,
                        #'w': 60,
                        'sp_a': 3,
                        #'sp_t': 6,
                        'cap': 'Delete...',  
                        'en': False,
                        'on_change': self._dlg_del_group,
                        }
                    )
                    
        self.n_groups = ct.dlg_proc(self.h, ct.DLG_CTL_ADD, 'combo_ro')
        ct.dlg_proc(self.h, ct.DLG_CTL_PROP_SET, index=self.n_groups,
                    prop={
                        'name': 'groups',
                        'p': 'parent',
                        'a_l': ('grp_label', ']'),
                        'a_t': ('grp_label','-'),
                        'a_r': ('del_group','['),
                        'sp_a': 3,
                        'act': True,
                        'on_change': self._on_group_selected,
                        'en': False,
                        }
                    )
                    
        # lexer
        n = ct.dlg_proc(self.h, ct.DLG_CTL_ADD, 'label')
        ct.dlg_proc(self.h, ct.DLG_CTL_PROP_SET, index=n,
                    prop={
                        'name': 'lex_label',
                        'p': 'parent',
                        'a_l': ('', '['),
                        'a_t': ('groups',']'),
                        'w_min': 80,
                        'sp_a': 3,
                        'sp_t': 6,
                        'sp_l': 30,
                        'cap': 'Group\'s lexers: ',  
                        }
                    )
                    
        self.n_add_lex = ct.dlg_proc(self.h, ct.DLG_CTL_ADD, 'button')
        ct.dlg_proc(self.h, ct.DLG_CTL_PROP_SET, index=self.n_add_lex,
                    prop={
                        'name': 'add_lex',
                        'p': 'parent',
                        'a_l': None,
                        'a_t': ('lex_label','-'),
                        'a_r': ('',']'),
                        #'a_b': ('',']'),
                        #'w_min': 60,
                        #'w': 60,
                        'sp_a': 3,
                        #'sp_t': 6,
                        'cap': 'Add Lexer...',  
                        'en': False,
                        'on_change': self._menu_add_lex,
                        }
                    )
                    
        self.n_lex = ct.dlg_proc(self.h, ct.DLG_CTL_ADD, 'edit')
        ct.dlg_proc(self.h, ct.DLG_CTL_PROP_SET, index=self.n_lex,
                    prop={
                        'name': 'lexers',
                        'p': 'parent',
                        'a_l': ('lex_label', ']'),
                        'a_t': ('lex_label','-'),
                        'a_r': ('add_lex','['),
                        'sp_a': 3,
                        'en': False,
                        }
                    )
                    
        # snippet
        n = ct.dlg_proc(self.h, ct.DLG_CTL_ADD, 'label')
        ct.dlg_proc(self.h, ct.DLG_CTL_PROP_SET, index=n,
                    prop={
                        'name': 'snip_label',
                        'p': 'parent',
                        'a_l': ('', '['),
                        'a_t': ('lexers',']'),
                        'w_min': 80,
                        'sp_a': 3,
                        'sp_t': 6,
                        'cap': 'Snippet: ',  
                        }
                    )
                    
        self.n_del_snip = ct.dlg_proc(self.h, ct.DLG_CTL_ADD, 'button')
        ct.dlg_proc(self.h, ct.DLG_CTL_PROP_SET, index=self.n_del_snip,
                    prop={
                        'name': 'del_snip',
                        'p': 'parent',
                        'a_l': None,
                        'a_t': ('snip_label','-'),
                        'a_r': ('',']'),
                        #'a_b': ('',']'),
                        #'w_min': 60,
                        #'w': 60,
                        'sp_a': 3,
                        #'sp_t': 6,
                        'cap': 'Delete...',  
                        'en': False,
                        'on_change': self._dlg_del_snip,
                        }
                    )
                    
        self.n_snippets = ct.dlg_proc(self.h, ct.DLG_CTL_ADD, 'combo_ro')
        ct.dlg_proc(self.h, ct.DLG_CTL_PROP_SET, index=self.n_snippets,
                    prop={
                        'name': 'snippets',
                        'p': 'parent',
                        'a_l': ('snip_label', ']'),
                        'a_t': ('snip_label','-'),
                        'a_r': ('del_snip','['),
                        'sp_a': 3,
                        'on_change': self._on_snippet_selected,
                        'act': True,
                        'en': False,
                        'cap': 'lol?',
                        'hint': 'crap!',
                        }
                    )
                    
        # alias
        n = ct.dlg_proc(self.h, ct.DLG_CTL_ADD, 'label')
        ct.dlg_proc(self.h, ct.DLG_CTL_PROP_SET, index=n,
                    prop={
                        'name': 'alias_label',
                        'p': 'parent',
                        'a_l': ('', '['),
                        'a_t': ('snippets',']'),
                        'w_min': 80,
                        'sp_a': 3,
                        'sp_t': 6,
                        'sp_l': 30,
                        'cap': 'Snippet\'s alias: ',  
                        }
                    )
                    
        self.n_alias = ct.dlg_proc(self.h, ct.DLG_CTL_ADD, 'edit')
        ct.dlg_proc(self.h, ct.DLG_CTL_PROP_SET, index=self.n_alias,
                    prop={
                        'name': 'alias',
                        'p': 'parent',
                        'a_l': ('alias_label', ']'),
                        'a_t': ('alias_label','-'),
                        'a_r': ('',']'),
                        'sp_a': 3,
                        'en': False,
                        }
                    )
        
                    
        self.n_edit = ct.dlg_proc(self.h, ct.DLG_CTL_ADD, 'editor')
        ct.dlg_proc(self.h, ct.DLG_CTL_PROP_SET, index=self.n_edit,
                    prop={
                        'name': 'editor',
                        'p': 'parent',
                        'a_l': ('', '['),
                        'a_t': ('alias',']'),
                        'a_r': ('',']'),
                        'a_b': ('',']'),
                        'sp_a': 3,
                        'sp_t': 6,
                        'en': False
                        }
                    )
        h_ed = ct.dlg_proc(self.h, ct.DLG_CTL_HANDLE, index=self.n_edit)
        self.ed = ct.Editor(h_ed)
        self.ed.set_prop(ct.PROP_NEWLINE, 'lf') # for ease of splitting to lines
        self.ed.set_prop(ct.PROP_UNPRINTED_SHOW, True)
        self.ed.set_prop(ct.PROP_UNPRINTED_SPACES, True)
        self.ed.set_prop(ct.PROP_TAB_SPACES, False)
        self.ed.set_prop(ct.PROP_GUTTER_BM, False)
        self.ed.set_prop(ct.PROP_MODERN_SCROLLBAR, False)
                    
        self._fill_forms(init_lex_sel=self.select_lex) # select first group with specified lexer if any
        
    def _fill_forms(self, init_lex_sel=None, sel_pkg_path=None, sel_group=None, sel_snip=None):
        # fill packages
        items = [pkg.get('name') for pkg in self.packages]
        self.pkg_items = [*items] #TODO use
        
        # select first group with <lexer>
        if init_lex_sel:
            found = False
            for pkg in self.packages:
                for fn,lexs in pkg.get('files', {}).items():
                    if init_lex_sel in lexs:
                        if not found:
                            found = True
                            sel_pkg_path = pkg['path']
                            sel_group = fn
                        break
                if found:
                    break
        # select package with specified lexer
        if self.select_lex:
            for i,pkg in enumerate(self.packages):
                for fn,lexs in pkg.get('files', {}).items():
                    if self.select_lex in lexs:
                        items[i] += f'   (*{self.select_lex})'
                        break
        
        items.insert(0, '[New...]')
        items = '\t'.join(items)
        props = {'items': items,}
        
        sel_pkg_ind = -1
        sel_pkg = None
        # select package, if specified
        if sel_pkg_path: # select new package:
            # fine selected package
            for i,pkg in enumerate(self.packages):
                if pkg['path'] == sel_pkg_path:
                    sel_pkg_ind = i
                    sel_pkg = pkg
                    props['val'] = 1 + sel_pkg_ind
                    break
                    
        ct.dlg_proc(self.h, ct.DLG_CTL_PROP_SET, index=self.n_package, prop=props)
        self._on_package_selected(-1,-1)

        # select group
        if sel_pkg != None  and sel_group  and sel_group in sel_pkg.get('files', {}):
            sel_group_ind = 1 + self._groups_items.index(sel_group)
            ct.dlg_proc(self.h, ct.DLG_CTL_PROP_SET, index=self.n_groups, prop={'val': sel_group_ind})
            self._on_group_selected(-1,-1)
            
            # select snippet
            if sel_snip != None  and sel_snip in self.snip_items:
                sel_snip_ind = 1 + self.snip_items.index(sel_snip)
                ct.dlg_proc(self.h, ct.DLG_CTL_PROP_SET, index=self.n_snippets, prop={'val': sel_snip_ind})
                self._on_snippet_selected(-1,-1)
            

    def show_add_snip(self):
        ct.dlg_proc(self.h, ct.DLG_SHOW_MODAL)
        #ct.dlg_proc(self.h, ct.DLG_SHOW_NONMODAL)
        ct.dlg_proc(self.h, ct.DLG_FREE)
        '!!! changed'
        #import sys
        #sys.exit(0)
        return False

    def _save_changes(self, *args, **vargs):
        print(f'saving changes: {self.modified}')
        
        pkg = self._get_sel_pkg()
        snips_fn,lexers = self._get_sel_group(pkg)
        #snips = self.file_snippets.get(pkg['path'])
        snip_name,snip = self._get_sel_snip(pkg, snips_fn)  if lexers != None else  (None,None)
        
        print(f' + {pkg["name"]} # {snips_fn}, [{lexers}] # <{snip_name}>:<{snip}>')
        
        ### load data from form
        # check if modified group's lexers
        if snips_fn != None and lexers != None:
            oldlexes = pkg["files"][snips_fn]
            p = ct.dlg_proc(self.h, ct.DLG_CTL_PROP_GET, index=self.n_lex)
            newlexs = [lex.strip() for lex in p['val'].split(',') if lex.strip()]
            if oldlexes != newlexs:
                print(f'* lexs changed: [{oldlexes}] => [{newlexs}]')
                pkg['files'][snips_fn] = newlexs
                self.modified.append((TYPE_PKG, pkg['path']))
            else:
                print(f' * lexs same: {newlexs}')

            # check if modified snippet (alias|body)  (only if group is selected)
            if snip_name != None  and snip != None:
                oldalias = snip.get('prefix')
                p = ct.dlg_proc(self.h, ct.DLG_CTL_PROP_GET, index=self.n_alias)
                newalias = p['val']
                if oldalias != newalias:
                    print(f'* snippet modified (alias): [{oldalias}] => [{newalias}]')
                    snip['prefix'] = newalias
                    self.modified.append((TYPE_GROUP, pkg['path'], snips_fn, snip_name))
                else:
                    print(f'* alias same: {newalias}')

                # check if modified snippet body
                oldbody = snip['body']
                newbody = self.ed.get_text_all().split('\n') # line end is always 'lf'
                if oldbody != newbody:
                    print('* snip body changed:\n{0}\n ==>>\n{1}'.format('\n'.join(oldbody), '\n'.join(newbody)))
                    if len(oldbody) != len(newbody):
                        print(f'  + len changed:{len(oldbody)} => {len(newbody)}')
                    else:
                        for old,new in zip(oldbody, newbody):
                            if old != new:
                                print(f'  + changed line: [{old}] => [{new}]')
                            else:
                                print(f'  + v [{old}]')

                    snip['body'] = newbody
                    self.modified.append((TYPE_GROUP, pkg['path'], snips_fn, snip_name)) 
                else:
                    print('* snip body same:\n{}'.format('\n'.join(newbody)))

        # save modified
        saved_files = set() # save each file only once
        for mod in self.modified:
            # lexers changed, created group, created package, deleted group 
            # -> save package config file
            if mod[0] == TYPE_PKG:
                type_,package_dir = mod
                path2pkg = {p['path']:p for p in self.packages  if p['path'] == package_dir}
                pkg_copy = {**path2pkg[package_dir]}
                del pkg_copy['path']
                 
                data = pkg_copy
                file_dst = os.path.join(package_dir, 'config.json')
            # snippet changed (alias, body), snippet created, deleted; created group
            # -> save snippets file
            elif mod[0] == TYPE_GROUP: 
                type_, package_dir, snips_fn, snip_name = [*mod, None][0:4] # fourth item is optional : None
                snips = self.file_snippets.get((package_dir, snips_fn))
                if snips == None:
                    print(f' ERR: trying to save snippets for unloaded group: {(package_dir, snips_fn)}')
                    continue
                    
                data = snips
                file_dst = os.path.join(package_dir, 'snippets', snips_fn)
            else:
                raise Exception('Invalid Modified type: {mod}')
            
            if file_dst in saved_files:
                print(f'* already saved, skipping: {file_dst}')
                continue
            saved_files.add(file_dst)
                
            if ALLOW_FILE_MODIFICATION:
                # DBG
                if not file_dst.startswith(DATA_DIR):
                    raise Exception('Saving to Wrong directory({mod}): {file_dst}')
                res = ct.msg_box('File modification allowed. Saving file:\n    '+file_dst}, 
                                                            ct.MB_OKCANCEL | ct.MB_ICONWARNING) 
                if res == ct.ID_OK:
                    print(f'*** saving data: {file_dst}')
                    
                    folder = os.path.dirname(file_dst)
                    if not os.path.exists(folder):
                        os.makedirs(folder)
                    
                    with open(file_dst, 'w', encoding='utf-8') as f:
                        json.dump(data, f, indent=2)
                    print(f'    saved...')

            else:
                print(f'! fake saving: {file_dst}:\n{json.dumps(data, indent=2)}')


    def _dismiss_dlg(self, *args, **vargs):
        ct.dlg_proc(self.h, ct.DLG_HIDE)
        #ct.dlg_proc(self.h, ct.DLG_FREE)
        
        
    def _on_snippet_selected(self, id_dlg, id_ctl, data='', info=''):
        print('snip sel')
        pkg = self._get_sel_pkg()
        snips_fn,lexers = self._get_sel_group(pkg)
        #snips = self.file_snippets.get(pkg['path'])
        snip_name,snip = self._get_sel_snip(pkg, snips_fn)
        
        if snip_name == 'new' and snip == None:
            self._create_snip(pkg, snips_fn)
            return

        print(f' snip sel:{snip_name}: {snip}')

        ct.dlg_proc(self.h, ct.DLG_CTL_PROP_SET, index=self.n_alias, prop={
                    'val': snip.get('prefix', ''),
                    'en': True,
                })
        ct.dlg_proc(self.h, ct.DLG_CTL_PROP_SET, index=self.n_edit, prop={
                    'en': True,
                })
        body = snip.get('body', [])
        txt = '\n'.join(body)  if type(body) == list else  body
        self.ed.set_text_all(txt)
        # enable del_snip btn
        ct.dlg_proc(self.h, ct.DLG_CTL_PROP_SET, index=self.n_del_snip, prop={'en': True})
                    
        
    def _on_group_selected(self, id_dlg, id_ctl, data='', info=''):
        print('group sel')
        #print(f'combo sel:{args}, {vargs}')
        # disable all below 'group'
        for n in [self.n_alias, self.n_edit] + [self.n_del_snip]:
            ct.dlg_proc(self.h, ct.DLG_CTL_PROP_SET, index=n, prop={
                        'val': None,
                        'en': False,
                    })
        self.ed.set_text_all('')
        
        pkg = self._get_sel_pkg()
        snips_fn,lexers = self._get_sel_group(pkg) 

        if snips_fn == 'new'  and lexers == None:
            self._create_group(pkg)
            return
        
        print(f' * selected B:group: {snips_fn}, lexers:{lexers}')

        if self.file_snippets.get((pkg['path'],snips_fn)) == None:
            self._load_package_snippets(pkg['path'])
            print(f'   + loaded group snips')

        
        ### fill groups
        # lexers
        ct.dlg_proc(self.h, ct.DLG_CTL_PROP_SET, index=self.n_lex, prop={
                    'val': ', '.join(lexers),
                    'en': True,
                })
                
        # snippet names
        snip_items = [name for name,val in self.file_snippets.get((pkg['path'],snips_fn)).items() 
                                                            if 'body' in val and 'prefix' in val]
        snip_items.sort()
        self.snip_items = [*snip_items]
        
        snip_items.insert(0, '[New...]')
        snip_items = '\t'.join(snip_items)
        ct.dlg_proc(self.h, ct.DLG_CTL_PROP_SET, index=self.n_snippets, prop={
                    'val': None, # selected item
                    'items': snip_items,
                    'en': True,
                })
        # enable del_group and add_lex btns
        ct.dlg_proc(self.h, ct.DLG_CTL_PROP_SET, index=self.n_del_group, prop={'en': True})
        ct.dlg_proc(self.h, ct.DLG_CTL_PROP_SET, index=self.n_add_lex, prop={'en': True})
        
    def _on_package_selected(self, id_dlg, id_ctl, data='', info=''):
    #def _on_package_selected(self, *args, **vargs):
        print('pkg sel')
        #print(f'combo sel:{args}, {vargs}')
        # disable all below 'group'
        disable_btns = [self.n_del_group, self.n_add_lex, self.n_del_snip]
        for n in [self.n_lex, self.n_snippets, self.n_alias, self.n_edit] + disable_btns:
            ct.dlg_proc(self.h, ct.DLG_CTL_PROP_SET, index=n, prop={
                        'val': None,
                        'en': False,
                        'items': None,
                    })
        self.ed.set_text_all('')
        
        pkg = self._get_sel_pkg()
        
        if pkg == 'new':
            changed = self._create_pkg()
            return
        elif pkg == None: # no package selected
            ct.dlg_proc(self.h, ct.DLG_CTL_PROP_SET, index=self.n_groups, prop={'en': False,})
            ct.dlg_proc(self.h, ct.DLG_CTL_PROP_SET, index=self.n_del_pkg, prop={'en': False,})
            return

        print(f' * selected pkg: {pkg["name"]}')

        # fill groups
        items = list(pkg['files'])
        items.sort()
        self._groups_items = [*items] #TODO reset when resetting
        
        # select package with specified lexer
        if self.select_lex and items:
            for i,lexs in enumerate(pkg.get('files', {}).values()):
                if self.select_lex in lexs:
                    items[i] += f'   (*{self.select_lex})'
        
        items.insert(0, '[New...]')
        items = '\t'.join(items)
        ct.dlg_proc(self.h, ct.DLG_CTL_PROP_SET, index=self.n_groups, prop={
                    'val': None,
                    'en': True,
                    'items': items,
                })
        ct.dlg_proc(self.h, ct.DLG_CTL_PROP_SET, index=self.n_del_pkg, prop={'en': True})
                
    def _create_snip(self, pkg, snips_fn):
        print(f' ~~~ new C:snip ~~~: {pkg["path"]};  group:{snips_fn}')
        name = ct.dlg_input('New snippet name:', '')
        print(f' snip name: {name}')

        
        #TODO check if exists
        if name:
            snips = self.file_snippets.get((pkg['path'], snips_fn))
            print(f'  snips:{snips}')

            if snips != None:
                snips[name] = {'prefix':name, 'body':''}
                self.modified.append((TYPE_GROUP, pkg['path'], snips_fn, name))
                
                # select new snip
                self._fill_forms(sel_pkg_path=pkg['path'], sel_group=snips_fn, sel_snip=name)
                
                
    def _create_group(self, pkg):
        print(f' ~~~ create new B:Group ===')
        lex = ct.ed.get_prop(ct.PROP_LEXER_FILE)
        name = lex  if lex else  'snippets'
        #TODO check if exists
        name = ct.dlg_input('New snippet group name:', name)
        print(f'new group name:{name}')
            
        if name: #TODO add to modifieds (group and package)
            if not name.endswith('.json'):
                name += '.json'
            if name in pkg:
                print(f'package already has group {name}')
            
            pkg['files'][name] = [lex]
            self.file_snippets[(pkg['path'], name)] = {} #TODO check if exists
            self.modified.append((TYPE_PKG, pkg['path']))
            self.modified.append((TYPE_GROUP, pkg['path'], name))
            
            # select new group
            self._fill_forms(sel_pkg_path=pkg['path'], sel_group=name)
            
    #TODO check if exists
    def _create_pkg(self):
        print(f' ~~~ create new package ===') # TODO sort after new, select new
        lex = ct.ed.get_prop(ct.PROP_LEXER_FILE)
        name = 'New_'+lex  if lex else  'NewPackage'
        name = ct.dlg_input('New package name:', name)
        print(f'new pkg name:{name}')

            
        if name: #TODO add to modifieds
            newpkg = {'name': name,
                        'files': {}, 
                        'path': os.path.join(MAIN_SNIP_DIR, name)}
            self.packages.append(newpkg) # update packages and select new
            self._sort_pkgs()
            self.modified.append((TYPE_PKG, newpkg['path']))
            # select new package
            self._fill_forms(sel_pkg_path=newpkg['path'])
            
    def _dlg_del_pkg(self, *args, **vargs):
        ''' show directory path to delete with OK|Cancel
            + remove from 'self.packages' if confirmed
        '''
        print(f' del pkg {args};; {vargs}')
        pkg = self._get_sel_pkg()
        if not pkg:
            return
        res = ct.dlg_input('To delete package "{}" - delete the following directory:'.format(pkg['name']), pkg['path'])
        if res != None: # removeing
            print('* confermed package deletion')
            self.packages.remove(pkg)
            self._fill_forms()
            
    def _dlg_del_group(self, *args, **vargs):
        ''' show group file to delete with OK|Cancel
            + remove from package cfg
            + queue save of package cfg file
        '''
        print(f' del group {args};; {vargs}')
        pkg = self._get_sel_pkg()
        snips_fn,lexers = self._get_sel_group(pkg)
        
        if (pkg and pkg != 'new')  and (snips_fn and snips_fn != 'new'):
            fstr = 'To delete snippet group "{0}" from package "{1}" - delete the following file:'
            group_filepath = os.path.join(pkg['path'], 'snippets', snips_fn)
            res = ct.dlg_input(fstr.format(snips_fn, pkg['name']), group_filepath)
            if res != None:
                print('* confermed package deletion')
                del pkg['files'][snips_fn]
                self.modified.append((TYPE_PKG, pkg['path'])) # package config is modified
                self._fill_forms(sel_pkg_path=pkg['path'])
        
            
    def _menu_add_lex(self, *args, lex=None, **vargs):
        ''' 
        '''
        if lex == None: # initial call: show menu
            lexs = ct.lexer_proc(ct.LEXER_GET_LEXERS, '')
            
            h_menu = ct.menu_proc(0, ct.MENU_CREATE)
            for lex in lexs: 
                ct.menu_proc(h_menu, ct.MENU_ADD, command=lambda l=lex: self._menu_add_lex(lex=l), caption=lex)
            ct.menu_proc(h_menu, ct.MENU_SHOW)
            
        else: # add specified lexer
            p = ct.dlg_proc(self.h, ct.DLG_CTL_PROP_GET, index=self.n_lex)
            val = p['val']
            newval = lex  if not val else  val +', '+ lex
            p = ct.dlg_proc(self.h, ct.DLG_CTL_PROP_SET, index=self.n_lex, prop={'val':newval})
        
            
    def _dlg_del_snip(self, *args, **vargs):
        ''' dlg OK|Cancel
            + remove from 'self.file_snippets' 
            + queue save of snippet group file
        '''
        print(f' del snip {args};; {vargs}')
        pkg = self._get_sel_pkg()
        snips_fn,lexers = self._get_sel_group(pkg)
        snip_name,snip = self._get_sel_snip(pkg, snips_fn)
        
        if (pkg and pkg != 'new')  and (snips_fn and snips_fn != 'new'):
            if snip_name and not (snip_name == 'new' and snip == None):
                res = ct.msg_box('Delete snippet "{0}"?'.format(snip_name), ct.MB_OKCANCEL | ct.MB_ICONWARNING)
                if res == ct.ID_OK:
                    snips = self.file_snippets.get((pkg['path'], snips_fn))
                    if snip_name in snips: # removing from snips dict
                        del snips[snip_name]
                        self.modified.append((TYPE_GROUP, pkg['path'], snips_fn, snip_name))
                        self._fill_forms(sel_pkg_path=pkg['path'], sel_group=snips_fn)
                        
        
    def _load_package_snippets(self, package_path):
        for pkg in self.packages:
            if pkg.get('path') != package_path:
                continue
            for snips_fn in pkg.get('files', {}): # filename, lexers
                snips_path = os.path.join(package_path, 'snippets', snips_fn)
                if not os.path.exists(snips_path):
                    print(f' ERR: snips_path not file:{snips_path}')
                    continue
                
                with open(snips_path, 'r', encoding='utf-8') as f:
                    snips = json.load(f)
                print(f' * loaded snips:{len(snips)}')

                self.file_snippets[(package_path,snips_fn)] = snips
            return
        else:
            print(' ERR: no suck pkg: {package_path}')

        
    def _load_packages(self):
        res = [] # list of configs
        for path in SNIP_DIRS:
            if not os.path.exists(path):
                return
            for pkg in os.scandir(path):
                if not pkg.is_dir():
                    continue
                cfg_path = os.path.join(pkg, 'config.json')
                if not os.path.exists(cfg_path):
                    print("{} - it isn't package".format(cfg_path))
                    return
                    
                with open(cfg_path, 'r', encoding='utf8') as f:
                    cfg = json.load(f)
                #lexers = set()
                #for lx in cfg.get('files', {}).values():
                    #lexers.update(lx)
                #cfg.update(
                    #{'path': pkg, 'type': sn_type, 'lexers': lexers, 'loaded': False}
                #)
                cfg['path'] = pkg.path #TODO remove path before saving
                res.append(cfg)
        return res
        
    def _sort_pkgs(self):
        self.packages.sort(key=lambda pkg: pkg.get('name'))
        
    def _get_sel_snip(self, pkg, snip_fn):
        p = ct.dlg_proc(self.h, ct.DLG_CTL_PROP_GET, index=self.n_snippets)
        isel = int(p['val'])
        if isel < 0:
            return None,None
        elif isel == 0:
            return 'new',None
        else:
            name = self.snip_items[isel-1] # new is first
            snip = self.file_snippets[(pkg['path'], snip_fn)][name]
            return name,snip
        
    def _get_sel_group(self, pkg):
        p = ct.dlg_proc(self.h, ct.DLG_CTL_PROP_GET, index=self.n_groups)
        isel = int(p['val'])
        if isel < 0:
            return None,None
        elif isel == 0:
            return 'new',None
        else:
            filename = self._groups_items[isel-1]
            lexers = pkg['files'][filename]
            return filename,lexers
        
    def _get_sel_pkg(self):
        p = ct.dlg_proc(self.h, ct.DLG_CTL_PROP_GET, index=self.n_package)
        isel = int(p['val'])
        if isel < 0:
            return None
        if isel == 0:
            return 'new'
        else:
            return self.packages[isel-1]
        
    
