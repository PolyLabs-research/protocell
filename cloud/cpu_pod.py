#!/usr/bin/env python3
"""CPU pods on RunPod for protocell's runs, under the chess project's proven lifecycle (``tinyalphazero.cloud`` in
``~/Documents/dev/chess``: the pod's deadline watchdog, the sweeper timer on this box, the budget check, the ledger).

    .venv/bin/python cloud/cpu_pod.py prices
    .venv/bin/python cloud/cpu_pod.py launch --tag protocell-pilot --flavor cpu5c --vcpu 32 --hours 4 --max-rate 2.24          # dry run
    .venv/bin/python cloud/cpu_pod.py launch --tag protocell-pilot --flavor cpu5c --vcpu 32 --hours 4 --max-rate 2.24 --yes    # creates it

The owner confirms the flavour, the rate ceiling, the hours and the worst cost before every ``--yes`` (docs/prereg/
stage1.md §13). After creation the pod's actual rate is checked against ``--max-rate`` and the budget, and a pod
over either is terminated at once. Everything after the launch is the chess tool's, which handles any ``taz-`` pod:

    (cd ~/Documents/dev/chess && .venv/bin/python scripts/runpod_pod.py wait-ssh POD_ID)   # also ssh, push, pull, status, terminate POD_ID

Never ``terminate --all-ours`` from here: the chess project's own pods carry the same prefix.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any, Dict, List

CHESS_SRC = Path("~/Documents/dev/chess/src").expanduser()
sys.path.insert(0, str(CHESS_SRC))
try:
    from tinyalphazero import cloud  # noqa: E402
except ImportError as e:  # pragma: no cover - only on a box without the chess repo
    raise SystemExit(f"the RunPod lifecycle library is not at {CHESS_SRC}: {e}")

#: RunPod's CPU base image (no CUDA). Its CMD is /start.sh, which the watchdog start command wraps, as on the GPU
#: image (checked in the registry's config, 2026-11-01). Published 2026-10-16.
CPU_IMAGE = "runpod/base:1.4.1-ubuntu2404"
FLAVORS = ("cpu3c", "cpu3g", "cpu3m", "cpu5c", "cpu5g", "cpu5m")


def cpu_prices(rp: "cloud.RunPod") -> List[Dict[str, Any]]:
    q = "query { cpuFlavors { id displayName minVcpu maxVcpu ramMultiplier specifics { securePrice stockStatus } } }"
    return rp._gql(q)["cpuFlavors"]  # noqa: SLF001 - the library's own GraphQL helper


def listed_rate(price: float, vcpu: int) -> float:
    """The rate the budget is planned at. RunPod lists one number per flavour without its unit. The pilot's pod settled
    it (2026-11-01: cpu5c listed 0.07, 32 vCPUs, billed $1.12/h), so the listed price is per two vCPUs an hour. The
    pod's own rate, read after creation, is still what binds."""
    return float(price) * vcpu / 2.0


def body(tag: str, deadline: int, flavor: str, vcpu: int, disk_gb: int) -> Dict[str, Any]:
    if flavor not in FLAVORS:
        raise cloud.CloudError(f"unknown CPU flavour {flavor!r}")
    if vcpu < 2 or vcpu & (vcpu - 1):
        raise cloud.CloudError("RunPod's v2 API takes a vCPU count that is a power of two, 2 or more")
    # RunPod's REST v2 ``CreatePodRequest`` (v1, rest.runpod.io, was retired in November 2026): as the chess library's
    # GPU request, with ``cpu`` in place of ``gpu``. The API refuses unknown fields.
    return {
        "name": cloud.pod_name(tag, deadline),
        "image": CPU_IMAGE,
        "cloud": "SECURE",
        "cpu": {"id": flavor, "vcpuCount": vcpu},
        "disk": disk_gb,
        # no ``mounts``: no volume, nothing that bills after a stop, and pods are never stopped
        "ports": ["22/tcp"],  # ssh.direct, the full SSH that rsync needs, publishes 22/tcp
        "startSsh": True,  # the account's registered SSH keys reach the pod's sshd
        "cmd": cloud.watchdog_start_cmd(True),
        "env": {"TAZ_DEADLINE": str(deadline)},
    }


