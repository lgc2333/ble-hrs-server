from typing import NamedTuple

HRS_UUID = "0000180d-0000-1000-8000-00805f9b34fb"
HRM_UUID = "00002a37-0000-1000-8000-00805f9b34fb"


class HRMData(NamedTuple):
    heart_rate: int
    sensor_contact: bool | None


def parse_val(val: bytearray) -> HRMData:
    flag = val[0]
    rate_is_u16 = flag & 0b00001 != 0
    sensor_contact_supported = flag & 0b00100 != 0
    sensor_contact = (flag & 0b00010 != 0) if sensor_contact_supported else None

    heart_rate = val[1]
    if rate_is_u16:
        heart_rate |= val[2] << 8

    return HRMData(heart_rate, sensor_contact)
