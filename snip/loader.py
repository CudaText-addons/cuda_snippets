import json
import os
import re

from cuda_snippets.snip.utils import load_json
from cuda_snippets.snip.snippet import Snippet, CT_SNIPPET, VS_SNIPPET

# from cuda_dev import dev

from cudax_lib import get_translation
_   = get_translation(__file__)  # I18N

SNIP_EXTENSION = '.synw-snippet'
SNIP_EXTENSION2 = '.cuda-snippet'
SNIP_EXTENSION_ALT = '.cuda-snips'


def mkdir(*args):
    if not os.path.exists(args[0]):
        os.mkdir(*args)


def save_to_json(data, fp, sort_keys=False):
    with open(fp, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4, sort_keys=sort_keys)


def parse_vs_snippets_file(fp, lex, sn_type=VS_SNIPPET):
    """Parser for VSCode snippets file."""
    res = []

    def _add(k, v):
        try:
            t = v['body']
            if isinstance(t, str):
                t = t.splitlines()
            res.append(Snippet(name=k, id=v['prefix'], text=t, lex=lex, t=sn_type))
        except Exception:
            pass

    with open(fp, mode='r', encoding='utf-8', errors='replace') as f:
        data = load_json(f)
        for k, v in data.items():
            if not isinstance(v, dict):
                continue
            if ('prefix' in v) and ('body' in v):
                _add(k, v)
            else:
                for kk, vv in v.items():
                    _add(kk, vv)

    return res


def parse_snippet_file(fp):
    """Parser for standard CudaText snippet file"""
    with open(fp, mode='r', encoding='utf-8', errors='replace') as f:
        res = Snippet()
        res.type = CT_SNIPPET

        lines = f.read().splitlines()
        for index, line in enumerate(lines):
            if line == 'text=':
                res.text = [lines[i] for i in range(index + 1, len(lines))]
                break
            elif line.startswith('name='):
                res.name = line[5:]
            elif line.startswith('id='):
                _id = line[3:].strip(',')
                res.id = _id if isinstance(_id, list) else [_id]
            elif line.startswith('lex='):
                res.lex = line[4:].split(',')

        # check data correct
        if res.text and (res.id or res.name):
            return res
        else:
            return


def parse_simple_snippet_line(fp):
    """ Parse one-line snippet definition
            [word ][/L="My Lexer"] [/N="My Name"] text text
        If word is omitted then /N= is required.
        Quotes around lexer/name are required if value has blanks.
        Text part can has \t \n \r \\ to include chr(9) chr(10) chr(13) and '\' .
        Minimum line need to have two words or /N=name and text .
        Return
            {'id'  :'word',
             'name':'My Name',  # 'name':'word' if no /N= in line
             'lex' :'My Lexer', # 'lex' :''     if no /L= in line
             'text':['text text']
            }
    """
    def opt_val(line, opt, defv):
        optv = defv
        opt = opt if opt[0] == '/' else '/' + opt + '='
        mtch = re.match(opt + r'("[^"]+")', line)
        if mtch:
            optv = mtch.group(1)
            line = line.replace(opt + optv, '').lstrip()
            optv = optv.strip('"')
        else:
            mtch = re.match(opt + r'(\S+)', line)
            if mtch:
                optv = mtch.group(1)
                line = line.replace(opt + optv, '').lstrip()
        return optv, line

    res = []
    with open(fp, mode='r', encoding='utf-8', errors='replace') as f:
        for line in f.readlines():
            if not line or line[0] in ('#', ' '):
                continue

            if len(line.split()) < 2:
                continue

            key = line.split()[0] if line[:3] not in ('/N=', '/L=') else ''
            line = line[len(key):].lstrip()

            name = key
            lex = ''
            if line[:3] == '/N=':
                name, line = opt_val(line, 'N', defv=key)
            if line[:3] == '/L=':
                lex, line = opt_val(line, 'L', defv='')
            if line[:3] == '/N=':
                name, line = opt_val(line, 'N', defv=name)

            if not key and not name:
                continue

            body = line.lstrip()
            body = body.replace('\\\\', chr(0))
            body = body.replace('\\t', chr(9)).replace('\\n', chr(10)).replace('\\r', chr(13))
            body = body.replace(chr(0), '\\\\')

            if not body:
                continue
            res.append(Snippet(name=name, id=[key], lex=lex, text=body.splitlines(), t=CT_SNIPPET))
    return res


