from .api_client import OctopusEnergyApiClient

def __get_interval_end(item):
    return item["interval_end"]

def __sort_consumption(consumption_data):
  sorted = consumption_data.copy()
  sorted.sort(key=__get_interval_end)
  return sorted

async def async_get_consumption_data(
  client: OctopusEnergyApiClient,
  previous_data,
  current_utc_timestamp,
  period_from,
  period_to,
  sensor_identifier,
  sensor_serial_number,
  is_electricity: bool
):
  if (previous_data == None or 
      ((len(previous_data) < 1 or previous_data[-1]["interval_end"] < period_to) and 
       current_utc_timestamp.minute % 30 == 0)
      ):
    if (is_electricity == True):
      data = await client.async_get_electricity_consumption(sensor_identifier, sensor_serial_number, period_from, period_to)
    else:
      data = await client.async_get_gas_consumption(sensor_identifier, sensor_serial_number, period_from, period_to)
    
    if data != None and len(data) > 0:
      data = __sort_consumption(data)
      return data
    
  if previous_data != None:
    return previous_data
  else:
    return []

def calculate_electricity_consumption(consumption_data, last_calculated_timestamp):
  if (consumption_data != None and len(consumption_data) > 0):

    sorted_consumption_data = __sort_consumption(consumption_data)

    if (last_calculated_timestamp == None or last_calculated_timestamp < sorted_consumption_data[-1]["interval_end"]):
      total = 0

      consumption_parts = []
      for consumption in sorted_consumption_data:
        total = total + consumption["consumption"]

        current_consumption = consumption["consumption"]

        consumption_parts.append({
          "from": consumption["interval_start"],
          "to": consumption["interval_end"],
          "consumption": current_consumption,
        })
      
      last_calculated_timestamp = sorted_consumption_data[-1]["interval_end"]

      return {
        "total": total,
        "last_calculated_timestamp": last_calculated_timestamp,
        "consumptions": consumption_parts
      }

async def async_calculate_electricity_cost(client: OctopusEnergyApiClient, consumption_data, last_calculated_timestamp, period_from, period_to, tariff_code, is_smart_meter):
  if (consumption_data != None and len(consumption_data) > 0):

    sorted_consumption_data = __sort_consumption(consumption_data)

    # Only calculate our consumption if our data has changed
    if (last_calculated_timestamp == None or last_calculated_timestamp < sorted_consumption_data[-1]["interval_end"]):
      rates = await client.async_get_electricity_rates(tariff_code, is_smart_meter, period_from, period_to)
      standard_charge_result = await client.async_get_electricity_standing_charge(tariff_code, period_from, period_to)

      if (rates != None and len(rates) > 0 and standard_charge_result != None):
        standard_charge = standard_charge_result["value_inc_vat"]

        charges = []
        total_cost_in_pence = 0
        for consumption in sorted_consumption_data:
          value = consumption["consumption"]
          consumption_from = consumption["interval_start"]
          consumption_to = consumption["interval_end"]

          try:
            rate = next(r for r in rates if r["valid_from"] == consumption_from and r["valid_to"] == consumption_to)
          except StopIteration:
            raise Exception(f"Failed to find rate for consumption between {consumption_from} and {consumption_to} for tariff {tariff_code}")

          cost = (rate["value_inc_vat"] * value)
          total_cost_in_pence = total_cost_in_pence + cost

          charges.append({
            "from": rate["valid_from"],
            "to": rate["valid_to"],
            "rate": f'{rate["value_inc_vat"]}p',
            "consumption": f'{value} kWh',
            "cost": f'£{round(cost / 100, 2)}'
          })
        
        total_cost = round(total_cost_in_pence / 100, 2)
        total_cost_plus_standing_charge = round((total_cost_in_pence + standard_charge) / 100, 2)

        last_calculated_timestamp = sorted_consumption_data[-1]["interval_end"]

        return {
          "standing_charge": standard_charge,
          "total_without_standing_charge": total_cost,
          "total": total_cost_plus_standing_charge,
          "last_calculated_timestamp": last_calculated_timestamp,
          "charges": charges
        }

