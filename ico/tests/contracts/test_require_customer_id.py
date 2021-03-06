"""Customer id tracking."""
import uuid

import pytest
from eth_tester.exceptions import TransactionFailed
from eth_utils import to_wei

from ico.tests.utils import time_travel
from ico.state import CrowdsaleState

from sha3 import keccak_256
from eth_utils import decode_hex

@pytest.fixture
def crowdsale(uncapped_flatprice, uncapped_flatprice_finalizer, team_multisig):
    """Set up a crowdsale with customer id require policy."""
    uncapped_flatprice.functions.setRequireCustomerId(True).transact({"from": team_multisig})
    return uncapped_flatprice


@pytest.fixture
def token(uncapped_token):
    """Token contract we are buying."""
    return uncapped_token


@pytest.fixture
def customer_id(uncapped_flatprice, uncapped_flatprice_finalizer, team_multisig) -> int:
    """Generate UUID v4 customer id as a hex string."""
    customer_id = int(uuid.uuid4().hex, 16)  # Customer ids are 128-bit UUID v4
    return customer_id


def test_only_owner_change_change_policy(crowdsale, customer):
    """Only owner change change customerId required policy."""

    with pytest.raises(TransactionFailed):
        crowdsale.functions.setRequireCustomerId(False).transact({"from": customer})


def test_participate_with_customer_id(chain, crowdsale, customer, customer_id, token):
    """Buy tokens with a proper customer id."""

    time_travel(chain, crowdsale.functions.startsAt().call() + 1)
    wei_value = to_wei(1, "ether")
    assert crowdsale.functions.getState().call() == CrowdsaleState.Funding
    checksumbyte = keccak_256(decode_hex(format(customer_id, 'x').zfill(32))).digest()[:1]
    crowdsale.functions.buyWithCustomerIdWithChecksum(
        customer_id, checksumbyte
    ).transact({"from": customer, "value": wei_value})

    # We got credited
    assert token.functions.balanceOf(customer).call() > 0

    # We have tracked the investor id
    events = crowdsale.events.Invested().createFilter(fromBlock=0).get_all_entries()
    assert len(events) == 1
    e = events[0]
    assert e["args"]["investor"] == customer
    assert e["args"]["weiAmount"] == wei_value
    assert e["args"]["customerId"] == customer_id


def test_participate_missing_customer_id(chain, crowdsale, customer, customer_id, token):
    """Cannot bypass customer id process."""

    time_travel(chain, crowdsale.functions.startsAt().call() + 1)
    wei_value = to_wei(1, "ether")
    assert crowdsale.functions.getState().call() == CrowdsaleState.Funding

    with pytest.raises(TransactionFailed):
        crowdsale.functions.buy().transact({"from": customer, "value": wei_value})
