"""Fault-tolerance add-on pieces that need no running chain: routing, the fault schedule, endpoint failover,
resending unconfirmed transactions, and node monitoring across restarts."""

import subprocess
import sys
import time

import pytest
import requests
from web3.exceptions import Web3RPCError

import src.common.blockchain as bc
from src.common.blockchain import Endpoints, NodeMonitor, _Link
from src.common.faults import Fault, FaultInjector
from src.pipeline import route


def test_route_keeps_home_fails_over_in_order_or_loses():
    assert route(1, [True, True, True], "recover") == 1
    assert route(1, [True, False, True], "recover") == 2           # the next one up, in index order
    assert route(2, [True, False, False], "recover") == 0          # wraps around
    assert route(0, [False, False], "recover") is None             # nothing left to take it
    assert route(1, [True, False], "none") is None                 # no recovery: traffic for a failed one is lost


def test_fault_targets_and_times_are_checked():
    assert Fault("node:3", 1).node == 3 and Fault("edge-01", 1).node is None
    for bad in ("edge", "node:x", "gateway", "device:"):
        with pytest.raises(ValueError):
            Fault(bad, 1)
    with pytest.raises(ValueError):
        Fault("cloud", 5, 5)                                        # repaired before (or when) it fails
    with pytest.raises(ValueError):
        FaultInjector([Fault("node:1", 1)])                         # node faults need a network
    with pytest.raises(ValueError):
        FaultInjector([Fault("cloud", 1, 2), Fault("cloud", 3, 4)])  # one fault per target


class _FakeNetwork:
    urls = ["n0", "n1", "n2", "n3"]

    def __init__(self):
        self.calls, self.down = [], set()

    def stop(self, i):
        self.calls.append(("stop", i))
        self.down.add(i)

    def start(self, i):
        self.calls.append(("start", i))
        self.down.discard(i)

    def head(self, i):
        return None if i in self.down else 7


def test_injector_applies_the_schedule_and_repairs_the_rest_at_the_end():
    net = _FakeNetwork()
    inj = FaultInjector([Fault("cloud", 0.05, 0.15), Fault("node:2", 0.05), Fault("edge-01", 10)], net)
    inj.start()
    assert inj.snapshot() == frozenset()
    time.sleep(0.1)
    assert inj.snapshot() == {"cloud", "node:2"}
    time.sleep(0.15)
    assert inj.snapshot() == {"node:2"}
    record = inj.finish()                                           # node:2 had no repair time; edge-01 never failed
    assert inj.snapshot() == frozenset() and net.calls == [("stop", 2), ("start", 2)]
    actions = [(e["target"], e["action"]) for e in record["log"]]
    assert actions == [("cloud", "down"), ("node:2", "down"), ("cloud", "up"), ("node:2", "up"), ("node:2", "resynced")]
    assert record["log"][3]["at_end_of_stream"] is True
    assert [f["target"] for f in record["schedule"]] == ["cloud", "node:2", "edge-01"]


def test_failover_moves_to_the_next_node_that_answers(monkeypatch):
    alive = {"b": False, "c": True, "a": True}
    monkeypatch.setattr(bc, "_answers", lambda url: alive[url])
    ep = Endpoints(["a", "b", "c"])
    ep.fail(seen=0)
    assert ep.url == "c" and ep.generation == 1 and ep.failovers[0]["from"] == "a"
    ep.fail(seen=0)                                                 # a second thread noticing the same failure
    assert ep.url == "c" and ep.generation == 1 and len(ep.failovers) == 1
    alive["c"] = False
    ep.fail(seen=1)                                                 # the others first, wrapping around
    assert ep.url == "a" and ep.generation == 2


def test_failover_gives_up_when_no_node_answers(monkeypatch):
    monkeypatch.setattr(bc, "_answers", lambda url: False)
    monkeypatch.setattr(bc.time, "sleep", lambda s: None)
    with pytest.raises(requests.exceptions.ConnectionError):
        Endpoints(["a", "b"]).fail(seen=0)


class _RawEth:
    def __init__(self, known=(), dead=False):
        self.sent, self.known, self.dead = [], set(known), dead

    def send_raw_transaction(self, raw):
        if self.dead:
            raise requests.exceptions.ConnectionError("refused")
        if raw in self.known:
            raise Web3RPCError("Known transaction")
        self.sent.append(raw)


class _RawW3:
    def __init__(self, **kw):
        self.eth = _RawEth(**kw)


def _link(w3, generation=1):
    link = _Link.__new__(_Link)
    link.endpoints = Endpoints(["a", "b"])
    link.endpoints.generation = link.generation = generation
    link.w3 = w3
    return link


def test_unconfirmed_transactions_sent_to_a_dead_node_are_resent_in_order():
    link = _link(_RawW3(known={b"t2"}))
    txs = [["h1", b"t1", 0], ["h2", b"t2", 0], ["h3", b"t3", 1], ["h4", None, 0]]   # [hash, signed, generation]
    link.resend_stale(txs)
    assert link.w3.eth.sent == [b"t1"]                  # t2 already known to the new node; t3 went to it already;
    assert [t[2] for t in txs] == [1, 1, 1, 0]          # t4 node-signed (single node), never resent


def test_resending_fails_over_again_if_the_new_node_dies_too(monkeypatch):
    monkeypatch.setattr(bc, "_answers", lambda url: True)
    link = _link(_RawW3(dead=True), generation=0)
    good = _RawW3()

    def refresh(self):                                  # reconnecting gives the next (live) node
        if self.generation == self.endpoints.generation:
            return False
        self.generation, self.w3 = self.endpoints.generation, good
        return True

    monkeypatch.setattr(_Link, "refresh", refresh)
    txs = [["h1", b"t1", -1]]
    link.resend_stale(txs)
    assert good.eth.sent == [b"t1"] and txs[0][2] == link.generation == 1


def test_node_monitor_follows_restarted_processes():
    def spawn():
        return subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"])

    procs = [spawn(), spawn()]
    monitor = NodeMonitor(lambda: [p.pid for p in procs])
    monitor.start()
    monitor.sample()
    procs[0].kill()
    procs[0].wait()
    procs[0] = spawn()                                  # "restarted": a new process for the same node
    time.sleep(0.2)
    monitor.sample()
    usage = monitor.stop()
    for p in procs:
        p.kill()
        p.wait()
    assert usage["node_cpu_s"] >= 0 and usage["node_peak_rss_mb"] > 0
    assert len(monitor._procs) == 3                     # both originals (one killed) and the restarted one
