from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from gamebook_jev import ProjectAonBook, GamebookEnv, Controller, Decision


class SafeController(Controller):
    def choose(self, state, choices):
        # deterministic fixture policy: first option
        return Decision(choices[0].key, 0.9, {c.key: (0.9 if c == choices[0] else 0.1) for c in choices}, 1.0)


def test_parse_and_run():
    book = ProjectAonBook.from_file(Path(__file__).with_name("fixture.xml"))
    assert set(book.sections) == {"1", "2", "3", "4"}
    assert book.sections["1"].choices[0].target == "2"
    env = GamebookEnv(book, start="1", goal="4")
    r = env.run(SafeController(), max_steps=10)
    assert r.status == "success"
    assert r.path == ["1", "2", "4"]
