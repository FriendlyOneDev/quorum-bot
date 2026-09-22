"""Cross-week grant vs refund. Runs against the test DB like the rest of test/."""
import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from data_utils import get_or_create_user, update_user, get_slots, add_slots, WEEKLY_SLOT_ALLOWANCE


def _stale(uid, slots=0):
    get_or_create_user(uid)
    update_user(uid, {"slots": slots, "slots_week": "2020-W01"})


def test_cross_week_grant_stacks_on_allowance():
    _stale(9001)
    add_slots(9001, 3)                       # /giveslot @user 3 on a fresh week
    assert get_slots(9001) == WEEKLY_SLOT_ALLOWANCE + 3


def test_cross_week_refund_drops():
    _stale(9002)
    add_slots(9002, 1, refund=True)          # left a game booked last week
    assert get_slots(9002) == WEEKLY_SLOT_ALLOWANCE


def test_same_week_grant_and_refund_both_add():
    get_or_create_user(9003)
    get_slots(9003)                          # normalise to current week
    add_slots(9003, 2)
    add_slots(9003, 1, refund=True)
    assert get_slots(9003) == WEEKLY_SLOT_ALLOWANCE + 3
