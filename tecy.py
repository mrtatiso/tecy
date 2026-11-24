#!/usr/bin/env python3
"""tecy: read random Wikipedia articles, cut every word into syllables, keep the useful ones.

    $ tecy              works until Ctrl+C, always on the same scrap.tecy
    $ tecy status       what scrap.tecy holds now

It alternates es.wikipedia and en.wikipedia. Each article is cut with the
rules of its own language and every syllable goes into one table in the
current folder:

    scrap.tecy      <syllable> TAB <count>, the most used first

After each article the rare syllables are dropped, so only the useful ones
stay. Stopping is safe: every article already read is saved. tecy is a tool
for building the table, not for users: two runs read different articles and
give different tables.

Words: only the Latin alphabet, accents included; lowercased; 1 to 32 letters;
at least one vowel; no letter three times in a row. Links, emails and numbers
are dropped.

Spanish: the syllable rules of the RAE (see _es below).
English: Liang's algorithm with the TeX patterns hyph-en-us (Gerard Kuiken),
kept next to this file with their notice and checked by sha256. TeX leaves
2 letters at the start and 3 at the end; tecy uses 1 and 2.
"""
import hashlib
import json
import os
import re
import sys
import time
import unicodedata
import urllib.parse
import urllib.request

__version__ = "2.0.0"
__all__ = ["words", "syllables", "count", "prune", "load", "save", "add", "status"]

HERE = os.path.dirname(os.path.abspath(__file__))
TABLE = "scrap.tecy"
MAX = 32
MIN_COUNT = 2            # a syllable seen fewer times than this is dropped…
SHARE = 1_000_000        # …or fewer than one in a million syllables counted, whichever is higher
PAUSE = 1.0              # seconds between requests to Wikipedia
USER_AGENT = f"tecy/{__version__} (+https://github.com/mrtatiso)"
PATTERNS = {
    "hyph-en-us.pat.txt": "0f57318b878b132547ae92db39a6e1d1cf2a05d9008874955d6ecb910007a463",
    "hyph-en-us.hyp.txt": "5e785c27e151f878c312991d937b5582615b77737ab30bac413d5967d6aa21da",
}


# ---------- words ----------

def _base(c: str) -> str:
    return unicodedata.normalize("NFD", c)[0]


def _latin(c: str) -> bool:
    """A Latin letter, accented or not. Phonetic symbols (IPA) do not count."""
    return unicodedata.name(c, "").startswith("LATIN") and not 0x0250 <= ord(c) <= 0x02AF


def _has_vowel(w: str) -> bool:
    return any(_base(c) in "aeiouy" for c in w)


def words(text: str) -> list:
    """Every useful word in the text, in order, repeats included."""
    text = unicodedata.normalize("NFC", text).lower().replace("i̇", "i")
    text = re.sub(r"https?://\S+|www\.\S+|\S+@\S+", " ", text)
    return [w for w in re.findall(r"[^\W\d_]+", text)
            if len(w) <= MAX and all(_latin(c) for c in w) and _has_vowel(w)
            and not re.search(r"(.)\1\1", w)]


# ---------- Spanish: rules of the RAE ----------
#
# Vowels: a e o are strong, i u ü weak. An accented í or ú counts as strong
# (that accent is what breaks a diphthong: dí·a, ba·úl).
# Two vowels together stay in one syllable (diphthong) unless both are strong
# (hiatus: le·ón, a·é·re·o). Three, weak-strong-weak, stay together (buey).
# An h between two vowels does not break a diphthong (prohi·bir, ahu·ma·do).
# ch, ll, rr are one consonant; so are qu, and gu before e or i (the u is silent).
# y is a vowel at the end of a word after a vowel (rey, muy) and as the word "y".
# Between two vowel groups: one consonant goes to the next syllable; with more,
# the last one goes, or the last two if they are p b t d c g f k + l or r
# (and tl, as in Mexico: a·tlas). The rest stay behind: ins·tan·te, abs·trac·to.

_CLUSTERS = {a + b for a in "pbtdcgfk" for b in "lr"} - {"dl"} | {"tl"}


def _es_units(w: str) -> list:
    """The word as (text, kind) units: kind is 'S' strong vowel, 'W' weak vowel, 'C' consonant."""
    units, i, n = [], 0, len(w)
    while i < n:
        two = w[i:i + 2]
        if two in ("ch", "ll", "rr") or two == "qu" or (two == "gu" and i + 2 < n and _base(w[i + 2]) in "ei"):
            units.append((two, "C"))
            i += 2
            continue
        c = w[i]
        b = _base(c)
        if c == "y":
            vowel = n == 1 or (i == n - 1 and units and units[-1][1] != "C")
            units.append((c, "W" if vowel else "C"))
        elif b in "aeo":
            units.append((c, "S"))
        elif b in "iu":
            units.append((c, "S" if c in "íúìù" else "W"))
        else:
            units.append((c, "C"))
        i += 1
    return units


def _es(w: str) -> list:
    u = _es_units(w)
    vowel = lambda k: k in "SW"
    together = lambda a, b: not (a == "S" and b == "S")
    nuclei, i = [], 0                                   # (first unit, last unit) of each vowel group
    while i < len(u):
        if not vowel(u[i][1]):
            i += 1
            continue
        j = i
        while True:
            if j + 1 < len(u) and vowel(u[j + 1][1]) and together(u[j][1], u[j + 1][1]):
                j += 1
            elif (j + 2 < len(u) and u[j + 1][0] == "h" and vowel(u[j + 2][1])
                  and together(u[j][1], u[j + 2][1])):
                j += 2
            else:
                break
        nuclei.append((i, j))
        i = j + 1
    cuts = []
    for (_, a), (b, _) in zip(nuclei, nuclei[1:]):
        between = [t for t, _ in u[a + 1:b]]
        if len(between) >= 2 and between[-2][-1] + between[-1][0] in _CLUSTERS:
            cuts.append(b - 2)
        elif between:
            cuts.append(b - 1)
        else:
            cuts.append(b)                              # hiatus: le·ón
    edges = [0] + cuts + [len(u)]
    return ["".join(t for t, _ in u[x:y]) for x, y in zip(edges, edges[1:])]


