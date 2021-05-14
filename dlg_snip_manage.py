import os
import json

#DBG
import datetime

import cudatext as ct
from cuda_snippets import vs

from cudax_lib import get_translation
_   = get_translation(__file__)  # I18N


DATA_DIR = ct.app_path(ct.APP_DIR_DATA)
MAIN_SNIP_DIR = os.path.join(DATA_DIR, 'snippets_ct')
SNIP_DIRS = [
    MAIN_SNIP_DIR,
    os.path.join(DATA_DIR, 'snippets_vs'),
]

TYPE_PKG = 101
TYPE_GROUP = 102


HELP_TEXT = _("""Markers:
    ${NN} | ${NN:default text}

Macros:
    ${sel} - Text selected before snippet insertion (if snippet called with Tab key, it's empty string)
    ${cp} - Current clipboard contents

    ${cmt_start} - Current lexer's "block comment" start symbols (or empty string)
    ${cmt_end} - Current lexer's "block comment" end symbols (or empty string)
    ${cmt_line} - Current lexer's "line comment" symbols (or empty string)

    ${fname} - File name only, without path
    ${fpath} - Full file name, with path
    ${fdir} - Directory of file
    ${fext} - Extension of file
    ${psep} - OS path separator: backslash on Windows, slash on Unix

    ${date:nnnn} - Current date/time formatted by string "nnnn"; see Python docs
    ${env:nnnn} - Value of OS environment variable "nnnn"
    
Sublime ($NAME | ${NAME}):
    $TM_SELECTED_TEXT - The currently selected text or the empty string
    $TM_CURRENT_LINE - The contents of the current line
    $TM_CURRENT_WORD - The contents of the word under cursor or the empty string
    $TM_LINE_INDEX - The zero-based line number
    $TM_LINE_NUMBER - The one-based line number
    $TM_FILEPATH - The full file path of the current document
    $TM_DIRECTORY - The directory of the current document
    $TM_FILENAME - The filename of the current document
    $TM_FILENAME_BASE - The filename of the current document without its extensions
    $CLIPBOARD - The contents of your clipboard
    $WORKSPACE_NAME - The name of the opened workspace or folder

    $BLOCK_COMMENT_START - Current lexer's "block comment" start symbols (or empty string)
    $BLOCK_COMMENT_END - Current lexer's "block comment" end symbols (or empty string)
    $LINE_COMMENT - Current lexer's "line comment" symbols (or empty string)
    
Date, time:
    $CURRENT_YEAR - The current year
    $CURRENT_YEAR_SHORT - The current year's last two digits
    $CURRENT_MONTH - The month as two digits (e.g. '02')
    $CURRENT_MONTH_NAME - The full name of the month (e.g. 'July')
    $CURRENT_MONTH_NAME_SHORT - The short name of the month (e.g. 'Jul')
    $CURRENT_DATE - The day of the month
    $CURRENT_DAY_NAME - The name of day (e.g. 'Monday')
    $CURRENT_DAY_NAME_SHORT - The short name of the day (e.g. 'Mon')
    $CURRENT_HOUR - The current hour in 24-hour clock format
    $CURRENT_MINUTE - The current minute
    $CURRENT_SECOND - The current second
    $CURRENT_SECONDS_UNIX - The number of seconds since the Unix epoch
""")


