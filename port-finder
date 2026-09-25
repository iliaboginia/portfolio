"""
===============================================================================
MikroTik L2 Access Port Finder (Heuristic MAC Locator)
===============================================================================

Author: Network Engineer
Purpose:
    Locates the physical edge/access port where an end-host is connected 
    across a distributed Layer-2 MikroTik network.

Problem Statement:
    In flat or switched L2 domains spanning multiple MikroTik switches, 
    a target MAC address is typically learned across multiple bridge tables, 
    including inter-switch uplinks and trunk ports. Determining the exact 
    access port manually requires tracing the MAC hop-by-hop across the topology, 
    which is time-consuming and error-prone.

How It Works:
    1. ARP Resolution:
       Connects to a core gateway/router via SSH to query the ARP table 
       and resolve the target IP address to its corresponding MAC address.
    
    2. Concurrent L2 Discovery:
       Leverages multi-threading (ThreadPoolExecutor) with Netmiko to scan 
       bridge host tables across all switches defined in 'devices.yaml' in parallel.
    
    3. Heuristic Scoring Engine:
       Any interface where the target MAC is seen receives a score based on 
       three criteria to distinguish edge ports from uplink/trunk ports:
       
       * MAC Count: 
         - Exactly 1 MAC (+3 score) -> high probability of an end-host.
         - 2-5 MACs (+2 score)      -> IP phone daisy-chain, hypervisor, or mini-switch.
         - >10 MACs (-3 score)      -> likely an uplink or core trunk.
       
       * VLAN Tagging:
         - Untagged (0 tagged VLANs) (+1 score) -> standard access port.
         - Multiple tagged VLANs (penalty)      -> indicates an 802.1Q trunk.
       
       * Interface Traffic Rank:
         - Lower relative RX throughput receives higher priority, penalizing 
           high-throughput inter-switch aggregation links.

Output:
    Outputs an ordered list of candidate switches/interfaces ranked by score, 
    highlighting the most probable physical port of the target device.
===============================================================================
"""


import paramiko
from netmiko import ConnectHandler
import yaml
import time
from concurrent.futures import ThreadPoolExecutor, as_completed


# add devices

with open('devices.yaml', 'r') as file:
    devices = yaml.safe_load(file)
    groups = devices['groups']


#input ip

ip = input(' Type an IP-address to search: ')


# get mac from address

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

ssh.connect(
    hostname='__IP-ADDRESS__',
    username='__USERNAME__',
    password='__PASSWORD__',
    port=1005
)

channel = ssh.invoke_shell()

time.sleep(1)
channel.send('8\n')

time.sleep(1)
channel.send('arp {}\n'.format(ip))

time.sleep(1)

result = channel.recv(10000).decode()

resultList = result.split()

arpResult = resultList[resultList.index('at') + 1].upper()

ssh.close()

print('\nMAC address:', arpResult)
print()


#list of candidates

candidates = []


# mac search on mikrotik

def search_mac(switch):

    print('Starting:', switch['host'])

    connection = ConnectHandler(**switch)

    #get interface

    hostInterface = connection.send_command(
        ':put [/interface bridge host get [find mac-address="{}"] on-interface]'.format(
            arpResult
        )
    ).strip()

    # if mac is not on device
    if not hostInterface:
        connection.disconnect()
        return None

    #mac count

    hostCountMac = connection.send_command(
        '/interface bridge host/print count-only where on-interface={} !local'.format(
            hostInterface
        )
    ).strip()

    # vlan count

    hostCountVlans = connection.send_command(
        ':put [:len [/interface bridge vlan find where tagged~"{}"]]'.format(
            hostInterface
        )
    ).strip()

    #rx traffic 

    hostTraf = connection.send_command(
        ':foreach i in=[/interface print stats-detail as-value where type~"ether|sfp|wlan"] do={ :put (($i->"name") . " " . ($i->"rx-byte")) }'
    )

    trafSplit = hostTraf.splitlines()

    trafSplitList = []

    for line in trafSplit:

        eachLine = line.split()

        if len(eachLine) == 2:

            eachLine[1] = int(eachLine[1])

            trafSplitList.append(eachLine)

    #sort rx traffic

    trafSplitList.sort(
        key=lambda x: x[1],
        reverse=True
    )

    # position

    trafficRank = None

    for position, interface in enumerate(trafSplitList, start=1):

        if interface[0] == hostInterface:

            trafficRank = position
            break

    # change to int

    try:
        macCount = int(hostCountMac)
    except ValueError:
        macCount = 999999

    try:
        vlanCount = int(hostCountVlans)
    except ValueError:
        vlanCount = 999999

    # scoring

    score = 0

    # mac count

    if macCount == 1:
        score += 3

    elif 2 <= macCount <= 5:
        score += 2

    elif 6 <= macCount <= 10:
        score += 0

    else:
        score -= 3

    # vlan count

    if vlanCount == 0:
        score += 1

    elif 1 <= vlanCount <= 2:
        score += 0

    elif 3 <= vlanCount <= 5:
        score -= 1

    else:
        score -= 2

    # traffic rank

    if trafficRank is not None:

        if trafficRank <= 3:
            score -= 3

        elif trafficRank <= 6:
            score -= 2

        elif trafficRank <= 10:
            score -= 1

    # device result

    candidate = {
        'host': switch['host'],
        'interface': hostInterface,
        'mac_count': macCount,
        'vlan_count': vlanCount,
        'traffic_rank': trafficRank,
        'score': score
    }

    connection.disconnect()

    return candidate


# multi 

executor = ThreadPoolExecutor(max_workers=15)

futures = []

for group in groups:

    for switch in groups[group]:

        future = executor.submit(
            search_mac,
            switch
        )

        futures.append(future)


# get results

for future in as_completed(futures):

    try:

        result = future.result()

        if result is not None:

            candidates.append(result)

            print(
                'FOUND:',
                result['host'],
                result['interface'],
                '| MACs:',
                result['mac_count'],
                '| VLANs:',
                result['vlan_count'],
                '| traffic rank:',
                result['traffic_rank'],
                '| score:',
                result['score']
            )

    except Exception as error:

        print('ERROR:', error)


executor.shutdown()


# if mac doesnt exist

if not candidates:

    print('\nMAC address was not found on any switch.')
    raise SystemExit


# score sort

candidates.sort(
    key=lambda x: x['score'],
    reverse=True
)


# all candidates

print('\n' + '=' * 60)
print('CANDIDATES')
print('=' * 60)

for candidate in candidates:

    print(
        candidate['host'],
        '->',
        candidate['interface'],
        '| score:',
        candidate['score'],
        '| MACs:',
        candidate['mac_count'],
        '| VLANs:',
        candidate['vlan_count'],
        '| traffic rank:',
        candidate['traffic_rank']
    )


# best candidate

best = candidates[0]

print('\n' + '=' * 60)
print('RESULT')
print('=' * 60)

print('IP:', ip)
print('MAC:', arpResult)
print('Switch:', best['host'])
print('Interface:', best['interface'])
print('Score:', best['score'])
print('MACs on interface:', best['mac_count'])
print('Tagged VLANs:', best['vlan_count'])
print('Traffic rank:', best['traffic_rank'])
