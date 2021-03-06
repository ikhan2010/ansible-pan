#!/usr/bin/env python

#  Copyright 2017 Palo Alto Networks, Inc
#
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.

ANSIBLE_METADATA = {'metadata_version': '1.1',
                    'status': ['preview'],
                    'supported_by': 'community'}

DOCUMENTATION = '''
---
module: panos_match_rule
short_description: Test for match against a security rule on PAN-OS devices or Panorama management console.
description:
    - Security policies allow you to enforce rules and take action, and can be as general or specific as needed.
author: "Robert Hagen (@rnh556)"
version_added: "2.5"
requirements:
    - pan-python can be obtained from PyPI U(https://pypi.python.org/pypi/pan-python)
    - pandevice can be obtained from PyPI U(https://pypi.python.org/pypi/pandevice)
    - xmltodict
notes:
    - Checkmode is not supported.
    - Panorama NOT is supported.
extends_documentation_fragment:
    - panos.transitional_provider
    - panos.rulebase
    - panos.vsys
options:
    rule_type:
        description:
            - Type of rule.
        choices:
            - security
            - nat
        default: "security"
    source_zone:
        description:
            - The source zone.
    source_ip:
        description:
            - The source IP address.
        required: true
    source_port:
        description:
            - The source port.
        type: int
    source_user:
        description:
            - The source user or group.
    to_interface:
        description:
            - The inbound interface in a NAT rule.
    destination_zone:
        description:
            - The destination zone.
    destination_ip:
        description:
            - The destination IP address.
        required: true
    destination_port:
        description:
            - The destination port.
        required: true
        type: int
    application:
        description:
            - The application.
    protocol:
        description:
            - The IP protocol number from 1 to 255.
        required: true
        type: int
    category:
        description:
            - URL category
    vsys_id:
        description:
            - B(Removed)
            - Use I(vsys) instead.
'''

EXAMPLES = '''
- name: check security rules for Google DNS
  panos_match_rule:
    provider: '{{ provider }}'
    source_ip: '10.0.0.0'
    destination_ip: '8.8.8.8'
    application: 'dns'
    destination_port: '53'
    protocol: '17'
  register: result
- debug: msg='{{ result.rule }}'

- name: check security rules inbound SSH with user match
  panos_match_rule:
    provider: '{{ provider }}'
    source_ip: '0.0.0.0'
    source_user: 'mydomain\\jsmith'
    destination_ip: '192.168.100.115'
    destination_port: '22'
    protocol: '6'
  register: result
- debug: msg='{{ result.rule }}'

- name: check NAT rules for source NAT
  panos_match_rule:
    provider: '{{ provider }}'
    rule_type: 'nat'
    source_zone: 'Prod-DMZ'
    source_ip: '10.10.118.50'
    to_interface: 'ethernet1/2'
    destination_zone: 'Internet'
    destination_ip: '0.0.0.0'
    protocol: '6'
  register: result
- debug: msg='{{ result.rule }}'

- name: check NAT rules for inbound web
  panos_match_rule:
    provider: '{{ provider }}'
    rule_type: 'nat'
    source_zone: 'Internet'
    source_ip: '0.0.0.0'
    to_interface: 'ethernet1/1'
    destination_zone: 'Prod DMZ'
    destination_ip: '192.168.118.50'
    destination_port: '80'
    protocol: '6'
  register: result
- debug: msg='{{ result.rule }}'

- name: check security rules for outbound POP3 in vsys4
  panos_match_rule:
    provider: '{{ provider }}'
    vsys_id: 'vsys4'
    source_ip: '10.0.0.0'
    destination_ip: '4.3.2.1'
    application: 'pop3'
    destination_port: '110'
    protocol: '6'
  register: result
- debug: msg='{{ result.rule }}'
'''

RETURN = '''
# Default return values
'''

import json

from ansible.module_utils.basic import AnsibleModule
from ansible.module_utils.network.panos.panos import get_connection


try:
    from pandevice.errors import PanDeviceError
    from pandevice.policies import NatRule
    from pandevice.policies import SecurityRule
except ImportError:
    pass


# TODO(gfreeman) - Remove this dependency in the next role release.
HAS_LIB = True
try:
    import xmltodict
    import xml.etree.ElementTree as ET
except ImportError:
    HAS_LIB = False


def main():
    helper = get_connection(
        vsys=True,
        rulebase=True,
        with_classic_provider_spec=True,
        panorama_error='Panorama is not supported',
        argument_spec=dict(
            rule_type=dict(default='security', choices=['security', 'nat']),
            source_zone=dict(),
            source_ip=dict(required=True),
            source_port=dict(type='int'),
            source_user=dict(),
            to_interface=dict(),
            destination_zone=dict(),
            destination_ip=dict(required=True),
            destination_port=dict(required=True, type='int'),
            application=dict(),
            protocol=dict(required=True, type='int'),
            category=dict(),

            # TODO(gfreeman) - Remove this in the next role release.
            vsys_id=dict(),
        ),
    )

    module = AnsibleModule(
        argument_spec=helper.argument_spec,
        supports_check_mode=False,
        required_one_of=helper.required_one_of,
    )

    # TODO(gfreeman) - Remove this in the next role release.
    if not HAS_LIB:
        module.fail_json(msg='Missing xmltodict library')
    if module.params['vsys_id'] is not None:
        module.fail_json(msg='Param "vsys_id" is removed; use vsys')

    parent = helper.get_pandevice_parent(module)

    params = (
        ('application', 'application', ['security', ]),
        ('category', 'category', ['security', ]),
        ('destination_ip', 'destination', ['security', 'nat']),
        ('destination_port', 'destination-port', ['security', 'nat']),
        ('source_zone', 'from', ['security', 'nat']),
        ('protocol', 'protocol', ['security', 'nat']),
        ('source_ip', 'source', ['security', 'nat']),
        ('source_user', 'source-user', ['security', ]),
        ('destination_zone', 'to', ['security', 'nat']),
        ('to_interface', 'to-interface', ['nat', ]),
    )

    cmd = []
    rtype = module.params['rule_type']

    if rtype == 'security':
        cmd.append('test security-policy-match')
        listing = SecurityRule.refreshall(parent)
    else:
        cmd.append('test nat-policy-match')
        listing = NatRule.refreshall(parent)

    for ansible_param, cmd_param, rule_types in params:
        if rtype not in rule_types or module.params[ansible_param] is None:
            continue
        cmd.append('{0} "{1}"'.format(cmd_param, module.params[ansible_param]))

    # Submit the op command with the appropriate test string
    test_string = ' '.join(cmd)
    try:
        response = helper.device.op(cmd=test_string, vsys=parent.vsys)
    except PanDeviceError as e:
        module.fail_json(msg='Failed "{0}": {1}'.format(test_string, e))

    elm = response.find('./result/rules/entry')
    if elm is not None:
        try:
            rule_name = elm.attrib['name']
        except KeyError:
            rule_name = elm.text
    else:
        module.exit_json(msg='No matching {0} rule.'.format(rtype))

    for x in listing:
        if x.name != rule_name:
            continue
        module.deprecate('The "stdout_lines" output is deprecated; use "rule" instead', '2.12')
        module.exit_json(
            stdout_lines=json.dumps(xmltodict.parse(x.element_str()), indent=2),
            msg='Rule matched',
            rule=x.about(),
        )

    module.fail_json(msg='Matched "{0}" with "{1}", but wasn\'t in rulebase'.format(rule_name, test_string))


if __name__ == '__main__':
    main()
