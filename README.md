# tecy

Reads random Wikipedia articles, cuts every word into syllables and keeps the useful ones in one table.

```
$ python3 tecy.py
es · Monterrey                                            1,204 words · table 3,118
en · Elephant                                               962 words · table 3,407
…
^C
stopped · every article already read is saved
```

No dependencies. One table. Runs until you stop it.

tecy is a tool for building the table, not for end users: two runs read different articles and give different tables. What gets shared is the table, not the run.

## Run

```
git clone https://github.com/mrtatiso/tecy
cd tecy
python3 tecy.py            # works until Ctrl+C
python3 tecy.py status     # what the table holds now
```

tecy is not a pip package: the English patterns must sit next to `tecy.py`, so run it from the cloned folder. The table is written in the folder you run it from.

## The table

`scrap.tecy`, always the same file, one syllable per line, the most used first:

```
<syllable> TAB <count>
```

Nothing else: no header, no signature. Every article adds to it. Stopping is safe at any moment: every article already read is saved, and the next run keeps adding to the same table.

## Published table

This repository includes `scrap.tecy`, the table built so far by the author's runs. It is published on purpose: it is the raw table, not a frozen one, and it is updated when new runs are added, so it changes over time. Its history is the git history of the file.

Running `tecy.py` from this folder keeps adding to that same table. To build your own from zero, run it from an empty folder:

    mkdir mytable && cd mytable && python3 ../tecy.py
    
## What it does

- **Alternates es.wikipedia and en.wikipedia**, one random article per second, as plain text through the MediaWiki API. The User-Agent says what tecy is and where it comes from, as Wikipedia asks of bots.
- **Keeps only useful words:** Latin alphabet, accents included; lowercased; 1 to 32 letters; at least one vowel; no letter three times in a row. Links, emails and numbers are dropped.
- **Cuts each word with the rules of its article's language.** No guessing: an article from es.wikipedia is Spanish, one from en.wikipedia is English. Once cut, the syllables of both languages go into the same table.
- **Drops the rare syllables after each article:** any syllable seen fewer than 2 times, or fewer than once per million syllables counted, whichever is higher. The threshold grows with the table.

### Spanish: the rules of the RAE

| rule | examples |
|---|---|
| a e o are strong, i u ü weak; an accented í ú counts as strong | dí·a, ba·úl, pa·ís |
| two vowels stay together unless both are strong | ciu·dad, au·la · le·ón, a·é·re·o |
| weak-strong-weak stays together | buey, a·ve·ri·guáis |
| an h between vowels does not break a diphthong | prohi·bir, ahu·ma·do · al·co·hol |
| ch, ll, rr are one consonant; so are qu, and gu before e/i | ca·rro, que·so, gue·rra · pin·güi·no |
| y is a vowel at the end of a word after a vowel, and as the word y | rey, muy · re·yes, a·yer |
| one consonant between vowels goes to the next syllable | ca·sa, ta·xi |
| with more, the last one goes, or the last two if they are p b t d c g f k + l/r, or tl | ins·tan·te, abs·trac·to, o·tro, a·tlas |

`tl` stays together as in Mexico (a·tlas). In Spain it is split (at·las).

### English: Liang's algorithm

The same algorithm TeX uses, with the American English patterns of the hyph-utf8 package (Gerard D.C. Kuiken). TeX leaves at least 2 letters at the start and 3 at the end of a word; tecy uses 1 and 2, which gives more cuts without wrong ones:

```
read·er  make  ta·ble  com·put·er  in·for·ma·tion  lit·tle  chil·dren  on·ly  hap·py
```

The patterns were made for typesetting, so they rarely leave one vowel alone: `about`, `many`, `very` stay whole.

## Files

| file | |
|---|---|
| `tecy.py` | the tool |
| `hyph-en-us.pat.txt` | 4,938 English patterns, unmodified |
| `hyph-en-us.hyp.txt` | 14 English exceptions, unmodified |
| `hyph-en-us.NOTICE` | copyright, licence and source of the two files above |
| `test/` | tests |
| `scrap.tecy` | the table built so far by the author's runs |

tecy checks the sha256 of both pattern files when it starts. If one is missing or different, it stops instead of cutting English wrong without saying so.

## Test

```
python3 -m unittest discover test
```

44 Spanish words, 12 English words, the table and the pattern check. No network needed.

## Licence

`tecy.py` and the tests: MIT, see `LICENSE`.

The English patterns are © 1990, 2004, 2005 Gerard D.C. Kuiken, part of [hyph-utf8](https://github.com/hyphenation/tex-hyphen), distributed under their own licence: copying and distribution, with or without modification, are permitted in any medium without royalty provided the copyright notice and this notice are preserved. See `hyph-en-us.NOTICE`.

## Verify

```
sha256sum tecy.py hyph-en-us.pat.txt hyph-en-us.hyp.txt
```

v2.0.0:

```
74d74943f84f87f6235ea27fe5c5a4a9cda34b7edf497b21f210c78bd8aa1013  tecy.py
0f57318b878b132547ae92db39a6e1d1cf2a05d9008874955d6ecb910007a463  hyph-en-us.pat.txt
5e785c27e151f878c312991d937b5582615b77737ab30bac413d5967d6aa21da  hyph-en-us.hyp.txt
```