# Adapted from https://www.theenergyshop.com/guides/how-to-convert-gas-units-to-kwh
def convert_m3_to_kwh(value):
  kwh_value = value * 1.02264 # Volume correction factor
  kwh_value = kwh_value * 40.0 # Calorific value
  return round(kwh_value / 3.6, 3) # kWh Conversion factor

def calculate_gas_consumption(consumption_data, last_calculated_timestamp):
  if (consumption_data != None and len(consumption_data) > 0):

    sorted_consumption_data = __sort_consumption(consumption_data)

    if (last_calculated_timestamp == None or last_calculated_timestamp < sorted_consumption_data[-1]["interval_end"]):
      total_m3 = 0
      total_kwh = 0

      consumption_parts = []
      for consumption in sorted_consumption_data:
        current_consumption_m3 = 0
        current_consumption_kwh = 0

        current_consumption = consumption["consumption"]
        
        # Despite what the documentation (https://developer.octopus.energy/docs/api/#consumption) states, after a few emails with 
        # Octopus Energy and personal experience, gas data is always reported in m3
        current_consumption_m3 = current_consumption
        current_consumption_kwh = convert_m3_to_kwh(current_consumption)

        total_m3 = total_m3 + current_consumption_m3
        total_kwh = total_kwh + current_consumption_kwh

        consumption_parts.append({
          "from": consumption["interval_start"],
          "to": consumption["interval_end"],
          "consumption_m3": current_consumption_m3,
          "consumption_kwh": current_consumption_kwh,
        })
      
      last_calculated_timestamp = sorted_consumption_data[-1]["interval_end"]

      return {
        "total_m3": round(total_m3, 3),
        "total_kwh": round(total_kwh, 3),
        "last_calculated_timestamp": last_calculated_timestamp,
        "consumptions": consumption_parts
      }
      
async def async_calculate_gas_cost(client: OctopusEnergyApiClient, consumption_data, last_calculated_timestamp, period_from, period_to, sensor):
  if (consumption_data != None and len(consumption_data) > 0):

    sorted_consumption_data = __sort_consumption(consumption_data)

    # Only calculate our consumption if our data has changed
    if (last_calculated_timestamp == None or last_calculated_timestamp < sorted_consumption_data[-1]["interval_end"]):
      rates = await client.async_get_gas_rates(sensor["tariff_code"], period_from, period_to)
      standard_charge_result = await client.async_get_gas_standing_charge(sensor["tariff_code"], period_from, period_to)

      if (rates != None and len(rates) > 0 and standard_charge_result != None):
        standard_charge = standard_charge_result["value_inc_vat"]

        charges = []
        total_cost_in_pence = 0
        for consumption in sorted_consumption_data:
          value = consumption["consumption"]

          # Despite what the documentation (https://developer.octopus.energy/docs/api/#consumption) states, after a few emails with 
          # Octopus Energy and personal experience, gas data is always reported in m3. So we need to convert to kWh before we calculate the cost
          value = convert_m3_to_kwh(value)

          consumption_from = consumption["interval_start"]
          consumption_to = consumption["interval_end"]

          try:
            rate = next(r for r in rates if r["valid_from"] == consumption_from and r["valid_to"] == consumption_to)
          except StopIteration:
            raise Exception(f"Failed to find rate for consumption between {consumption_from} and {consumption_to} for tariff {sensor['tariff_code']}")

          cost = (rate["value_inc_vat"] * value)
          total_cost_in_pence = total_cost_in_pence + cost

          charges.append({
            "from": rate["valid_from"],
            "to": rate["valid_to"],
            "rate": f'{rate["value_inc_vat"]}p',
            "consumption": f'{value} kWh',
            "cost": f'£{round(cost / 100, 2)}'
          })
        
        total_cost = round(total_cost_in_pence / 100, 2)
        total_cost_plus_standing_charge = round((total_cost_in_pence + standard_charge) / 100, 2)
        last_calculated_timestamp = sorted_consumption_data[-1]["interval_end"]

        return {
          "standing_charge": standard_charge,
          "total_without_standing_charge": total_cost,
          "total": total_cost_plus_standing_charge,
          "last_calculated_timestamp": last_calculated_timestamp,
          "charges": charges
        }