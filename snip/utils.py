import json
import string

CHARS_SNIP = string.ascii_letters + string.digits + '_.$>:'
# char '>' is here to disable plugin work after "ul>li",
# to pass it to Emmet (which has lower event priority)


def get_word(ed):
    # multi-carets? stop
    carets = ed.get_carets()
    if len(carets) != 1:
        return
    x, y, x1, y1 = carets[0]

    # selection? stop
    if y1 >= 0:
        return
    # check line index
    if y >= ed.get_line_count():
        return

    line = ed.get_text_line(y)
    # caret after lineend? stop
    if x > len(line):
        return

    x0 = x
    while x > 0 and (line[x - 1] in CHARS_SNIP):
        x -= 1
    return line[x:x0]


# def _readfile(fn):
#     return open(fn, encoding='utf8', errors='replace').read()
COMMENT_PREFIX = ("#", ";", "//")
MULTILINE_START = "/*"
MULTILINE_END = "*/"
LONG_STRING = '"""'


def load_json(fp, *args, **kwargs):
    lines = fp.readlines()
    # Process the lines to remove commented ones
    standard_json = ""
    is_multiline = False

    keep_trail_space = 0
    for line in lines:
        # 0 if there is no trailing space
        # 1 otherwise
        keep_trail_space = int(line.endswith(" "))

        # Remove all whitespace on both sides
        line = line.strip()

        # Skip blank lines
        if len(line) == 0:
            continue

        # Skip single line comments
        if line.startswith(COMMENT_PREFIX):
            continue

        # Mark the start of a multiline comment
        # Not skipping, to identify single line comments using multiline comment tokens, like
        # /***** Comment *****/
        if line.startswith(MULTILINE_START):
            is_multiline = True

        # Skip a line of multiline comments
        if is_multiline:
            # Mark the end of a multiline comment
            if line.endswith(MULTILINE_END):
                is_multiline = False
            continue

        # Replace the multi line data token to the JSON valid one
        if LONG_STRING in line:
            line = line.replace(LONG_STRING, '"')

        # del bad JSON chars
        line = line.replace(chr(0xC2), '')
        line = line.replace(chr(0xA0), '')

        # \n here to allow user to see the resulting text in Console if exception occurs in json.loads
        standard_json += line + " " * keep_trail_space + '\n'

    # Removing non-standard trailing commas
    standard_json = standard_json.replace(",]", "]")
    standard_json = standard_json.replace(",}", "}")
    if not standard_json:
        return {}
    # Calls the wrapped to parse JSON
    try:
        return json.loads(standard_json, *args, **kwargs)
    except json.decoder.JSONDecodeError:
        print('ERROR: Plugin "Snippets" failed to load JSON content')
        print(standard_json)
        raise
