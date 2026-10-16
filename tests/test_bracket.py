"""Tests for skills/arena/bracket.py. Standard library only.

    python3 -m unittest discover -s tests -v

The headline test drives a full 100-agent tournament through the real command
line with random winners and checks it ends with exactly one survivor.
"""
import collections
import json
import os
import random
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
SKILL = os.path.join(REPO, "skills", "arena")
BRACKET = os.path.join(SKILL, "bracket.py")
sys.path.insert(0, SKILL)

import bracket as B  # noqa: E402

W = B.load_weights(B.RUBRIC_PATH)
EM_DASH, EN_DASH = chr(0x2014), chr(0x2013)   # spelled as code points so this file stays clean


def cli(*args, cwd=None):
    return subprocess.run([sys.executable, BRACKET] + [str(a) for a in args],
                          capture_output=True, text=True, cwd=cwd)


def write(path, text):
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text)


def read(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def load(d):
    with open(os.path.join(d, "arena.json"), encoding="utf-8") as fh:
        return json.load(fh)


class TempDir(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="arena-test-")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def ok(self, *args):
        r = cli(*args)
        self.assertEqual(r.returncode, 0, "bracket.py %s failed:\n%s%s" % (" ".join(map(str, args)), r.stdout, r.stderr))
        return r.stdout


class SimulatedTournament(TempDir):
    """Random winners, driven only through the CLI: init, pairings, record, advance, status, winner."""

    def run_tournament(self, n, seed):
        d = os.path.join(self.tmp, "run-%d" % n)
        self.ok("init", "--agents", n, "--seed", seed, "--task", "Simulated task.", "--dir", d)
        rng = random.Random(seed)
        alive_at_start = []
        while True:
            state = load(d)
            if state["champion"]:
                break
            rd = state["rounds"][-1]
            alive_at_start.append(len(rd["alive"]))
            out = self.ok("pairings", "--dir", d)
            self.assertIn("round %d:" % rd["n"], out)
            in_round = [x for m in rd["matches"] for x in (m["a"], m["b"])] + ([rd["bye"]] if rd["bye"] else [])
            self.assertEqual(sorted(in_round), sorted(rd["alive"]), "everyone alive plays once or gets the bye")
            self.assertEqual(len(in_round), len(set(in_round)))
            for m in rd["matches"]:
                self.ok("record", m["id"], rng.choice([m["a"], m["b"]]), "--reason", "simulated", "--dir", d)
            self.ok("advance", "--dir", d)
        alive_at_start.append(1)
        return d, load(d), alive_at_start

    def test_100_agents_reach_exactly_one_survivor(self):
        d, state, sizes = self.run_tournament(100, 7)
        self.assertEqual(sizes, [100, 50, 25, 13, 7, 4, 2, 1])
        self.assertEqual(len(state["rounds"]), 7)
        alive = [a for a, v in state["agents"].items() if v["alive"]]
        self.assertEqual(alive, [state["champion"]])
        dead = [v for v in state["agents"].values() if not v["alive"]]
        self.assertEqual(len(dead), 99)
        self.assertTrue(all(v["eliminated_in"] and v["eliminated_by"] for v in dead))
        self.assertEqual(sum(len(rd["matches"]) for rd in state["rounds"]), 99)
        self.assertEqual([rd["bye"] is not None for rd in state["rounds"]],
                         [False, False, True, True, True, False, False])
        self.assertTrue(all(v["byes"] <= 1 for v in state["agents"].values()), "no agent gets two byes")
        status = self.ok("status", "--dir", d)
        self.assertIn("now: 1 alive, 99 eliminated, champion %s" % state["champion"], status)
        won = self.ok("winner", "--dir", d)
        self.assertIn("CHAMPION  %s" % state["champion"], won)
        self.assertIn("7 played, 100 agents in, 1 left", won)
        self.assertIn("last one standing", self.ok("pairings", "--dir", d))

    def test_16_agents(self):
        _, state, sizes = self.run_tournament(16, 3)
        self.assertEqual(sizes, [16, 8, 4, 2, 1])
        self.assertEqual(len(state["rounds"]), 4)
        self.assertTrue(all(rd["bye"] is None for rd in state["rounds"]))
        self.assertEqual(sum(v["alive"] for v in state["agents"].values()), 1)

    def test_7_agents_with_a_bye(self):
        _, state, sizes = self.run_tournament(7, 11)
        self.assertEqual(sizes, [7, 4, 2, 1])
        self.assertEqual(len(state["rounds"]), 3)
        self.assertIsNotNone(state["rounds"][0]["bye"])
        self.assertEqual(sum(v["alive"] for v in state["agents"].values()), 1)

    def test_1_agent_is_already_the_winner(self):
        d, state, sizes = self.run_tournament(1, 1)
        self.assertEqual(sizes, [1])
        self.assertEqual(state["rounds"], [])
        self.assertEqual(state["champion"], "a001")
        self.assertIn("0 played, 1 agents in, 1 left", self.ok("winner", "--dir", d))
        self.assertIn("last one standing", self.ok("pairings", "--dir", d))

    def test_many_sizes_and_seeds_always_end_with_one(self):
        data = B.load_strategies()
        for n in (2, 3, 5, 9, 16, 31, 64, 100, 101, 144, 250):
            for seed in range(3):
                st = B.new_state(n, seed, data, os.path.join(self.tmp, "api"))
                rng = random.Random(seed)
                sizes = []
                while not st["champion"]:
                    rd = B.current_round(st)
                    sizes.append(len(rd["alive"]))
                    for m in rd["matches"]:
                        B.record(st, m["id"], rng.choice([m["a"], m["b"]]))
                    B.advance(st)
                self.assertEqual(sizes + [1], B.bracket_sizes(n))
                self.assertEqual(len(B.alive_ids(st)), 1)


class Dealer(unittest.TestCase):
    def setUp(self):
        self.data = B.load_strategies()

    def test_card_count(self):
        self.assertEqual(len(self.data["reasoning"]), 15)
        self.assertEqual(len(self.data["workflows"]), 12)
        self.assertEqual(len(self.data["strategies"]), 12)
        self.assertEqual(B.combo_count(self.data), 2160)

    def check(self, n, seed):
        cards = B.deal(n, seed, self.data)
        self.assertEqual(len(cards), n)
        self.assertEqual(len(set(cards)), n, "no card is dealt twice")
        for dim, size in enumerate((15, 12, 12)):
            count = collections.Counter(c[dim] for c in cards)
            per = [count.get(i, 0) for i in range(size)]
            self.assertLessEqual(max(per) - min(per), 1, "balanced: n=%d seed=%d dim=%d %s" % (n, seed, dim, per))
        if n <= 144:
            for a, b in ((0, 1), (0, 2), (1, 2)):
                pairs = collections.Counter((c[a], c[b]) for c in cards)
                self.assertEqual(max(pairs.values()), 1, "two agents share two parts: n=%d seed=%d" % (n, seed))
        return cards

    def test_100_agents_unique_balanced_and_every_part_used(self):
        cards = self.check(100, 7)
        self.assertEqual(len({c[0] for c in cards}), 15)
        self.assertEqual(len({c[1] for c in cards}), 12)
        self.assertEqual(len({c[2] for c in cards}), 12)

    def test_guarantees_hold_across_sizes_and_seeds(self):
        for n in (1, 2, 7, 16, 32, 50, 99, 100, 101, 144):
            for seed in range(25):
                self.check(n, seed)
        for n in (145, 180, 500, 2160):
            self.check(n, 1)

    def test_deterministic_for_a_seed(self):
        self.assertEqual(B.deal(100, 42, self.data), B.deal(100, 42, self.data))
        self.assertNotEqual(B.deal(100, 42, self.data), B.deal(100, 43, self.data))

    def test_out_of_range(self):
        with self.assertRaises(B.ArenaError):
            B.deal(0, 1, self.data)
        with self.assertRaises(B.ArenaError):
            B.deal(2161, 1, self.data)

    def test_pairing_prefers_different_reasoning_modes(self):
        for seed in range(50):
            st = B.new_state(100, seed, self.data, "/tmp/unused")
            same = 0
            for m in st["rounds"][0]["matches"]:
                a, b = st["agents"][m["a"]], st["agents"][m["b"]]
                same += a["card"]["reasoning"]["id"] == b["card"]["reasoning"]["id"]
            self.assertLessEqual(same, 1, "at most one forced same-mode match in a 50-match round")


class Plan(unittest.TestCase):
    def test_numbers(self):
        self.assertEqual(B.bracket_sizes(100), [100, 50, 25, 13, 7, 4, 2, 1])
        t = B.plan_totals(100)
        self.assertEqual((t["rounds"], t["calls"], t["waves"]), (7, 601, 70))
        t = B.plan_totals(16)
        self.assertEqual((t["rounds"], t["calls"], t["waves"]), (4, 97, 16))

    def test_panel_in_the_last_two_rounds(self):
        self.assertEqual([B.judges_in(100, r) for r in range(1, 8)], [1, 1, 1, 1, 1, 3, 3])
        self.assertEqual([B.judges_in(16, r) for r in range(1, 5)], [1, 1, 3, 3])
        self.assertEqual(B.judges_in(2, 1), 3)


class Verdicts(unittest.TestCase):
    def scores(self, c, m, s, r, cl, fatal=False):
        return {"correctness": c, "completeness": m, "specificity": s, "robustness": r, "clarity": cl, "fatal": fatal}

    def test_weights_come_from_the_rubric_table(self):
        self.assertEqual(W, [("correctness", 30), ("completeness", 25), ("specificity", 15),
                             ("robustness", 20), ("clarity", 10)])
        creative = B.load_weights(B.rubric_path("creative"))
        self.assertEqual([k for k, _ in creative], ["fit", "impact", "distinctiveness", "robustness", "clarity"])
        self.assertEqual(sum(w for _, w in creative), 100)

    def test_tie_goes_to_the_heaviest_criterion(self):
        creative = B.load_weights(B.rubric_path("creative"))
        rest = {"distinctiveness": 7, "robustness": 7, "clarity": 7}
        v = {"scores": {"a001": dict(rest, fit=5, impact=10), "a002": dict(rest, fit=10, impact=4)}}
        w, totals, _ = B.decide(v, "a001", "a002", creative)
        self.assertEqual(totals["a001"], totals["a002"])
        self.assertEqual(w, "a002")

    def test_total(self):
        self.assertEqual(B.weighted_total(self.scores(10, 10, 10, 10, 10), W), 100.0)
        self.assertEqual(B.weighted_total(self.scores(8, 6, 7, 5, 9), W), 68.5)   # (240 + 150 + 105 + 100 + 90) / 10
        self.assertIsNone(B.weighted_total({"correctness": 8}, W))

    def test_scores_beat_the_judges_pick(self):
        v = {"scores": {"a001": self.scores(5, 5, 5, 5, 5), "a002": self.scores(8, 8, 8, 8, 8)}, "winner": "a001"}
        w, totals, note = B.decide(v, "a001", "a002", W)
        self.assertEqual(w, "a002")
        self.assertIn("scores win", note)

    def test_fatal_rule(self):
        v = {"scores": {"a001": self.scores(9, 9, 9, 9, 9, fatal=True), "a002": self.scores(4, 4, 4, 4, 4)}}
        self.assertEqual(B.decide(v, "a001", "a002", W)[0], "a002")

    def test_tie_goes_to_fewer_standing_attacks(self):
        v = {"scores": {"a001": self.scores(7, 7, 7, 7, 7), "a002": self.scores(7, 7, 7, 7, 7)},
             "standing": {"a001": ["x", "y"], "a002": ["z"]}}
        self.assertEqual(B.decide(v, "a001", "a002", W)[0], "a002")

    def test_incomplete_scores_fall_back_to_the_pick(self):
        v = {"scores": {"a001": {"correctness": 3}}, "winner": "a001"}
        self.assertEqual(B.decide(v, "a001", "a002", W)[0], "a001")
        with self.assertRaises(B.ArenaError):
            B.decide({"scores": {}}, "a001", "a002", W)

    def test_json_inside_a_code_fence(self):
        self.assertEqual(B.extract_json('```json\n{"winner": "a001"}\n```'), {"winner": "a001"})
        self.assertIsNone(B.extract_json("no json here"))


class FullPipelineWithFakeAgents(TempDir):
    """Every phase, through the CLI, with fake sub-agents writing the files real ones would."""

    TASK = "Write a haiku about the sea.\nIt must mention salt.\nLiteral braces stay: {{name}} and {not_a_placeholder}."

    def fake_outputs(self, state, phase, jobs, rng):
        for j in jobs:
            for path in j["outputs"]:
                os.makedirs(os.path.dirname(path), exist_ok=True)
            if phase == "spawn":
                body = "Salt on the wind, from %s." % j["agent"]
                write(j["outputs"][0], body)
            elif phase == "attack":
                write(j["outputs"][0], "ATTACK 1 [MINOR] too short\nWhere: line 1\nProblem: it is short.\n")
            elif phase == "defend":
                write(j["outputs"][0], "ATTACK 1: CONCEDE. Made it longer.\n")
                write(j["outputs"][1], "Salt on the long wind, revised by %s." % j["agent"])
            elif phase == "judge":
                a, b = j["a"], j["b"]
                s = lambda: {k: rng.randint(3, 10) for k, _ in state["weights"]}
                v = {"match": j["match"], "scores": {a: s(), b: s()}, "winner": a, "reason": "fake",
                     "survived": ["too short"], "standing": {a: [], b: []}}
                write(j["outputs"][0], json.dumps(v))
            elif phase == "final":
                v = {"scores": {"X": {k: 8 for k, _ in state["weights"]}, "Y": {k: 4 for k, _ in state["weights"]}},
                     "winner": "X", "reason": "fake", "fixed": ["salt"]}
                write(j["outputs"][0], json.dumps(v))

    def test_every_phase_to_done(self):
        d = os.path.join(self.tmp, "run")
        task_file = os.path.join(self.tmp, "task.md")
        base_file = os.path.join(self.tmp, "baseline.md")
        write(task_file, self.TASK)
        write(base_file, "The sea is big.")
        self.ok("init", "--agents", 5, "--seed", 9, "--task-file", task_file, "--baseline-file", base_file, "--dir", d)
        self.assertTrue(os.path.isfile(os.path.join(d, "rubric.md")), "the run has its own rubric copy")
        rng = random.Random(9)
        seen = []
        for _ in range(200):
            out = self.ok("next", "--dir", d)
            phase = re.search(r"^(NEXT: (\w+)|DONE)", out, re.M)
            phase = "done" if phase.group(0) == "DONE" else phase.group(2)
            seen.append(phase)
            if phase == "done":
                break
            if phase in ("collect", "advance"):
                self.ok(phase, "--dir", d)
                continue
            listing = self.ok("prompts", phase, "--dir", d)
            state = load(d)
            jobs = B.phase_jobs(state, phase)
            for j in jobs:
                self.assertIn(j["prompt"], listing)
                with open(j["prompt"], encoding="utf-8") as fh:
                    brief = fh.read()
                self.assertNotIn("{{agent", brief)
                self.assertNotIn("{{out", brief)
                self.assertNotRegex(brief.replace("{{name}}", ""), r"\{\{\w+\}\}", "unfilled placeholder")
                if phase == "spawn":
                    task_block = brief.split("=== THE TASK (identical for every competitor) ===\n")[1]
                    task_block = task_block.split("\n=== END OF THE TASK ===")[0]
                    self.assertEqual(task_block, self.TASK)
                    card = state["agents"][j["agent"]]["card"]
                    self.assertIn("Reasoning mode: %s." % card["reasoning"]["name"], brief)
                    self.assertIn("NOT satisfied", brief)
                if phase == "judge":
                    self.assertNotIn("Reasoning mode", brief, "judges never see the cards")
            self.fake_outputs(state, phase, jobs, rng)
            self.ok("check", phase, "--dir", d)
        self.assertEqual(seen[-1], "done")
        self.assertIn("spawn", seen)
        self.assertIn("final", seen)
        self.assertEqual(seen.count("advance"), 3, "5 agents take 3 rounds")
        state = load(d)
        champ = state["agents"][state["champion"]]
        self.assertIn(".solution.md", champ["solution"], "the champion carries its revised solution")
        self.assertIn("revised by %s" % state["champion"], read(champ["solution"]))
        pair = {read(os.path.join(d, "final", "X.md")).strip(), read(os.path.join(d, "final", "Y.md")).strip()}
        self.assertIn("The sea is big.", pair)
        rep = json.loads(self.ok("winner", "--json", "--dir", d))
        self.assertEqual(rep["rounds"], 3)
        self.assertEqual(rep["final"]["better"], state["final"]["X"])
        self.assertTrue(rep["attacks_survived"])

    def test_spawn_briefs_share_one_task_and_differ_in_card(self):
        d = os.path.join(self.tmp, "run16")
        self.ok("init", "--quick", "--seed", 4, "--task", self.TASK, "--dir", d)
        self.ok("prompts", "spawn", "--dir", d)
        blocks, cards = set(), set()
        for name in sorted(os.listdir(os.path.join(d, "prompts", "r0"))):
            brief = read(os.path.join(d, "prompts", "r0", name))
            blocks.add(brief.split("=== THE TASK (identical for every competitor) ===\n")[1].split("\n=== END")[0])
            cards.add(brief.split("=== YOUR STRATEGY CARD ===")[1].split("=== END OF THE CARD ===")[0])
        self.assertEqual(len(os.listdir(os.path.join(d, "prompts", "r0"))), 16)
        self.assertEqual(blocks, {self.TASK}, "every competitor gets the exact same task text")
        self.assertEqual(len(cards), 16, "every competitor gets a different card")

    def test_unreadable_verdict_is_set_aside_and_rerun(self):
        d = os.path.join(self.tmp, "bad")
        self.ok("init", "--agents", 2, "--seed", 1, "--task", "t", "--dir", d)
        state = load(d)
        m = state["rounds"][0]["matches"][0]
        path = B.verdict_out(d, 1, m["id"], 1)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        write(path, "the judge rambled and wrote no json")
        r = cli("collect", "--dir", d)
        self.assertEqual(r.returncode, 1)
        self.assertIn("unreadable", r.stdout)
        self.assertFalse(os.path.exists(path))
        self.assertTrue(os.path.exists(path + ".unreadable"))


class FailedJobs(TempDir):
    """bracket.py fail: stand-ins for a job that failed twice, by phase."""

    def setUp(self):
        super().setUp()
        self.d = os.path.join(self.tmp, "run")
        self.ok("init", "--agents", 2, "--seed", 1, "--task", "t", "--dir", self.d)
        m = load(self.d)["rounds"][0]["matches"][0]
        self.mid, self.a, self.b = m["id"], m["a"], m["b"]

    def fail(self, job_id):
        return self.ok("fail", job_id, "--dir", self.d)

    def test_failed_spawn_has_no_solution(self):
        os.makedirs(os.path.join(self.d, "r0"))
        write(B.spawn_out(self.d, self.a), "real work")
        self.assertIn("already has all its outputs", self.fail(self.a + ".spawn"))
        self.fail(self.b + ".spawn")
        self.assertEqual(read(B.spawn_out(self.d, self.a)), "real work")
        self.assertEqual(read(B.spawn_out(self.d, self.b)), "NO OUTPUT\n")

    def test_failed_attack_is_no_attacks(self):
        os.makedirs(os.path.join(self.d, "r0"))
        for aid in (self.a, self.b):
            write(B.spawn_out(self.d, aid), "solution of %s" % aid)
        self.fail("%s.%s.attack" % (self.mid, self.a))
        self.assertEqual(read(B.attack_out(self.d, 1, self.mid, self.a)), "NO OUTPUT\n")

    def test_failed_defense_keeps_the_solution(self):
        os.makedirs(os.path.join(self.d, "r1"))
        os.makedirs(os.path.join(self.d, "r0"))
        for aid in (self.a, self.b):
            write(B.spawn_out(self.d, aid), "solution of %s" % aid)
            write(B.attack_out(self.d, 1, self.mid, aid), "ATTACK 1 [MINOR] x\n")
        write(B.defense_out(self.d, 1, self.mid, self.a), "ATTACK 1: REBUT. no.\n")
        self.fail("%s.%s.defend" % (self.mid, self.a))
        self.fail("%s.%s.defend" % (self.mid, self.b))
        self.assertEqual(read(B.defense_out(self.d, 1, self.mid, self.a)), "ATTACK 1: REBUT. no.\n")
        self.assertEqual(read(B.defense_out(self.d, 1, self.mid, self.b)), "NO OUTPUT\n")
        for aid in (self.a, self.b):
            self.assertEqual(read(B.revised_out(self.d, 1, self.mid, aid)), "solution of %s" % aid)
        self.assertIn("NEXT: judge", self.ok("next", "--dir", self.d))

    def test_judges_and_unknown_jobs_are_refused(self):
        r = cli("fail", "%s.judge1" % self.mid, "--dir", self.d)
        self.assertEqual(r.returncode, 2)
        self.assertIn("fresh run", r.stderr)
        self.assertEqual(cli("fail", "r9-m01.a001.attack", "--dir", self.d).returncode, 2)


class Panel(TempDir):
    """The last rounds: three judges per match, alternating order, majority wins."""

    def setUp(self):
        super().setUp()
        self.d = os.path.join(self.tmp, "run")
        self.ok("init", "--agents", 2, "--seed", 1, "--task", "t", "--dir", self.d)
        m = load(self.d)["rounds"][0]["matches"][0]
        self.mid, self.a, self.b = m["id"], m["a"], m["b"]
        os.makedirs(os.path.join(self.d, "r1"))

    def verdict(self, k, high, low):
        s = lambda x: {c: x for c, _ in W}
        write(B.verdict_out(self.d, 1, self.mid, k),
              json.dumps({"scores": {high: s(8), low: s(5)}, "winner": high, "reason": "judge %d" % k}))

    def test_judges_alternate_who_is_read_first(self):
        jobs = B.phase_jobs(load(self.d), "judge")
        self.assertEqual([j["id"] for j in jobs], ["%s.judge%d" % (self.mid, k) for k in (1, 2, 3)])
        self.assertEqual([(j["a"], j["b"]) for j in jobs],
                         [(self.a, self.b), (self.b, self.a), (self.a, self.b)])

    def test_majority_wins_and_totals_are_averaged(self):
        self.verdict(1, self.b, self.a)
        self.verdict(2, self.a, self.b)
        self.verdict(3, self.a, self.b)
        out = self.ok("collect", "--dir", self.d)
        self.assertIn("(panel 2-1)", out)
        m = load(self.d)["rounds"][0]["matches"][0]
        self.assertEqual((m["winner"], m["source"], m["reason"]), (self.a, "panel 2-1", "judge 2"))
        self.assertEqual(m["scores"], {self.a: 70.0, self.b: 60.0})

    def test_a_missing_panel_verdict_holds_the_match(self):
        self.verdict(1, self.a, self.b)
        self.verdict(2, self.a, self.b)
        r = cli("collect", "--dir", self.d)
        self.assertEqual(r.returncode, 1)
        self.assertIn("%s.judge3" % self.mid, r.stdout)
        self.assertIsNone(load(self.d)["rounds"][0]["matches"][0]["winner"])


class Rubrics(TempDir):
    def judge_brief(self, *rubric):
        d = os.path.join(self.tmp, "run" + "".join(rubric))
        self.ok("init", "--agents", 2, "--seed", 1, "--task", "t", "--dir", d, *rubric)
        self.ok("prompts", "judge", "--dir", d)
        mid = load(d)["rounds"][0]["matches"][0]["id"]
        return d, read(B.prompt_path(d, 1, mid + ".judge1"))

    def test_default_rubric_brief(self):
        d, brief = self.judge_brief()
        blank = '{"correctness": 0, "completeness": 0, "specificity": 0, "robustness": 0, "clarity": 0, "fatal": false}'
        self.assertEqual(brief.count(blank), 2)
        self.assertEqual(load(d)["rubric"], "default")

    def test_creative_rubric_is_copied_and_scored(self):
        d, brief = self.judge_brief("--rubric", "creative")
        self.assertIn('{"fit": 0, "impact": 0, "distinctiveness": 0, "robustness": 0, "clarity": 0, "fatal": false}', brief)
        self.assertNotIn("correctness", brief)
        self.assertEqual(read(os.path.join(d, "rubric.md")), read(B.rubric_path("creative")))
        self.assertEqual(load(d)["weights"], [list(kw) for kw in B.load_weights(B.rubric_path("creative"))])

    def test_unknown_rubric_is_refused(self):
        r = cli("init", "--agents", 2, "--task", "t", "--rubric", "nope", "--dir", os.path.join(self.tmp, "x"))
        self.assertEqual(r.returncode, 2)
        self.assertIn("creative", r.stderr)
        self.assertFalse(os.path.exists(os.path.join(self.tmp, "x")), "nothing is created for a bad rubric")

    def test_bad_weights_are_refused(self):
        bad = os.path.join(self.tmp, "bad.md")
        for table in ("| A | 50 | q |\n| B | 40 | q |\n", "| A | 50 | q |\n| A | 50 | q |\n",
                      "| A | 50 | q |\n| Fatal | 50 | q |\n", "no table\n"):
            write(bad, table)
            with self.assertRaises(B.ArenaError):
                B.load_weights(bad)


class Briefs(TempDir):
    def test_half_the_field_never_sees_the_rejected_answer(self):
        d = os.path.join(self.tmp, "run")
        base = os.path.join(self.tmp, "old.md")
        write(base, "The sea is big.")
        self.ok("init", "--agents", 4, "--seed", 1, "--task", "t", "--baseline-file", base, "--dir", d)
        self.ok("prompts", "spawn", "--dir", d)
        for aid, sees in (("a001", True), ("a002", False), ("a003", True), ("a004", False)):
            brief = read(B.prompt_path(d, 0, aid + ".spawn"))
            self.assertEqual(os.path.join(d, "baseline.md") in brief, sees, aid)
            self.assertEqual("You are not shown that answer" in brief, not sees, aid)

    def test_judge_sees_word_counts_before_and_after_the_defense(self):
        d = os.path.join(self.tmp, "run")
        self.ok("init", "--agents", 2, "--seed", 1, "--task", "t", "--dir", d)
        m = load(d)["rounds"][0]["matches"][0]
        os.makedirs(os.path.join(d, "r0"))
        os.makedirs(os.path.join(d, "r1"))
        write(B.spawn_out(d, m["a"]), "one two three")
        write(B.revised_out(d, 1, m["id"], m["a"]), "one two three four five")
        write(B.spawn_out(d, m["b"]), "one two")
        write(B.revised_out(d, 1, m["id"], m["b"]), "one two")
        self.ok("prompts", "judge", "--dir", d)
        brief = read(B.prompt_path(d, 1, m["id"] + ".judge1"))
        self.assertIn("%s (5 words, 3 before the defense)" % B.revised_out(d, 1, m["id"], m["a"]), brief)
        self.assertIn("%s (2 words, 2 before the defense)" % B.revised_out(d, 1, m["id"], m["b"]), brief)

    def test_models_are_printed_per_phase(self):
        cases = ((("--model", "sonnet", "--judge-model", "opus"), "model: sonnet", "model: opus"),
                 (("--model", "haiku"), "model: haiku", "model: haiku"),
                 ((), None, None))
        for k, (flags, spawn_line, judge_line) in enumerate(cases):
            d = os.path.join(self.tmp, "run%d" % k)
            self.ok("init", "--agents", 2, "--seed", 1, "--task", "t", "--dir", d, *flags)
            for phase, line in (("spawn", spawn_line), ("judge", judge_line)):
                out = self.ok("prompts", phase, "--dir", d)
                if line:
                    self.assertIn(line + ",", out)
                else:
                    self.assertNotIn("model:", out)


FAKE_CLAUDE = r'''#!%(python)s
"""Stands in for the claude CLI: writes what a real sub-agent would for the job in the brief."""
import json, os, re, sys
sys.path.insert(0, %(skill)r)
import bracket as B
argv = sys.argv[1:]
if "--help" in argv:
    flags = [f for f in B.NEEDED_FLAGS if f != os.environ.get("FAKE_LACK")]
    print("Options:\n" + "\n".join("  %%s <x>" %% f for f in flags))
    sys.exit(0)
brief = re.match(r"Read (\S+) and follow", argv[argv.index("-p") + 1]).group(1)
d = brief.split(os.sep + "prompts" + os.sep)[0]
job_id = os.path.basename(brief)[:-3]
with open(os.environ["FAKE_LOG"], "a") as fh:
    fh.write(json.dumps({"job": job_id, "argv": argv, "cwd": os.getcwd()}) + "\n")
if any(p and p in job_id for p in os.environ.get("FAKE_FAIL", "").split(",")):
    sys.exit(1)
state = json.load(open(os.path.join(d, "arena.json")))
job = next(j for ph in B.PHASES for j in B.phase_jobs(state, ph) if j["id"] == job_id)
def put(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    open(path, "w").write(text)
s = {k: 7 for k, _ in state["weights"]}
if job["kind"] == "competitor":
    put(job["outputs"][0], "solution by %%s" %% job["agent"])
elif job["kind"] == "attacker":
    put(job["outputs"][0], "ATTACK 1 [MINOR] short\n")
elif job["kind"] == "defender":
    put(job["outputs"][0], "ATTACK 1: CONCEDE. ok\n")
    put(job["outputs"][1], "revised by %%s" %% job["agent"])
elif job["kind"] == "judge":
    put(job["outputs"][0], json.dumps({"scores": {job["a"]: dict(s, correctness=9), job["b"]: s}, "winner": job["a"]}))
elif job["kind"] == "synth":
    champ = state["agents"][state["champion"]]["solution"]
    put(job["outputs"][0], open(champ).read() if os.environ.get("FAKE_SYNTH_SAME") else "merged by the editor")
elif job["kind"] == "synthjudge":
    x = "merged" in open(os.path.join(d, "synth", "X.md")).read()
    good, bad = ("X", "Y") if x else ("Y", "X")
    put(job["outputs"][0], json.dumps({"scores": {good: dict(s, correctness=9), bad: s}, "winner": good}))
else:
    put(job["outputs"][0], json.dumps({"scores": {"X": dict(s, correctness=9), "Y": s}, "winner": "X"}))
print(json.dumps([{"type": "system"}, {"type": "result", "total_cost_usd": 0.01, "permission_denials": []}]))
'''


class HeadlessRun(TempDir):
    """bracket.py run, with a fake claude CLI."""

    def setUp(self):
        super().setUp()
        self.fake = os.path.join(self.tmp, "claude")
        write(self.fake, FAKE_CLAUDE % {"python": sys.executable, "skill": SKILL})
        os.chmod(self.fake, 0o755)
        self.log = os.path.join(self.tmp, "calls.jsonl")
        self.d = os.path.join(self.tmp, "run")

    def run_arena(self, *init, fail="", lack="", same=""):
        if not os.path.exists(os.path.join(self.d, "arena.json")):
            self.ok("init", "--seed", 3, "--task", "t", "--dir", self.d, *init)
        env = dict(os.environ, FAKE_LOG=self.log, FAKE_FAIL=fail, FAKE_LACK=lack, FAKE_SYNTH_SAME=same)
        return subprocess.run([sys.executable, BRACKET, "run", "--dir", self.d, "--claude", self.fake, "--parallel", "4"],
                              capture_output=True, text=True, env=env)

    def calls(self):
        with open(self.log) as fh:
            return [json.loads(line) for line in fh]

    def test_runs_every_phase_to_a_champion(self):
        base = os.path.join(self.tmp, "old.md")
        write(base, "old answer")
        r = self.run_arena("--agents", 5, "--baseline-file", base, "--model", "sonnet", "--judge-model", "opus")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("DONE. Sub-agent cost about $0.", r.stdout)
        state = load(self.d)
        self.assertTrue(state["champion"])
        self.assertEqual(state["final"]["result"]["better"], state["final"]["X"])
        calls = self.calls()
        self.assertEqual(len(calls), B.plan_totals(5)["calls"] + 1)
        for c in calls:
            argv = c["argv"]
            self.assertEqual(argv[argv.index("--tools") + 1], "Read,Grep,Glob,Write,WebSearch")
            self.assertEqual(argv[argv.index("--allowedTools") + 1], "WebSearch Edit(/%s/**)" % self.d)
            self.assertEqual(argv[argv.index("--permission-prompts") + 1], "none")
            self.assertIn("--safe-mode", argv)
            judge = ".judge" in c["job"]
            self.assertEqual(argv[argv.index("--model") + 1], "opus" if judge else "sonnet", c["job"])
            self.assertEqual(os.path.realpath(c["cwd"]), os.path.realpath(state["workdir"]))
        self.assertIn("You run one job", calls[0]["argv"][calls[0]["argv"].index("--append-system-prompt") + 1])

    def test_a_job_that_fails_twice_gets_a_stand_in(self):
        r = self.run_arena("--agents", 4, fail="a002.spawn")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("got stand-ins: a002.spawn", r.stdout)
        self.assertEqual([c["job"] for c in self.calls()].count("a002.spawn"), 2)
        self.assertEqual(read(B.spawn_out(self.d, "a002")), "NO OUTPUT\n")
        self.assertNotIn("--model", self.calls()[0]["argv"], "no model flag unless one was given")

    def test_a_failing_judge_stops_the_run_and_a_second_run_finishes(self):
        r = self.run_arena("--agents", 2, fail="judge")
        self.assertEqual(r.returncode, 2)
        self.assertIn("failed 3 times", r.stderr)
        self.assertIsNone(load(self.d)["champion"])
        r = self.run_arena()
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertTrue(load(self.d)["champion"])

    def test_synthesis_that_wins_goes_to_the_final_check(self):
        base = os.path.join(self.tmp, "old.md")
        write(base, "old answer")
        r = self.run_arena("--agents", 5, "--baseline-file", base, "--synth", "--judge-model", "opus")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        state = load(self.d)
        self.assertEqual(state["synth"]["result"]["better"], "merged")
        self.assertEqual(state["synth"]["result"]["votes"], "3-0")
        jobs = [c["job"] for c in self.calls()]
        self.assertEqual(len(jobs), B.plan_totals(5)["calls"] + 1 + 3 + 1)
        self.assertLess(jobs.index("synth.judge3"), jobs.index("final.judge"))
        judge = next(c["argv"] for c in self.calls() if c["job"] == "synth.judge1")
        self.assertEqual(judge[judge.index("--model") + 1], "opus")
        brief = read(B.prompt_path(self.d, None, "synth.merge"))
        runners = B.runners_up(state)
        self.assertEqual(len(runners), 2, "5 agents: one out in each of the last two rounds")
        for aid in runners:
            self.assertIn(state["agents"][aid]["solution"], brief)
        self.assertNotIn(state["champion"] + ".", brief.split("runners-up, latest")[1].split("The judges")[0])
        finalists = {read(os.path.join(self.d, "final", f)) for f in ("X.md", "Y.md")}
        self.assertEqual(finalists, {"merged by the editor", "old answer\n"})
        rep = json.loads(self.ok("winner", "--json", "--dir", self.d))
        self.assertEqual(rep["solution"], B.synth_out(self.d))
        self.assertIn("synthesis: the edited version beat the champion", self.ok("winner", "--dir", self.d))

    def test_an_edit_that_changes_nothing_is_not_judged(self):
        r = self.run_arena("--agents", 4, "--synth", same="1")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertNotIn("synth.judge1", [c["job"] for c in self.calls()])
        state = load(self.d)
        self.assertEqual(state["synth"]["result"]["better"], "champion")
        self.assertEqual(B.winner_report(state)["solution"], state["agents"][state["champion"]]["solution"])

    def test_a_failed_edit_keeps_the_champion(self):
        r = self.run_arena("--agents", 4, "--synth", fail="synth.merge")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("got stand-ins: synth.merge", r.stdout)
        self.assertEqual(load(self.d)["synth"]["result"]["better"], "champion")

    def test_one_agent_has_nobody_to_borrow_from(self):
        r = self.run_arena("--agents", 1, "--synth")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual([c["job"] for c in self.calls()], ["a001.spawn"])
        self.assertEqual(load(self.d)["synth"]["result"]["reason"], "no runners-up to borrow from")

    def test_an_old_cli_is_refused_before_anything_runs(self):
        r = self.run_arena("--agents", 2, lack="--safe-mode")
        self.assertEqual(r.returncode, 2)
        self.assertIn("lacks --safe-mode", r.stderr)
        self.assertFalse(os.path.exists(self.log))


class Guards(TempDir):
    def test_init_refuses_to_overwrite_and_bad_sizes(self):
        d = os.path.join(self.tmp, "run")
        self.ok("init", "--agents", 4, "--task", "t", "--dir", d)
        self.assertEqual(cli("init", "--agents", 4, "--task", "t", "--dir", d).returncode, 2)
        self.assertEqual(cli("init", "--agents", 0, "--task", "t", "--dir", d + "2").returncode, 2)
        self.assertEqual(cli("init", "--agents", 2161, "--task", "t", "--dir", d + "3").returncode, 2)
        self.assertEqual(cli("init", "--quick", "--agents", 8, "--task", "t", "--dir", d + "4").returncode, 2)
        self.assertEqual(cli("init", "--agents", 4, "--task", "   ", "--dir", d + "5").returncode, 2)

    def test_quick_is_16(self):
        d = os.path.join(self.tmp, "quick")
        self.ok("init", "--quick", "--task", "t", "--dir", d)
        self.assertEqual(load(d)["agents_n"], 16)

    def test_default_is_16_and_full_is_100(self):
        d = os.path.join(self.tmp, "sizes")
        self.ok("init", "--task", "t", "--dir", d + "1")
        self.assertEqual(load(d + "1")["agents_n"], 16)
        self.ok("init", "--full", "--task", "t", "--dir", d + "2")
        self.assertEqual(load(d + "2")["agents_n"], 100)
        self.assertIn("16 agents, 4 rounds", self.ok("plan"))
        self.assertIn("100 agents, 7 rounds", self.ok("plan", "--full"))
        self.assertEqual(cli("init", "--full", "--agents", 8, "--task", "t", "--dir", d + "3").returncode, 2)
        self.assertEqual(cli("init", "--full", "--quick", "--task", "t", "--dir", d + "4").returncode, 2)

    def test_init_keeps_run_files_out_of_git(self):
        r = cli("init", "--agents", 2, "--task", "t", cwd=self.tmp)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(read(os.path.join(self.tmp, ".arena", ".gitignore")), "*\n")
        d = os.path.join(self.tmp, "custom")
        self.ok("init", "--agents", 2, "--task", "t", "--dir", d)
        self.assertEqual(read(os.path.join(d, ".gitignore")), "*\n")

    def test_printed_commands_work_from_any_directory(self):
        d = os.path.join(self.tmp, "run")
        self.ok("init", "--agents", 2, "--task", "t", "--dir", d)
        line = next(x for x in self.ok("next", "--dir", d).splitlines() if " prompts spawn " in x)
        printed = shlex.split(line.split(". ", 1)[1])
        self.assertEqual(printed[-2:], ["--dir", d])
        elsewhere = os.path.join(self.tmp, "elsewhere")
        os.makedirs(elsewhere)
        r = subprocess.run([sys.executable] + printed[1:], capture_output=True, text=True, cwd=elsewhere)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("round 0, spawn: 2 job(s)", r.stdout)

    def test_record_rejects_an_outsider(self):
        d = os.path.join(self.tmp, "rec")
        self.ok("init", "--agents", 4, "--seed", 2, "--task", "t", "--dir", d)
        m = load(d)["rounds"][0]["matches"][0]
        outsider = next(a for a in load(d)["agents"] if a not in (m["a"], m["b"]))
        self.assertEqual(cli("record", m["id"], outsider, "--dir", d).returncode, 2)
        self.assertEqual(cli("advance", "--dir", d).returncode, 2, "cannot advance with open matches")

    def test_every_template_file_exists(self):
        self.assertEqual(sorted(B.load_templates()), sorted(B.TEMPLATES))

    def test_worker_agent_cannot_edit(self):
        text = read(os.path.join(REPO, "agents", "arena-worker.md"))
        front = text.split("---\n")[1]
        self.assertIn("name: arena-worker\n", front)
        tools = re.search(r"^tools: (.*)$", front, re.M).group(1).split(", ")
        self.assertIn("Write", tools)
        self.assertNotIn("Edit", tools)
        self.assertNotIn("NotebookEdit", tools)
        self.assertIn("arena-skill:arena-worker", read(os.path.join(SKILL, "SKILL.md")))

    def test_no_em_dashes_anywhere(self):
        for root, dirs, files in os.walk(REPO):
            dirs[:] = [x for x in dirs if x not in (".git", "__pycache__")]
            for name in files:
                path = os.path.join(root, name)
                with open(path, encoding="utf-8", errors="ignore") as fh:
                    text = fh.read()
                self.assertNotIn(EM_DASH, text, "em dash in %s" % os.path.relpath(path, REPO))
                self.assertNotIn(EN_DASH, text, "en dash in %s" % os.path.relpath(path, REPO))


if __name__ == "__main__":
    unittest.main(verbosity=2)