class DlgSnipMan:
    def __init__(self, select_lex=None):
        self.select_lex = select_lex # select first group with this lexer, mark in menus
        
        self.snippets_changed = False
        self.h_help = None
        
        self.packages = self._load_packages()
        self._sort_pkgs()
        self.file_snippets = {} # tuple (<pkg path>,<group>) : snippet dict
        self.modified = [] # (type, name)
    
        w, h = 530, 400  # w=500 is too small for translations
        bw, lw = 90, 80  # button width, label width
        self.h = ct.dlg_proc(0, ct.DLG_CREATE)
        ct.dlg_proc(self.h, ct.DLG_PROP_SET, 
                    prop={'cap': _('Manage snippets'),
                        'w_min': 5 * bw,
                        'w': w,
                        'h': h,
                        'resize': True,
                        }
                    )
                    
 
        ### Controls
        
        # Cancel | Ok | Help
        self.n_ok = ct.dlg_proc(self.h, ct.DLG_CTL_ADD, 'button')
        ct.dlg_proc(self.h, ct.DLG_CTL_PROP_SET, index=self.n_ok,
                    prop={
                        'name': 'ok',
                        'a_l': None,
                        'a_t': None,
                        'a_r': ('', ']'),
                        'a_b': ('',']'),
                        'w_min': bw,
                        'sp_a': 6,
                        'autosize': True,
                        'cap': _('OK'),  
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
                        'w_min': bw,
                        'sp_a': 6,
                        'autosize': True,
                        'cap': _('Cancel'),  
                        'on_change': self._dismiss_dlg,
                        }
                    )
                    
        n = ct.dlg_proc(self.h, ct.DLG_CTL_ADD, 'button')
        ct.dlg_proc(self.h, ct.DLG_CTL_PROP_SET, index=n,
                    prop={
                        'name': 'ed_lex',
                        'a_l': ('', '['),
                        'a_t': ('ok', '-'),
                        'a_r': None,
                        'a_b': ('',']'),
                        'w_min': bw,
                        'sp_a': 6,
                        'autosize': True,
                        'cap': _('Editor\'s Lexer'),  
                        'on_change': self._menu_ed_lex,
                        }
                    )
                    
        n = ct.dlg_proc(self.h, ct.DLG_CTL_ADD, 'button')
        ct.dlg_proc(self.h, ct.DLG_CTL_PROP_SET, index=n,
                    prop={
                        'name': 'help',
                        'a_l': ('ed_lex', ']'),
                        'a_t': ('ok', '-'),
                        'a_r': None,
                        'a_b': ('',']'),
                        'w_min': bw,
                        'sp_a': 6,
                        'sp_l': 10,
                        'autosize': True,
                        'cap': _('Macros Help'),  
                        'on_change': self._dlg_help,
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
                        'sp_a': 3,
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
                        'w_min': lw,
                        'sp_a': 3,
                        'sp_t': 6,
                        'cap': _('Package: '),  
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
                        'w_min': bw,
                        'sp_a': 3,
                        'cap': _('Delete...'),  
                        'en': False,
                        'on_change': self._dlg_del_pkg,
                        }
                    )
                    
        self.n_add_pkg = ct.dlg_proc(self.h, ct.DLG_CTL_ADD, 'button')
        ct.dlg_proc(self.h, ct.DLG_CTL_PROP_SET, index=self.n_add_pkg,
                    prop={
                        'name': 'add_pkg',
                        'p': 'parent',
                        'a_l': None,
                        'a_t': ('pkg_label','-'),
                        'a_r': ('del_pkg','['),
                        'w_min': bw,
                        'sp_a': 3,
                        'cap': _('Add...'),  
                        'en': True,
                        'on_change': self._create_pkg,
                        }
                    )
                    
        self.n_package = ct.dlg_proc(self.h, ct.DLG_CTL_ADD, 'combo_ro')
        ct.dlg_proc(self.h, ct.DLG_CTL_PROP_SET, index=self.n_package,
                    prop={
                        'name': 'packages',
                        'p': 'parent',
                        'a_l': ('pkg_label', ']'),
                        'a_t': ('pkg_label','-'),
                        'a_r': ('add_pkg','['),
                        'sp_a': 3,
                        'act': True,
                        'on_change': self._on_package_selected,
                        }
                    )
                    
        # group
        n = ct.dlg_proc(self.h, ct.DLG_CTL_ADD, 'label')
        ct.dlg_proc(self.h, ct.DLG_CTL_PROP_SET, index=n,
                    prop={
                        'name': 'grp_label',
                        'p': 'parent',
                        'a_l': ('', '['),
                        'a_t': ('packages',']'),
                        'w_min': lw,
                        'sp_a': 3,
                        'sp_t': 6,
                        'cap': _('Group: '),  
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
                        'w_min': bw,
                        'sp_a': 3,
                        'cap': _('Delete...'),  
                        'en': False,
                        'on_change': self._dlg_del_group,
                        }
                    )
                    
        self.n_add_group = ct.dlg_proc(self.h, ct.DLG_CTL_ADD, 'button')
        ct.dlg_proc(self.h, ct.DLG_CTL_PROP_SET, index=self.n_add_group,
                    prop={
                        'name': 'add_group',
                        'p': 'parent',
                        'a_l': None,
                        'a_t': ('grp_label','-'),
                        'a_r': ('del_group','['),
                        'w_min': bw,
                        'sp_a': 3,
                        'cap': _('Add...'),  
                        'en': False,
                        'on_change': self._create_group,
                        }
                    )
                    
        self.n_groups = ct.dlg_proc(self.h, ct.DLG_CTL_ADD, 'combo_ro')
        ct.dlg_proc(self.h, ct.DLG_CTL_PROP_SET, index=self.n_groups,
                    prop={
                        'name': 'groups',
                        'p': 'parent',
                        'a_l': ('grp_label', ']'),
                        'a_t': ('grp_label','-'),
                        'a_r': ('add_group','['),
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
                        'w_min': lw,
                        'sp_a': 3,
                        'sp_t': 6,
                        'sp_l': 30,
                        'cap': _('Group\'s lexers: '),  
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
                        'w_min': 2*bw + 3,
                        'sp_a': 3,
                        'cap': _('Add Lexer...'),  
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
                        'w_min': lw,
                        'sp_a': 3,
                        'sp_t': 6,
                        'cap': _('Snippet: '),  
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
                        'w_min': bw,
                        'sp_a': 3,
                        'cap': _('Delete...'),  
                        'en': False,
                        'on_change': self._dlg_del_snip,
                        }
                    )
                    
        self.n_add_snip = ct.dlg_proc(self.h, ct.DLG_CTL_ADD, 'button')
        ct.dlg_proc(self.h, ct.DLG_CTL_PROP_SET, index=self.n_add_snip,
                    prop={
                        'name': 'add_snip',
                        'p': 'parent',
                        'a_l': None,
                        'a_t': ('snip_label','-'),
                        'a_r': ('del_snip','['),
                        'w_min': bw,
                        'sp_a': 3,
                        'cap': _('Add...'),  
                        'en': False,
                        'on_change': self._create_snip,
                        }
                    )
                    
        self.n_snippets = ct.dlg_proc(self.h, ct.DLG_CTL_ADD, 'combo_ro')
        ct.dlg_proc(self.h, ct.DLG_CTL_PROP_SET, index=self.n_snippets,
                    prop={
                        'name': 'snippets',
                        'p': 'parent',
                        'a_l': ('snip_label', ']'),
                        'a_t': ('snip_label','-'),
                        'a_r': ('add_snip','['),
                        'sp_a': 3,
                        'on_change': self._on_snippet_selected,
                        'act': True,
                        'en': False,
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
                        'w_min': lw,
                        'sp_a': 3,
                        'sp_t': 6,
                        'sp_l': 30,
                        'cap': _('Snippet\'s alias: '),  
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
        # mark packages with specified lexer
        if self.select_lex:
            for i,pkg in enumerate(self.packages):
                for fn,lexs in pkg.get('files', {}).items():
                    if self.select_lex in lexs:
                        items[i] += '   (*{0})'.format(self.select_lex)
                        break
        
        items = '\t'.join(items)
        props = {'items': items,}
        
        sel_pkg_ind = -1
        sel_pkg = None
        # select package, if specified
        if sel_pkg_path: # select new package:
            # find selected package
            for i,pkg in enumerate(self.packages):
                if pkg['path'] == sel_pkg_path:
                    sel_pkg_ind = i
                    sel_pkg = pkg
                    props['val'] = sel_pkg_ind
                    break
                    
        ct.dlg_proc(self.h, ct.DLG_CTL_PROP_SET, index=self.n_package, prop=props)
        self._on_package_selected(-1,-1)

        # select group
        if sel_pkg is not None  and sel_group  and sel_group in sel_pkg.get('files', {}):
            sel_group_ind = self._groups_items.index(sel_group)
            ct.dlg_proc(self.h, ct.DLG_CTL_PROP_SET, index=self.n_groups, prop={'val': sel_group_ind})
            self._on_group_selected(-1,-1)
            
            # select snippet
            if sel_snip is not None  and sel_snip in self.snip_items:
                sel_snip_ind = self.snip_items.index(sel_snip)
                ct.dlg_proc(self.h, ct.DLG_CTL_PROP_SET, index=self.n_snippets, prop={'val': sel_snip_ind})
                self._on_snippet_selected(-1,-1)
            

    def show_add_snip(self):
        ct.dlg_proc(self.h, ct.DLG_SHOW_MODAL)
        ct.dlg_proc(self.h, ct.DLG_FREE)
        
        if self.h_help is not None:
            ct.dlg_proc(self.h_help, ct.DLG_FREE)
            
        return self.snippets_changed

    def _save_changes(self, *args, **vargs):
        print(_('Saving changes'))

        #pass; print('saving changes: {0}'.format(self.modified))
        
        pkg = self._get_sel_pkg()
        snips_fn,lexers = self._get_sel_group(pkg)
        snip_name,snip = self._get_sel_snip(pkg, snips_fn)  if lexers is not None else  (None,None)
        
        _pkg_name = pkg["name"]  if pkg else  "<no_pkg>"
        #pass; print(' + {} # {}, [{}] # <{}>:<{}>'.format(_pkg_name, snips_fn, lexers, snip_name, snip))
        
        ### load data from form
        # check if modified group's lexers
        if snips_fn is not None and lexers is not None:
            oldlexes = pkg["files"][snips_fn]
            p = ct.dlg_proc(self.h, ct.DLG_CTL_PROP_GET, index=self.n_lex)
            newlexs = [lex.strip() for lex in p['val'].split(',') if lex.strip()]
            if oldlexes != newlexs:
                print(_('* Group\'s lexers changed: [{0}] => [{1}]').format(oldlexes, newlexs))
                pkg['files'][snips_fn] = newlexs
                self.modified.append((TYPE_PKG, pkg['path']))

            # check if modified snippet (alias|body)  (only if group is selected)
            if snip_name is not None  and snip is not None:
                oldalias = snip.get('prefix')
                p = ct.dlg_proc(self.h, ct.DLG_CTL_PROP_GET, index=self.n_alias)
                newalias = p['val']
                if oldalias != newalias:
                    print(_('* snippet\'s alias changed: [{0}] => [{1}]').format(oldalias, newalias))
                    snip['prefix'] = newalias
                    self.modified.append((TYPE_GROUP, pkg['path'], snips_fn, snip_name))

                # check if modified snippet body
                oldbody = snip['body']
                newbody = self.ed.get_text_all().split('\n') # line end is always 'lf'
                if oldbody != newbody:
                    print(_('* snippet\'s body changed:\n{0}\n ==>>\n{1}').format('\n'.join(oldbody), '\n'.join(newbody)))
                    snip['body'] = newbody
                    self.modified.append((TYPE_GROUP, pkg['path'], snips_fn, snip_name)) 

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
                if snips is None:
                    print(_('! ERROR: trying to save snippets for unloaded group: {0}').format((package_dir, snips_fn)))
                    continue
                    
                data = snips
                file_dst = os.path.join(package_dir, 'snippets', snips_fn)
            else:
                raise Exception('Invalid Modified type: {mod}')
            
            if file_dst in saved_files:
                #pass; print('* already saved, skipping: {0}'.format(file_dst))
                continue
            saved_files.add(file_dst)
                
            #pass; print('*** saving data: {0}'.format(file_dst))
                    
            self.snippets_changed = True
                    
            folder = os.path.dirname(file_dst)
            if not os.path.exists(folder):
                os.makedirs(folder)
                    
            with open(file_dst, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2)
                
        if self.modified:    
            print('    '+_('Saved.'))
        
        ct.dlg_proc(self.h, ct.DLG_HIDE)


    def _dismiss_dlg(self, *args, **vargs):
        ct.dlg_proc(self.h, ct.DLG_HIDE)
        
        
    def _on_snippet_selected(self, id_dlg, id_ctl, data='', info=''):
        #pass; print('snip sel')
        pkg = self._get_sel_pkg()
        snips_fn,lexers = self._get_sel_group(pkg)
        snip_name,snip = self._get_sel_snip(pkg, snips_fn)

        #pass; print(' snip sel:{0}: {1}'.format(snip_name, snip))
        
        if not all((pkg, snips_fn, snip_name, snip)):
            return

        self._enable_ctls(True, self.n_alias, self.n_edit,  self.n_add_snip, self.n_del_snip)
        
        ct.dlg_proc(self.h, ct.DLG_CTL_PROP_SET, index=self.n_alias, prop={
                    'val': snip.get('prefix', ''),
                })
        body = snip.get('body', [])
        txt = '\n'.join(body)  if type(body) == list else  body
        self.ed.set_text_all(txt)
                    
        
    def _on_group_selected(self, id_dlg, id_ctl, data='', info=''):
        #pass; print('group sel')
        
        # disable all below 'group'
        self._enable_ctls(False, self.n_alias, self.n_edit,  self.n_add_snip, self.n_del_snip)
        
        self.ed.set_text_all('')
        
        pkg = self._get_sel_pkg()
        snips_fn,lexers = self._get_sel_group(pkg) 
        
        #pass; print(' * selected B:group: {0}, lexers:{1}'.format(snips_fn, lexers))
        
        if not pkg or not snips_fn:
            return

        if self.file_snippets.get((pkg['path'],snips_fn)) is None:
            self._load_package_snippets(pkg['path'])
            #pass; print('   + loaded group snips')

        
        # enable stuff
        self._enable_ctls(True, self.n_lex, self.n_snippets,  
                            self.n_add_group, self.n_del_group, self.n_add_lex, self.n_add_snip)
        
        ### fill groups
        # lexers
        ct.dlg_proc(self.h, ct.DLG_CTL_PROP_SET, index=self.n_lex, prop={
                    'val': ', '.join(lexers),
                })
                
        # snippet names
        snip_items = [name for name,val in self.file_snippets.get((pkg['path'],snips_fn)).items() 
                                                            if 'body' in val and 'prefix' in val]
        snip_items.sort()
        self.snip_items = [*snip_items]
        
        snip_items = '\t'.join(snip_items)
        ct.dlg_proc(self.h, ct.DLG_CTL_PROP_SET, index=self.n_snippets, prop={
                    'val': None, # selected item
                    'items': snip_items,
                })
        
        # set editor lexer to first existing lexer of snippet group
        if lexers:
            ed_lex = self.ed.get_prop(ct.PROP_LEXER_FILE)
            if not ed_lex  or ed_lex not in lexers: # dont change if current editor lex is in group
                app_lexs = ct.lexer_proc(ct.LEXER_GET_LEXERS, '')
                for lex in lexers:
                    if lex in app_lexs:
                        self.ed.set_prop(ct.PROP_LEXER_FILE, lex)
            
        
    def _on_package_selected(self, id_dlg, id_ctl, data='', info=''):
        #pass; print('pkg sel')
        # disable all below 'group'
        disable_btns = [self.n_add_group, self.n_del_group, self.n_add_lex, self.n_add_snip, self.n_del_snip]
        self._enable_ctls(False, self.n_lex, self.n_snippets, self.n_alias, self.n_edit,  *disable_btns)
        
        self.ed.set_text_all('')
        
        pkg = self._get_sel_pkg()
        
        if pkg is None: # no package selected
            for n in [self.n_groups,  self.n_del_pkg]:
                ct.dlg_proc(self.h, ct.DLG_CTL_PROP_SET, index=n, prop={'en': False,})
            self._groups_items = None
            return

        #pass; print(' * selected pkg: {0}'.format(pkg["name"]))

        # fill groups
        items = list(pkg['files'])
        items.sort()
        self._groups_items = [*items]
        
        # select package with specified lexer
        if self.select_lex and items:
            for i,lexs in enumerate(pkg.get('files', {}).values()):
                if self.select_lex in lexs:
                    items[i] += '   (*{0})'.format(self.select_lex)
        
        items = '\t'.join(items)
        
        self._enable_ctls(True, self.n_groups,  self.n_add_pkg, self.n_del_pkg, self.n_add_group)
        
        ct.dlg_proc(self.h, ct.DLG_CTL_PROP_SET, index=self.n_groups, prop={
                    'val': None,
                    'en': True,
                    'items': items,
                })
                
        # if have only one snip file - select it
        if id_dlg != -1  and len(pkg.get('files', {})) == 1: # -1 - called manually (from fill_forms())
            ct.dlg_proc(self.h, ct.DLG_CTL_PROP_SET, index=self.n_groups, prop={'val': 0})
            self._on_group_selected(-1,-1)
            
                
    #def _create_snip(self, pkg, snips_fn):
    def _create_snip(self, id_dlg, id_ctl, data='', info=''):
        pkg = self._get_sel_pkg()
        snips_fn,lexers = self._get_sel_group(pkg)
        if not pkg  or not snips_fn:
            return
        
        #pass; print(' ~~~ new C:snip ~~~: {0};  group:{1}'.format(pkg["path"], snips_fn))
        name = ct.dlg_input(_('New snippet name:'), '')
        #pass; print(' snip name: {0}'.format(name))

        if name:
            snips = self.file_snippets.get((pkg['path'], snips_fn)) # snippets of selected group will be loaded

            if snips is not None:
                if name not in snips:
                    snips[name] = {'prefix':name, 'body':''}
                    self.modified.append((TYPE_GROUP, pkg['path'], snips_fn, name))
                
                    # select new snip
                    self._fill_forms(sel_pkg_path=pkg['path'], sel_group=snips_fn, sel_snip=name)
                else:
                    print(_('"{0}" - snippet already exists.').format(name))
                
                
    #def _create_group(self, pkg):
    def _create_group(self, id_dlg, id_ctl, data='', info=''):
        pkg = self._get_sel_pkg()
        if not pkg:
            return
        
        #pass; print(' ~~~ create new B:Group ===')
        lex = ct.ed.get_prop(ct.PROP_LEXER_FILE)
        name = lex  if lex else  'snippets'
        name = ct.dlg_input(_('New snippet group filename:'), name)
        #pass; print('new group name:{0}'.format(name))
            
        if name:
            if not name.endswith('.json'):
                name += '.json'
            # checking for file in case of case-insensitive filesystem
            if os.path.exists(os.path.join(pkg['path'], 'snippets', name)):
                print(_('"{0}" - group already exists.').format(name))
                return
            
            pkg['files'][name] = [lex]
            self.file_snippets[(pkg['path'], name)] = {}
            self.modified.append((TYPE_PKG, pkg['path']))
            self.modified.append((TYPE_GROUP, pkg['path'], name))
            
            # select new group
            self._fill_forms(sel_pkg_path=pkg['path'], sel_group=name)
            
    def _create_pkg(self, id_dlg, id_ctl, data='', info=''):
        #pass; print(' ~~~ create new package ===')
        lex = ct.ed.get_prop(ct.PROP_LEXER_FILE)
        name = 'New_'+lex  if lex else  'NewPackage'
        name = ct.dlg_input(_('New package name (should be a valid directory name):'), name)
        #pass; print('new pkg name:{0}'.format(name))
            
        if name:
            newpkg = {'name': name,
                      'files': {}, 
                      'path': os.path.join(MAIN_SNIP_DIR, name)}
            
            if os.path.exists(os.path.join(MAIN_SNIP_DIR, name, 'config.json')):
                print(_('"{0}" - package already exists.').format(os.path.join(MAIN_SNIP_DIR, name, 'config.json')))
                return
                        
            self.packages.append(newpkg) # update packages and select new
            self._sort_pkgs()
            self.modified.append((TYPE_PKG, newpkg['path']))
            # select new package
            self._fill_forms(sel_pkg_path=newpkg['path'])
            
    def _dlg_del_pkg(self, *args, **vargs):
        ''' show directory path to delete with OK|Cancel
            + remove from 'self.packages' if confirmed
        '''
        #pass; print('del pkg {0};; {1}'.format(args, vargs))
        pkg = self._get_sel_pkg()
        if not pkg:
            return
        res = ct.dlg_input(_('To delete package "{}" - delete the following directory:').format(pkg['name']), pkg['path'])
        if res is not None: # removeing
            #pass; print('* confirmed package deletion')
            self.packages.remove(pkg)
            self._fill_forms()
            
    def _dlg_del_group(self, *args, **vargs):
        ''' show group file to delete with OK|Cancel
            + remove from package cfg
            + queue save of package cfg file
        '''
        #pass; print(' del group')
        pkg = self._get_sel_pkg()
        snips_fn,lexers = self._get_sel_group(pkg)
        
        if pkg  and snips_fn:
            fstr = _('To delete snippet group "{0}" from package "{1}" - delete the following file:')
            group_filepath = os.path.join(pkg['path'], 'snippets', snips_fn)
            res = ct.dlg_input(fstr.format(snips_fn, pkg['name']), group_filepath)
            if res is not None:
                #pass; print('* confirmed group deletion')
                del pkg['files'][snips_fn]
                self.modified.append((TYPE_PKG, pkg['path'])) # package config is modified
                self._fill_forms(sel_pkg_path=pkg['path'])
        
            
    def _menu_add_lex(self, *args, lex=None, **vargs):
        if lex is None: # initial call: show menu
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
        #pass; print(' del snip')
        pkg = self._get_sel_pkg()
        snips_fn,lexers = self._get_sel_group(pkg)
        snip_name,snip = self._get_sel_snip(pkg, snips_fn)
        
        if pkg  and snips_fn  and snip_name  and snip:
            res = ct.msg_box(_('Delete snippet "{0}"?').format(snip_name), ct.MB_OKCANCEL | ct.MB_ICONWARNING)
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
                    print(_('! ERROR: snippets path is not a file:{0}').format(snips_path))
                    continue
                
                with open(snips_path, 'r', encoding='utf-8') as f:
                    snips = json.load(f)
                #pass; print(' * loaded snips:{0}'.format(len(snips)))

                self.file_snippets[(package_path,snips_fn)] = snips
            return
        else:
            print(_('! ERROR: no such package: {0}').format(package_path))

        
    def _load_packages(self):
        res = [] # list of configs
        for path in SNIP_DIRS:
            if not os.path.exists(path):
                continue
            for pkg in os.scandir(path):
                if not pkg.is_dir():
                    continue
                cfg_path = os.path.join(pkg, 'config.json')
                if not os.path.exists(cfg_path):
                    print(_('! ERROR: {0} - is not a package').format(cfg_path))
                    continue
                    
                with open(cfg_path, 'r', encoding='utf8') as f:
                    cfg = json.load(f)
                cfg['path'] = pkg.path
                res.append(cfg)
        return res
        
    def _sort_pkgs(self):
        self.packages.sort(key=lambda pkg: pkg.get('name'))
        
    def _get_sel_snip(self, pkg, snip_fn):
        p = ct.dlg_proc(self.h, ct.DLG_CTL_PROP_GET, index=self.n_snippets)
        isel = int(p['val'])
        if isel < 0:
            return None,None
        else:
            name = self.snip_items[isel] 
            snip = self.file_snippets[(pkg['path'], snip_fn)][name]
            return name,snip
        
    def _get_sel_group(self, pkg):
        p = ct.dlg_proc(self.h, ct.DLG_CTL_PROP_GET, index=self.n_groups)
        isel = int(p['val'])
        if isel < 0:
            return None,None
        else:
            filename = self._groups_items[isel]
            lexers = pkg['files'][filename]
            return filename,lexers
        
    def _get_sel_pkg(self):
        p = ct.dlg_proc(self.h, ct.DLG_CTL_PROP_GET, index=self.n_package)
        isel = int(p['val'])
        if isel < 0:
            return None
        else:
            return self.packages[isel]
            
    def _menu_ed_lex(self, id_dlg, id_ctl, data='', info=''):
        pkg = self._get_sel_pkg()
        snips_fn,group_lexers = self._get_sel_group(pkg)
        
        group_lexers = set(group_lexers)  if group_lexers else  set()
        
        ### menu
        h_menu = ct.menu_proc(0, ct.MENU_CREATE)
        
        # fill
        app_lexs = ct.lexer_proc(ct.LEXER_GET_LEXERS, '')
        for lex in app_lexs:
            caption = '** '+lex  if lex in group_lexers else  lex # mark lexers of current snippet group
            command = lambda l=lex: self.ed.set_prop(ct.PROP_LEXER_FILE, l)
            ct.menu_proc(h_menu, ct.MENU_ADD, command=command, caption=caption)
            
        ct.menu_proc(h_menu, ct.MENU_SHOW)
        
    
    def _enable_ctls(self, enable, *ns):
        prop = {'en':enable, 'val': None, 'items': None,}
        for n in ns:
            ct.dlg_proc(self.h, ct.DLG_CTL_PROP_SET, index=n, prop=prop)
        
        
    def _dlg_help(self, *args, **vargs):
        if self.h_help is None:
            w, h = 750, 600
            self.h_help = ct.dlg_proc(0, ct.DLG_CREATE)
            ct.dlg_proc(self.h_help, ct.DLG_PROP_SET, 
                        prop={'cap': _('Syntax Help'),
                            'w': w,
                            'h': h,
                            'resize': True,
                            }
                        )
                    
            n = ct.dlg_proc(self.h_help, ct.DLG_CTL_ADD, 'memo')
            ct.dlg_proc(self.h_help, ct.DLG_CTL_PROP_SET, index=n,
                        prop={
                            'name': 'help_memo',
                            'align': ct.ALIGN_CLIENT,
                            'val': HELP_TEXT,
                            'sp_a':6,
                            }
                        )            
                    
        ct.dlg_proc(self.h_help, ct.DLG_SHOW_MODAL)