# ---------- English: Liang's algorithm with the TeX patterns ----------

_PATTERNS, _EXCEPTIONS = None, None
LEFT, RIGHT = 1, 2


def _load_patterns():
    global _PATTERNS, _EXCEPTIONS
    if _PATTERNS is not None:
        return
    for name, digest in PATTERNS.items():
        path = os.path.join(HERE, name)
        if not os.path.exists(path):
            raise SystemExit(f"tecy: {name} is missing next to tecy.py")
        with open(path, "rb") as f:
            if hashlib.sha256(f.read()).hexdigest() != digest:
                raise SystemExit(f"tecy: {name} is not the expected file (sha256 differs)")
    _PATTERNS = {}
    with open(os.path.join(HERE, "hyph-en-us.pat.txt"), encoding="utf-8") as f:
        for p in f.read().split():
            letters = re.sub(r"\d", "", p)
            points, i = [0] * (len(letters) + 1), 0
            for c in p:
                if c.isdigit():
                    points[i] = int(c)
                else:
                    i += 1
            _PATTERNS[letters] = points
    with open(os.path.join(HERE, "hyph-en-us.hyp.txt"), encoding="utf-8") as f:
        _EXCEPTIONS = {e.replace("-", ""): e.split("-") for e in f.read().split()}


def _en(w: str) -> list:
    _load_patterns()
    if w in _EXCEPTIONS:
        return list(_EXCEPTIONS[w])
    s = "." + w + "."
    points = [0] * (len(s) + 1)
    for i in range(len(s)):
        for j in range(i + 1, len(s) + 1):
            p = _PATTERNS.get(s[i:j])
            if p:
                for k, v in enumerate(p):
                    points[i + k] = max(points[i + k], v)
    cuts = [i for i in range(LEFT, len(w) - RIGHT + 1) if points[i + 1] % 2]
    edges = [0] + cuts + [len(w)]
    return [w[x:y] for x, y in zip(edges, edges[1:])]


def syllables(w: str, lang: str) -> list:
    """The syllables of one word in 'es' or 'en'."""
    return _es(w) if lang == "es" else _en(w)


# ---------- the table ----------

def count(ws, lang: str, table=None) -> dict:
    table = {} if table is None else table
    for w in ws:
        for s in syllables(w, lang):
            table[s] = table.get(s, 0) + 1
    return table


def prune(table: dict) -> dict:
    """Only the syllables seen at least the threshold number of times."""
    limit = max(MIN_COUNT, sum(table.values()) // SHARE)
    return {s: n for s, n in table.items() if n >= limit}


def load(path: str = TABLE) -> dict:
    table = {}
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            for line in f:
                s, n = line.rstrip("\n").split("\t")
                table[s] = int(n)
    return table


def save(table: dict, path: str = TABLE) -> None:
    rows = sorted(table.items(), key=lambda x: (-x[1], x[0]))
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write("".join(f"{s}\t{n}\n" for s, n in rows))
    os.replace(tmp, path)


def add(text: str, lang: str, path: str = TABLE) -> int:
    """Cut one text, add it to the table, drop the rare syllables, save. Returns words read."""
    ws = words(text)
    save(prune(count(ws, lang, load(path))), path)
    return len(ws)


# ---------- Wikipedia ----------

def random_article(lang: str):
    """(title, plain text) of one random article from {lang}.wikipedia.org."""
    q = urllib.parse.urlencode({"action": "query", "format": "json", "generator": "random",
                                "grnnamespace": 0, "grnlimit": 1, "prop": "extracts",
                                "explaintext": 1, "maxlag": 5})
    req = urllib.request.Request(f"https://{lang}.wikipedia.org/w/api.php?{q}",
                                 headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=30) as r:
        data = json.load(r)
    page = next(iter(data["query"]["pages"].values()))
    return page["title"], page.get("extract", "")


def status(path: str = TABLE) -> str:
    t = load(path)
    top = sorted(t.items(), key=lambda x: (-x[1], x[0]))[:12]
    return (f"syllables {len(t):,} · counted {sum(t.values()):,}\n"
            f"most used {'  '.join(f'{s} {n:,}' for s, n in top) or '(empty)'}")


def main(args=None) -> int:
    args = sys.argv[1:] if args is None else args
    if args == ["status"]:
        print(status())
        return 0
    if args:
        print(__doc__.split("\n\n")[1], file=sys.stderr)
        return 2
    _load_patterns()
    n = 0
    try:
        while True:
            lang = "es" if n % 2 == 0 else "en"
            try:
                title, text = random_article(lang)
                read = add(text, lang)
                t = load()
                print(f"{lang} · {title[:50]:<50} {read:>6,} words · table {len(t):,}")
            except (OSError, ValueError, KeyError) as e:
                print(f"tecy: {lang}: {e}", file=sys.stderr)
            n += 1
            time.sleep(PAUSE)
    except KeyboardInterrupt:
        print("\nstopped · every article already read is saved")
    return 0


if __name__ == "__main__":
    sys.exit(main())
