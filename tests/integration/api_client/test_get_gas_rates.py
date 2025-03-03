from datetime import datetime, timedelta
import os
import pytest

from integration import get_test_context
from custom_components.octopus_energy.api_client import OctopusEnergyApiClient

period_from = datetime.strptime("2021-12-01T00:00:00Z", "%Y-%m-%dT%H:%M:%S%z")
period_to = datetime.strptime("2021-12-02T00:00:00Z", "%Y-%m-%dT%H:%M:%S%z")

@pytest.mark.asyncio
@pytest.mark.parametrize("tariff",[("G-1R-SUPER-GREEN-24M-21-07-30-A")])
async def test_when_get_gas_rates_is_called_for_existent_tariff_then_rates_are_returned(tariff):
    # Arrange
    context = get_test_context()

    client = OctopusEnergyApiClient(context["api_key"])

    # Act
    data = await client.async_get_gas_rates(tariff, period_from, period_to)

    # Assert
    assert len(data) == 48

    # Make sure our data is returned in 30 minute increments
    expected_valid_from = period_from
    for item in data:
        expected_valid_to = expected_valid_from + timedelta(minutes=30)

        assert "valid_from" in item
        assert item["valid_from"] == expected_valid_from
        assert "valid_to" in item
        assert item["valid_to"] == expected_valid_to

        assert "value_exc_vat" in item
        assert "value_inc_vat" in item

        expected_valid_from = expected_valid_to

@pytest.mark.asyncio
@pytest.mark.parametrize("tariff",[("G-1R-NOT-A-TARIFF-A")])
async def test_when_get_gas_rates_is_called_for_non_existent_tariff_then_none_is_returned(tariff):
    # Arrange
    context = get_test_context()

    client = OctopusEnergyApiClient(context["api_key"])

    # Act
    data = await client.async_get_gas_rates(tariff, period_from, period_to)

    # Assert
    assert data == None