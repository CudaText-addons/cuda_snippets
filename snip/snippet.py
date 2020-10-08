import re
import typing
from collections import OrderedDict
from os import path as op
from time import strftime, time

import cudatext as ct
import cudatext_cmd
# from cuda_dev import dev

TABSTOP = 0
PLACEHOLDER = 1
RE_TOKEN_PART = re.compile(r"(?<!\\)\$\d+|\${\d+:|\${|}")
RE_DATE = re.compile(r'\${date:(.*?)}')

_tabstop = r"\$(\d+)"
_placeholder_head = r"\${(\d+):?"
_placeholder_tail = "}"
RE_TABSTOP = re.compile(_tabstop)
RE_PLACEHOLDER = re.compile(_placeholder_head)
RE_TOKEN_PART = re.compile(r"(?<!\\)"+_tabstop+'|'+_placeholder_head+'|'+_placeholder_tail)


# https://code.visualstudio.com/docs/editor/userdefinedsnippets?wt.mc_id=devto-blog-chnoring


def is_tabstop(s):
    m = RE_TABSTOP.match(s)
    if not m:
        return False
    elif m[0] == s:
        return True
    else:
        return False


def is_placeholder_head(s):
    m = RE_PLACEHOLDER.match(s)
    if not m:
        return False
    elif m[0] == s:
        return True
    else:
        return False


def is_placeholder_tail(s):
    return True if s == '}' else False


def get_word_under_cursor(line, x, seps='.,:-!<>()[]{}\'"\t\n\r'):
    """get current word under cursor position"""
    if not 0 <= x <= len(line):
        return '', 0
    for sep in seps:
        if sep in line:
            line = line.replace(sep, ' ')
    s = ' ' + line + ' '
    start = s.rfind(' ', 0, x+1)
    end = s.find(' ', x+1) - 1
    word = line[start:end]
    return word, x - start  # word, position cursor in word


def marker(x=0, y=0, tag=0, len_x=0, len_y=0):
    return {
        'id': ct.MARKERS_ADD,
        'x': x,
        'y': y,
        'tag': tag,
        'len_x': len_x,
        'len_y': len_y
    }


class Placeholder:
    __slots__ = ['x0', 'x1', 'y', 'shift', 'tag']

    def __init__(self, x0, x1, y, shift, tag):
        self.x0 = x0
        self.x1 = x1
        self.y = y
        self.shift = shift
        self.tag = tag


