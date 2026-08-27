#
# Copyright (c) 2026 Nordic Semiconductor ASA
#
# SPDX-License-Identifier: Apache-2.0
#
"""Per-command descriptions, from the SDK's own documentation.

Generated from `nrf/doc/nrf/includes/wifi_radio_test_subcommands.txt` at NCS v3.4.0, which is the source the rendered
"Radio test subcommands" page is built from. Using the source keeps these pinned
to the same tree the firmware was built from.

Covers the 44 `wifi_radio_test` subcommands the doc lists. The other 11 in the
table are nRF71-only or undocumented, and fall back to their shell help text.

KIND separates a command that changes a parameter from one that acts on the
radio, which is the doc's own Configuration and Action split.
"""

DESCRIPTIONS = {
    'set_defaults': 'Reset all configuration parameters to their default values.',
    'phy_calib_rxdc': 'Enable/Disable RX DC calibration.',
    'phy_calib_txdc': 'Enable/Disable TX DC calibration.',
    'phy_calib_txpow': 'Enable/Disable TX power calibration.',
    'phy_calib_rxiq': 'Enable/Disable RX IQ calibration.',
    'phy_calib_txiq': 'Enable/Disable TX IQ calibration.',
    'he_ltf': 'Configure HE long training field (LTF) value while transmitting the packet.',
    'he_gi': 'Configure HE guard interval (GI) while transmitting the packet.',
    'tx_pkt_tput_mode': 'Throughput mode to be used for transmitting the packet.',
    'tx_pkt_sgi': 'Enable/Disable Short guard interval (GI) while transmitting the packet.',
    'tx_pkt_preamble': 'Type of preamble to be used for each packet. Short/Long Preamble are applicable only when tx_pkt_tput_mode is set to Legacy and Mixed Preamble is applicable only when tx_pkt_tput_mode is set to HT/VHT.',
    'tx_pkt_mcs': 'MCS index at which TX packet will be transmitted. Mutually exclusive with tx_pkt_rate.',
    'tx_pkt_rate': 'Legacy rate at which packets will be transmitted. Mutually exclusive with tx_pkt_mcs.',
    'tx_pkt_gap': 'Interval between TX packets in microseconds.',
    'tx_pkt_num': 'Number of packets to transmit before stopping.',
    'tx_pkt_len': 'Packet data length to be used for the TX stream.',
    'tx_power': 'Transmit power for frame transmission.',
    'ru_tone': 'Configure the resource unit (RU) size.',
    'ru_index': 'Configure the location of resource unit (RU) in 20 MHz spectrum.',
    'rx_capture_length': 'Number of RX samples to be captured.',
    'rx_capture_timeout': 'Duration of packet detection. If no packets are detected, the command will timeout.',
    'rx_lna_gain': 'LNA gain to be configured.',
    'rx_bb_gain': 'Baseband gain to be configured.',
    'tx_tone_freq': 'Tone frequency in the range of -10 MHz to 10 MHz with a resolution of 1 MHz.',
    'dpd': 'Enable or bypass DPD.',
    'set_xo_val': 'Set XO value.',
    'show_config': 'Display the current configuration values.',
    'init': 'Initialize the radio to a default state with the configured channel. This will also reset all other configuration parameters to their default values.',
    'tx': 'Enable/Disable packet transmission. Transmits configured number of packets (tx_pkt_num) of packet length (tx_pkt_len).',
    'rx': 'Enable/Disable packet reception.',
    'rx_cap': 'Capture ADC samples at 40 MHz sampling rate, capture filtered ADC samples at 20 MHz sampling rate, or capture packets at 20 MHz sampling rate after valid packet detection.',
    'tx_tone': 'Enable/Disable transmit tone.',
    'get_temperature': 'Get temperature.',
    'get_rf_rssi': 'Get RF RSSI.',
    'compute_optimal_xo_val': 'Compute optimal XO trim value.',
    'get_stats': 'Display statistics.',
    'tx_pkt_cw': 'Contention window for transmitted packets.',
    'reg_domain': 'Configure WLAN regulatory domain country code.',
    'bypass_reg_domain': 'Configure WLAN to bypass current regulatory domain in TX test.',
    'set_ant_gain': '<val> is subtracted from the transmit power.',
    'set_edge_bo': 'If the channel is an edge channel, the value of <val> is subtracted from the transmit power.',
    'config_pta': 'Allows configuration of PTA for different Wi-Fi operating bands, antenna modes, and Short-Range protocols.',
    'get_voltage': 'Get battery voltage.',
    'sr_ant_switch_ctrl': 'Allows configuration of the Short Range (SR) side switch to connect to either SR antenna or Wi-Fi antenna.',
}

