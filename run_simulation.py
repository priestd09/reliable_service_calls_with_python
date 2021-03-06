#!/usr/bin/env python
# encoding: utf-8

import argparse
import requests
import time

from contextlib import contextmanager

from requests import ConnectionError, ConnectTimeout
from subprocess import run, PIPE, CalledProcessError

try:
    IP = run('docker-machine ip', shell=True, stdout=PIPE, check=True).stdout.strip().decode()
except CalledProcessError:
    print('Failed to get docker-machine IP address. Canceling simulation.')
    exit(1)

SETTINGS_URL = f"http://{IP}/settings"
HOME_URL = f"http://{IP}"
HEADERS = {
    'Authorization': 'Token 0x123'
}


parser = argparse.ArgumentParser(description='Run an outage simulation')
parser.add_argument('simulation_type', choices=['ideal', 'performance', 'outage'],
                    help='The type of simulation to run')
parser.add_argument('--retries', action='store_true', default=False,
                    help='Retry connection failures using "full-jitter" exponential backoff')
parser.add_argument('--timeout', action='store', default=60,  # 60s is like having no timeout
                    help='Timeout connections after the specified number of seconds')
parser.add_argument('--circuit-breakers', action='store_true', default=False,
                    help='Wrap connections in a circuit breaker')
parser.add_argument('--home-url', default=HOME_URL,
                    help='The URL to use when requesting the home page service')
parser.add_argument('--settings-url', default=SETTINGS_URL,
                    help='The URL of the settings API')
parser.add_argument('--duration', default=10,
                    help='The duration in seconds of each simulation')


def docker(cmd, failure):
    try:
        result = run(f'eval $(docker-machine env default) && docker-compose {cmd}', shell=True, check=True)
    except CalledProcessError:
        print(failure)
        print(result)
        exit(1)


def setup(flags):
    settings = {
        'circuit_breakers': flags.circuit_breakers,
        'timeout': flags.timeout,
        'retries': flags.retries,
        'outages': [],
        'performance_problems': []
    }

    if flags.simulation_type == 'outage':
        settings['outages'] = ['/recommendations']
    elif flags.simulation_type == 'performance':
        settings['performance_problems'] = ['/recommendations']

    response = requests.put(flags.settings_url, headers=HEADERS, json=settings)

    if response.status_code != 200:
        print("Failed to set simulation settings. Debug with `docker-compose logs settings`.")
        exit(1)


def run_wrk(flags):
    print("Running simulation")
    print(run(f'wrk -d {flags.duration} {flags.home_url} -H "Authorization: 0x123"',
              shell=True, stdout=PIPE).stdout.strip().decode())
    print("Finished")


def simulate():
    flags = parser.parse_args()

    docker('up -d', failure='Failed to start settings service. Canceling simulation.')
    time.sleep(1)

    # Adjust settings for the simulation -- requires that Python services restart.
    setup(flags)

    # Stopping and starting services seems to be more reliable. Just 'restart'
    # sometimes results in Docker errors about non-running containers.
    RESTART_ERROR = 'Failed to restart services. Canceling simulation.'
    docker('stop', failure=RESTART_ERROR)
    docker('up -d', failure=RESTART_ERROR)

    # Wait a max of five seconds for the homepage service to become available.
    for _ in range(5):
        try:
            response = requests.get(flags.home_url, headers=HEADERS)
        except (ConnectionError, ConnectTimeout):
            response = None
        if response and response.status_code == 200:
            break
        time.sleep(1)
    else:
        print("Homepage service is unavailable. Debug with `docker-compose logs home`.")
        exit(1)

    run_wrk(flags)


if __name__ == '__main__':
    simulate()