def cmd_prices(rp: "cloud.RunPod", args: argparse.Namespace) -> int:
    for f in cpu_prices(rp):
        s = f.get("specifics") or {}
        print(f"{f['id']:6s} {f['displayName']:18s} vCPU {f['minVcpu']}-{f['maxVcpu']}  RAM x{f['ramMultiplier']}  "
              f"listed {s.get('securePrice')}  stock {s.get('stockStatus')}")
    print(f"account {json.dumps(rp.balance())}")
    return 0


def cmd_launch(rp: "cloud.RunPod", args: argparse.Namespace) -> int:
    limits = cloud.Limits.load()
    flavors = {f["id"]: f for f in cpu_prices(rp)}
    if args.flavor not in flavors:
        raise cloud.CloudError(f"RunPod lists no flavour {args.flavor!r}")
    f = flavors[args.flavor]
    if not f["minVcpu"] <= args.vcpu <= f["maxVcpu"]:
        raise cloud.CloudError(f"{args.flavor} takes {f['minVcpu']}-{f['maxVcpu']} vCPUs")
    rate = listed_rate(f["specifics"]["securePrice"], args.vcpu)
    if rate > args.max_rate:
        raise cloud.CloudError(f"the planned rate ${rate:.3f}/h is over the confirmed ceiling ${args.max_rate:.3f}/h")
    account = rp.balance()
    worst = cloud.plan(rate, args.hours, account["balance"], limits)
    deadline = int(time.time() + args.hours * 3600)
    b = body(args.tag, deadline, args.flavor, args.vcpu, args.disk)
    print(f"plan: {args.flavor} ({f['displayName']}), {args.vcpu} vCPU, SECURE, planned at ${rate:.3f}/h (listed {f['specifics']['securePrice']} "
          f"per two vCPUs an hour), {args.hours} h cap -> worst case ${worst:.2f}; ceiling ${args.max_rate:.2f}/h; balance ${account['balance']:.2f}\n"
          f"      name {b['name']}  deadline {time.strftime('%H:%M:%S %Z', time.localtime(deadline))}  image {CPU_IMAGE}  disk {args.disk} GB")
    if not args.yes:
        print("dry run: nothing created (pass --yes to launch)")
        return 0
    pod = rp.create_pod(b)
    cloud.ledger("launch", pod_id=pod["id"], name=b["name"], deadline=deadline,
                 spec={"project": "protocell", "flavor": args.flavor, "vcpu": args.vcpu, "hours": args.hours, "image": CPU_IMAGE})
    actual = float(pod.get("cost") or rate)  # v2: the pod's hourly rate
    refusal = None
    if actual > args.max_rate:
        refusal = f"the pod's rate ${actual:.3f}/h is over the confirmed ceiling ${args.max_rate:.3f}/h"
    else:
        try:
            cloud.plan(actual, args.hours, account["balance"], limits)
        except cloud.BudgetError as e:
            refusal = str(e)
    if refusal:
        rp.terminate_pod(pod["id"])
        cloud.ledger("terminate", pod_id=pod["id"], reason=f"actual rate refused: {refusal}")
        print(f"terminated {pod['id']} at once: {refusal}")
        return 2
    print(f"launched {pod['id']} {b['name']} at ${actual:.3f}/h (vCPU {(pod.get('cpu') or {}).get('vcpuCount')}, RAM {(pod.get('cpu') or {}).get('memory')} GB); "
          f"worst case ${actual * args.hours:.2f} by the deadline")
    return 0


def main(argv: List[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("prices")
    p = sub.add_parser("launch")
    p.add_argument("--tag", required=True, help="lowercase [a-z0-9_-]; protocell's pods start protocell-")
    p.add_argument("--flavor", default="cpu5c", choices=FLAVORS)
    p.add_argument("--vcpu", type=int, default=32)
    p.add_argument("--hours", type=float, required=True, help="the hard deadline, from now")
    p.add_argument("--max-rate", type=float, required=True, help="the $/h ceiling the owner confirmed")
    p.add_argument("--disk", type=int, default=20, help="container disk, GB")
    p.add_argument("--yes", action="store_true", help="actually create the pod")
    args = ap.parse_args(argv)
    if args.cmd == "launch" and not args.tag.startswith("protocell-"):
        ap.error("protocell's pod tags start protocell-")
    rp = cloud.RunPod()
    try:
        return {"prices": cmd_prices, "launch": cmd_launch}[args.cmd](rp, args)
    except cloud.CloudError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