DEFAULTS = {
    'phy_calib_rxdc': '1',
    'phy_calib_txdc': '1',
    'phy_calib_txpow': '0',
    'phy_calib_rxiq': '1',
    'phy_calib_txiq': '1',
    'he_ltf': '2',
    'he_gi': '2',
    'tx_pkt_tput_mode': '0',
    'tx_pkt_sgi': '0',
    'tx_pkt_preamble': '0',
    'tx_pkt_mcs': '0',
    'tx_pkt_rate': '6',
    'tx_pkt_gap': '0',
    'tx_pkt_num': '-1',
    'tx_pkt_len': '1400',
    'tx_power': '0',
    'ru_tone': '26',
    'ru_index': '1',
    'rx_capture_length': '0',
    'rx_capture_timeout': '0',
    'rx_lna_gain': '0',
    'rx_bb_gain': '0',
    'tx_tone_freq': '0',
    'dpd': '0',
    'set_xo_val': '42 or value programmed in OTP',
    'init': '1',
    'tx': '0',
    'rx': '0',
    'tx_tone': '0',
    'tx_pkt_cw': '15',
    'reg_domain': '00 (world regulatory)',
    'bypass_reg_domain': '0',
    'set_ant_gain': '0',
    'set_edge_bo': '0',
    'config_pta': '0',
    'sr_ant_switch_ctrl': '0',
}

# Explicit Min/Max from the doc's Argument column. The authority for a bound:
# a shell help string put tx_pkt_gap's minimum at 200 where the doc says 0, and
# a device accepting a value only proves it does not range-check.
RANGES = {
    'tx_pkt_gap': (0, 200000),
    'tx_power': (0, 24),
    'rx_capture_length': (0, 16383),
    'rx_capture_timeout': (0, 600),
    'tx_tone_freq': (-10, 10),
    'set_xo_val': (0, 127),
    'set_ant_gain': (0, 6),
    'set_edge_bo': (0, 10),
}

KIND = {
    'set_defaults': 'Configuration',
    'phy_calib_rxdc': 'Configuration',
    'phy_calib_txdc': 'Configuration',
    'phy_calib_txpow': 'Configuration',
    'phy_calib_rxiq': 'Configuration',
    'phy_calib_txiq': 'Configuration',
    'he_ltf': 'Configuration',
    'he_gi': 'Configuration',
    'tx_pkt_tput_mode': 'Configuration',
    'tx_pkt_sgi': 'Configuration',
    'tx_pkt_preamble': 'Configuration',
    'tx_pkt_mcs': 'Configuration',
    'tx_pkt_rate': 'Configuration',
    'tx_pkt_gap': 'Configuration',
    'tx_pkt_num': 'Configuration',
    'tx_pkt_len': 'Configuration',
    'tx_power': 'Configuration',
    'ru_tone': 'Configuration',
    'ru_index': 'Configuration',
    'rx_capture_length': 'Configuration',
    'rx_capture_timeout': 'Configuration',
    'rx_lna_gain': 'Configuration',
    'rx_bb_gain': 'Configuration',
    'tx_tone_freq': 'Configuration',
    'dpd': 'Configuration',
    'set_xo_val': 'Configuration',
    'show_config': 'Configuration',
    'init': 'Action',
    'tx': 'Action',
    'rx': 'Action',
    'rx_cap': 'Action',
    'tx_tone': 'Action',
    'get_temperature': 'Action',
    'get_rf_rssi': 'Action',
    'compute_optimal_xo_val': 'Action',
    'get_stats': 'Action',
    'tx_pkt_cw': 'Configuration',
    'reg_domain': 'Action',
    'bypass_reg_domain': 'Configuration',
    'set_ant_gain': 'Configuration',
    'set_edge_bo': 'Configuration',
    'config_pta': 'Configuration',
    'get_voltage': 'Action',
    'sr_ant_switch_ctrl': 'Configuration',
}


def describe(command):
    """Doc description for a command, falling back to its shell help."""
    return DESCRIPTIONS.get(command.name) or command.help


def is_action(name):
    """True when the doc calls this an Action rather than Configuration."""
    return KIND.get(name) == "Action"