class Snippet:
    """Base snippet class."""
    __slots__ = ['name', 'id', 'lex', 'text']

    def __init__(self, name='', id: typing.List = '', lex='', text=None):
        self.name = name
        self.id = id if isinstance(id, list) else [id]
        self.lex = lex
        self.text = [text] if isinstance(text, str) else text

    def __repr__(self):
        lex = ', '.join(self.lex) if isinstance(self.lex, list) else self.lex
        _id = ', '.join(self.id)
        return self.name + '\t' + _id + '  [' + lex + ']'

    def __eq__(self, o):
        return self is o

    def __ne__(self, o):
        return self is not o

    def __lt__(self, o):
        return self.name < o.name

    def insert(self, ed: ct.Editor):
        if not self.text:
            return
        sn = self.text.copy()

        carets = ed.get_carets()
        if len(carets) != 1:
            return
        x0, y0, x1, y1 = carets[0]

        tab_spaces = ed.get_prop(ct.PROP_TAB_SPACES)
        tab_size = ed.get_prop(ct.PROP_TAB_SIZE)

        # apply indent to lines from second
        x_col, _ = ed.convert(ct.CONVERT_CHAR_TO_COL, x0, y0)
        indent = ' ' * x_col
        if not tab_spaces:
            indent = indent.replace(' ' * tab_size, '\t')
        for i in range(1, len(sn)):
            sn[i] = indent + sn[i]

        # replace tab-chars
        if tab_spaces:
            indent = ' ' * tab_size
            sn = [item.replace('\t', indent) for item in sn]

        # parse variables
        sn = self.parse_vars_vs(ed, sn)

        # delete selection
        text_sel = ed.get_text_sel()
        if text_sel:
            # sort coords (x0/y0 is left)
            if (y1 > y0) or ((y1 == y0) and (x1 >= x0)):
                pass
            else:
                x0, y0, x1, y1 = x1, y1, x0, y0
            ed.delete(x0, y0, x1, y1)
            ed.set_caret(x0, y0)

        # parse Tabstops and Placeholders
        _mrks = ed.markers(ct.MARKERS_GET) or {}
        basetag = max([i[-1] for i in _mrks]) if _mrks else 0
        # s_text, zero_markers, markers = self.parse_tabstops_vs(sn, x0, y0, basetag=basetag)
        s_text, zero_markers, markers = self.parse_tabstops(sn, x0, y0, basetag=basetag)
        if not s_text:
            print('Wrong snippet: {}'.format(self.name))
            return

        # insert text
        ed.insert(x0, y0, '\n'.join(s_text))

        # delete old markers
        mark_placed = False
        ed.markers(ct.MARKERS_DELETE_ALL)

        # sync old markers from editor with new text position
        old_zero_markers, old_markers = [], []
        basetag = max([i['tag'] for i in markers]) if markers else 0
        for mk in _mrks:
            x, y = mk[0], mk[1]
            tag = mk[4]

            if tag != 0:
                tag += basetag
            if y > y0:
                y += len(sn) - 1
            elif y == y0 and x > x0:
                x += len(sn[0]) - 1

            m = marker(x, y, tag, mk[2], mk[3])
            if m['tag'] == 0:
                old_zero_markers.append(m)
            else:
                old_markers.append(m)

        old_zero_markers.sort(key=lambda k: k['tag'], reverse=True)

        # insert old markers
        for m in old_zero_markers:
            ed.markers(**m)
        for m in old_markers:
            ed.markers(**m)

        # insert new markers
        for m in zero_markers:
            ed.markers(**m)
            mark_placed = True
        for m in markers:
            ed.markers(**m)
            mark_placed = True

        # this only for new marks
        if mark_placed:
            ed.set_prop(ct.PROP_TAB_COLLECT_MARKERS, '1')
            ed.cmd(cudatext_cmd.cmd_Markers_GotoLastAndDelete)
        else:
            # place caret after text
            len_y = len(s_text)
            if len_y == 0:
                pass
            elif len_y == 1:
                len_x = len(s_text[0])
                ed.set_caret(x0 + len_x, y0)
            else:
                len_x = len(s_text[-1])
                ed.set_caret(len_x, y0 + len_y)

    @staticmethod
    def parse_vars_vs(ed, sn):

        def date_var(ln):
            start = 0
            _ln = ""
            for p in RE_DATE.finditer(ln):
                _ln += ln[start:p.start(0)+1] + strftime(p.group(1))
                start = p.end(0)
            _ln += ln[start:]
            return _ln

        fp = ed.get_filename()
        fn = op.basename(fp)
        x0, y0, x1, y1 = ed.get_carets()[0]
        text_sel = ed.get_text_sel()
        clipboard = ct.app_proc(ct.PROC_GET_CLIP, '')
        line = ed.get_text_line(y0)
        word, _ = get_word_under_cursor(line, x0)

        lexer = ed.get_prop(ct.PROP_LEXER_FILE)
        prop = ct.lexer_proc(ct.LEXER_GET_PROP, lexer)
        if prop:
            prop_str = prop.get('c_str')
            prop_line = prop.get('c_line')
            cmt_start = prop_str[0] if prop_str else ''
            cmt_end = prop_str[1] if prop_str else ''
            cmt_line = prop_line if prop_line else ''
        else:
            cmt_start = ''
            cmt_end = ''
            cmt_line = ''

        ct_variables = {
            # cudatext macro
            '${sel}': text_sel,  # The currently selected text or the empty string
            '${cp}': clipboard,
            '${fname}': fn,
            '${cmt_start}': cmt_start,
            '${cmt_end}': cmt_end,
            '${cmt_line}': cmt_line
        }
        ct_variables = OrderedDict(sorted(ct_variables.items(), reverse=True))

        variables = {
            # The following variables can be used:
            "TM_SELECTED_TEXT": text_sel,  # The currently selected text or the empty string
            "TM_CURRENT_LINE": line,  # The contents of the current line
            "TM_CURRENT_WORD": word,  # The contents of the word under cursor or the empty string
            "TM_LINE_INDEX": str(y0),  # The zero-index based line number
            "TM_LINE_NUMBER": str(y0 + 1),  # The one-index based line number
            "TM_FILEPATH": fp,  # The full file path of the current document
            "TM_DIRECTORY": op.dirname(fp),  # The directory of the current document
            "TM_FILENAME": fn,  # The filename of the current document
            "TM_FILENAME_BASE": op.splitext(fn)[0],  # The filename of the current document without its extensions
            "CLIPBOARD": clipboard,  # The contents of your clipboard
            "WORKSPACE_NAME": "",  # The name of the opened workspace or folder

            # For inserting the current date and time:
            "CURRENT_YEAR": strftime('%Y'),  # The current year
            "CURRENT_YEAR_SHORT": strftime('%y'),  # The current year's last two digits
            "CURRENT_MONTH": strftime('%m'),  # The month as two digits (example '02')
            "CURRENT_MONTH_NAME": strftime('%B'),  # The full name of the month (example 'July')
            "CURRENT_MONTH_NAME_SHORT": strftime('%B')[:4],  # The short name of the month (example 'Jul')
            "CURRENT_DATE": strftime('%d'),  # The day of the month
            "CURRENT_DAY_NAME": strftime('%A'),  # The name of day (example 'Monday')
            "CURRENT_DAY_NAME_SHORT": strftime('%a'),  # The short name of the day (example 'Mon')
            "CURRENT_HOUR": strftime('%H'),  # The current hour in 24-hour clock format
            "CURRENT_MINUTE": strftime('%M'),  # The current minute
            "CURRENT_SECOND": strftime('%S'),  # The current second
            "CURRENT_SECONDS_UNIX": str(int(time())),  # The number of seconds since the Unix epoch

            # For inserting line or block comments, honoring the current language:
            "BLOCK_COMMENT_START": cmt_start,  # Example output: in PHP /* or in HTML <!--
            "BLOCK_COMMENT_END": cmt_end,  # Example output: in PHP */ or in HTML -->
            "LINE_COMMENT": cmt_line,  # Example output: in PHP //
        }
        variables = OrderedDict(sorted(variables.items(), reverse=True))

        for i, ln in enumerate(sn):
            # replace ct variables
            for var, v in ct_variables.items():
                # replace '${date:': ,  # no }
                ln = date_var(ln.replace(var, v))

            # replace VS variables
            for var, v in variables.items():
                ln = ln.replace('$'+var, v)
                ln = ln.replace('${'+var+'}', v)

            # replace VS variables transform
            # ln = re_var_transform.sub(transform_repl, ln)

            sn[i] = ln
        return sn

    @staticmethod
    def parse_tabstops(sn, x0, y0, basetag):
        zero_markers = []
        markers = []

        buf = []
        for y, ln in enumerate(sn):
            shift = 0
            for t in RE_TOKEN_PART.finditer(ln):

                if is_tabstop(t[0]):
                    _tag = int(t[1])
                    m = marker(
                        x=t.start(0) + shift + (x0 if y == 0 else 0),
                        y=y+y0,
                        tag=_tag + basetag
                    )
                    if _tag == 0:
                        zero_markers.append(m)
                    else:
                        markers.append(m)
                    shift -= len(t[0])

                elif is_placeholder_head(t[0]):
                    p = Placeholder(
                        x0=t.start(0),
                        x1=t.end(0),
                        y=y,
                        shift=shift,
                        tag=int(t[2])
                    )
                    buf.append(p)
                    shift -= t.end(0) - t.start(0)

                elif is_placeholder_tail(t[0]):
                    if not buf:
                        return None, None, None
                    p = buf.pop()
                    x = t.start(0)
                    ln_x = x - p.x1 if y - p.y == 0 else x + shift
                    m = marker(
                        x=p.x0+p.shift+(x0 if y == 0 else 0),
                        y=p.y+y0,
                        tag=p.tag + basetag,
                        len_x=ln_x,
                        len_y=y-p.y
                    )
                    # dev(m)
                    if p.tag == 0:
                        zero_markers.append(m)
                    else:
                        markers.append(m)
                    shift -= 1

            # cln text line
            sn[y] = RE_TOKEN_PART.sub('', ln)

        # convert zero markers to maximum markers if already has markers in editor
        if basetag != 0 and markers:
            basetag = max([mrk['tag'] for mrk in markers])
            for m in zero_markers:
                m['tag'] = basetag
                markers.append(m)
            zero_markers = []

        markers.sort(key=lambda k: k['tag'], reverse=True)
        return sn, zero_markers, markers