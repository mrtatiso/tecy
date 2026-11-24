import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import tecy  # noqa: E402

ES = {
    # basics and consonant groups
    "casa": "ca·sa", "hombre": "hom·bre", "otro": "o·tro", "perla": "per·la",
    "instante": "ins·tan·te", "abstracto": "abs·trac·to", "obstáculo": "obs·tá·cu·lo",
    "inspección": "ins·pec·ción", "acción": "ac·ción", "construir": "cons·truir",
    "examen": "e·xa·men", "taxi": "ta·xi", "atlas": "a·tlas",
    # digraphs and silent u
    "carro": "ca·rro", "calle": "ca·lle", "coche": "co·che", "queso": "que·so",
    "guerra": "gue·rra", "agua": "a·gua", "pingüino": "pin·güi·no",
    # diphthongs, hiatus, triphthongs
    "ciudad": "ciu·dad", "cielo": "cie·lo", "aula": "au·la", "día": "dí·a",
    "baúl": "ba·úl", "león": "le·ón", "aéreo": "a·é·re·o", "buey": "buey",
    "averiguáis": "a·ve·ri·guáis", "creíais": "cre·í·ais", "país": "pa·ís",
    # h between vowels
    "ahumado": "ahu·ma·do", "prohibir": "prohi·bir", "alcohol": "al·co·hol",
    "búho": "bú·ho", "deshielo": "des·hie·lo", "ahí": "a·hí",
    # y
    "rey": "rey", "reyes": "re·yes", "ayer": "a·yer", "muy": "muy", "y": "y",
    "rayo": "ra·yo", "estoy": "es·toy",
}

EN = {
    "reader": "read·er", "make": "make", "table": "ta·ble", "strength": "strength",
    "computer": "com·put·er", "information": "in·for·ma·tion", "little": "lit·tle",
    "children": "chil·dren", "together": "to·geth·er", "happy": "hap·py",
    "elephant": "ele·phant", "project": "project",
}


class TestWords(unittest.TestCase):
    def test_filters_noise(self):
        t = "Hola HTTP xml jajjja aaaah 2026 https://x.org a@b.com Ñandú страна ʃip mundo"
        self.assertEqual(tecy.words(t), ["hola", "ñandú", "mundo"])


class TestSpanish(unittest.TestCase):
    def test_rae(self):
        for w, s in ES.items():
            self.assertEqual("·".join(tecy.syllables(w, "es")), s, w)

    def test_rebuilds_the_word(self):
        for w in ES:
            self.assertEqual("".join(tecy.syllables(w, "es")), w)


class TestEnglish(unittest.TestCase):
    def test_liang(self):
        for w, s in EN.items():
            self.assertEqual("·".join(tecy.syllables(w, "en")), s, w)

    def test_rebuilds_the_word(self):
        for w in EN:
            self.assertEqual("".join(tecy.syllables(w, "en")), w)


class TestTable(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.TemporaryDirectory()
        self.path = os.path.join(self.d.name, "scrap.tecy")

    def tearDown(self):
        self.d.cleanup()

    def test_both_languages_one_table(self):
        tecy.add("casa casa mesa mesa", "es", self.path)
        tecy.add("table table reader reader", "en", self.path)
        t = tecy.load(self.path)
        for s in ("sa", "ca", "ble", "read"):
            self.assertIn(s, t)

    def test_rare_dropped_and_most_used_first(self):
        tecy.add("casa casa casa mesa mesa strength", "es", self.path)
        with open(self.path, encoding="utf-8") as f:
            rows = [l.rstrip("\n").split("\t") for l in f]
        self.assertEqual(rows[0][0], "sa")
        self.assertNotIn("strength", [r[0] for r in rows])
        for s, n in rows:
            self.assertTrue(s.isalpha() and n.isdigit())


class TestPatterns(unittest.TestCase):
    def _with_here(self, here):
        old = tecy.HERE, tecy._PATTERNS, tecy._EXCEPTIONS
        tecy.HERE, tecy._PATTERNS, tecy._EXCEPTIONS = here, None, None
        try:
            with self.assertRaises(SystemExit):
                tecy._load_patterns()
        finally:
            tecy.HERE, tecy._PATTERNS, tecy._EXCEPTIONS = old

    def test_missing_patterns_stop_tecy(self):
        with tempfile.TemporaryDirectory() as d:
            self._with_here(d)

    def test_changed_patterns_stop_tecy(self):
        with tempfile.TemporaryDirectory() as d:
            for name in tecy.PATTERNS:
                with open(os.path.join(tecy.HERE, name), "rb") as f:
                    data = f.read()
                with open(os.path.join(d, name), "wb") as f:
                    f.write(data + (b"x\n" if name.endswith("hyp.txt") else b""))
            self._with_here(d)


if __name__ == "__main__":
    unittest.main()