class Loader():
    def __init__(self, basedir):
        self.packages = []
        self.snippets = {}

        self.load_packages_cfg(os.path.join(basedir, 'snippets_ct'), CT_SNIPPET)
        self.load_packages_cfg(os.path.join(basedir, 'snippets_vs'), VS_SNIPPET)

    def load_by_lexer(self, lex):
        for pkg in self.packages:
            pkg_lexers = pkg['lexers']
            if not pkg['loaded'] and ('*' in pkg_lexers or lex in pkg_lexers):
                self.load_pkg(pkg)
        return self.snippets.get(lex, []) + self.snippets.get('*', [])

    def load_all(self):
        for pkg in self.packages:
            self.load_pkg(pkg)

    def load_pkg(self, pkg):
        path = pkg['path']
        files = pkg.get('files', {})
        for fn, lexs in files.items():
            fp = os.path.join(path, 'snippets', fn)
            _snips = parse_vs_snippets_file(fp, lexs, pkg['type'])
            for lx in lexs:
                self.snippets.setdefault(lx, []).extend(_snips)
        pkg['loaded'] = True

    def load_packages_cfg(self, path, sn_type):
        if not os.path.exists(path):
            return
        for pkg in os.scandir(path):
            if not pkg.is_dir():
                continue
            cfg_path = os.path.join(pkg, 'config.json')
            if not os.path.exists(cfg_path):
                print(_("{} - it isn't package").format(cfg_path))
                return
            with open(cfg_path, 'r', encoding='utf-8', errors='replace') as _cfg:
                cfg = json.load(_cfg)
            lexers = set()
            for lx in cfg.get('files', {}).values():
                lexers.update(lx)
            cfg.update(
                {'path': pkg, 'type': sn_type, 'lexers': lexers, 'loaded': False}
            )
            self.packages.append(cfg)


def convert_old_pkg(old_pkg, sn_ct_dir):
    config = {}
    name = os.path.basename(old_pkg)
    config['name'] = name

    snips = {}
    glob = []

    for sn in os.scandir(old_pkg):
        if sn.path.endswith(SNIP_EXTENSION) or sn.path.endswith(SNIP_EXTENSION2):
            res = parse_snippet_file(sn)
            if res:
                if res.lex:
                    lx = res.lex if isinstance(res.lex, str) else ','.join(res.lex)
                    snips.setdefault(lx, []).append(res)
                else:
                    glob.append(res)
        if sn.path.endswith(SNIP_EXTENSION_ALT):
            for res in parse_simple_snippet_line(sn):
                if res.lex:
                    lx = res.lex if isinstance(res.lex, str) else ','.join(res.lex)
                    snips.setdefault(lx, []).append(res)
                else:
                    glob.append(res)

    print("{}".format(old_pkg))
    if snips or glob:
        # shutil.rmtree(old_pkg)
        mkdir(sn_ct_dir)
        # make new snippets package folder
        new_pkg = os.path.join(sn_ct_dir, name)
        mkdir(new_pkg)
        mkdir(os.path.join(new_pkg, "snippets"))

        for lex in snips:
            # dev(f'{lex}={len(snips[lex])}')
            sn_f = {sn._name: {"prefix": sn.id, "body": sn.text} for sn in snips[lex]}
            # dev(sn_f)
            file_name = lex + '.json'
            save_to_json(sn_f, os.path.join(new_pkg, "snippets", file_name), sort_keys=True)
            config.setdefault('files', {}).update({file_name: lex.split(',')})
        # save config.json
        save_to_json(config, os.path.join(new_pkg, 'config.json'))
        print(_("Package of snippets converted."))
    else:
        print(_("It is not a snippets package."))


if __name__ == '__main__':
    pass

    # dev.tstart()
    # ld = Loader(r"b:\TC_LOM\Plugins\exe\Cudatext\data")
    # dev.tstop()

    # dev.tstart()
    # ld.load_by_lexer('Python')
    # dev.tstop()

    # dev.tstart()
    # ld.load_by_lexer('Python')
    # dev.tstop()

    # dev.tstart()
    # ld.load_all()
    # dev.tstop()
