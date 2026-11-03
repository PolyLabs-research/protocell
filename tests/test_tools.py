"""The tools for looking at the cell (tools/): the simulation's observer, the replays, the network page."""

from __future__ import annotations

import base64
import json
import re

import protocell  # noqa: F401
import numpy as np
import pytest

from experiments.cave import SEED, configure
from protocell.cell import decode, random_genomes
from protocell.config import CAVE, STAGE0
from protocell.rng import stream
from protocell.sim import simulate
from protocell.world import lifetimes, sample_starts
from tests.test_stage0_pinned import RECORDED, RECORDED_ON, platform_fingerprint
from tools import pages
from tools.network_doc import describe
from tools.replay import MAX_CELLS, parse_cell, record, write_page


def _dec(b64: str, dtype: str) -> np.ndarray:
    return np.frombuffer(base64.b64decode(b64), dtype=dtype)


def test_the_observer_reads_without_changing_a_run() -> None:
    genomes = random_genomes(STAGE0, "fourier1", 5, stream(0, "genomes"))
    few = sample_starts(STAGE0, "spot", 100, 0).numbered(range(51, 56))
    seen = []
    spec = {"controller": "network", "mode": "fourier1", "genomes": genomes}
    run = simulate(STAGE0, few, spec, seed=0, cell_ids=[1, 2, 3, 4, 5], record=True,
                   observe=lambda t, s: seen.append((t, s["beats"].shape, float(s["energy"][0]))))
    alone = simulate(STAGE0, few, spec, seed=0, cell_ids=[1, 2, 3, 4, 5], record=True)
    assert run.run_hash() == alone.run_hash()  # the same bits with an observer attached, on any platform
    if platform_fingerprint() == RECORDED_ON:
        assert run.run_hash() == RECORDED["spot"]  # and stage 0's recorded hash, on the platform that recorded it
    assert [t for t, _, _ in seen] == list(range(STAGE0.lifetime)) and seen[0][1] == (5, 16)
    assert seen[-1][2] == run.final_energy[0]
    cfg = configure("burn", quick=True)
    starts = sample_starts(cfg, "cave", 4, SEED)
    spec = {"controller": "reflex", "k": 30.0, "rest_below": cfg.rest_below, "retreat_above": cfg.damage_threshold}
    quiet = simulate(cfg, starts, spec, seed=SEED, record=True)
    watched = simulate(cfg, starts, spec, seed=SEED, record=True, observe=lambda t, s: None)
    assert quiet.run_hash() == watched.run_hash() and np.array_equal(quiet.fitness, watched.fitness)


def test_a_replay_keeps_its_frames_and_matches_the_run(tmp_path) -> None:
    cfg = configure("burn", quick=True)  # a 2,000-tick day
    starts = sample_starts(cfg, "cave", 3, SEED).numbered([3])
    cells = [parse_cell("b0", cfg, "burn"), parse_cell("b2rr:30", cfg, "burn"), parse_cell("genome:fourier1:2", cfg, "burn")]
    assert cells[1].spec["retreat_on"] == "max"  # the replays' B2rr is the amended one (cave.md A1)
    rep = record(cfg, "burn", starts, cells, stride=7)
    life = int(lifetimes(cfg, starts)[0])
    ticks = _dec(rep["tick"], "<i4")
    expected = list(range(0, life, 7)) + ([life - 1] if (life - 1) % 7 else [])
    assert ticks.tolist() == expected and rep["frames"] == len(expected)
    alone = simulate(cfg, starts, cells[2].spec, seed=SEED, cell_ids=[2])
    genome = rep["cells"][2]
    assert genome["summary"]["fitness"] == float(alone.fitness[0]) and genome["cell_id"] == 2
    assert _dec(genome["energy"], "<f4")[-1] == np.float32(alone.final_energy[0])
    assert genome["alpha"] == pytest.approx(float(decode(cfg, "fourier1", cells[2].spec["genomes"]).alpha[0]))
    assert genome["core"] is not None and rep["cells"][0]["core"] is None and rep["cells"][1]["core"] is None
    beats = _dec(rep["cells"][0]["beats"], "u1")
    assert beats.shape == (len(expected) * 16,) and (beats == 0).all()  # the still cell never beats
    assert rep["world"]["damage_threshold"] == cfg.damage_threshold and rep["start"]["number"] == 3
    out = write_page(rep, tmp_path / "r.html")
    html = out.read_text()
    assert pages.DATA_MARK not in html and pages.BODY_MARK not in html and html.startswith("<!doctype html>")
    back = json.loads(re.search(r'<script id="replay-data" type="application/json">(.*?)</script>', html, re.S).group(1))
    assert back == json.loads(json.dumps(rep))
    with pytest.raises(ValueError):
        record(cfg, "burn", starts, cells * 2)
    assert MAX_CELLS == 3


