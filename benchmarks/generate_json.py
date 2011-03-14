"""Generate a JSON file for json decode benchmarking purposes using freqdata.py.
Works with pypy and python.

Initial setup::

    $ git clone -b pypy-support git://github.com/simplejson/simplejson.git; \
      cd simplejson

To generate::

    $ mkdir -p build/bench; \
      PYTHONPATH=. python benchmarks/generate_json.py > build/bench/feed.json

To run the read benchmark::

    $ python -m timeit -n 1 -r 5 \
      -s 'import simplejson;s = open("build/bench/feed.json", "rb").read()' \
      'simplejson.loads(s)'

To run the write benchmark::

    $ python -m timeit -n 1 -r 5 \
      -s 'import simplejson;s = open("build/bench/feed.json", "rb").read()' \
      -s 'd = simplejson.loads(s)' \
      'simplejson.dumps(d)'

"""
import sys
import operator
from random import Random

import simplejson

from freqdata import FREQ

def main(num_games, freq=FREQ):
    game_keys = sorted([k for k in freq.iterkeys() if not isinstance(k, tuple)])
    rng = Random()
    rng.seed(6935051420896)

    def type_chooser(type_freq):
        types = sorted(type_freq.iteritems(), key=operator.itemgetter(1, 0))
        type_sum = sum([v for (k, v) in types])
        def chooser():
            orig_i = rng.randrange(0, type_sum)
            i = orig_i
            for typ, freq in types:
                if i < freq:
                    return typ
                i -= freq
            assert False, "orig_i=%r type_sum=%r" % (orig_i, type_sum)
        return chooser

    choosers = dict((k, type_chooser(v)) for (k, v) in freq.iteritems())

    def generate_string(typ, (start, stop), coderangegen):
        if typ is str:
            empty, char = '', chr
        else:
            empty, char = u'', unichr
        for _ in xrange(rng.randrange(start, stop)):
            loword, highord = coderangegen()
        return empty.join([char(rng.randrange(*coderangegen()))
                           for _ in xrange(rng.randrange(start, stop))])

    def generate_list(key, typ):
        start, stop = typ[1]
        return [key_chooser((key, typ))
                for _ in xrange(rng.randrange(start, stop))]

    def key_chooser(key):
        typ = choosers[key]()
        if typ is None:
            return None
        elif typ is bool:
            return rng.choice((False, True))
        elif typ is float:
            # actually 100.0 is included in the actual data
            return rng.uniform(0.0, 100.0)
        elif typ is int:
            # this is arbitrary, not from data
            return rng.randrange(0, 10000000)
        elif isinstance(typ, tuple):
            (parent, rest) = typ
            if parent in (str, unicode):
                return generate_string(parent, rest, choosers.get((key, typ)))
            elif parent is list:
                return generate_list(key, typ)
        raise NotImplementedError(typ)

    def digits(n):
        s = str(rng.randrange(0, 10 ** n))
        return ('0' * (n - len(s))) + s

    def timestamp():
        return '{}-{}-{}T{}:{}:{}.{}'.format(
            *(digits(n) for n in (4, 2, 2, 2, 2, 2, 6)))

    def metascore():
        # actually 100.0 is included in the actual data
        return rng.uniform(0.0, 100.0)

    def game():
        d = {}
        for k in game_keys:
            d[k] = key_chooser(k)
        return d

    json = {}
    json['generated'] = timestamp()
    json['games'] = [game() for _ in xrange(num_games)]
    return simplejson.dumps(json, sort_keys=True)

if __name__ == '__main__':
    try:
        num = int(sys.argv[1])
    except IndexError:
        num = 20000
    print main(num)
