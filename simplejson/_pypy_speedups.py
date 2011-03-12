"""PyPy replacements for the _speedups C extension"""
import sys

from simplejson.errors import JSONDecodeError

DEFAULT_ENCODING = "utf-8"

def next_terminator(s, begin):
    # FLAGS = re.VERBOSE | re.MULTILINE | re.DOTALL
    # STRINGCHUNK = re.compile(r'(.*?)(["\\\x00-\x1f])', FLAGS)
    end = begin
    needs_decode = False
    while 1:
        c = s[end]
        if c > '\x7f':
            needs_decode = True
        if ('\x00' <= c <= '\x1f') or (c == '"') or (c == '\\'):
            return s[begin:end], c, end + 1, needs_decode
        end += 1
    raise IndexError(-1)


def scanstring(s, end, encoding=None, strict=True):
    """Scan the string s for a JSON string. End is the index of the
    character in s after the quote that started the JSON string.
    Unescapes all valid JSON string escape sequences and raises ValueError
    on attempt to decode an invalid string. If strict is False then literal
    control characters are allowed in the string.

    Returns a tuple of the decoded string and the index of the character in s
    after the end quote."""
    if encoding is None:
        encoding = DEFAULT_ENCODING
    chunks = []
    begin = end - 1
    is_unicode = isinstance(s, unicode)
    while 1:
        try:
            content, terminator, end, needs_decode = next_terminator(s, end)
        except IndexError:
            raise JSONDecodeError(
                "Unterminated string starting at", s, begin)
        # Content is contains zero or more unescaped string characters
        if not is_unicode and needs_decode:
            content = unicode(content, encoding)
        if content:
            chunks.append(content)
        # Terminator is the end of string, a literal control character,
        # or a backslash denoting that an escape sequence follows
        if terminator == '"':
            break
        elif terminator != '\\':
            if strict:
                msg = "Invalid control character %r at" % (terminator,)
                raise JSONDecodeError(msg, s, end)
            else:
                chunks.append(terminator)
                continue
        try:
            esc = s[end]
        except IndexError:
            raise JSONDecodeError(
                "Unterminated string starting at", s, begin)
        # If not a unicode escape sequence, must be in the lookup table
        if esc != 'u':
            if esc == '"':
                char =  '"'
            elif esc == '\\':
                char =  '\\'
            elif esc == '/':
                char =  '/'
            elif esc == 'b':
                char =  '\b'
            elif esc == 'f':
                char =  '\f'
            elif esc == 'n':
                char =  '\n'
            elif esc == 'r':
                char =  '\r'
            elif esc == 't':
                char =  '\t'
            else:
                msg = "Invalid \\escape: " + repr(esc)
                raise JSONDecodeError(msg, s, end)
            end += 1
        else:
            # Unicode escape sequence
            esc = s[end + 1:end + 5]
            next_end = end + 5
            if len(esc) != 4:
                msg = "Invalid \\uXXXX escape"
                raise JSONDecodeError(msg, s, end)
            uni = int(esc, 16)
            # Check for surrogate pair on UCS-4 systems
            if 0xd800 <= uni <= 0xdbff and sys.maxunicode > 65535:
                msg = "Invalid \\uXXXX\\uXXXX surrogate pair"
                if not s[end + 5:end + 7] == '\\u':
                    raise JSONDecodeError(msg, s, end)
                esc2 = s[end + 7:end + 11]
                if len(esc2) != 4:
                    raise JSONDecodeError(msg, s, end)
                uni2 = int(esc2, 16)
                uni = 0x10000 + (((uni - 0xd800) << 10) | (uni2 - 0xdc00))
                next_end += 6
            char = unichr(uni)
            end = next_end
        # Append the unescaped character
        chunks.append(char)
    if is_unicode:
        return u''.join(chunks), end
    else:
        return ''.join(chunks), end


def make_scanner(context):
    parse_object = context.parse_object
    parse_array = context.parse_array
    parse_string = context.parse_string
    encoding = context.encoding
    strict = context.strict
    parse_float = context.parse_float
    parse_int = context.parse_int
    parse_constant = context.parse_constant
    object_hook = context.object_hook
    object_pairs_hook = context.object_pairs_hook
    memo = context.memo

    def match_number(s, start):
        idx = start
        end_idx = len(s) - 1
        is_float = False
        if s[idx] == '-':
            # read a sign if it's there, make sure it's not the end of the
            # string
            idx += 1
            if idx > end_idx:
                raise StopIteration
        if '1' <= s[idx] <= '9':
            # read as many integer digits as we find as long as it doesn't
            # start with 0
            idx += 1
            while (idx <= end_idx) and ('0' <= s[idx] <= '9'):
                idx += 1
        elif s[idx] == '0':
            # if it starts with 0 we only expect one integer digit
            idx += 1
        else:
            # no integer digits, error
            raise StopIteration
        if (idx < end_idx) and (s[idx] == '.') and ('0' <= s[idx + 1] <= '9'):
            # if the next char is '.' followed by a digit then read all float
            # digits
            is_float = True
            idx += 2
            while (idx <= end_idx) and ('0' <= s[idx] <= '9'):
                idx += 1
        if (idx < end_idx) and (s[idx] == 'e' or s[idx] == 'E'):
            # if the next char is 'e' or 'E' then maybe read the exponent (or
            # backtrack)
            # save the index of the 'e' or 'E' just in case we need to
            # backtrack
            e_start = idx
            idx += 1
            # read an exponent sign if present
            if (idx < end_idx) and (s[idx] == '-' or s[idx] == '+'):
                idx += 1
            # read all digits
            while (idx <= end_idx) and ('0' <= s[idx] <= '9'):
                idx += 1
            # if we got a digit, then parse as float. if not, backtrack
            if '0' <= s[idx - 1] <= '9':
                is_float = True
            else:
                idx = e_start
        numstr = s[start:idx]
        if is_float:
            return context.parse_float(numstr), idx
        else:
            return context.parse_int(numstr), idx

    def _scan_once(string, idx):
        try:
            nextchar = string[idx]
        except IndexError:
            raise StopIteration

        if nextchar == '"':
            return parse_string(string, idx + 1, encoding, strict)
        elif nextchar == '{':
            return parse_object((string, idx + 1), encoding, strict,
                _scan_once, object_hook, object_pairs_hook, memo)
        elif nextchar == '[':
            return parse_array((string, idx + 1), _scan_once)
        elif nextchar == 'n' and string[idx:idx + 4] == 'null':
            return None, idx + 4
        elif nextchar == 't' and string[idx:idx + 4] == 'true':
            return True, idx + 4
        elif nextchar == 'f' and string[idx:idx + 5] == 'false':
            return False, idx + 5
        elif nextchar == 'N' and string[idx:idx + 3] == 'NaN':
            return parse_constant('NaN'), idx + 3
        elif nextchar == 'I' and string[idx:idx + 8] == 'Infinity':
            return parse_constant('Infinity'), idx + 8
        elif nextchar == '-' and string[idx:idx + 9] == '-Infinity':
            return parse_constant('-Infinity'), idx + 9
        else:
            return match_number(string, idx)

    def scan_once(string, idx):
        try:
            return _scan_once(string, idx)
        finally:
            memo.clear()

    return scan_once