def test_cells_are_read_from_their_command_line_form(tmp_path) -> None:
    cfg = configure("day", quick=True)
    with pytest.raises(SystemExit):
        parse_cell("b2rr:10", cfg, "day")  # no damage in the day configuration, so no retreat
    with pytest.raises(SystemExit):
        parse_cell("b2r", cfg, "day", data_dir=tmp_path)  # no checks have run there to give the gain
    (tmp_path / "day").mkdir()
    (tmp_path / "day" / "summary.json").write_text(json.dumps({"checks": {"K4": {"bar": {"k": 30}}, "K7": {"judged": False}}}))
    assert parse_cell("b2r", cfg, "day", data_dir=tmp_path).spec["k"] == 30.0
    g = parse_cell("genome:uniform:5", cfg, "day")
    assert np.array_equal(g.spec["genomes"][0], random_genomes(cfg, "uniform", 5, stream(SEED, "genomes"))[4]) and g.cell_id == 5
    np.save(tmp_path / "evolved.npy", random_genomes(cfg, "fourier1", 2, stream(9, "genomes")))
    f = parse_cell(f"file:fourier1:{tmp_path / 'evolved.npy'}:1", cfg, "day")
    assert f.kind == "network" and f.spec["genomes"].shape == (1, 135)
    with pytest.raises(SystemExit):
        parse_cell("b8", cfg, "day")  # no such cell (b6 and b7 are stage 3c's controls)


def test_the_network_page_describes_the_code(tmp_path) -> None:
    d = describe()
    mask = np.array(d["mask"])
    assert mask.shape == (24, 24) and mask.sum() == 368
    allowed = set(map(tuple, np.argwhere(mask == 1).tolist()))
    for mode, length in (("uniform", 103), ("fourier1", 135)):
        md = d["modes"][mode]
        assert md["length"] == length == len(md["genes"]) == md["blocks"][-1]["stop"]
        set_by_genes = {(i, j) for g in md["genes"] for i, j, _ in g["W"]}
        assert set_by_genes == allowed  # every allowed weight is set by some number, and nothing outside the mask is
        ring = [g for g in md["genes"] if g["block"] == "ring"]
        assert [len(g["W"]) for g in ring] == [16, 16, 16, 0, 0, 0]  # the three shared ring weights
        assert len(ring[3]["bias"]) == 16 and len(ring[4]["tau"]) == 16 and ring[5]["gain"]
        spokes = [len(g["W"]) for g in md["genes"] if g["block"].startswith("spokes")]
        assert set(spokes) == ({16} if mode == "uniform" else {14, 16})
        examples = random_genomes(CAVE, mode, 3, stream(SEED, "genomes"))
        decoded = decode(CAVE, mode, examples)
        assert np.allclose(md["examples"][1]["W"], decoded.W[1], atol=1e-4)
    page = pages.render("network.html", d, fragment=True)
    assert not page.startswith("<!doctype") and pages.DATA_MARK not in page and "<title>Protocell Network</title>" in page


def test_pages_escape_the_data_and_write_whole_or_fragment() -> None:
    data = {"label": "</script><b>"}
    whole = pages.render("replay.html", data, fragment=False)
    frag = pages.render("replay.html", data, fragment=True)
    assert "</script><b>" not in whole.split("replay-data")[1].split("</script>")[0]
    assert whole.startswith("<!doctype html>") and "<head>" in whole and not frag.startswith("<!doctype")
    assert frag.lstrip().startswith("<title>")


def test_replays_run_in_the_translucent_world_with_b5() -> None:
    from tools.replay import TRANSLUCENT, world

    cfg, seed = world(TRANSLUCENT, quick=True)
    assert cfg.shade_floor == 1.0 and cfg.cave_falloff == 600.0 and seed == 8
    b5 = parse_cell("b5:30", cfg, TRANSLUCENT)
    assert b5.spec == {"controller": "runwait", "tau": 30.0, "rest_below": cfg.rest_below} and b5.short == "B5" and b5.kind == "runwait"
    starts = sample_starts(cfg, "cave", 2, seed).numbered([2])
    rep = record(cfg, TRANSLUCENT, starts, [b5], seed=seed, stride=50)
    assert rep["configuration"] == TRANSLUCENT and rep["cells"][0]["summary"]["fitness"] > 0


def test_a_replay_cell_can_wear_the_goggles(tmp_path) -> None:
    from tools.replay import TRANSLUCENT, world

    cfg, seed = world(TRANSLUCENT, True)
    mirrored = parse_cell("b6@-1", cfg, TRANSLUCENT, seed=seed)
    assert mirrored.senses == -1.0 and "mirrored" in mirrored.label and mirrored.short == "B6k-1"
    assert parse_cell("b7", cfg, TRANSLUCENT, seed=seed).kind == "walk" and parse_cell("b6@1", cfg, TRANSLUCENT, seed=seed).senses == 1.0
    starts = sample_starts(cfg, "cave", 2, seed).numbered([2])
    rep = record(cfg, TRANSLUCENT, starts, [parse_cell("b6", cfg, TRANSLUCENT, seed=seed), mirrored], seed=seed, stride=50, ticks=600)
    alone = simulate(cfg.but(sense_contrast=-1.0), starts, mirrored.spec, seed=seed, ticks=600)
    assert rep["cells"][1]["senses"] == -1.0 and rep["cells"][1]["summary"]["fitness"] == float(alone.fitness[0])
    assert write_page(rep, tmp_path / "goggles.html").exists()
